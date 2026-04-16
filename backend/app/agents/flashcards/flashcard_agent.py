"""
Flashcard Generator Agent

Generates Anki-compatible flashcards from lecture page analyses and conversation history.
Refactored to use LangGraph for state persistence and resumability.

Performance optimizations:
- Batch page processing (3-5 pages per LLM call for text-only pages)
- Optimized O(n) deduplication with hash pre-filtering
- Prefetched messages to avoid N+1 queries
- Cached Langfuse prompts with TTL
- Non-blocking AnkiWeb sync
"""

import hashlib
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional, Tuple

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.agents.base import BaseAgent
from app.models.schemas import PageSkipDecision, FlashcardGenerationResult, MaterialClassification
from app.core.adapters import get_page_analysis, get_message, get_material, get_flashcard
from app.services.snippet_service import get_snippets_for_material, get_snippet_public_url
from app.services.analyzer import get_gemini_model
from app.services.observability import create_callback_handler, get_langfuse_client
from app.core.config import settings

logger = logging.getLogger(__name__)

# Maximum snippets per page (can be configured in settings)
MAX_SNIPPETS_PER_PAGE = settings.MAX_SNIPPETS_PER_PAGE

# Batch processing configuration
BATCH_SIZE_PAGES = 4  # Number of pages to process per LLM call (for text-only pages)


from app.services.anki_sync_service import AnkiSyncService
from app.services.flashcard_prompt_service import FlashcardPromptService
from app.services.flashcard_deduplication_service import FlashcardDeduplicationService

# Maximum snippets per page (can be configured in settings)
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
    messages_by_page: Dict[str, List[Dict[str, Any]]] = {}  # Prefetched messages indexed by page_id
    
    # Pre-evaluated skip decisions (optimization: evaluated in parallel upfront)
    skip_decisions: Dict[int, bool] = {}  # page_index -> should_skip
    
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
    
    # Deduplication (Anki-first architecture)
    deduplicate_course: bool = False  # Enable course-wide deduplication
    existing_anki_fronts: List[str] = []  # Card fronts from Anki (for dedup)
    parent_deck_name: Optional[str] = None  # Course deck (e.g., "Marketing 101")
    target_deck_name: Optional[str] = None  # Full deck (e.g., "Marketing 101::Lecture 3")
    
    # Anki sync results
    anki_synced: bool = False  # Whether cards were successfully added to local Anki
    ankiweb_synced: bool = False  # Whether cards were successfully synced to AnkiWeb



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
        
        # Use extracted services
        self.prompt_service = FlashcardPromptService()
        self.anki_sync_service = AnkiSyncService()
        
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
        Initialize node: Load page analyses, snippets, and prefetch messages from database.
        
        Performance optimization: Prefetches all messages in a single batch query
        instead of N+1 queries during page processing.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with page_analyses, snippets_by_page, and messages_by_page loaded
        """
        logger.info(f"Initializing flashcard generation for material {state['course_material_id']}")
        
        # Load page analyses
        page_analyses = get_page_analysis().get_all_for_material(
            state["course_material_id"],
            state["user_id"]
        )
        
        if not page_analyses:
            logger.warning(f"No page analyses found for material {state['course_material_id']}")
            return {
                **state,
                "page_analyses": [],
                "snippets_by_page": {},
                "messages_by_page": {},
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
        
        # Prefetch all messages in a single batch query (optimization: avoids N+1 queries)
        page_ids = [p["id"] for p in page_analyses if p.get("id")]
        messages_by_page = {}
        if page_ids:
            try:
                messages_by_page = get_message().get_for_pages_batch(page_ids, state["user_id"])
                total_messages = sum(len(msgs) for msgs in messages_by_page.values())
                logger.info(f"Prefetched {total_messages} messages for {len(messages_by_page)} pages (batch query)")
            except Exception as e:
                logger.warning(f"Failed to batch-fetch messages, will fallback to per-page: {e}")
                messages_by_page = {}
        
        # Load existing card fronts from Anki if deduplication is enabled
        existing_anki_fronts = []
        if state.get("deduplicate_course", False):
            parent_deck = state.get("parent_deck_name", "")
            if parent_deck:
                existing_anki_fronts = self.anki_sync_service.get_existing_fronts(
                    parent_deck, 
                    state["course_id"],
                    state["user_id"]
                )
                logger.info(f"Loaded {len(existing_anki_fronts)} existing fronts for deduplication")
        
        return {
            **state,
            "page_analyses": page_analyses,
            "snippets_by_page": snippets_by_page,
            "messages_by_page": messages_by_page,
            "current_page_index": 0,
            "processed_page_indices": [],
            "skipped_page_indices": [],
            "all_cards": [],
            "existing_anki_fronts": existing_anki_fronts
        }
    
    def classify_node(self, state: FlashcardState) -> FlashcardState:
        """
        Get material classification and evaluate skip decisions in parallel.
        
        This node:
        1. Gets/generates material classification
        2. Evaluates skip decisions for all pages in parallel (optimization)
        
        Classification is typically generated during PDF upload/processing.
        This node checks the database for cached classification first.
        If not found (e.g., for older materials), generates classification on-demand.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with classification fields and skip_decisions
        """
        material_id = state["course_material_id"]
        user_id = state["user_id"]
        course_id = state["course_id"]
        
        # 1. Get classification
        classification = None
        classification_confidence = None
        classification_reasoning = None
        
        # Check if classification exists in DB (cached from upload)
        cached = get_material().get_classification(material_id, user_id)
        
        if cached and not cached.get("classification_override", False):
            # Use cached classification (from upload)
            logger.info(f"Using classification from upload for material {material_id}: {cached['classification']}")
            classification = cached["classification"]
            classification_confidence = cached.get("classification_confidence")
            classification_reasoning = cached.get("classification_reasoning")
        else:
            # Generate classification on-demand (fallback for older materials not yet classified)
            logger.info(f"Classification not found in cache for material {material_id}, generating on-demand")
            try:
                classification_result = self._generate_classification(state)
                
                # Store in database for future use
                get_material().update_classification(
                    material_id=material_id,
                    classification=classification_result["category"],
                    confidence=classification_result["confidence"],
                    reasoning=classification_result["reasoning"],
                    override=False
                )
                
                logger.info(
                    "Classified material %s as '%s' (confidence=%.3f)",
                    material_id,
                    classification_result["category"],
                    classification_result["confidence"],
                )
                
                classification = classification_result["category"]
                classification_confidence = classification_result["confidence"]
                classification_reasoning = classification_result["reasoning"]
                
            except Exception as e:
                logger.error(f"Error classifying material {material_id}: {e}", exc_info=True)
                # On error, use default
                classification = "general"
        
        # 2. Evaluate skip decisions for all pages in parallel (optimization)
        page_analyses = state.get("page_analyses", [])
        skip_decisions = {}
        
        if page_analyses:
            try:
                skip_decisions = self._evaluate_skip_decisions_parallel(
                    page_analyses=page_analyses,
                    user_id=user_id,
                    course_material_id=material_id,
                    course_id=course_id,
                    max_workers=5  # Limit concurrent LLM calls
                )
            except Exception as e:
                logger.warning(f"Parallel skip evaluation failed, will fallback to per-page: {e}")
                skip_decisions = {}
        
        return {
            **state,
            "classification": classification,
            "classification_confidence": classification_confidence,
            "classification_reasoning": classification_reasoning,
            "skip_decisions": skip_decisions
        }
    
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
        prompt = self.prompt_service.get_classification_prompt(summaries, key_terms)
        
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

    
    def _evaluate_skip_decisions_parallel(
        self, 
        page_analyses: List[Dict[str, Any]],
        user_id: str,
        course_material_id: str,
        course_id: str,
        max_workers: int = 5
    ) -> Dict[int, bool]:
        """
        Evaluate skip decisions for all pages in parallel.
        
        Performance optimization: Uses ThreadPoolExecutor to run skip decisions
        concurrently instead of sequentially. This reduces N sequential LLM calls
        to ~N/max_workers parallel batches.
        
        Args:
            page_analyses: List of page analysis dicts
            user_id: User ID for Langfuse metadata
            course_material_id: Material ID for Langfuse metadata
            course_id: Course ID for Langfuse metadata
            max_workers: Maximum number of concurrent threads (default 5)
            
        Returns:
            Dict mapping page_index -> should_skip (True/False)
        """
        skip_decisions: Dict[int, bool] = {}
        
        if not page_analyses:
            return skip_decisions
        
        def evaluate_page(page_idx: int, page_analysis: Dict[str, Any]) -> Tuple[int, bool]:
            """Evaluate skip decision for a single page."""
            summary = page_analysis.get("summary", "")
            key_terms = page_analysis.get("key_terms", [])
            page_number = page_analysis.get("page_number", 0)
            
            # Default: don't skip if no summary
            if not summary:
                return (page_idx, False)
            
            try:
                # Get prompt (uses cache)
                prompt = self.prompt_service.get_skip_decision_prompt(summary, key_terms)
                
                # Create Langfuse callback handler
                callback_handler = create_callback_handler()
                
                config = {}
                if callback_handler:
                    metadata = {
                        "langfuse_user_id": user_id,
                        "langfuse_session_id": course_material_id,
                        "material_id": course_material_id,
                        "course_id": course_id,
                        "page_number": page_number,
                        "agent_name": self.name,
                        "operation": "skip_decision_parallel"
                    }
                    config["callbacks"] = [callback_handler]
                    config["metadata"] = metadata
                
                message = HumanMessage(content=prompt)
                decision = self.skip_decision_llm.invoke([message], config=config if config else None)
                
                should_skip = decision.skip
                logger.debug(f"Page {page_number}: skip={should_skip}, reason={decision.reason}")
                return (page_idx, should_skip)
                
            except Exception as e:
                logger.warning(f"Error in parallel skip decision for page {page_number}: {e}, defaulting to not skip")
                return (page_idx, False)
        
        # Execute skip decisions in parallel using ThreadPoolExecutor
        logger.info(f"Evaluating skip decisions for {len(page_analyses)} pages in parallel (max_workers={max_workers})")
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(evaluate_page, idx, page): idx 
                for idx, page in enumerate(page_analyses)
            }
            
            for future in as_completed(futures):
                try:
                    page_idx, should_skip = future.result()
                    skip_decisions[page_idx] = should_skip
                except Exception as e:
                    page_idx = futures[future]
                    logger.warning(f"Skip decision future failed for page index {page_idx}: {e}")
                    skip_decisions[page_idx] = False  # Default to not skip
        
        elapsed_time = time.time() - start_time
        skipped_count = sum(1 for v in skip_decisions.values() if v)
        logger.info(
            f"Parallel skip evaluation completed in {elapsed_time:.2f}s: "
            f"{skipped_count}/{len(page_analyses)} pages marked for skip"
        )
        
        return skip_decisions
    
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
        Skip decision node: Use pre-evaluated skip decision for current page.
        
        Performance optimization: Skip decisions are evaluated in parallel during
        the classify node. This node now only looks up the pre-computed decision
        instead of making an LLM call (saves ~1-2 seconds per page).
        
        Falls back to per-page LLM evaluation if pre-evaluated decisions are not available.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with skip decision
        """
        page_analysis = state.get("current_page_analysis")
        if not page_analysis:
            logger.warning("No current_page_analysis in state, defaulting to not skip")
            return state
        
        current_index = state.get("current_page_index", 0)
        page_number = page_analysis.get("page_number", 0)
        
        # Check if we have pre-evaluated skip decisions (from parallel evaluation)
        skip_decisions = state.get("skip_decisions", {})
        
        if current_index in skip_decisions:
            # Use pre-evaluated decision (no LLM call needed)
            should_skip = skip_decisions[current_index]
            if should_skip:
                logger.debug(f"Using pre-evaluated skip decision for page {page_number}: skip=True")
                skipped_indices = state.get("skipped_page_indices", [])
                skipped_indices.append(current_index)
                return {
                    **state,
                    "skipped_page_indices": skipped_indices
                }
            else:
                logger.debug(f"Using pre-evaluated skip decision for page {page_number}: skip=False")
                return state
        
        # Fallback: Evaluate skip decision for this page (if parallel evaluation failed)
        logger.debug(f"No pre-evaluated skip decision for page {page_number}, evaluating now")
        
        summary = page_analysis.get("summary", "")
        key_terms = page_analysis.get("key_terms", [])
        
        if not summary:
            logger.debug(f"Page {page_number} has no summary, not skipping")
            return state
        
        # Get prompt from Langfuse
        try:
            prompt = self.prompt_service.get_skip_decision_prompt(summary, key_terms)
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
                skipped_indices.append(current_index)
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
        Get context node: Get conversation messages and snippet URL for current page.
        
        Performance optimization: Uses prefetched messages from messages_by_page
        (loaded in initialize_node) instead of per-page database queries.
        
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
        
        # Get messages for this page (use prefetched if available)
        messages = []
        messages_by_page = state.get("messages_by_page", {})
        
        if page_id:
            if page_id in messages_by_page:
                # Use prefetched messages (no DB call needed)
                messages = messages_by_page[page_id]
                logger.debug(f"Using prefetched messages for page {page_number}: {len(messages)} messages")
            else:
                # Fallback to individual query if not prefetched
                try:
                    messages = get_messages_for_page(page_id, user_id)
                    logger.debug(f"Fallback: fetched messages for page {page_number}: {len(messages)} messages")
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
            classification = state.get("classification") or "general"  # Safe fallback
            logger.info(
                "Using classification '%s' for card generation on page %s",
                classification,
                page_number,
            )
            
            # #region agent log
            # try:
            #     with open("/Users/milan/on mac/cursor AAI/.cursor/debug.log", "a") as f:
            #         f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"flashcard_agent.py:644","message":"Before prompt generation","data":{"classification":classification,"has_summary":bool(summary),"has_key_terms":bool(key_terms)},"timestamp":int(__import__("time").time()*1000)}) + "\n")
            # except: pass
            # #endregion
            
            prompt = self.prompt_service.get_card_generation_prompt(
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
            
            # Convert to dict format with metadata tags
            cards = []
            page_analysis_id = page_analysis.get("id")
            for card in result.cards:
                # Build metadata tags (page:N, source:uuid) + LLM-generated tags
                metadata_tags = [
                    f"page:{page_number}",
                    f"source:{page_analysis_id}"
                ]
                all_tags = metadata_tags + (card.tags if card.tags else [])
                
                card_dict = {
                    "front": card.front,
                    "back": card.back,
                    "tags": all_tags,
                    # Keep source_page_analysis_id for backward compatibility during transition
                    "source_page_analysis_id": page_analysis_id
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
        Save cards node: Apply deduplication, add to Anki, and cache to database.
        
        Flow:
        1. Apply deduplication if enabled (compare against Anki fronts)
        2. Add unique cards to Anki (source of truth) - if available
        3. Cache to database (backup) - ALWAYS save, even if Anki unavailable
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with deduplicated cards
        """
        save_to_db = state.get("save_to_db", False)
        all_cards = state.get("all_cards", [])
        
        if not all_cards:
            return state
        
        # 1. Apply deduplication if enabled
        if state.get("deduplicate_course", False):
            existing_fronts = state.get("existing_anki_fronts", [])
            all_cards, removed_count = deduplicate_flashcards(all_cards, existing_fronts)
            if removed_count > 0:
                logger.info(f"Deduplication removed {removed_count} similar cards")
        
        if not all_cards:
            logger.info("No unique cards remaining after deduplication")
            return {**state, "all_cards": []}
        
        # 2. Add to Anki (source of truth) - if available
        target_deck = state.get("target_deck_name")
        note_ids = []
        anki_synced = False  # Cards added to local Anki
        ankiweb_synced = False  # Cards synced to AnkiWeb
        anki_available = False
        
        if target_deck:
            try:
                note_ids, ankiweb_synced = self.anki_sync_service.add_cards(all_cards, target_deck)
                successful_adds = len([n for n in note_ids if n])
                logger.info(f"Added {successful_adds} cards to Anki deck '{target_deck}', AnkiWeb synced: {ankiweb_synced}")
                # Consider local Anki sync successful if at least one card was added
                anki_synced = successful_adds > 0
                anki_available = True
            except Exception as e:
                logger.error(f"Failed to add cards to Anki: {e}")
                logger.info("Anki Connect not available - will save flashcards with temporary IDs for APKG download")
                
                # If all cards are duplicates, they're already in Anki
                # This should count as "synced" since the cards exist
                error_str = str(e)
                if "duplicate" in error_str.lower():
                    anki_synced = True  # Cards are already in Anki (duplicates)
                    logger.info("All cards were duplicates - cards already exist in Anki")
        
        # 3. Save to database (flashcard_cache table - Anki-aligned)
        # IMPORTANT: Always save to DB, even if Anki is unavailable
        # This allows users to download APKG files even without Anki Connect
        if save_to_db:
            user_id = state.get("user_id", "")
            course_id = state.get("course_id", "")
            
            # NOTE: Dual-write disabled - now using only flashcard_cache table
            # Old flashcards table is preserved but no longer written to
            
            # Generate temporary negative note IDs if Anki is not available
            # These will be replaced with real Anki note IDs if Anki becomes available later
            if not note_ids:
                # Generate temporary negative IDs starting from -1
                # These are safe because Anki never uses negative note IDs
                note_ids = [-(i + 1) for i in range(len(all_cards))]
                logger.info(f"Generated {len(note_ids)} temporary note IDs for database storage (Anki unavailable)")
            
            try:
                get_flashcard().cache(
                    all_cards,
                    note_ids,
                    user_id,
                    target_deck or "Default",
                    course_id,
                    synced_to_ankiweb=ankiweb_synced
                )
                logger.info(
                    f"Cached {len(all_cards)} flashcards to database "
                    f"(anki_available={anki_available}, ankiweb_synced={ankiweb_synced})"
                )
            except Exception as e:
                logger.warning(f"Failed to cache flashcards: {str(e)}")
        
        return {**state, "all_cards": all_cards, "anki_synced": anki_synced, "ankiweb_synced": ankiweb_synced}
    
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
        deduplicate_course: bool = False,
        parent_deck_name: Optional[str] = None,
        target_deck_name: Optional[str] = None,
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
            deduplicate_course: Enable course-wide deduplication via Anki
            parent_deck_name: Course deck name for Anki query (e.g., "Marketing 101")
            target_deck_name: Full deck name for adding cards (e.g., "Marketing 101::Lecture 3")
            
        Returns:
            Dict with "cards" (list of flashcard dicts) and "anki_synced" (bool)
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
            # Deduplication config
            "deduplicate_course": deduplicate_course,
            "existing_anki_fronts": [],
            "parent_deck_name": parent_deck_name,
            "target_deck_name": target_deck_name,
        }
        
        # Use thread_id if provided (for resumability), otherwise generate new
        if thread_id is None:
            thread_id = f"flashcard-{course_material_id}-{user_id}"
            if task_id:
                thread_id = f"flashcard-task-{task_id}"
        
        # Recursion limit: 10 * page count so large PDFs don't hit default 25
        page_analyses_pre = get_page_analysis().get_all_for_material(course_material_id, user_id)
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
            
            # Return cards and sync status from final state
            all_cards = final_state.get("all_cards", [])
            anki_synced = final_state.get("anki_synced", False)
            ankiweb_synced = final_state.get("ankiweb_synced", False)
            logger.info(f"Flashcard generation completed: {len(all_cards)} cards generated, anki_synced={anki_synced}, ankiweb_synced={ankiweb_synced}")
            return {"cards": all_cards, "anki_synced": anki_synced, "ankiweb_synced": ankiweb_synced}
            
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
