"""
Quiz Generator Agent

Subagent that generates comprehension quizzes from lecture material.
Used by the Tutor Agent when a subtopic is completed.
"""

import json
import logging
from typing import Optional, List, Dict, Any
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
from app.exceptions.quiz_exceptions import QuizStateError, QuizValidationError

logger = logging.getLogger(__name__)


class QuizGeneratorState(MessagesState):
    """
    State for Quiz Generator Agent.
    
    Extends MessagesState with fields needed for quiz generation.
    Required fields must be provided when invoking the graph.
    """
    page_analyses: List[Dict[str, Any]]
    topic: str
    start_page: int
    end_page: int
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
        - page_analyses: List of page analysis dicts (required)
        - topic: Topic name (required)
        - start_page: Starting page number (required)
        - end_page: Ending page number (required)
        - course_material_id: Course material ID (optional, for tracing)
        - user_id: User ID (optional, for tracing)
        
        Raises:
            QuizStateError: If required state fields are missing or invalid
        """
        # Validate state before processing
        logger.info("🟡 generate_node called - starting quiz generation")
        logger.debug(f"🟡 State type: {type(state)}, State keys: {list(state.keys()) if isinstance(state, dict) else 'not a dict'}")
        
        # Validate required fields
        page_analyses = state.get("page_analyses")
        topic = state.get("topic")
        start_page = state.get("start_page")
        end_page = state.get("end_page")
        
        # Validate page_analyses
        if not page_analyses:
            state_info = {
                "has_page_analyses": "page_analyses" in state,
                "page_analyses_type": type(page_analyses).__name__ if page_analyses is not None else "None",
                "page_analyses_length": len(page_analyses) if isinstance(page_analyses, list) else "N/A",
                "state_keys": list(state.keys()) if isinstance(state, dict) else "N/A"
            }
            raise QuizStateError(
                "Keine Seitenanalysen verfügbar für Quiz-Generierung",
                state_info=state_info
            )
        
        # Validate topic
        if not topic or not topic.strip():
            raise QuizStateError(
                "Topic fehlt im State",
                state_info={"topic": topic, "state_keys": list(state.keys()) if isinstance(state, dict) else "N/A"}
            )
        
        # Validate page range
        if start_page is None or end_page is None:
            raise QuizStateError(
                "Seitenbereich fehlt im State",
                state_info={"start_page": start_page, "end_page": end_page}
            )
        
        if start_page > end_page:
            raise QuizStateError(
                f"Ungültiger Seitenbereich: start_page ({start_page}) > end_page ({end_page})",
                state_info={"start_page": start_page, "end_page": end_page}
            )
        
        course_material_id = state.get("course_material_id")
        user_id = state.get("user_id")
        
        logger.info(f"🟡 State validated: pages={len(page_analyses)}, topic={topic}, start={start_page}, end={end_page}")
        
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
            
            # Parse result - structured_llm should return QuizData directly
            quiz_data = self._parse_quiz_result(result)
            
            logger.info(f"Received QuizData with {len(quiz_data.questions)} questions")
            
            # Validate difficulty distribution
            self._validate_quiz(quiz_data)
            logger.info("Quiz validation passed")
            
            # Store result in state - use quiz_data directly, not JSON string
            logger.info(f"Quiz generated successfully: {len(quiz_data.questions)} questions")
            return {"quiz_data": quiz_data}
        
        except (QuizStateError, QuizValidationError) as e:
            # Re-raise our custom exceptions
            logger.error(f"Quiz generation failed: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            # Wrap unexpected errors
            logger.error(f"Unexpected error during quiz generation: {str(e)}", exc_info=True)
            from app.exceptions.quiz_exceptions import QuizGenerationError
            raise QuizGenerationError(
                f"Fehler bei Quiz-Generierung: {str(e)}",
                details={"error_type": type(e).__name__, "error_message": str(e)}
            ) from e
    
    def _parse_quiz_result(self, result: any) -> QuizData:
        """
        Parse and validate quiz result using Pydantic.
        
        Handles return types from structured_llm:
        - QuizData instance (direct return from structured_llm)
        - dict (needs conversion via Pydantic)
        
        Args:
            result: Result from structured_llm.invoke() - should be QuizData or dict
            
        Returns:
            Validated QuizData instance
            
        Raises:
            QuizDataError: If result cannot be parsed or validated
        """
        # Case 1: Already a QuizData instance (expected from structured_llm)
        if isinstance(result, QuizData):
            logger.debug("Result is already QuizData instance")
            return result
        
        # Case 2: Dict - use Pydantic model_validate
        if isinstance(result, dict):
            logger.debug("Result is dict, validating with Pydantic")
            try:
                return QuizData.model_validate(result)
            except Exception as e:
                logger.error(f"Failed to validate dict as QuizData: {str(e)}")
                from app.exceptions.quiz_exceptions import QuizDataError
                raise QuizDataError(
                    f"Ungültiges Quiz-Format: {str(e)}",
                    data_info={
                        "result_type": type(result).__name__,
                        "result_keys": list(result.keys()) if isinstance(result, dict) else "N/A",
                        "error": str(e)
                    }
                ) from e
        
        # Case 3: Unexpected type
        logger.error(f"Unexpected result type: {type(result)}, value: {result}")
        from app.exceptions.quiz_exceptions import QuizDataError
        raise QuizDataError(
            f"Unerwarteter Rückgabetyp vom LLM: {type(result)}",
            data_info={"result_type": type(result).__name__, "result_value": str(result)[:200]}
        )
    
    def _validate_quiz(self, quiz_data: QuizData) -> None:
        """
        Validate quiz meets requirements.
        
        Raises:
            QuizValidationError: If quiz doesn't meet requirements
        """
        questions = quiz_data.questions
        validation_errors = {}
        
        # Validate question count
        if len(questions) < 3:
            validation_errors["question_count"] = f"Quiz muss mindestens 3 Fragen haben, hat aber nur {len(questions)}"
        
        if len(questions) > 8:
            validation_errors["question_count"] = f"Quiz darf maximal 8 Fragen haben, hat aber {len(questions)}"
        
        # Count difficulties
        easy_count = sum(1 for q in questions if q.difficulty == "easy")
        medium_count = sum(1 for q in questions if q.difficulty == "medium")
        hard_count = sum(1 for q in questions if q.difficulty == "hard")
        
        # Validate distribution
        if easy_count < 1:
            validation_errors["difficulty_easy"] = "Quiz muss mindestens 1 leichte Frage haben"
        
        if medium_count < 1:
            validation_errors["difficulty_medium"] = "Quiz muss mindestens 1 mittlere Frage haben"
        
        if hard_count < 1:
            validation_errors["difficulty_hard"] = "Quiz muss mindestens 1 schwere Frage haben"
        
        # Validate each question
        question_errors = {}
        for i, question in enumerate(questions):
            question_id = question.id
            errors_for_question = []
            
            if len(question.options) != 4:
                errors_for_question.append(f"Frage {i+1} muss genau 4 Antwortmöglichkeiten haben (A, B, C, D)")
            
            if question.correct_answer not in question.options:
                errors_for_question.append(f"Frage {i+1}: correct_answer '{question.correct_answer}' ist nicht in options")
            
            if not question.explanation or not question.explanation.strip():
                errors_for_question.append(f"Frage {i+1}: Erklärung fehlt")
            
            # Only add to question_errors if there are actual errors
            if errors_for_question:
                question_errors[question_id] = errors_for_question
        
        # Add question errors to validation errors only if there are actual errors
        if question_errors:
            validation_errors["questions"] = question_errors
        
        # Raise exception if validation failed
        if validation_errors:
            raise QuizValidationError(
                "Quiz-Validierung fehlgeschlagen",
                validation_errors=validation_errors,
                details={
                    "question_count": len(questions),
                    "easy_count": easy_count,
                    "medium_count": medium_count,
                    "hard_count": hard_count
                }
            )
        
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
        
        # Run agent with Langfuse tracing for graph execution
        logger.info(f"Invoking quiz generation graph for pages {start_page}-{end_page}")
        logger.debug(f"🟡 Initial state before invoke: page_analyses count={len(initial_state.get('page_analyses', []))}")
        
        # Wrap graph invocation with Langfuse span for unique trace naming
        langfuse_client = get_langfuse_client()
        if langfuse_client and settings.LANGFUSE_ENABLED:
            try:
                graph_span_ctx = langfuse_client.start_as_current_observation(
                    as_type="span",
                    name="quiz-generator-agent/graph-execution",
                    input={
                        "start_page": start_page,
                        "end_page": end_page,
                        "topic": topic,
                        "course_material_id": course_material_id,
                        "user_id": user_id
                    }
                )
                graph_span = graph_span_ctx.__enter__()
                logger.info(f"🟡 Langfuse: Started graph execution span 'quiz-generator-agent/graph-execution'")
            except Exception as e:
                logger.warning(f"🔴 Langfuse: Failed to start graph execution span: {e}")
                graph_span_ctx = None
                graph_span = None
        else:
            graph_span_ctx = None
            graph_span = None
        
        try:
            result = self.graph.invoke(initial_state)
            logger.info(f"Graph invocation completed. Result keys: {list(result.keys())}")
            
            # Update span with success
            if graph_span:
                try:
                    graph_span.update(output={"status": "success", "result_keys": list(result.keys())})
                    logger.info("🟢 Langfuse: Graph execution span updated with success")
                except Exception as e:
                    logger.warning(f"🔴 Langfuse: Failed to update graph execution span: {e}")
        except Exception as e:
            # Update span with error
            if graph_span:
                try:
                    graph_span.update(output={"status": "error", "error": str(e)})
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
        
        # Extract quiz_data from state (should always be present after generate_node)
        if "quiz_data" not in result:
            from app.exceptions.quiz_exceptions import QuizStateError
            raise QuizStateError(
                "Quiz-Daten fehlen im State nach Graph-Ausführung",
                state_info={"result_keys": list(result.keys())}
            )
        
        quiz_data_value = result["quiz_data"]
        
        if not isinstance(quiz_data_value, QuizData):
            from app.exceptions.quiz_exceptions import QuizDataError
            raise QuizDataError(
                f"Quiz-Daten im State haben falschen Typ: {type(quiz_data_value)}",
                data_info={"expected_type": "QuizData", "actual_type": type(quiz_data_value).__name__}
            )
        
        quiz_data = quiz_data_value
        # Final validation (safety check)
        self._validate_quiz(quiz_data)
        logger.info(f"Returning quiz_data from state: {len(quiz_data.questions)} questions")
        return quiz_data
