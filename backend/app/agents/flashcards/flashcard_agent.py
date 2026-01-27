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

logger = logging.getLogger(__name__)


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
            prompt = self._get_card_generation_prompt(
                summary=summary,
                key_terms=key_terms,
                exam_questions=exam_questions,
                diagram_description=diagram_description,
                conversation_context=conversation_context,
                course_id=state.get("course_id", ""),
                material_id=state.get("course_material_id", ""),
                page_number=page_number,
                snippet_image_url=state.get("current_snippet_url")
            )
        except Exception as e:
            logger.error(f"Failed to get card generation prompt: {e}")
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
        snippet_image_url: Optional[str] = None
    ) -> str:
        """
        Get card generation prompt from Langfuse.
        
        Args:
            summary: Page summary
            key_terms: List of key terms
            exam_questions: List of exam questions
            diagram_description: Diagram description
            conversation_context: Conversation context
            course_id: Course ID
            material_id: Material ID
            page_number: Page number
            snippet_image_url: Optional snippet image URL (for vision input and img tag)
            
        Returns:
            Compiled prompt string
        """
        """
        Get card generation prompt from Langfuse.
        
        Args:
            summary: Page summary
            key_terms: List of key terms
            exam_questions: List of exam questions
            diagram_description: Diagram description
            conversation_context: Conversation context
            course_id: Course ID
            material_id: Material ID
            page_number: Page number
            
        Returns:
            Compiled prompt string
            
        Raises:
            RuntimeError: If Langfuse client is not available or prompt cannot be loaded
        """
        if not self.langfuse_client:
            raise RuntimeError("Langfuse client is not available. Cannot load card-generation prompt.")
        
        try:
            langfuse_prompt = self.langfuse_client.get_prompt(
                "flashcard-agent/card-generation",
                label="production"
            )
            # Prepare variables for compilation
            key_terms_str = ', '.join(key_terms) if key_terms else 'Keine'
            exam_questions_str = ', '.join(exam_questions) if exam_questions else 'Keine'
            diagram_desc_str = diagram_description if diagram_description else 'Kein Diagramm'
            conv_context_str = conversation_context if conversation_context else 'Keine relevanten Konversationen'
            
            # Log what we received - CRITICAL DEBUG INFO
            logger.info(f"🔍 _get_card_generation_prompt CALLED")
            logger.info(f"🔍 _get_card_generation_prompt: snippet_image_url parameter received: {snippet_image_url is not None}")
            logger.info(f"🔍 _get_card_generation_prompt: snippet_image_url type: {type(snippet_image_url)}")
            if snippet_image_url:
                logger.info(f"📸 Snippet URL value received: {snippet_image_url[:150]}...")
                logger.info(f"📸 Snippet URL length: {len(snippet_image_url)}")
            else:
                logger.error(f"❌ _get_card_generation_prompt: snippet_image_url is None or empty! This is the problem!")
                logger.error(f"❌ This means the URL was not passed correctly from generate_flashcards()")
            
            # Prepare snippet info for prompt
            # If snippet exists, create info text; otherwise empty string
            if snippet_image_url:
                snippet_info = f"- **VISUELLES SNIPPET:** Ein wichtiger visueller Ausschnitt (z.B. Diagramm, Formel, Tabelle) ist vorhanden. URL: {snippet_image_url}\n- Du siehst das Bild direkt in dieser Nachricht als Vision-Input. Analysiere es und füge es bei relevanten Karteikarten ein."
            else:
                snippet_info = ""
            
            # Compile prompt with variables
            # IMPORTANT: Langfuse might remove empty variables, so we use a placeholder
            # that we'll replace manually after compilation
            SNIPPET_PLACEHOLDER = "___SNIPPET_IMAGE_URL_PLACEHOLDER___"
            
            # Log what we're about to pass to compile()
            logger.info(f"🔍 About to call langfuse_prompt.compile()")
            logger.info(f"🔍 Will pass snippet_image_url to compile: {snippet_image_url is not None}")
            if snippet_image_url:
                logger.info(f"🔍 snippet_image_url value to compile: {snippet_image_url[:100]}...")
            else:
                logger.warning(f"⚠️ snippet_image_url is None/empty, will use placeholder")
            
            # Always pass a non-empty value to ensure Langfuse doesn't remove the variable
            compile_kwargs = {
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
            logger.info(f"🔍 compile() kwargs keys: {list(compile_kwargs.keys())}")
            logger.info(f"🔍 compile() snippet_image_url value: {compile_kwargs['snippet_image_url']}")
            
            compiled_prompt = langfuse_prompt.compile(**compile_kwargs)
            
            logger.info(f"🔍 After compilation, placeholder appears {compiled_prompt.count(SNIPPET_PLACEHOLDER)} times")
            if SNIPPET_PLACEHOLDER not in compiled_prompt:
                logger.error(f"❌ Placeholder NOT found in compiled prompt! Langfuse may have removed the variable!")
            
            # Now manually replace the placeholder with actual values
            if snippet_image_url:
                # Count how many times the placeholder appears
                placeholder_count = compiled_prompt.count(SNIPPET_PLACEHOLDER)
                logger.info(f"🔍 Found {placeholder_count} occurrences of placeholder to replace")
                
                if placeholder_count > 0:
                    # Split by placeholder to get parts
                    parts = compiled_prompt.split(SNIPPET_PLACEHOLDER, placeholder_count)
                    
                    # First occurrence (in INPUT DATEN) should become info text
                    # All other occurrences (in BILD-EINFÜGUNG img tag) should become the URL
                    if len(parts) >= 2:
                        # Build result: first part + info text + (middle parts with URL) + last part
                        result_parts = [parts[0]]  # First part before placeholder
                        result_parts.append(snippet_info)  # Info text for first occurrence
                        
                        # All remaining parts (except last) need the URL between them
                        for i in range(1, len(parts) - 1):
                            result_parts.append(snippet_image_url)  # URL
                            result_parts.append(parts[i])  # Part between placeholders
                        
                        # Last part needs URL before it
                        if len(parts) > 1:
                            result_parts.append(snippet_image_url)  # URL for last occurrence
                            result_parts.append(parts[-1])  # Last part
                        
                        compiled_prompt = "".join(result_parts)
                        logger.info(f"✅ Replaced {placeholder_count} placeholder(s) - first with info text, rest with URL")
                    else:
                        # Fallback: just replace all with URL
                        compiled_prompt = compiled_prompt.replace(SNIPPET_PLACEHOLDER, snippet_image_url)
                        logger.warning(f"⚠️ Unexpected placeholder structure, replaced all with URL")
                    
                    # Verify URL is in final prompt
                    if snippet_image_url in compiled_prompt:
                        url_count = compiled_prompt.count(snippet_image_url)
                        logger.info(f"✅ Snippet URL successfully in final prompt (appears {url_count} times)")
                    else:
                        logger.error(f"❌ Snippet URL NOT in final prompt after replacement!")
                else:
                    logger.error(f"❌ Placeholder not found in compiled prompt! Langfuse may have removed it.")
            else:
                # No snippet - remove placeholder occurrences
                compiled_prompt = compiled_prompt.replace(SNIPPET_PLACEHOLDER, "")
                logger.debug("📝 No snippet - removed placeholder from prompt")
            logger.debug("✅ Using Langfuse prompt for card-generation")
            return compiled_prompt
        except Exception as e:
            logger.error(f"Failed to load Langfuse prompt for card-generation: {e}")
            raise RuntimeError(f"Cannot load card-generation prompt from Langfuse: {e}") from e
    
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
        
        config = {"configurable": {"thread_id": thread_id}}
        
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
        
        config = {"configurable": {"thread_id": thread_id}}
        
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
