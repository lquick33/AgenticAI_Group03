"""
Quiz Generator Agent

Subagent that generates comprehension quizzes from lecture material.
Used by the Tutor Agent when a subtopic is completed.
"""

import json
import logging
from typing import Optional
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.base import BaseAgent
from app.models.schemas import QuizData, QuizQuestion
from app.services.storage import get_page_analyses_for_range
from app.services.observability import create_callback_handler, get_langfuse_client
from app.services.analyzer import get_gemini_model
from app.core.config import settings
from langgraph.graph import MessagesState
from typing import TypedDict, Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class QuizGeneratorState(MessagesState):
    """
    State for Quiz Generator Agent.
    
    Extends MessagesState with fields needed for quiz generation.
    All fields are optional to allow gradual state building.
    """
    page_analyses: Optional[List[Dict[str, Any]]] = None
    topic: Optional[str] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    course_material_id: Optional[str] = None
    user_id: Optional[str] = None
    quiz_data: Optional[QuizData] = None


class QuizGeneratorAgent(BaseAgent):
    """
    Quiz Generator Subagent.
    
    Generates comprehension quizzes (3-5 questions) from lecture material
    for a specific page range. Questions focus on understanding, not memorization.
    
    Difficulty distribution:
    - 1-2 easy questions
    - 1 medium question
    - At least 1 hard question
    """
    
    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        name: str = "QuizGeneratorAgent",
        checkpointer: Optional[MemorySaver] = None,
        language: str = "de"
    ):
        # Use provided LLM or create default Gemini model
        if llm is None:
            llm = get_gemini_model()
        
        # Store language for prompt loading
        self.language = language
        
        # Langfuse client for prompt management
        self.langfuse_client = get_langfuse_client()
        
        # Build system prompt (loads from Langfuse)
        system_prompt = self._build_system_prompt(language)
        
        super().__init__(
            llm=llm,
            name=name,
            system_prompt=system_prompt,
            checkpointer=checkpointer
        )
    
    def _build_system_prompt(self, language: str = "de") -> str:
        """
        Build system prompt for quiz generation.
        Loads prompt from Langfuse if available, otherwise uses fallback.
        
        Args:
            language: Language code (e.g., "de", "en")
            
        Returns:
            System prompt string
        """
        # Try to load from Langfuse first
        if self.langfuse_client:
            try:
                prompt_name = f"quiz-generator/system-prompt-{language}"
                langfuse_prompt = self.langfuse_client.get_prompt(
                    prompt_name,
                    label="production",
                    type="chat"
                )
                
                # Extract system message content from compiled chat prompt
                if langfuse_prompt and isinstance(langfuse_prompt, list) and len(langfuse_prompt) > 0:
                    system_message = langfuse_prompt[0]
                    if isinstance(system_message, dict) and system_message.get("role") == "system":
                        logger.debug(f"✅ Using Langfuse prompt for {prompt_name}")
                        return system_message.get("content", "")
                    elif hasattr(system_message, "content"):
                        logger.debug(f"✅ Using Langfuse prompt for {prompt_name}")
                        return system_message.content
                
                logger.warning(f"Invalid prompt structure from Langfuse for {prompt_name}, using fallback")
            except Exception as e:
                logger.warning(f"Failed to load Langfuse prompt for quiz-generator: {e}, using fallback")
        
        # Fallback prompt if Langfuse is not available or fails
        return """Du bist ein Quiz-Generator für Vorlesungsmaterialien. Deine Aufgabe ist es, Verständnisfragen zu erstellen, die das Verständnis der Studenten prüfen, nicht das Auswendiglernen.

WICHTIGE REGELN:
1. Erstelle 3-5 Fragen (bei komplexen Themen können es auch mehr sein, max. 8)
2. Schwierigkeitsverteilung:
   - 1-2 leichte Fragen (Grundverständnis, Definitionen)
   - 1 mittlere Frage (Anwendung, Zusammenhänge)
   - Mindestens 1 schwere Frage (tiefes Verständnis, Analyse, Synthese)
3. Jede Frage muss genau 4 Antwortmöglichkeiten haben (A, B, C, D)
4. Fragen sollen VERSTÄNDNIS prüfen, nicht Auswendiglernen
5. Jede Frage braucht eine Erklärung der richtigen Antwort
6. Die Fragen sollen auf dem bereitgestellten Material basieren

FRAGEN-TYPEN (bevorzugt):
- Anwendungsfragen: "Wie würde man X in Situation Y anwenden?"
- Verständnisfragen: "Warum funktioniert X auf diese Weise?"
- Analysefragen: "Was wäre das Ergebnis, wenn man X ändert?"
- Synthesefragen: "Wie hängen X und Y zusammen?"

VERMEIDE:
- Reine Faktenfragen ("Was ist die Definition von X?")
- Auswendiglern-Fragen ohne Kontext
- Fragen, die nicht im Material behandelt wurden"""
    
    def _build_graph(self) -> None:
        """Build the LangGraph workflow for quiz generation."""
        workflow = StateGraph(state_schema=QuizGeneratorState)
        
        # Simple linear graph: just generate quiz
        workflow.add_node("generate", self.generate_node)
        workflow.add_edge(START, "generate")
        workflow.add_edge("generate", END)
        
        self.compile_graph(workflow)
    
    def generate_node(self, state: QuizGeneratorState) -> QuizGeneratorState:
        """
        Generate quiz from state context.
        
        Expects state to contain:
        - page_analyses: List of page analysis dicts
        - topic: Topic name
        - start_page: Starting page number
        - end_page: Ending page number
        - course_material_id: Course material ID (optional, for tracing)
        - user_id: User ID (optional, for tracing)
        """
        # Extract context from state
        logger.info("🟡 generate_node called - starting quiz generation")
        logger.debug(f"🟡 State type: {type(state)}, State keys: {list(state.keys()) if isinstance(state, dict) else 'not a dict'}")
        
        page_analyses = state.get("page_analyses") or []
        topic = state.get("topic") or "Unbekanntes Thema"
        start_page = state.get("start_page") or 1
        end_page = state.get("end_page") or 1
        course_material_id = state.get("course_material_id")
        user_id = state.get("user_id")
        
        logger.info(f"🟡 State extracted: pages={len(page_analyses) if page_analyses else 0}, topic={topic}, start={start_page}, end={end_page}")
        
        # Debug: Check if page_analyses is actually in state
        if "page_analyses" not in state:
            logger.error(f"🔴 CRITICAL: 'page_analyses' key not found in state! State keys: {list(state.keys())}")
        elif not page_analyses:
            logger.warning(f"⚠️ 'page_analyses' key exists in state but is empty or None. Value type: {type(state.get('page_analyses'))}, Value: {state.get('page_analyses')}")
        
        if not page_analyses:
            error_msg = "Keine Seitenanalysen verfügbar für Quiz-Generierung"
            logger.error(f"🔴 {error_msg}")
            logger.error(f"🔴 Full state dump: {state}")
            return {"messages": [HumanMessage(content=error_msg)]}
        
        # Build context from page analyses
        context_parts = []
        for analysis in page_analyses:
            page_num = analysis.get("page_number", "?")
            summary = analysis.get("summary", "")
            key_terms = analysis.get("key_terms", [])
            
            context_parts.append(f"Seite {page_num}:")
            context_parts.append(f"Zusammenfassung: {summary}")
            if key_terms:
                context_parts.append(f"Wichtige Begriffe: {', '.join(key_terms)}")
            context_parts.append("")
        
        context_text = "\n".join(context_parts)
        
        # Create prompt for quiz generation
        prompt = f"""Erstelle ein Quiz für das folgende Thema: {topic}

Das Thema wurde auf den Seiten {start_page} bis {end_page} behandelt.

MATERIAL:
{context_text}

AUFGABE:
Erstelle ein Quiz mit 3-5 Fragen (bei komplexen Themen können es auch mehr sein, max. 8), die das VERSTÄNDNIS prüfen.

Schwierigkeitsverteilung:
- 1-2 leichte Fragen (Grundverständnis)
- 1 mittlere Frage (Anwendung)
- Mindestens 1 schwere Frage (tiefes Verständnis, Analyse)

Jede Frage muss:
- Genau 4 Antwortmöglichkeiten haben (A, B, C, D)
- Eine Erklärung der richtigen Antwort enthalten
- Das Verständnis prüfen, nicht das Auswendiglernen

Gib das Quiz im JSON-Format zurück (verwende das QuizData Schema)."""
        
        # Prepare LLM with structured output
        # Use descriptive run_name for Langfuse tracking (consistent with other agents)
        structured_llm = self.llm.with_structured_output(QuizData).with_config({
            "run_name": "quiz-generator-agent/structured-generation"
        })
        
        # Create Langfuse callback handler
        callback_handler = create_callback_handler()
        
        # Prepare config with callbacks and metadata for Langfuse tracing
        # Follow the same pattern as TutorAgent for consistency
        config = {}
        if callback_handler:
            metadata = {
                "langfuse_user_id": user_id,
                "langfuse_session_id": course_material_id,  # Use course_material_id as session
                "agent_name": self.name,
                "operation": "quiz_generation",
                "topic": topic,
                "start_page": start_page,
                "end_page": end_page,
                "page_range": f"{start_page}-{end_page}",
                "language": self.language,
                "course_material_id": course_material_id,
                "quiz_generator_version": "1.0"
            }
            config["callbacks"] = [callback_handler]
            config["metadata"] = metadata
            logger.info(
                f"🟡 Langfuse: Sending quiz generation LLM call "
                f"(run_name: quiz-generator-agent/structured-generation) "
                f"with metadata: user_id={user_id}, session_id={course_material_id}, "
                f"topic={topic}, pages={start_page}-{end_page}"
            )
        
        try:
            # Call LLM with structured output
            messages = [HumanMessage(content=prompt)]
            messages_for_llm = self.add_system_message(messages)
            
            logger.info(f"Calling structured LLM for quiz generation (topic: {topic}, pages: {start_page}-{end_page})")
            logger.debug(f"Prompt length: {len(prompt)} chars, Context length: {len(context_text)} chars")
            
            result = structured_llm.invoke(messages_for_llm, config=config if config else None)
            
            if callback_handler:
                logger.info(
                    f"🟢 Langfuse: Quiz generation LLM call completed "
                    f"(run_name: quiz-generator-agent/structured-generation) - "
                    f"data tracked by CallbackHandler"
                )
            
            # Robust parsing with Pydantic validation
            # Handle different return types from structured_llm
            quiz_data = self._parse_quiz_result(result)
            
            logger.info(f"Received QuizData with {len(quiz_data.questions)} questions")
            
            # Validate difficulty distribution
            self._validate_quiz(quiz_data)
            logger.info("Quiz validation passed")
            
            # Store result in state as JSON string for extraction in generate_quiz()
            # Use Pydantic's model_dump_json for reliable JSON serialization
            json_content = quiz_data.model_dump_json(ensure_ascii=False)
            logger.info(f"Quiz generated successfully: {len(quiz_data.questions)} questions, JSON length: {len(json_content)} chars")
            return {"messages": [HumanMessage(content=json_content)], "quiz_data": quiz_data}
        
        except Exception as e:
            logger.error(f"Failed to generate quiz: {str(e)}", exc_info=True)
            error_msg = f"Fehler bei Quiz-Generierung: {str(e)}"
            return {"messages": [HumanMessage(content=error_msg)]}
    
    def _parse_quiz_result(self, result: any) -> QuizData:
        """
        Parse and validate quiz result using Pydantic.
        
        Handles different return types from structured_llm:
        - QuizData instance (direct)
        - dict (needs conversion)
        - str (needs JSON parsing)
        
        Args:
            result: Result from structured_llm.invoke()
            
        Returns:
            Validated QuizData instance
            
        Raises:
            ValueError: If result cannot be parsed or validated
        """
        # Case 1: Already a QuizData instance
        if isinstance(result, QuizData):
            logger.debug("Result is already QuizData instance")
            return result
        
        # Case 2: Dict - use Pydantic model_validate
        if isinstance(result, dict):
            logger.info("Result is dict, validating with Pydantic")
            try:
                return QuizData.model_validate(result)
            except Exception as e:
                logger.error(f"Failed to validate dict as QuizData: {str(e)}")
                raise ValueError(f"Ungültiges Quiz-Format: {str(e)}")
        
        # Case 3: String - try to parse as JSON
        if isinstance(result, str):
            logger.info("Result is string, attempting JSON parse")
            content = result.strip()
            
            # Check if content is empty after strip
            if not content:
                logger.error("Empty content string received from LLM")
                raise ValueError("Fehler beim Parsen des JSON: Leere Antwort vom LLM erhalten")
            
            # Check if content is an error message (starts with "Fehler", "Error", or "Keine")
            error_keywords = ["Fehler", "Error", "Keine", "keine", "failed", "Failed", "Leere"]
            if any(content.startswith(keyword) for keyword in error_keywords):
                logger.error(f"🔴 Agent returned error message instead of quiz data: {content[:200]}")
                raise ValueError(content)
            
            # Try to extract JSON from markdown code blocks if present
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end != -1:
                    content = content[start:end].strip()
                else:
                    logger.warning("Found ```json but no closing ```, trying to parse entire content")
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                if end != -1:
                    content = content[start:end].strip()
                else:
                    logger.warning("Found ``` but no closing ```, trying to parse entire content")
            
            # Check again if content is empty after extraction
            if not content:
                logger.error(f"Content is empty after markdown extraction. Original result length: {len(result)}")
                logger.debug(f"Original result preview: {result[:500]}")
                raise ValueError("Fehler beim Parsen des JSON: Kein JSON-Inhalt nach Markdown-Extraktion gefunden")
            
            # Log content preview for debugging
            logger.debug(f"Attempting to parse JSON, content length: {len(content)}, preview: {content[:200]}")
            
            # Parse JSON
            try:
                parsed_dict = json.loads(content)
                return QuizData.model_validate(parsed_dict)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {str(e)}")
                logger.error(f"Content that failed to parse (first 500 chars): {content[:500]}")
                logger.error(f"Content that failed to parse (last 200 chars): {content[-200:]}")
                raise ValueError(f"Fehler beim Parsen des JSON: {str(e)}")
            except Exception as e:
                logger.error(f"Failed to validate parsed JSON as QuizData: {str(e)}")
                logger.error(f"Parsed dict keys: {list(parsed_dict.keys()) if isinstance(parsed_dict, dict) else 'N/A'}")
                raise ValueError(f"Ungültiges Quiz-Format: {str(e)}")
        
        # Case 4: Unknown type
        logger.error(f"Unexpected result type: {type(result)}, value: {result}")
        raise ValueError(f"Unerwarteter Rückgabetyp vom LLM: {type(result)}")
    
    def _validate_quiz(self, quiz_data: QuizData) -> None:
        """
        Validate quiz meets requirements.
        
        Raises:
            ValueError: If quiz doesn't meet requirements
        """
        questions = quiz_data.questions
        
        if len(questions) < 3:
            raise ValueError(f"Quiz muss mindestens 3 Fragen haben, hat aber nur {len(questions)}")
        
        if len(questions) > 8:
            raise ValueError(f"Quiz darf maximal 8 Fragen haben, hat aber {len(questions)}")
        
        # Count difficulties
        easy_count = sum(1 for q in questions if q.difficulty == "easy")
        medium_count = sum(1 for q in questions if q.difficulty == "medium")
        hard_count = sum(1 for q in questions if q.difficulty == "hard")
        
        # Validate distribution
        if easy_count < 1:
            raise ValueError("Quiz muss mindestens 1 leichte Frage haben")
        
        if medium_count < 1:
            raise ValueError("Quiz muss mindestens 1 mittlere Frage haben")
        
        if hard_count < 1:
            raise ValueError("Quiz muss mindestens 1 schwere Frage haben")
        
        # Validate each question
        for i, question in enumerate(questions):
            if len(question.options) != 4:
                raise ValueError(f"Frage {i+1} muss genau 4 Antwortmöglichkeiten haben (A, B, C, D)")
            
            if question.correct_answer not in question.options:
                raise ValueError(f"Frage {i+1}: correct_answer '{question.correct_answer}' ist nicht in options")
            
            if not question.explanation or not question.explanation.strip():
                raise ValueError(f"Frage {i+1}: Erklärung fehlt")
        
        # Update metadata
        quiz_data.metadata = {
            "easy_count": easy_count,
            "medium_count": medium_count,
            "hard_count": hard_count
        }
    
    def generate_quiz(
        self,
        start_page: int,
        end_page: int,
        course_material_id: str,
        user_id: str
    ) -> QuizData:
        """
        Generate quiz for a page range.
        
        Args:
            start_page: Starting page number (1-indexed, inclusive)
            end_page: Ending page number (1-indexed, inclusive)
            course_material_id: Course material ID
            user_id: User ID for authorization
            
        Returns:
            QuizData with generated questions
            
        Raises:
            ValueError: If no page analyses found or validation fails
            Exception: If generation fails
        """
        # Get page analyses for range
        logger.info(f"🟡 Fetching page analyses for range {start_page}-{end_page} (material: {course_material_id}, user: {user_id})")
        page_analyses = get_page_analyses_for_range(
            course_material_id=course_material_id,
            user_id=user_id,
            start_page=start_page,
            end_page=end_page
        )
        logger.info(f"🟢 Retrieved {len(page_analyses)} page analyses from database")
        
        if not page_analyses:
            error_msg = (
                f"Keine Seitenanalysen gefunden für Seiten {start_page}-{end_page} "
                f"in Material {course_material_id}"
            )
            logger.error(f"🔴 {error_msg}")
            raise ValueError(error_msg)
        
        # Determine topic name from first page summary
        first_summary = page_analyses[0].get("summary", "")
        # Extract topic from summary (first sentence or key terms)
        topic = first_summary.split(".")[0].strip() if first_summary else f"Thema (Seiten {start_page}-{end_page})"
        if len(topic) > 100:
            topic = topic[:100] + "..."
        
        # Prepare state (include IDs for tracing)
        initial_state = {
            "messages": [],
            "page_analyses": page_analyses,
            "topic": topic,
            "start_page": start_page,
            "end_page": end_page,
            "course_material_id": course_material_id,
            "user_id": user_id
        }
        
        logger.info(f"🟡 Prepared initial_state: pages={len(page_analyses)}, topic={topic}, start={start_page}, end={end_page}")
        logger.debug(f"🟡 State keys: {list(initial_state.keys())}")
        logger.debug(f"🟡 First page_analysis keys: {list(page_analyses[0].keys()) if page_analyses else 'N/A'}")
        
        # Run agent
        logger.info(f"Invoking quiz generation graph for pages {start_page}-{end_page}")
        logger.debug(f"🟡 Initial state before invoke: page_analyses count={len(initial_state.get('page_analyses', []))}")
        result = self.graph.invoke(initial_state)
        logger.info(f"Graph invocation completed. Result keys: {list(result.keys())}")
        
        # Try to get quiz_data directly from state first (more reliable)
        if "quiz_data" in result:
            quiz_data_value = result["quiz_data"]
            logger.info(f"Found quiz_data in state, type: {type(quiz_data_value)}")
            
            if isinstance(quiz_data_value, QuizData):
                quiz_data = quiz_data_value
                # Validate again (safety check)
                self._validate_quiz(quiz_data)
                logger.info(f"Returning quiz_data from state: {len(quiz_data.questions)} questions")
                return quiz_data
            else:
                logger.warning(f"quiz_data in state is not QuizData instance: {type(quiz_data_value)}")
        
        # Fallback: Extract from messages (for compatibility)
        messages = result.get("messages", [])
        logger.info(f"Extracting from messages. Message count: {len(messages)}")
        
        if not messages:
            logger.error("No messages in result")
            raise ValueError("Agent hat keine Antwort generiert")
        
        last_message = messages[-1]
        logger.info(f"Last message type: {type(last_message)}, has content: {hasattr(last_message, 'content')}")
        
        if not hasattr(last_message, "content"):
            logger.error(f"Last message has no content attribute: {last_message}")
            raise ValueError("Ungültige Agent-Antwort")
        
        # Parse JSON from message content using robust Pydantic validation
        try:
            content = last_message.content
            logger.info(f"Message content length: {len(content) if content else 0} chars")
            logger.debug(f"Message content preview: {content[:200] if content else 'EMPTY'}")
            
            if not content or not content.strip():
                logger.error("Empty content in message")
                raise ValueError("Leere Antwort vom Agent")
            
            # Check if content is an error message (starts with "Fehler", "Error", or "Keine")
            content_stripped = content.strip()
            error_keywords = ["Fehler", "Error", "Keine", "keine", "failed", "Failed", "Leere"]
            if any(content_stripped.startswith(keyword) for keyword in error_keywords):
                logger.error(f"🔴 Agent returned error message instead of quiz data: {content_stripped[:200]}")
                raise ValueError(content_stripped)
            
            # Use robust parsing method that handles various formats
            quiz_data = self._parse_quiz_result(content)
            logger.info(f"Successfully parsed QuizData from message with {len(quiz_data.questions)} questions")
            
            # Validate again (safety check)
            self._validate_quiz(quiz_data)
            logger.info("Quiz validation passed")
            
            return quiz_data
        
        except ValueError as e:
            # Re-raise ValueError as-is (already formatted)
            raise
        except Exception as e:
            logger.error(f"Error parsing quiz data: {str(e)}", exc_info=True)
            raise ValueError(f"Fehler bei Quiz-Generierung: {str(e)}")
