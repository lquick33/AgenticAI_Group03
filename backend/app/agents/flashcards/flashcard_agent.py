"""
Flashcard Generator Agent

Generates Anki-compatible flashcards from lecture page analyses and conversation history.
Refactored to use LangGraph for state persistence and resumability.
"""

import logging
from typing import List, Dict, Any, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.agents.base import BaseAgent
from app.models.schemas import PageSkipDecision, FlashcardGenerationResult, MaterialClassification
from app.services.storage import (
    get_all_page_analyses_for_material,
    get_messages_for_page,
    save_flashcards,
    get_material_classification,
    update_material_classification,
)
from app.services.snippet_service import get_snippets_for_material, get_snippet_public_url
from app.services.analyzer import get_gemini_model
from app.services.observability import create_callback_handler, get_langfuse_client
from app.core.config import settings

logger = logging.getLogger(__name__)

# Maximum snippets per page (can be configured in settings)
MAX_SNIPPETS_PER_PAGE = settings.MAX_SNIPPETS_PER_PAGE


class FlashcardState(MessagesState):
    """
    State for Flashcard Generator Agent.
    
    Extends MessagesState with fields needed for flashcard generation.
    """
    # Required inputs
    course_material_id: str
    user_id: str
    course_id: str
    
    # Page processing data
    page_analyses: List[Dict[str, Any]]  # All pages to process
    snippets_by_page: Dict[int, Dict[str, Any]]  # Snippets indexed by page number
    
    # Progress tracking
    current_page_index: int = 0  # Current page being processed
    processed_page_indices: List[int] = []  # Successfully processed pages
    skipped_page_indices: List[int] = []  # Pages that were skipped
    
    # Results
    all_cards: List[Dict[str, Any]] = []  # Accumulated flashcards
    
    # Current page context (for processing)
    current_page_analysis: Optional[Dict[str, Any]] = None
    current_page_messages: List[Dict[str, Any]] = []
    current_snippet_url: Optional[str] = None
    
    # Configuration
    save_to_db: bool = False
    task_id: Optional[str] = None  # For progress tracking
    
    # Classification
    classification: Optional[str] = None
    classification_confidence: Optional[float] = None
    classification_reasoning: Optional[str] = None


class FlashcardGeneratorAgent(BaseAgent):
    """
    Agent for generating flashcards from lecture materials.
    
    This agent processes page analyses and conversation history to create
    educational flashcards that can be imported into Anki.
    """
    
    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        language: str = "de",
        checkpointer: Optional[BaseCheckpointSaver] = None,
        name: str = "FlashcardGeneratorAgent",
    ):
        """
        Initialize the flashcard generator agent.
        
        Args:
            llm: Language model to use (defaults to Gemini if None)
            language: Language for prompts and output (default: "de")
            checkpointer: Optional checkpointer for state persistence
            name: Agent name
        """
        # Use provided LLM or create default Gemini model
        if llm is None:
            llm = get_gemini_model()
        
        self.language = language
        
        # Create structured LLMs for different tasks
        self.skip_decision_llm = llm.with_structured_output(PageSkipDecision).with_config({"run_name": "flashcard-llm-skip-decision"})
        self.card_generation_llm = llm.with_structured_output(FlashcardGenerationResult).with_config({"run_name": "flashcard-llm-generation"})
        
        # Langfuse client for prompt management
        self.langfuse_client = get_langfuse_client()
        
        # Build system prompt (not used for flashcard generation, but required by BaseAgent)
        system_prompt = "You are a flashcard generator agent that creates educational flashcards from lecture materials."
        
        # Initialize BaseAgent
        super().__init__(
            llm=llm,
            name=name,
            system_prompt=system_prompt,
            checkpointer=checkpointer
        )
    
    def _build_graph(self) -> None:
        """Build the LangGraph workflow for flashcard generation."""
        workflow = StateGraph(state_schema=FlashcardState)
        
        # Add nodes
        workflow.add_node("initialize", self.initialize_node)
        workflow.add_node("classify", self.classify_node)  # NEW: Classification node
        workflow.add_node("process_page", self.process_page_node)
        workflow.add_node("skip_decision", self.skip_decision_node)
        workflow.add_node("get_context", self.get_context_node)
        workflow.add_node("generate_cards", self.generate_cards_node)
        workflow.add_node("update_progress", self.update_progress_node)
        workflow.add_node("save_cards", self.save_cards_node)
        
        # Set entry point
        workflow.add_edge(START, "initialize")
        
        # After initialization, classify
        workflow.add_edge("initialize", "classify")
        
        # After classification, check if there are pages to process
        workflow.add_conditional_edges(
            "classify",
            self.check_more_pages,
            {
                "continue": "process_page",
                "done": "save_cards"
            }
        )
        
        # Process current page
        workflow.add_edge("process_page", "skip_decision")
        
        # Conditional: skip or generate?
        workflow.add_conditional_edges(
            "skip_decision",
            self.should_skip_routing,
            {
                "skip": "update_progress",
                "generate": "get_context"
            }
        )
        
        # Get context then generate cards
        # All classifications go to the same generate_cards node, which uses
        # classification from state to select the appropriate prompt
        workflow.add_edge("get_context", "generate_cards")
        workflow.add_edge("generate_cards", "update_progress")
        
        # After updating progress, check if more pages
        workflow.add_conditional_edges(
            "update_progress",
            self.check_more_pages,
            {
                "continue": "process_page",
                "done": "save_cards"
            }
        )
        
        # Save cards and end
        workflow.add_edge("save_cards", END)
        
        # Compile graph
        self.compile_graph(workflow)
    
    def initialize_node(self, state: FlashcardState) -> FlashcardState:
        """
        Initialize node: Load page analyses and snippets from database.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with page_analyses and snippets_by_page loaded
        """
        logger.info(f"Initializing flashcard generation for material {state['course_material_id']}")
        
        # Load page analyses
        page_analyses = get_all_page_analyses_for_material(
            state["course_material_id"],
            state["user_id"]
        )
        
        if not page_analyses:
            logger.warning(f"No page analyses found for material {state['course_material_id']}")
            return {
                **state,
                "page_analyses": [],
                "snippets_by_page": {},
                "current_page_index": 0
            }
        
        logger.info(f"Loaded {len(page_analyses)} page analyses")
        
        # Load snippets
        snippets = get_snippets_for_material(
            state["course_material_id"],
            state["user_id"]
        )
        snippets_by_page = {s["page_number"]: s for s in snippets}
        logger.info(f"Loaded {len(snippets)} snippets for {len(snippets_by_page)} pages")
        
        return {
            **state,
            "page_analyses": page_analyses,
            "snippets_by_page": snippets_by_page,
            "current_page_index": 0,
            "processed_page_indices": [],
            "skipped_page_indices": [],
            "all_cards": []
        }
    
    def classify_node(self, state: FlashcardState) -> FlashcardState:
        """
        Classify material type on-demand.
        
        Checks database for cached classification first.
        If not found, generates classification using LLM and stores it.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with classification fields
        """
        material_id = state["course_material_id"]
        user_id = state["user_id"]
        
        # Check if classification exists in DB (cached)
        cached = get_material_classification(material_id, user_id)
        
        if cached and not cached.get("classification_override", False):
            # Use cached classification
            logger.info(f"Using cached classification for material {material_id}: {cached['classification']}")
            return {
                **state,
                "classification": cached["classification"],
                "classification_confidence": cached.get("classification_confidence"),
                "classification_reasoning": cached.get("classification_reasoning")
            }
        
        # Generate classification on-demand
        logger.info(f"Generating classification for material {material_id}")
        try:
            classification_result = self._generate_classification(state)
            
            # Store in database for future use
            update_material_classification(
                material_id=material_id,
                classification=classification_result["category"],
                confidence=classification_result["confidence"],
                reasoning=classification_result["reasoning"],
                override=False
            )
            
            logger.info(f"Classified material {material_id} as: {classification_result['category']}")
            
            return {
                **state,
                "classification": classification_result["category"],
                "classification_confidence": classification_result["confidence"],
                "classification_reasoning": classification_result["reasoning"]
            }
        except Exception as e:
            logger.error(f"Error classifying material {material_id}: {e}", exc_info=True)
            # On error, continue without classification (don't block flashcard generation)
            return state
    
    def _generate_classification(self, state: FlashcardState) -> Dict[str, Any]:
        """
        Generate classification using LLM.
        
        Analyzes aggregated page content to determine material type.
        
        Args:
            state: Current agent state
            
        Returns:
            Dict with category, confidence, and reasoning
        """
        # Get all page analyses
        page_analyses = state.get("page_analyses", [])
        
        if not page_analyses:
            logger.warning("No page analyses available for classification")
            return {
                "category": "general",
                "confidence": 0.5,
                "reasoning": "No page analyses available, defaulting to general"
            }
        
        # Aggregate content from all pages
        summaries = [p.get("summary", "") for p in page_analyses if p.get("summary")]
        key_terms = []
        for p in page_analyses:
            key_terms.extend(p.get("key_terms", []))
        
        # Get classification prompt
        prompt = self._get_classification_prompt(summaries, key_terms)
        
        # Use structured output
        llm = get_gemini_model()
        classification_llm = llm.with_structured_output(MaterialClassification)
        
        # Create Langfuse callback
        callback_handler = create_callback_handler()
        config = {}
        if callback_handler:
            config["callbacks"] = [callback_handler]
            config["metadata"] = {
                "langfuse_user_id": state.get("user_id"),
                "langfuse_session_id": state.get("course_material_id"),
                "material_id": state.get("course_material_id"),
                "operation": "classification"
            }
        
        try:
            message = HumanMessage(content=prompt)
            result = classification_llm.invoke([message], config=config if config else None)
            
            return {
                "category": result.category,
                "confidence": result.confidence,
                "reasoning": result.reasoning
            }
        except Exception as e:
            logger.error(f"Error in LLM classification: {e}", exc_info=True)
            # Fallback to general
            return {
                "category": "general",
                "confidence": 0.3,
                "reasoning": f"Classification failed: {str(e)}"
            }
    
    def _get_classification_prompt(self, summaries: List[str], key_terms: List[str]) -> str:
        """
        Get classification prompt from Langfuse.
        
        Falls back to hardcoded prompt if Langfuse unavailable.
        
        Args:
            summaries: List of page summaries
            key_terms: List of key terms from all pages
            
        Returns:
            Compiled prompt string
        """
        if not self.langfuse_client:
            return self._get_fallback_classification_prompt(summaries, key_terms)
        
        try:
            langfuse_prompt = self.langfuse_client.get_prompt(
                "material-classifier/classification",
                label="production"
            )
            
            # Aggregate summaries (limit to avoid token explosion)
            summaries_text = "\n".join(summaries[:10])  # First 10 pages
            key_terms_text = ", ".join(key_terms[:50])  # First 50 terms
            
            compiled_prompt = langfuse_prompt.compile(
                page_summaries=summaries_text,
                key_terms=key_terms_text
            )
            return compiled_prompt
        except Exception as e:
            logger.warning(f"Failed to load Langfuse prompt: {e}, using fallback")
            return self._get_fallback_classification_prompt(summaries, key_terms)
    
    def _get_fallback_classification_prompt(self, summaries: List[str], key_terms: List[str]) -> str:
        """Fallback prompt if Langfuse unavailable."""
        summaries_text = "\n".join(summaries[:10])
        key_terms_text = ", ".join(key_terms[:50])
        
        return f"""Analyze the following lecture material and classify it into one of these categories:
- language_learning: Materials focused on vocabulary, grammar, translations, language practice
- math: Materials with formulas, equations, proofs, mathematical concepts
- business_administration: Materials covering business models, case studies, management concepts
- general: General educational materials without specific domain focus

Page Summaries:
{summaries_text}

Key Terms: {key_terms_text}

Based on the content, classify this material and provide:
1. The most appropriate category
2. A confidence score (0.0 to 1.0)
3. Brief reasoning for your choice

Respond with a JSON object matching this structure:
{{
  "category": "one of the categories above",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}"""
    
    def check_more_pages(self, state: FlashcardState) -> str:
        """
        Conditional routing: Check if there are more pages to process.
        
        Args:
            state: Current agent state
            
        Returns:
            "continue" if more pages, "done" if all processed
        """
        current_index = state.get("current_page_index", 0)
        page_analyses = state.get("page_analyses", [])
        
        if current_index < len(page_analyses):
            return "continue"
        return "done"
    
    def process_page_node(self, state: FlashcardState) -> FlashcardState:
        """
        Process page node: Set up current page context.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with current_page_analysis set
        """
        current_index = state.get("current_page_index", 0)
        page_analyses = state.get("page_analyses", [])
        
        if current_index >= len(page_analyses):
            logger.warning(f"current_page_index {current_index} >= len(page_analyses) {len(page_analyses)}")
            return state
        
        current_page = page_analyses[current_index]
        page_number = current_page.get("page_number", 0)
        
        logger.info(f"Processing page {page_number} (index {current_index})")
        
        return {
            **state,
            "current_page_analysis": current_page,
            "current_page_messages": [],
            "current_snippet_url": None
        }
    
    def skip_decision_node(self, state: FlashcardState) -> FlashcardState:
        """
        Skip decision node: Determine if current page should be skipped.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with skip decision
        """
        page_analysis = state.get("current_page_analysis")
        if not page_analysis:
            logger.warning("No current_page_analysis in state, defaulting to not skip")
            return state
        
        summary = page_analysis.get("summary", "")
        key_terms = page_analysis.get("key_terms", [])
        page_number = page_analysis.get("page_number", 0)
        
        if not summary:
            logger.debug(f"Page {page_number} has no summary, not skipping")
            return state
        
        # Get prompt from Langfuse
        try:
            prompt = self._get_skip_decision_prompt(summary, key_terms)
        except Exception as e:
            logger.warning(f"Failed to get skip decision prompt: {e}, defaulting to not skip")
            return state
        
        # Create Langfuse callback handler
        callback_handler = create_callback_handler()
        
        # Prepare config with callbacks and metadata
        config = {}
        if callback_handler:
            metadata = {
                "langfuse_user_id": state.get("user_id"),
                "langfuse_session_id": state.get("course_material_id"),
                "material_id": state.get("course_material_id"),
                "course_id": state.get("course_id"),
                "page_number": page_number,
                "agent_name": self.name,
                "operation": "skip_decision"
            }
            config["callbacks"] = [callback_handler]
            config["metadata"] = metadata
        
        try:
            message = HumanMessage(content=prompt)
            decision = self.skip_decision_llm.invoke([message], config=config if config else None)
            
            should_skip = decision.skip
            reason = decision.reason
            
            if should_skip:
                logger.debug(f"Skipping page {page_number}: {reason}")
                skipped_indices = state.get("skipped_page_indices", [])
                skipped_indices.append(state.get("current_page_index", 0))
                return {
                    **state,
                    "skipped_page_indices": skipped_indices
                }
            else:
                logger.debug(f"Not skipping page {page_number}: {reason}")
                return state
        except Exception as e:
            logger.warning(f"Error in skip decision for page {page_number}: {str(e)}, defaulting to not skip")
            return state
    
    def should_skip_routing(self, state: FlashcardState) -> str:
        """
        Conditional routing: Check if current page should be skipped.
        
        Args:
            state: Current agent state
            
        Returns:
            "skip" if page should be skipped, "generate" otherwise
        """
        current_index = state.get("current_page_index", 0)
        skipped_indices = state.get("skipped_page_indices", [])
        
        if current_index in skipped_indices:
            return "skip"
        return "generate"
    
    def get_context_node(self, state: FlashcardState) -> FlashcardState:
        """
        Get context node: Fetch conversation messages and snippet URL for current page.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with current_page_messages and current_snippet_url
        """
        page_analysis = state.get("current_page_analysis")
        if not page_analysis:
            logger.warning("No current_page_analysis in state")
            return state
        
        page_id = page_analysis.get("id")
        page_number = page_analysis.get("page_number", 0)
        user_id = state.get("user_id")
        
        # Get messages for this page
        messages = []
        if page_id:
            try:
                messages = get_messages_for_page(page_id, user_id)
            except Exception as e:
                logger.warning(f"Error getting messages for page {page_number}: {e}")
        
        # Check for snippets and get URL if available
        snippet_image_url = None
        snippets_by_page = state.get("snippets_by_page", {})
        
        if page_number in snippets_by_page:
            snippet = snippets_by_page[page_number]
            image_path = snippet.get("image_path")
            
            if image_path:
                try:
                    snippet_image_url = get_snippet_public_url(image_path)
                    logger.info(f"Found snippet for page {page_number}, URL length: {len(snippet_image_url) if snippet_image_url else 0}")
                except Exception as e:
                    logger.error(f"Failed to get snippet URL for page {page_number}: {e}", exc_info=True)
                    snippet_image_url = None
        
        return {
            **state,
            "current_page_messages": messages,
            "current_snippet_url": snippet_image_url
        }
    
    def generate_cards_node(self, state: FlashcardState) -> FlashcardState:
        """
        Generate cards node: Generate flashcards for current page.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with cards added to all_cards
        """
        page_analysis = state.get("current_page_analysis")
        if not page_analysis:
            logger.warning("No current_page_analysis in state")
            return state
        
        summary = page_analysis.get("summary", "")
        key_terms = page_analysis.get("key_terms", [])
        exam_questions = page_analysis.get("exam_questions", [])
        diagram_description = page_analysis.get("diagram_description", "")
        page_number = page_analysis.get("page_number", 0)
        
        # #region agent log
        # import json
        # try:
        #     with open("/Users/milan/on mac/cursor AAI/.cursor/debug.log", "a") as f:
        #         f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"flashcard_agent.py:616","message":"Extracted page content","data":{"summary_len":len(summary),"key_terms_count":len(key_terms),"exam_questions_count":len(exam_questions),"diagram_desc_len":len(diagram_description),"page_number":page_number,"summary_preview":summary[:100] if summary else "","key_terms_preview":key_terms[:5] if key_terms else []},"timestamp":int(__import__("time").time()*1000)}) + "\n")
        # except: pass
        # #endregion
        
        # Build conversation context
        messages = state.get("current_page_messages", [])
        conversation_context = ""
        if messages:
            relevant_messages = []
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    # Look for questions or clarifications
                    if role == "user" and ("?" in content or "verstehe" in content.lower() or "erkläre" in content.lower()):
                        relevant_messages.append(f"User: {content}")
                    elif role == "assistant" and len(relevant_messages) > 0:
                        # Include assistant response if it follows a user question
                        relevant_messages.append(f"Assistant: {content[:200]}...")  # Truncate long responses
            
            if relevant_messages:
                conversation_context = "\n".join(relevant_messages[-6:])  # Last 3 Q&A pairs
        
        # Get prompt from Langfuse
        try:
            url = state.get("current_snippet_url")
            classification = state.get("classification", "general")  # Get from state
            
            # #region agent log
            # try:
            #     with open("/Users/milan/on mac/cursor AAI/.cursor/debug.log", "a") as f:
            #         f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"flashcard_agent.py:644","message":"Before prompt generation","data":{"classification":classification,"has_summary":bool(summary),"has_key_terms":bool(key_terms)},"timestamp":int(__import__("time").time()*1000)}) + "\n")
            # except: pass
            # #endregion
            
            prompt = self._get_card_generation_prompt(
                summary=summary,
                key_terms=key_terms,
                exam_questions=exam_questions,
                diagram_description=diagram_description,
                conversation_context=conversation_context,
                course_id=state.get("course_id", ""),
                material_id=state.get("course_material_id", ""),
                page_number=page_number,
                classification=classification,  # NEW: Pass classification
                snippet_image_urls=[url] if url else None,
            )
            
            # #region agent log
            # try:
            #     with open("/Users/milan/on mac/cursor AAI/.cursor/debug.log", "a") as f:
            #         prompt_preview = prompt[:500] if prompt else ""
            #         has_summary_in_prompt = "{{summary}}" not in prompt and summary and summary[:50] in prompt if summary else False
            #         f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"flashcard_agent.py:656","message":"After prompt generation","data":{"prompt_len":len(prompt) if prompt else 0,"prompt_preview":prompt_preview,"has_summary_in_prompt":has_summary_in_prompt,"has_placeholders":("{{summary}}" in prompt or "{{key_terms}}" in prompt)},"timestamp":int(__import__("time").time()*1000)}) + "\n")
            # except: pass
            # #endregion
        except Exception as e:
            logger.error(f"Failed to get card generation prompt: {e}")
            # #region agent log
            # try:
            #     with open("/Users/milan/on mac/cursor AAI/.cursor/debug.log", "a") as f:
            #         f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"flashcard_agent.py:658","message":"Prompt generation error","data":{"error":str(e)},"timestamp":int(__import__("time").time()*1000)}) + "\n")
            # except: pass
            # #endregion
            return state
        
        # Create Langfuse callback handler
        callback_handler = create_callback_handler()
        
        # Prepare config with callbacks and metadata
        config = {}
        if callback_handler:
            metadata = {
                "langfuse_user_id": state.get("user_id"),
                "langfuse_session_id": state.get("course_material_id"),
                "material_id": state.get("course_material_id"),
                "course_id": state.get("course_id"),
                "page_number": page_number,
                "agent_name": self.name,
                "operation": "card_generation"
            }
            config["callbacks"] = [callback_handler]
            config["metadata"] = metadata
        
        try:
            # Create message with optional image if snippet is available
            snippet_url = state.get("current_snippet_url")
            if snippet_url:
                message = HumanMessage(
                    content=[
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": snippet_url}}
                    ]
                )
                logger.info(f"Including snippet image in vision input for page {page_number}")
            else:
                message = HumanMessage(content=prompt)
            
            # #region agent log
            # try:
            #     import json
            #     with open("/Users/milan/on mac/cursor AAI/.cursor/debug.log", "a") as f:
            #         msg_content_preview = str(message.content)[:800] if hasattr(message, 'content') else str(message)[:800]
            #         msg_has_summary = summary and summary[:50] in str(message.content) if (hasattr(message, 'content') and summary) else False
            #         f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"K","location":"flashcard_agent.py:691","message":"Message sent to LLM","data":{"message_type":type(message).__name__,"content_len":len(str(message.content)) if hasattr(message, 'content') else 0,"content_preview":msg_content_preview,"has_summary_in_message":msg_has_summary,"has_image":isinstance(message.content, list) if hasattr(message, 'content') else False},"timestamp":int(__import__("time").time()*1000)}) + "\n")
            # except: pass
            # #endregion
            
            result = self.card_generation_llm.invoke([message], config=config if config else None)
            
            # Convert to dict format with source_page_analysis_id
            cards = []
            for card in result.cards:
                card_dict = {
                    "front": card.front,
                    "back": card.back,
                    "tags": card.tags,
                    "source_page_analysis_id": page_analysis.get("id")
                }
                cards.append(card_dict)
            
            # Append cards to all_cards
            all_cards = state.get("all_cards", [])
            all_cards.extend(cards)
            
            logger.info(f"Generated {len(cards)} cards for page {page_number}")
            
            return {
                **state,
                "all_cards": all_cards
            }
        except Exception as e:
            logger.error(f"Error generating cards for page {page_number}: {str(e)}", exc_info=True)
            # On error, continue with empty cards for this page
            return state
    
    def update_progress_node(self, state: FlashcardState) -> FlashcardState:
        """
        Update progress node: Increment index and update processed pages.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with incremented current_page_index
        """
        current_index = state.get("current_page_index", 0)
        processed_indices = state.get("processed_page_indices", [])
        
        # Add current index to processed if not skipped
        skipped_indices = state.get("skipped_page_indices", [])
        if current_index not in skipped_indices:
            processed_indices.append(current_index)
        
        # Increment index
        new_index = current_index + 1
        
        logger.info(f"Updated progress: processed {len(processed_indices)} pages, current index: {new_index}")
        
        return {
            **state,
            "current_page_index": new_index,
            "processed_page_indices": processed_indices,
            "current_page_analysis": None,
            "current_page_messages": [],
            "current_snippet_url": None
        }
    
    def save_cards_node(self, state: FlashcardState) -> FlashcardState:
        """
        Save cards node: Save flashcards to database if requested.
        
        Args:
            state: Current agent state
            
        Returns:
            State unchanged (cards already in all_cards)
        """
        save_to_db = state.get("save_to_db", False)
        all_cards = state.get("all_cards", [])
        
        if save_to_db and all_cards:
            try:
                save_flashcards(
                    all_cards,
                    state.get("user_id", ""),
                    state.get("course_id", "")
                )
                logger.info(f"Saved {len(all_cards)} flashcards to database")
            except Exception as e:
                logger.warning(f"Failed to save flashcards to database: {str(e)}")
        
        return state
    
    def _prepare_snippet_info(self, snippet_image_urls: Optional[List[str]]) -> str:
        """
        Prepare snippet information string for prompt.
        
        Args:
            snippet_image_urls: Optional list of snippet image URLs
            
        Returns:
            Formatted snippet info string
        """
        if not snippet_image_urls:
            return ""
        
        if len(snippet_image_urls) == 1:
            return f"- **VISUELLES SNIPPET (1 Bild):** Ein wichtiger visueller Ausschnitt ist vorhanden. URL: {snippet_image_urls[0]}\n- Du siehst das Bild direkt in dieser Nachricht als Vision-Input. Analysiere es und füge es bei relevanten Karteikarten ein."
        else:
            urls_list = '\n'.join([f"  - Snippet {i+1}: {url}" for i, url in enumerate(snippet_image_urls)])
            return f"- **VISUELLE SNIPPETS ({len(snippet_image_urls)} Bilder):** Mehrere wichtige visuelle Ausschnitte sind vorhanden:\n{urls_list}\n- Du siehst alle Bilder direkt in dieser Nachricht als Vision-Input. Analysiere sie und füge die relevanten Bilder bei passenden Karteikarten ein. Du kannst mehrere Bilder pro Karte verwenden, wenn es sinnvoll ist."
    
    def _get_skip_decision_prompt(self, summary: str, key_terms: List[str]) -> str:
        """
        Get skip decision prompt from Langfuse.
        
        Args:
            summary: Page summary
            key_terms: List of key terms
            
        Returns:
            Compiled prompt string
            
        Raises:
            RuntimeError: If Langfuse client is not available or prompt cannot be loaded
        """
        if not self.langfuse_client:
            raise RuntimeError("Langfuse client is not available. Cannot load skip-decision prompt.")
        
        try:
            langfuse_prompt = self.langfuse_client.get_prompt(
                "flashcard-agent/skip-decision",
                label="production"
            )
            # Compile prompt with variables
            key_terms_str = ', '.join(key_terms[:10]) if key_terms else 'Keine'
            compiled_prompt = langfuse_prompt.compile(
                summary=summary,
                key_terms=key_terms_str
            )
            logger.debug("✅ Using Langfuse prompt for skip-decision")
            return compiled_prompt
        except Exception as e:
            logger.error(f"Failed to load Langfuse prompt for skip-decision: {e}")
            raise RuntimeError(f"Cannot load skip-decision prompt from Langfuse: {e}") from e
    
    def _get_base_card_generation_prompt(self, compile_vars: Optional[Dict[str, Any]] = None) -> str:
        """
        Get base flashcard generation prompt from Langfuse.
        
        Contains common instructions applicable to all subjects.
        
        Args:
            compile_vars: Optional dict of variables to compile into the base prompt.
                         If provided, placeholders like {{summary}} will be replaced.
        
        Returns:
            Base prompt string (compiled if compile_vars provided)
        """
        if not self.langfuse_client:
            base_prompt = self._get_fallback_base_prompt()
            # If compile_vars provided, manually replace variables in fallback
            if compile_vars:
                base_prompt = base_prompt.replace("{{summary}}", compile_vars.get("summary", ""))
                base_prompt = base_prompt.replace("{{key_terms}}", compile_vars.get("key_terms", ""))
                base_prompt = base_prompt.replace("{{exam_questions}}", compile_vars.get("exam_questions", ""))
                base_prompt = base_prompt.replace("{{diagram_description}}", compile_vars.get("diagram_description", ""))
                base_prompt = base_prompt.replace("{{conversation_context}}", compile_vars.get("conversation_context", ""))
                base_prompt = base_prompt.replace("{{course_id}}", compile_vars.get("course_id", ""))
                base_prompt = base_prompt.replace("{{material_id}}", compile_vars.get("material_id", ""))
                base_prompt = base_prompt.replace("{{page_number}}", str(compile_vars.get("page_number", "")))
                base_prompt = base_prompt.replace("{{snippet_image_url}}", compile_vars.get("snippet_image_url", ""))
            return base_prompt
        
        try:
            langfuse_prompt = self.langfuse_client.get_prompt(
                "flashcard-agent/card-generation-base",
                label="production"
            )
            # Compile with variables if provided, otherwise return template
            if compile_vars:
                return langfuse_prompt.compile(**compile_vars)
            else:
                return langfuse_prompt.compile()
        except Exception as e:
            logger.warning(f"Failed to load base prompt from Langfuse: {e}, using fallback")
            base_prompt = self._get_fallback_base_prompt()
            # If compile_vars provided, manually replace variables in fallback
            if compile_vars:
                base_prompt = base_prompt.replace("{{summary}}", compile_vars.get("summary", ""))
                base_prompt = base_prompt.replace("{{key_terms}}", compile_vars.get("key_terms", ""))
                base_prompt = base_prompt.replace("{{exam_questions}}", compile_vars.get("exam_questions", ""))
                base_prompt = base_prompt.replace("{{diagram_description}}", compile_vars.get("diagram_description", ""))
                base_prompt = base_prompt.replace("{{conversation_context}}", compile_vars.get("conversation_context", ""))
                base_prompt = base_prompt.replace("{{course_id}}", compile_vars.get("course_id", ""))
                base_prompt = base_prompt.replace("{{material_id}}", compile_vars.get("material_id", ""))
                base_prompt = base_prompt.replace("{{page_number}}", str(compile_vars.get("page_number", "")))
                base_prompt = base_prompt.replace("{{snippet_image_url}}", compile_vars.get("snippet_image_url", ""))
            return base_prompt
    
    def _get_classification_specific_prompt(
        self,
        classification: str,
        summary: str,
        key_terms: List[str],
        exam_questions: List[str],
        diagram_description: str,
        conversation_context: str,
        course_id: str,
        material_id: str,
        page_number: int,
        snippet_image_urls: Optional[List[str]] = None
    ) -> str:
        """
        Get classification-specific prompt. May extend base prompt or be standalone.
        
        This method:
        1. Tries to load classification-specific prompt from Langfuse
        2. Checks if prompt uses {{base_prompt_content}} variable
        3. If yes: loads base prompt and combines
        4. If no: uses prompt as standalone
        5. Falls back to general if classification-specific prompt not found
        
        Args:
            classification: Material classification category (extensible - any string)
            summary: Page summary
            key_terms: List of key terms
            exam_questions: List of exam questions
            diagram_description: Diagram description
            conversation_context: Conversation context
            course_id: Course ID
            material_id: Material ID
            page_number: Page number
            snippet_image_urls: Optional list of snippet image URLs
            
        Returns:
            Final compiled prompt string
        """
        # Prepare variables
        key_terms_str = ', '.join(key_terms) if key_terms else 'Keine'
        exam_questions_str = ', '.join(exam_questions) if exam_questions else 'Keine'
        diagram_desc_str = diagram_description if diagram_description else 'Kein Diagramm'
        conv_context_str = conversation_context if conversation_context else 'Keine relevanten Konversationen'
        
        # Prepare snippet info
        snippet_info = self._prepare_snippet_info(snippet_image_urls)
        
        # Try to load classification-specific prompt
        if not self.langfuse_client:
            return self._get_fallback_classification_prompt(
                classification, summary, key_terms_str, exam_questions_str,
                diagram_desc_str, conv_context_str, course_id, material_id,
                page_number, snippet_info
            )
        
        try:
            prompt_name = f"flashcard-agent/card-generation-{classification}"
            langfuse_prompt = self.langfuse_client.get_prompt(
                prompt_name,
                label="production"
            )
            
            # Check if prompt template contains {{base_prompt_content}}
            # This indicates the prompt wants to extend the base prompt
            # Try to get the prompt template string
            prompt_template = None
            if hasattr(langfuse_prompt, 'prompt'):
                prompt_template = str(langfuse_prompt.prompt)
            elif hasattr(langfuse_prompt, 'messages') and langfuse_prompt.messages:
                # For chat prompts, check first message
                first_msg = langfuse_prompt.messages[0] if isinstance(langfuse_prompt.messages, list) else None
                if first_msg and hasattr(first_msg, 'content'):
                    prompt_template = str(first_msg.content)
                elif isinstance(first_msg, dict) and 'content' in first_msg:
                    prompt_template = str(first_msg['content'])
            else:
                # Try to compile with empty vars to see template
                try:
                    test_compile = langfuse_prompt.compile()
                    prompt_template = test_compile
                except:
                    pass
            
            # #region agent log
            # try:
            #     import json
            #     with open("/Users/milan/on mac/cursor AAI/.cursor/debug.log", "a") as f:
            #         template_preview = prompt_template[:300] if prompt_template else "None"
            #         has_summary_var = "{{summary}}" in (prompt_template or "")
            #         has_key_terms_var = "{{key_terms}}" in (prompt_template or "")
            #         f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"J","location":"flashcard_agent.py:919","message":"Prompt template analysis","data":{"prompt_name":prompt_name,"has_template":bool(prompt_template),"template_preview":template_preview,"has_summary_var":has_summary_var,"has_key_terms_var":has_key_terms_var},"timestamp":int(__import__("time").time()*1000)}) + "\n")
            # except: pass
            # #endregion
            
            uses_base_prompt = prompt_template and "{{base_prompt_content}}" in prompt_template
            
            # IMPORTANT: Langfuse might remove empty variables, so we use a placeholder for snippets
            SNIPPET_PLACEHOLDER = "___SNIPPET_IMAGE_URL_PLACEHOLDER___"
            
            compile_vars = {
                "summary": summary,
                "key_terms": key_terms_str,
                "exam_questions": exam_questions_str,
                "diagram_description": diagram_desc_str,
                "conversation_context": conv_context_str,
                "course_id": course_id,
                "material_id": material_id,
                "page_number": str(page_number),
                "snippet_image_url": SNIPPET_PLACEHOLDER  # Always pass placeholder, replace manually
            }
            
            # #region agent log
            # try:
            #     import json
            #     with open("/Users/milan/on mac/cursor AAI/.cursor/debug.log", "a") as f:
            #         f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"flashcard_agent.py:942","message":"Before prompt compilation","data":{"classification":classification,"prompt_name":prompt_name,"uses_base_prompt":uses_base_prompt,"summary_len":len(summary),"key_terms_str_len":len(key_terms_str),"compile_vars_keys":list(compile_vars.keys())},"timestamp":int(__import__("time").time()*1000)}) + "\n")
            # except: pass
            # #endregion
            
            # If prompt uses base, load and compile it with variables first
            if uses_base_prompt:
                # Compile base prompt WITH variables so placeholders are replaced
                base_prompt_content = self._get_base_card_generation_prompt(compile_vars=compile_vars)
                compile_vars["base_prompt_content"] = base_prompt_content
                logger.info(f"Using base prompt + {classification}-specific prompt")
                
                # #region agent log
                # try:
                #     import json
                #     with open("/Users/milan/on mac/cursor AAI/.cursor/debug.log", "a") as f:
                #         has_summary = summary and summary[:50] in base_prompt_content if summary else False
                #         f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"flashcard_agent.py:980","message":"Base prompt loaded and compiled with vars","data":{"base_prompt_len":len(base_prompt_content) if base_prompt_content else 0,"has_summary_in_base":has_summary,"summary_in_base_preview":base_prompt_content[base_prompt_content.find(summary[:30]):base_prompt_content.find(summary[:30])+100] if summary and summary[:30] in base_prompt_content else "not found"},"timestamp":int(__import__("time").time()*1000)}) + "\n")
                # except: pass
                # #endregion
            else:
                logger.info(f"Using standalone {classification}-specific prompt (no base)")
            
            # Compile prompt with all variables
            compiled = langfuse_prompt.compile(**compile_vars)
            
            # #region agent log
            # try:
            #     with open("/Users/milan/on mac/cursor AAI/.cursor/debug.log", "a") as f:
            #         compiled_preview = compiled[:500] if compiled else ""
            #         has_summary_compiled = summary and summary[:50] in compiled if summary else False
            #         has_placeholders_remaining = "{{summary}}" in compiled or "{{key_terms}}" in compiled
            #         f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"G","location":"flashcard_agent.py:963","message":"After prompt compilation","data":{"compiled_len":len(compiled) if compiled else 0,"compiled_preview":compiled_preview,"has_summary_compiled":has_summary_compiled,"has_placeholders_remaining":has_placeholders_remaining},"timestamp":int(__import__("time").time()*1000)}) + "\n")
            # except: pass
            # #endregion
            
            # Handle snippet placeholder replacement (similar to original logic)
            if snippet_image_urls:
                placeholder_count = compiled.count(SNIPPET_PLACEHOLDER)
                if placeholder_count > 0:
                    parts = compiled.split(SNIPPET_PLACEHOLDER, placeholder_count)
                    if len(parts) >= 2:
                        result_parts = [parts[0]]
                        result_parts.append(snippet_info)  # Info text for first occurrence
                        
                        # For remaining occurrences, use first URL (agent will decide which URLs to use)
                        primary_url = snippet_image_urls[0]
                        for i in range(1, len(parts) - 1):
                            result_parts.append(primary_url)
                            result_parts.append(parts[i])
                        
                        if len(parts) > 1:
                            result_parts.append(primary_url)
                            result_parts.append(parts[-1])
                        
                        compiled = "".join(result_parts)
                        logger.info(f"✅ Replaced placeholders with {len(snippet_image_urls)} snippet info")
                    else:
                        compiled = compiled.replace(SNIPPET_PLACEHOLDER, snippet_info)
            else:
                # No snippets - remove placeholder occurrences
                compiled = compiled.replace(SNIPPET_PLACEHOLDER, "")
                logger.debug("📝 No snippets - removed placeholder from prompt")
            
            # #region agent log
            # try:
            #     import json
            #     with open("/Users/milan/on mac/cursor AAI/.cursor/debug.log", "a") as f:
            #         final_preview = compiled[:800] if compiled else ""
            #         final_has_summary = summary and summary[:50] in compiled if summary else False
            #         f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H","location":"flashcard_agent.py:991","message":"Final compiled prompt","data":{"final_len":len(compiled) if compiled else 0,"final_preview":final_preview,"final_has_summary":final_has_summary},"timestamp":int(__import__("time").time()*1000)}) + "\n")
            # except: pass
            # #endregion
            
            return compiled
            
        except Exception as e:
            logger.warning(f"Failed to load {classification} prompt: {e}, trying general")
            
            # #region agent log
            # try:
            #     import json
            #     with open("/Users/milan/on mac/cursor AAI/.cursor/debug.log", "a") as f:
            #         f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"I","location":"flashcard_agent.py:995","message":"Prompt load failed, falling back","data":{"classification":classification,"error":str(e)},"timestamp":int(__import__("time").time()*1000)}) + "\n")
            # except: pass
            # #endregion
            
            # Fallback to general if specific prompt not found
            if classification != "general":
                return self._get_classification_specific_prompt(
                    "general", summary, key_terms, exam_questions,
                    diagram_description, conversation_context, course_id,
                    material_id, page_number, snippet_image_urls
                )
            
            # Try old prompt name as fallback (for backward compatibility)
            logger.info("Trying old prompt name 'flashcard-agent/card-generation' as fallback")
            try:
                SNIPPET_PLACEHOLDER = "___SNIPPET_IMAGE_URL_PLACEHOLDER___"
                old_prompt_name = "flashcard-agent/card-generation"
                old_langfuse_prompt = self.langfuse_client.get_prompt(
                    old_prompt_name,
                    label="production"
                )
                
                # Use old prompt (doesn't use base_prompt_content)
                compile_vars = {
                    "summary": summary,
                    "key_terms": key_terms_str,
                    "exam_questions": exam_questions_str,
                    "diagram_description": diagram_desc_str,
                    "conversation_context": conv_context_str,
                    "course_id": course_id,
                    "material_id": material_id,
                    "page_number": str(page_number),
                    "snippet_image_url": SNIPPET_PLACEHOLDER
                }
                
                compiled = old_langfuse_prompt.compile(**compile_vars)
                
                # Handle snippet placeholder replacement
                if snippet_image_urls:
                    placeholder_count = compiled.count(SNIPPET_PLACEHOLDER)
                    if placeholder_count > 0:
                        parts = compiled.split(SNIPPET_PLACEHOLDER, placeholder_count)
                        if len(parts) >= 2:
                            result_parts = [parts[0]]
                            result_parts.append(snippet_info)
                            primary_url = snippet_image_urls[0]
                            for i in range(1, len(parts) - 1):
                                result_parts.append(primary_url)
                                result_parts.append(parts[i])
                            if len(parts) > 1:
                                result_parts.append(primary_url)
                                result_parts.append(parts[-1])
                            compiled = "".join(result_parts)
                        else:
                            compiled = compiled.replace(SNIPPET_PLACEHOLDER, snippet_info)
                else:
                    compiled = compiled.replace(SNIPPET_PLACEHOLDER, "")
                
                logger.info("✅ Using old prompt 'flashcard-agent/card-generation' as fallback")
                return compiled
            except Exception as old_prompt_error:
                logger.warning(f"Old prompt also not found: {old_prompt_error}, using hardcoded fallback")
            
            # Final fallback to hardcoded prompts
            return self._get_fallback_classification_prompt(
                "general", summary, key_terms_str, exam_questions_str,
                diagram_desc_str, conv_context_str, course_id, material_id,
                page_number, snippet_info
            )
    
    def _get_card_generation_prompt(
        self,
        summary: str,
        key_terms: List[str],
        exam_questions: List[str],
        diagram_description: str,
        conversation_context: str,
        course_id: str,
        material_id: str,
        page_number: int,
        classification: Optional[str] = None,
        snippet_image_urls: Optional[List[str]] = None
    ) -> str:
        """
        Get card generation prompt from Langfuse (delegates to classification-specific method).
        
        This method now delegates to _get_classification_specific_prompt which handles
        the extensible prompt loading logic with base prompt detection.
        
        Args:
            summary: Page summary
            key_terms: List of key terms
            exam_questions: List of exam questions
            diagram_description: Diagram description
            conversation_context: Conversation context
            course_id: Course ID
            material_id: Material ID
            page_number: Page number
            classification: Material classification category (extensible - any string)
            snippet_image_urls: Optional list of snippet image URLs (for vision input and img tags)
            
        Returns:
            Compiled prompt string
            
        Raises:
            RuntimeError: If Langfuse client is not available or prompt cannot be loaded
        """
        classification = classification or "general"
        return self._get_classification_specific_prompt(
            classification=classification,
            summary=summary,
            key_terms=key_terms,
            exam_questions=exam_questions,
            diagram_description=diagram_description,
            conversation_context=conversation_context,
            course_id=course_id,
            material_id=material_id,
            page_number=page_number,
            snippet_image_urls=snippet_image_urls
        )
    
    def _get_fallback_base_prompt(self) -> str:
        """Fallback base prompt if Langfuse unavailable."""
        return """You are a flashcard generator that creates educational flashcards from lecture materials.

**General Instructions:**
- Create 1-2 flashcards per page based on content complexity
- Front side should be a clear question or prompt
- Back side should contain the answer with context
- Use appropriate tags for categorization
- Consider conversation context when available
- Include visual snippets when relevant

**Output Format:**
You must respond with a valid JSON object matching this structure:
{
  "cards": [
    {
      "front": "question or prompt",
      "back": "answer with context",
      "tags": ["tag1", "tag2"]
    }
  ]
}"""
    
    def _get_fallback_classification_prompt(
        self,
        classification: str,
        summary: str,
        key_terms: str,
        exam_questions: str,
        diagram_description: str,
        conversation_context: str,
        course_id: str,
        material_id: str,
        page_number: str,
        snippet_info: str
    ) -> str:
        """
        Fallback classification-specific prompt when Langfuse unavailable.
        
        For known classifications, returns base + specific additions.
        For unknown classifications, returns general fallback.
        This makes the system extensible - new classifications fall back to general.
        """
        # Load base prompt for fallback
        base_prompt = self._get_fallback_base_prompt()
        
        # Known classification-specific additions
        classification_additions = {
            "language_learning": "\n\n**Language Learning Focus:**\n- Focus on vocabulary, grammar, translations\n- Create cards for verb conjugations and word meanings\n- Include pronunciation hints when relevant\n- Use language-specific tags (e.g., \"vocabulary\", \"grammar\", \"verb\")",
            "math": "\n\n**Math Focus:**\n- Focus on formulas, equations, proofs\n- Create cards for mathematical concepts and problem-solving steps\n- Include step-by-step solutions when relevant\n- Use math-specific tags (e.g., \"formula\", \"theorem\", \"proof\")",
            "business_administration": "\n\n**Business Administration Focus:**\n- Focus on business models, case studies, management concepts\n- Create cards for strategic thinking and business terminology\n- Include real-world examples when relevant\n- Use business-specific tags (e.g., \"strategy\", \"case_study\", \"management\")",
            "general": ""  # General uses base as-is
        }
        
        # Get classification-specific addition (or empty for unknown)
        addition = classification_additions.get(classification, "")
        
        # Build final prompt
        final_prompt = base_prompt + addition
        
        # Add page information section
        final_prompt += f"""

**Page Information:**
- Summary: {summary}
- Key Terms: {key_terms}
- Exam Questions: {exam_questions}
- Diagram Description: {diagram_description}
- Conversation Context: {conversation_context}
- Course ID: {course_id}
- Material ID: {material_id}
- Page Number: {page_number}
{snippet_info}"""
        
        return final_prompt
    
    def generate_flashcards(
        self,
        course_material_id: str,
        user_id: str,
        course_id: str,
        save_to_db: bool = False,
        task_id: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate flashcards for all relevant pages in a course material.
        
        Uses LangGraph to process pages with state persistence and resumability.
        Supports multiple snippets per page - the agent receives all snippets
        for a page as vision inputs and decides which ones to include in cards.
        
        Args:
            course_material_id: Course material ID
            user_id: User ID
            course_id: Course ID
            save_to_db: Whether to save flashcards to database
            task_id: Optional task ID for progress tracking
            thread_id: Optional thread ID for resumability (if not provided, generates one)
            
        Returns:
            List of flashcard dicts with front, back, tags, source_page_analysis_id
        """
        # Prepare initial state
        initial_state = {
            "messages": [],
            "course_material_id": course_material_id,
            "user_id": user_id,
            "course_id": course_id,
            "save_to_db": save_to_db,
            "task_id": task_id,
            "page_analyses": [],  # Will be loaded in initialize_node
            "snippets_by_page": {},  # Will be loaded in initialize_node
            "current_page_index": 0,
            "processed_page_indices": [],
            "skipped_page_indices": [],
            "all_cards": [],
            "current_page_analysis": None,
            "current_page_messages": [],
            "current_snippet_url": None,
            "classification": None,
            "classification_confidence": None,
            "classification_reasoning": None,
        }
        
        # Use thread_id if provided (for resumability), otherwise generate new
        if thread_id is None:
            thread_id = f"flashcard-{course_material_id}-{user_id}"
            if task_id:
                thread_id = f"flashcard-task-{task_id}"
        
        # Recursion limit: 10 * page count so large PDFs don't hit default 25
        page_analyses_pre = get_all_page_analyses_for_material(course_material_id, user_id)
        total_pages_pre = len(page_analyses_pre) if page_analyses_pre else 0
        recursion_limit = 10 * max(1, total_pages_pre)
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": recursion_limit}
        
        # Add Langfuse tracing for graph execution
        langfuse_client = get_langfuse_client()
        graph_span_ctx = None
        graph_span = None
        
        if langfuse_client:
            try:
                graph_span_ctx = langfuse_client.start_as_current_observation(
                    as_type="span",
                    name="flashcard-generator-agent/graph-execution",
                    input={
                        "course_material_id": course_material_id,
                        "user_id": user_id,
                        "course_id": course_id,
                        "task_id": task_id,
                    }
                )
                graph_span = graph_span_ctx.__enter__()
                logger.info("🟡 Langfuse: Started graph execution span 'flashcard-generator-agent/graph-execution'")
            except Exception as e:
                logger.warning(f"🔴 Langfuse: Failed to start graph execution span: {e}")
                graph_span_ctx = None
                graph_span = None
        
        try:
            # Invoke graph
            logger.info(f"Starting flashcard generation graph for material {course_material_id} (thread_id: {thread_id})")
            result = self.graph.invoke(initial_state, config)
            
            # Update span with success
            if graph_span:
                try:
                    cards_count = len(result.get("all_cards", []))
                    graph_span.update(
                        output={
                            "status": "success",
                            "cards_generated": cards_count,
                            "pages_processed": len(result.get("processed_page_indices", [])),
                            "pages_skipped": len(result.get("skipped_page_indices", []))
                        }
                    )
                    logger.info("🟢 Langfuse: Graph execution span updated with success")
                except Exception as e:
                    logger.warning(f"🔴 Langfuse: Failed to update graph execution span: {e}")
            
            # Return cards from state
            all_cards = result.get("all_cards", [])
            logger.info(f"Flashcard generation completed: {len(all_cards)} cards generated")
            return all_cards
            
        except Exception as e:
            # Update span with error
            if graph_span:
                try:
                    graph_span.update(
                        output={"status": "error", "error": str(e)},
                        level="ERROR"
                    )
                    logger.warning("🔴 Langfuse: Graph execution span updated with error")
                except Exception:
                    pass
            raise
        finally:
            # Close span
            if graph_span_ctx:
                try:
                    graph_span_ctx.__exit__(None, None, None)
                    logger.info("🟢 Langfuse: Graph execution span closed")
                except Exception as e:
                    logger.warning(f"🔴 Langfuse: Error closing graph execution span: {e}")
    
    def generate_flashcards_with_progress(
        self,
        course_material_id: str,
        user_id: str,
        course_id: str,
        save_to_db: bool = False,
        task_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        progress_callback: Optional[callable] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate flashcards with progress tracking via callback.
        
        This method streams the graph execution and calls the progress callback
        after each node to provide real-time progress updates.
        
        Args:
            course_material_id: Course material ID
            user_id: User ID
            course_id: Course ID
            save_to_db: Whether to save flashcards to database
            task_id: Optional task ID for progress tracking
            thread_id: Optional thread ID for resumability (if not provided, generates one)
            progress_callback: Optional callback function(current_page_index, total_pages, processed_pages, skipped_pages, cards_generated, progress)
            
        Returns:
            List of flashcard dicts with front, back, tags, source_page_analysis_id
        """
        # Prepare initial state
        initial_state = {
            "messages": [],
            "course_material_id": course_material_id,
            "user_id": user_id,
            "course_id": course_id,
            "save_to_db": save_to_db,
            "task_id": task_id,
            "page_analyses": [],
            "snippets_by_page": {},
            "current_page_index": 0,
            "processed_page_indices": [],
            "skipped_page_indices": [],
            "all_cards": [],
            "current_page_analysis": None,
            "current_page_messages": [],
            "current_snippet_url": None,
            "classification": None,
            "classification_confidence": None,
            "classification_reasoning": None,
        }
        
        # Use thread_id if provided (for resumability), otherwise generate new
        if thread_id is None:
            thread_id = f"flashcard-{course_material_id}-{user_id}"
            if task_id:
                thread_id = f"flashcard-task-{task_id}"
        
        # Recursion limit: 10 * page count so large PDFs don't hit default 25
        page_analyses_pre = get_all_page_analyses_for_material(course_material_id, user_id)
        total_pages_pre = len(page_analyses_pre) if page_analyses_pre else 0
        recursion_limit = 10 * max(1, total_pages_pre)
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": recursion_limit}
        
        # Add Langfuse tracing for graph execution
        langfuse_client = get_langfuse_client()
        graph_span_ctx = None
        graph_span = None
        
        if langfuse_client:
            try:
                graph_span_ctx = langfuse_client.start_as_current_observation(
                    as_type="span",
                    name="flashcard-generator-agent/graph-execution",
                    input={
                        "course_material_id": course_material_id,
                        "user_id": user_id,
                        "course_id": course_id,
                        "task_id": task_id,
                    }
                )
                graph_span = graph_span_ctx.__enter__()
                logger.info("🟡 Langfuse: Started graph execution span 'flashcard-generator-agent/graph-execution'")
            except Exception as e:
                logger.warning(f"🔴 Langfuse: Failed to start graph execution span: {e}")
                graph_span_ctx = None
                graph_span = None
        
        try:
            # Stream graph execution to get intermediate state updates
            logger.info(f"Starting flashcard generation graph with progress tracking (thread_id: {thread_id})")
            final_state = None
            total_pages = 0
            
            for event in self.graph.stream(initial_state, config):
                # Get the latest state from the event
                # Event format: {node_name: state_update}
                for node_name, state_update in event.items():
                    final_state = state_update
                    
                    # Extract progress information from state
                    current_index = state_update.get("current_page_index", 0)
                    page_analyses = state_update.get("page_analyses", [])
                    processed_indices = state_update.get("processed_page_indices", [])
                    skipped_indices = state_update.get("skipped_page_indices", [])
                    all_cards = state_update.get("all_cards", [])
                    
                    # Update total_pages after initialize_node
                    if node_name == "initialize" and page_analyses:
                        total_pages = len(page_analyses)
                        logger.info(f"Initialized: {total_pages} pages to process")
                    
                    # Call progress callback after update_progress_node (primary update point)
                    # Also call after initialize_node to set initial progress (0%)
                    if progress_callback:
                        should_update = False
                        
                        # After initialize_node: set initial progress (0%)
                        if node_name == "initialize" and total_pages > 0:
                            should_update = True
                        
                        # After update_progress_node: update progress as pages are processed
                        elif node_name == "update_progress" and total_pages > 0:
                            should_update = True
                        
                        if should_update:
                            try:
                                # Calculate progress: processed pages / total pages
                                processed_count = len(processed_indices)
                                skipped_count = len(skipped_indices)
                                cards_count = len(all_cards)
                                
                                # Handle division by zero and ensure progress <= 1.0
                                progress = processed_count / total_pages if total_pages > 0 else 0.0
                                progress = min(progress, 1.0)  # Ensure progress never exceeds 1.0
                                
                                # Call progress callback
                                progress_callback(
                                    current_page_index=current_index,
                                    total_pages=total_pages,
                                    processed_pages=processed_count,
                                    skipped_pages=skipped_count,
                                    cards_generated=cards_count,
                                    progress=progress
                                )
                                
                                logger.debug(
                                    f"Progress update: {processed_count}/{total_pages} pages "
                                    f"({progress*100:.1f}%), {cards_count} cards generated"
                                )
                            except Exception as e:
                                # Don't let callback errors crash the graph
                                logger.warning(f"Error in progress callback: {e}")
            
            if final_state is None:
                raise RuntimeError("Graph execution completed but no final state was captured")
            
            # Update span with success
            if graph_span:
                try:
                    cards_count = len(final_state.get("all_cards", []))
                    graph_span.update(
                        output={
                            "status": "success",
                            "cards_generated": cards_count,
                            "pages_processed": len(final_state.get("processed_page_indices", [])),
                            "pages_skipped": len(final_state.get("skipped_page_indices", []))
                        }
                    )
                    logger.info("🟢 Langfuse: Graph execution span updated with success")
                except Exception as e:
                    logger.warning(f"🔴 Langfuse: Failed to update graph execution span: {e}")
            
            # Return cards from final state
            all_cards = final_state.get("all_cards", [])
            logger.info(f"Flashcard generation completed: {len(all_cards)} cards generated")
            return all_cards
            
        except Exception as e:
            # Update span with error
            if graph_span:
                try:
                    graph_span.update(
                        output={"status": "error", "error": str(e)},
                        level="ERROR"
                    )
                    logger.warning("🔴 Langfuse: Graph execution span updated with error")
                except Exception:
                    pass
            raise
        finally:
            # Close span
            if graph_span_ctx:
                try:
                    graph_span_ctx.__exit__(None, None, None)
                    logger.info("🟢 Langfuse: Graph execution span closed")
                except Exception as e:
                    logger.warning(f"🔴 Langfuse: Error closing graph execution span: {e}")
