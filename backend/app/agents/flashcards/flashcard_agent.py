"""
Flashcard Generator Agent

Generates Anki-compatible flashcards from lecture page analyses and conversation history.
"""

import json
from typing import List, Dict, Any, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from app.models.schemas import PageSkipDecision, FlashcardGenerationResult, Flashcard
from app.services.storage import (
    get_all_page_analyses_for_material,
    get_messages_for_page,
)
from app.services.analyzer import get_gemini_model


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
        self.skip_decision_llm = self.llm.with_structured_output(PageSkipDecision)
        self.card_generation_llm = self.llm.with_structured_output(FlashcardGenerationResult)
    
    def _should_skip_page(self, page_analysis: Dict[str, Any]) -> tuple[bool, str]:
        """
        Determine if a page should be skipped (intro/title/TOC).
        
        Args:
            page_analysis: Page analysis dict with summary, key_terms, etc.
            
        Returns:
            Tuple of (should_skip: bool, reason: str)
        """
        summary = page_analysis.get("summary", "")
        key_terms = page_analysis.get("key_terms", [])
        
        if not summary:
            return False, "No summary available"
        
        # Build prompt for skip decision
        if self.language == "de":
            prompt = f"""Analysiere diese Vorlesungsseite und entscheide, ob sie übersprungen werden sollte.

Seitenzusammenfassung: {summary}
Wichtige Begriffe: {', '.join(key_terms[:10]) if key_terms else 'Keine'}

Überspringe die Seite, wenn sie:
- Eine Titelseite ist
- Ein Inhaltsverzeichnis ist
- Eine Einleitungsseite mit nur allgemeinen Informationen ist
- Keine fachlichen Inhalte enthält

Antworte mit JSON: {{"skip": true/false, "reason": "Kurze Begründung"}}"""
        else:
            prompt = f"""Analyze this lecture page and decide if it should be skipped.

Page summary: {summary}
Key terms: {', '.join(key_terms[:10]) if key_terms else 'None'}

Skip the page if it is:
- A title page
- A table of contents
- An introduction page with only general information
- Contains no academic content

Respond with JSON: {{"skip": true/false, "reason": "Brief reason"}}"""
        
        try:
            message = HumanMessage(content=prompt)
            decision = self.skip_decision_llm.invoke([message])
            return decision.skip, decision.reason
        except Exception as e:
            # On error, don't skip (safer to include than exclude)
            return False, f"Error in skip decision: {str(e)}"
    
    def _generate_cards_for_page(
        self,
        page_analysis: Dict[str, Any],
        messages: List[Dict[str, Any]],
        course_id: str,
        material_id: str,
        page_number: int
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
        
        # Build prompt for card generation
        if self.language == "de":
            prompt = f"""Erstelle Lernkarteikarten für diese Vorlesungsseite.

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
            prompt = f"""Create flashcards for this lecture page.

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
        
        try:
            message = HumanMessage(content=prompt)
            result = self.card_generation_llm.invoke([message])
            
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
            # On error, return empty list
            print(f"Error generating cards for page {page_number}: {str(e)}")
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
        
        if not page_analyses:
            return []
        
        all_cards = []
        
        # Process each page
        for page_analysis in page_analyses:
            page_number = page_analysis.get("page_number", 0)
            page_id = page_analysis.get("id")
            
            # Check if page should be skipped
            should_skip, reason = self._should_skip_page(page_analysis)
            if should_skip:
                print(f"Skipping page {page_number}: {reason}")
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
                page_number=page_number
            )
            
            all_cards.extend(cards)
        
        # Save to database if requested
        if save_to_db and all_cards:
            from app.services.storage import save_flashcards
            try:
                save_flashcards(all_cards, user_id, course_id)
            except Exception as e:
                print(f"Warning: Failed to save flashcards to database: {str(e)}")
        
        return all_cards
