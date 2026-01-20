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
        Get skip decision prompt from Langfuse or fallback to hardcoded version.
        
        Args:
            summary: Page summary
            key_terms: List of key terms
            
        Returns:
            Compiled prompt string
        """
        # Try to load prompt from Langfuse
        if self.langfuse_client:
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
                logger.warning(f"Failed to load Langfuse prompt for skip-decision, using fallback: {e}")
        
        # Fallback to hardcoded prompt
        if self.language == "de":
            return f"""Analysiere diese Vorlesungsseite und entscheide, ob sie übersprungen werden sollte.

Seitenzusammenfassung: {summary}
Wichtige Begriffe: {', '.join(key_terms[:10]) if key_terms else 'Keine'}

Überspringe die Seite, wenn sie:
- Eine Titelseite ist
- Ein Inhaltsverzeichnis ist
- Eine Einleitungsseite mit nur allgemeinen Informationen ist
- Keine fachlichen Inhalte enthält

Antworte mit JSON: {{"skip": true/false, "reason": "Kurze Begründung"}}"""
        else:
            return f"""Analyze this lecture page and decide if it should be skipped.

Page summary: {summary}
Key terms: {', '.join(key_terms[:10]) if key_terms else 'None'}

Skip the page if it is:
- A title page
- A table of contents
- An introduction page with only general information
- Contains no academic content

Respond with JSON: {{"skip": true/false, "reason": "Brief reason"}}"""
    
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
        
        # Get prompt (from Langfuse or fallback)
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
        page_number: int
    ) -> str:
        """
        Get card generation prompt from Langfuse or fallback to hardcoded version.
        
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
        """
        # Try to load prompt from Langfuse
        if self.langfuse_client:
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
                
                # Compile prompt with variables
                compiled_prompt = langfuse_prompt.compile(
                    summary=summary,
                    key_terms=key_terms_str,
                    exam_questions=exam_questions_str,
                    diagram_description=diagram_desc_str,
                    conversation_context=conv_context_str,
                    course_id=course_id,
                    material_id=material_id,
                    page_number=str(page_number)
                )
                logger.debug("✅ Using Langfuse prompt for card-generation")
                return compiled_prompt
            except Exception as e:
                logger.warning(f"Failed to load Langfuse prompt for card-generation, using fallback: {e}")
        
        # Fallback to hardcoded prompt
        if self.language == "de":
            return f"""Erstelle Lernkarteikarten für diese Vorlesungsseite.

SEITENINHALT:
Zusammenfassung: {summary}
Wichtige Begriffe: {', '.join(key_terms) if key_terms else 'Keine'}
Prüfungsfragen: {', '.join(exam_questions) if exam_questions else 'Keine'}
Diagrammbeschreibung: {diagram_description if diagram_description else 'Kein Diagramm'}

KONVERSATION ZU DIESER SEITE:
{conversation_context if conversation_context else 'Keine relevanten Konversationen'}

AUFGABE:
Erstelle mindestens 1, idealerweise 2-4 Lernkarteikarten für diese Seite.
- Wenn der Student spezifische Verständnisprobleme in der Konversation hatte, erstelle eine Karte, die genau dieses Problem behandelt.
- Erstelle Karten für wichtige Konzepte, Definitionen, Formeln oder Zusammenhänge.
- Die Vorderseite sollte eine Frage oder einen Begriff enthalten.
- Die Rückseite sollte eine klare, prägnante Antwort oder Definition enthalten.
- Verwende Tags: course:{course_id}, material:{material_id}, page:{page_number}, und zusätzliche thematische Tags.

Antworte mit JSON: {{"cards": [{{"front": "...", "back": "...", "tags": ["tag1", "tag2", ...]}}, ...]}}"""
        else:
            return f"""Create flashcards for this lecture page.

PAGE CONTENT:
Summary: {summary}
Key terms: {', '.join(key_terms) if key_terms else 'None'}
Exam questions: {', '.join(exam_questions) if exam_questions else 'None'}
Diagram description: {diagram_description if diagram_description else 'No diagram'}

CONVERSATION FOR THIS PAGE:
{conversation_context if conversation_context else 'No relevant conversations'}

TASK:
Create at least 1, ideally 2-4 flashcards for this page.
- If the student had specific understanding problems in the conversation, create a card that addresses exactly this problem.
- Create cards for important concepts, definitions, formulas, or relationships.
- The front side should contain a question or term.
- The back side should contain a clear, concise answer or definition.
- Use tags: course:{course_id}, material:{material_id}, page:{page_number}, and additional thematic tags.

Respond with JSON: {{"cards": [{{"front": "...", "back": "...", "tags": ["tag1", "tag2", ...]}}, ...]}}"""
    
    def _generate_cards_for_page(
        self,
        page_analysis: Dict[str, Any],
        messages: List[Dict[str, Any]],
        course_id: str,
        material_id: str,
        page_number: int,
        user_id: Optional[str] = None
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
        
        # Get prompt (from Langfuse or fallback)
        prompt = self._get_card_generation_prompt(
            summary=summary,
            key_terms=key_terms,
            exam_questions=exam_questions,
            diagram_description=diagram_description,
            conversation_context=conversation_context,
            course_id=course_id,
            material_id=material_id,
            page_number=page_number
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
            
            # Generate cards for this page
            cards = self._generate_cards_for_page(
                page_analysis=page_analysis,
                messages=messages,
                course_id=course_id,
                material_id=course_material_id,
                page_number=page_number,
                user_id=user_id
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
