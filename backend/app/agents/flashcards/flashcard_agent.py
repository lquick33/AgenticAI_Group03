"""
Flashcard Generator Agent

Generates Anki-compatible flashcards from lecture page analyses and conversation history.
"""

import logging
from typing import List, Dict, Any, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from app.models.schemas import PageSkipDecision, FlashcardGenerationResult
from app.services.storage import (
    get_all_page_analyses_for_material,
    get_messages_for_page,
)
from app.services.snippet_service import get_snippets_for_material, get_snippet_public_url
from app.services.analyzer import get_gemini_model
from app.services.observability import create_callback_handler, get_langfuse_client

logger = logging.getLogger(__name__)


class FlashcardGeneratorAgent:
    """
    Agent for generating flashcards from lecture materials.
    
    This agent processes page analyses and conversation history to create
    educational flashcards that can be imported into Anki.
    """
    
    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        language: str = "de"
    ):
        """
        Initialize the flashcard generator agent.
        
        Args:
            llm: Language model to use (defaults to Gemini if None)
            language: Language for prompts and output (default: "de")
        """
        self.llm = llm or get_gemini_model()
        self.language = language
        
        # Create structured LLMs for different tasks
        self.skip_decision_llm = self.llm.with_structured_output(PageSkipDecision).with_config({"run_name": "flashcard-llm-skip-decision"})
        self.card_generation_llm = self.llm.with_structured_output(FlashcardGenerationResult).with_config({"run_name": "flashcard-llm-generation"})
        
        # Langfuse client for prompt management
        self.langfuse_client = get_langfuse_client()
    
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
    
    def _should_skip_page(
        self, 
        page_analysis: Dict[str, Any],
        user_id: Optional[str] = None,
        course_material_id: Optional[str] = None,
        course_id: Optional[str] = None,
        page_number: Optional[int] = None
    ) -> tuple[bool, str]:
        """
        Determine if a page should be skipped (intro/title/TOC).
        
        Args:
            page_analysis: Page analysis dict with summary, key_terms, etc.
            user_id: User ID for Langfuse tracking (optional)
            course_material_id: Course material ID for Langfuse tracking (optional)
            course_id: Course ID for Langfuse tracking (optional)
            page_number: Page number for Langfuse tracking (optional)
            
        Returns:
            Tuple of (should_skip: bool, reason: str)
        """
        summary = page_analysis.get("summary", "")
        key_terms = page_analysis.get("key_terms", [])
        
        if not summary:
            return False, "No summary available"
        
        # Get prompt from Langfuse
        prompt = self._get_skip_decision_prompt(summary, key_terms)
        
        # Create Langfuse callback handler für automatisches Tracking
        callback_handler = create_callback_handler()
        
        # Prepare config with callbacks and metadata
        config = {}
        if callback_handler:
            metadata = {
                "langfuse_user_id": user_id,
                "langfuse_session_id": course_material_id,  # Use material_id as session
                "material_id": course_material_id,
                "course_id": course_id,
                "page_number": page_number,
                "agent_name": "FlashcardGeneratorAgent",
                "operation": "skip_decision"
            }
            config["callbacks"] = [callback_handler]
            config["metadata"] = metadata
            logger.debug(f"🟡 Langfuse: Sending skip_decision LLM call with metadata: user_id={user_id}, material_id={course_material_id}, page={page_number}")
        
        try:
            message = HumanMessage(content=prompt)
            decision = self.skip_decision_llm.invoke([message], config=config if config else None)
            
            if callback_handler:
                logger.debug("🟢 Langfuse: Skip decision LLM call completed - data tracked by CallbackHandler")
            
            return decision.skip, decision.reason
        except Exception as e:
            logger.warning(f"Error in skip decision for page: {str(e)}")
            # On error, don't skip (safer to include than exclude)
            return False, f"Error in skip decision: {str(e)}"
    
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
    
    def _generate_cards_for_page(
        self,
        page_analysis: Dict[str, Any],
        messages: List[Dict[str, Any]],
        course_id: str,
        material_id: str,
        page_number: int,
        user_id: Optional[str] = None,
        snippet_image_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate flashcards for a single page.
        
        Args:
            page_analysis: Page analysis dict
            messages: Conversation messages for this page
            course_id: Course ID for tags
            material_id: Material ID for tags
            page_number: Page number for tags
            
        Returns:
            List of flashcard dicts with front, back, tags
        """
        summary = page_analysis.get("summary", "")
        key_terms = page_analysis.get("key_terms", [])
        exam_questions = page_analysis.get("exam_questions", [])
        diagram_description = page_analysis.get("diagram_description", "")
        
        # Build conversation context (only user questions and assistant answers that show understanding issues)
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
        
        # Log before getting prompt
        logger.info(f"🔍 _generate_cards_for_page: About to call _get_card_generation_prompt")
        logger.info(f"🔍 _generate_cards_for_page: snippet_image_url parameter = {snippet_image_url is not None}")
        if snippet_image_url:
            logger.info(f"🔍 _generate_cards_for_page: snippet_image_url value = {snippet_image_url[:100]}...")
        else:
            logger.warning(f"⚠️ _generate_cards_for_page: snippet_image_url is None or empty!")
        
        # Get prompt from Langfuse
        prompt = self._get_card_generation_prompt(
            summary=summary,
            key_terms=key_terms,
            exam_questions=exam_questions,
            diagram_description=diagram_description,
            conversation_context=conversation_context,
            course_id=course_id,
            material_id=material_id,
            page_number=page_number,
            snippet_image_url=snippet_image_url
        )
        
        # Create Langfuse callback handler für automatisches Tracking
        callback_handler = create_callback_handler()
        
        # Prepare config with callbacks and metadata
        config = {}
        if callback_handler:
            metadata = {
                "langfuse_user_id": user_id,
                "langfuse_session_id": material_id,  # Use material_id as session
                "material_id": material_id,
                "course_id": course_id,
                "page_number": page_number,
                "agent_name": "FlashcardGeneratorAgent",
                "operation": "card_generation"
            }
            config["callbacks"] = [callback_handler]
            config["metadata"] = metadata
            logger.debug(f"🟡 Langfuse: Sending card_generation LLM call with metadata: user_id={user_id}, material_id={material_id}, course_id={course_id}, page={page_number}")
        
        try:
            # Create message with optional image if snippet is available
            if snippet_image_url:
                # Send image as vision input so agent can see it
                message = HumanMessage(
                    content=[
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": snippet_image_url}}
                    ]
                )
                logger.info(f"📸 Including snippet image in vision input for page {page_number}")
            else:
                message = HumanMessage(content=prompt)
            
            result = self.card_generation_llm.invoke([message], config=config if config else None)
            
            if callback_handler:
                logger.debug("🟢 Langfuse: Card generation LLM call completed - data tracked by CallbackHandler")
            
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
            
            return cards
        except Exception as e:
            logger.error(f"Error generating cards for page {page_number}: {str(e)}", exc_info=True)
            # On error, return empty list
            return []
    
    def generate_flashcards(
        self,
        course_material_id: str,
        user_id: str,
        course_id: str,
        save_to_db: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Generate flashcards for all relevant pages in a course material.
        
        Args:
            course_material_id: Course material ID
            user_id: User ID
            course_id: Course ID
            save_to_db: Whether to save flashcards to database
            
        Returns:
            List of flashcard dicts with front, back, tags, source_page_analysis_id
        """
        # Get all page analyses
        page_analyses = get_all_page_analyses_for_material(course_material_id, user_id)
        logger.info(f"Generating flashcards for {len(page_analyses) if page_analyses else 0} pages")
        
        if not page_analyses:
            return []
            
        # Get all snippets for this material to avoid DB calls in loop
        logger.info(f"🔍 Getting snippets for material {course_material_id}, user {user_id}")
        snippets = get_snippets_for_material(course_material_id, user_id)
        logger.info(f"🔍 Found {len(snippets)} snippets total")
        if snippets:
            logger.info(f"🔍 Snippet page numbers: {[s.get('page_number') for s in snippets]}")
        snippets_by_page = {s["page_number"]: s for s in snippets}
        logger.info(f"🔍 snippets_by_page dict keys: {list(snippets_by_page.keys())}")
        
        all_cards = []
        
        # Process each page
        for idx, page_analysis in enumerate(page_analyses):
            page_number = page_analysis.get("page_number", 0)
            page_id = page_analysis.get("id")
            
            # Check if page should be skipped
            should_skip, reason = self._should_skip_page(
                page_analysis,
                user_id=user_id,
                course_material_id=course_material_id,
                course_id=course_id,
                page_number=page_number
            )
            
            if should_skip:
                logger.debug(f"Skipping page {page_number}: {reason}")
                continue
            
            # Get messages for this page
            messages = []
            if page_id:
                messages = get_messages_for_page(page_id, user_id)
            
            # Check for snippets and get URL if available
            snippet_image_url = None
            logger.info(f"🔍 Checking for snippets for page {page_number}...")
            logger.info(f"🔍 snippets_by_page keys: {list(snippets_by_page.keys())}")
            
            if page_number in snippets_by_page:
                snippet = snippets_by_page[page_number]
                logger.info(f"✅ Snippet found in dict for page {page_number}: {snippet}")
                image_path = snippet.get("image_path")
                logger.info(f"🔍 image_path from snippet: {image_path}")
                
                if image_path:
                    try:
                        logger.info(f"🔍 Calling get_snippet_public_url with: {image_path}")
                        snippet_image_url = get_snippet_public_url(image_path)
                        logger.info(f"✅ URL generated successfully! Length: {len(snippet_image_url) if snippet_image_url else 0}")
                        logger.info(f"✅ Found snippet for page {page_number}, URL: {snippet_image_url[:100] if snippet_image_url else 'None'}...")
                        logger.info(f"📸 snippet_image_url is not None: {snippet_image_url is not None}")
                        logger.info(f"📸 snippet_image_url type: {type(snippet_image_url)}")
                        logger.info(f"📸 snippet_image_url value (first 100 chars): {str(snippet_image_url)[:100] if snippet_image_url else 'None'}")
                    except Exception as e:
                        logger.error(f"❌ Failed to get snippet URL for page {page_number}: {e}", exc_info=True)
                        snippet_image_url = None
                else:
                    logger.warning(f"⚠️ Snippet found but image_path is None or empty for page {page_number}")
            else:
                logger.debug(f"No snippet found for page {page_number} in snippets_by_page")
            
            # Log before passing to _generate_cards_for_page
            logger.info(f"🔍 About to call _generate_cards_for_page with snippet_image_url: {snippet_image_url is not None}")
            if snippet_image_url:
                logger.info(f"🔍 snippet_image_url value: {snippet_image_url[:100]}...")
            
            # Generate cards for this page (agent will see image and decide where to include it)
            cards = self._generate_cards_for_page(
                page_analysis=page_analysis,
                messages=messages,
                course_id=course_id,
                material_id=course_material_id,
                page_number=page_number,
                user_id=user_id,
                snippet_image_url=snippet_image_url
            )
            
            all_cards.extend(cards)
        
        # Save to database if requested
        if save_to_db and all_cards:
            from app.services.storage import save_flashcards
            try:
                save_flashcards(all_cards, user_id, course_id)
            except Exception as e:
                logger.warning(f"Failed to save flashcards to database: {str(e)}")
        
        return all_cards
