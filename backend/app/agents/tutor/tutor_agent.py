from __future__ import annotations

"""Tutor agent with explicit planner/executor/verifier orchestration."""

import json
import logging
from typing import Any, Literal, Optional
from uuid import uuid4

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from pydantic import Field

from app.agents.base import BaseAgent, State
from app.agents.shared import (
    PhaseScopedToolRegistry,
    StateAwareToolNode,
    TutorExecutionPlan,
    TutorIntentDecision,
    TutorVerificationResult,
    build_tool_call,
    fix_incomplete_tool_calls,
)
from app.core.adapters import get_material, get_page_analysis
from app.core.config import settings
from app.services.observability import create_callback_handler, get_langfuse_client
from app.services.tutor_rollout import TutorGraphVersion, resolve_tutor_graph_default_version
from app.tools.course_material_tool import GetCourseMaterialSummaryTool
from app.tools.page_analysis_tool import GetPageAnalysisTool
from app.tools.page_image_tool import GetPageImageTool
from app.tools.quiz_tool import CreateQuizTool

logger = logging.getLogger(__name__)


class TutorState(State):
    current_page: Optional[int] = None
    material_id: Optional[str] = None
    user_id: Optional[str] = None
    course_material_summary: Optional[dict[str, Any]] = None

    turn_id: Optional[str] = None
    current_user_message: Optional[str] = None
    prepared_messages: list[dict[str, Any]] = Field(default_factory=list)
    intent: Optional[str] = None
    intent_confidence: float = 0.0
    required_capabilities: list[str] = Field(default_factory=list)
    context_bundle: dict[str, Any] = Field(default_factory=dict)
    execution_trace: list[dict[str, Any]] = Field(default_factory=list)
    draft_answer: Optional[str] = None
    verification_result: Optional[dict[str, Any]] = None
    execution_plan: Optional[dict[str, Any]] = None
    needs_verification: bool = False
    intent_reason: Optional[str] = None
    verification_attempts: int = 0
    quiz_completed: bool = False


class TutorAgent(BaseAgent):
    MAX_HISTORY_MESSAGES = 10

    def __init__(
        self,
        llm: BaseChatModel,
        name: str = "TutorAgent",
        system_prompt: Optional[str] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        graph_version: TutorGraphVersion | None = None,
        language: str = "de",
        personality_config: Optional[dict[str, str]] = None,
    ):
        self.language = language
        self.personality_config = personality_config or {}
        self.graph_version = graph_version or resolve_tutor_graph_default_version()
        self.langfuse_client = get_langfuse_client()

        self.page_analysis_tool = GetPageAnalysisTool()
        self.course_material_tool = GetCourseMaterialSummaryTool()
        self.quiz_tool = CreateQuizTool()
        self.page_image_tool = GetPageImageTool()
        self.langchain_tools = [
            self.page_analysis_tool.to_langchain_tool(),
            self.course_material_tool.to_langchain_tool(),
            self.quiz_tool.to_langchain_tool(),
            self.page_image_tool.to_langchain_tool(),
        ]
        self.tools_by_name = {tool.name: tool for tool in self.langchain_tools}
        self.phase_tool_registry = PhaseScopedToolRegistry(
            tools_by_name=self.tools_by_name,
            phase_map={
                "tutoring": [
                    "get_page_analysis",
                    "get_course_material_summary",
                    "get_page_image",
                ],
                "quiz": ["create_quiz"],
                "clarification": [],
            },
        )

        self.base_llm = llm
        self.legacy_llm = self._bind_tools(llm, self.langchain_tools)
        self.response_llm = self._with_config(llm, {"run_name": "tutor-agent/respond"})
        self.intent_llm = self._create_structured_llm(
            llm,
            TutorIntentDecision,
            "tutor-agent/understand-request",
        )
        self.verifier_llm = self._create_structured_llm(
            llm,
            TutorVerificationResult,
            "tutor-agent/verify-response",
        )

        self.tool_node = StateAwareToolNode(self.langchain_tools)
        self.tutoring_tool_node = StateAwareToolNode(
            self.phase_tool_registry.get_tools_for_phase("tutoring")
        )
        self.quiz_tool_node = StateAwareToolNode(
            self.phase_tool_registry.get_tools_for_phase("quiz")
        )

        if system_prompt is None:
            system_prompt = self._build_system_prompt(language, personality_config)

        super().__init__(
            llm=llm if self.graph_version == "v2" else self.legacy_llm,
            name=name,
            system_prompt=system_prompt,
            checkpointer=checkpointer,
        )

    @staticmethod
    def _bind_tools(llm: Any, tools: list[Any]) -> Any:
        if hasattr(llm, "bind_tools"):
            return llm.bind_tools(tools)
        return llm

    @staticmethod
    def _with_config(runnable: Any, config: dict[str, Any]) -> Any:
        if hasattr(runnable, "with_config"):
            return runnable.with_config(config)
        return runnable

    def _create_structured_llm(self, llm: Any, schema: type, run_name: str) -> Any | None:
        if not hasattr(llm, "with_structured_output"):
            return None
        try:
            runnable = llm.with_structured_output(schema)
            return self._with_config(runnable, {"run_name": run_name})
        except Exception as exc:
            logger.warning("Structured output unavailable for %s: %s", schema.__name__, exc)
            return None

    def _build_graph(self) -> None:
        if self.graph_version == "v2":
            self._build_graph_v2()
            return

        workflow = StateGraph(state_schema=TutorState)
        workflow.add_node("agent", self.call_model)
        workflow.add_node("tools", self.tool_node)
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges(
            "agent",
            self.should_continue,
            {"continue": "tools", "end": END},
        )
        workflow.add_edge("tools", "agent")
        self.compile_graph(workflow)

    def _build_graph_v2(self) -> None:
        workflow = StateGraph(state_schema=TutorState)
        workflow.add_node("prepare_turn", self.prepare_turn)
        workflow.add_node("hydrate_context", self.hydrate_context)
        workflow.add_node("understand_request", self.understand_request)
        workflow.add_node("tutoring_subgraph", self._build_tutoring_subgraph())
        workflow.add_node("quiz_subgraph", self._build_quiz_subgraph())
        workflow.add_node("clarification_subgraph", self._build_clarification_subgraph())
        workflow.add_node("verify_response", self.verify_response)
        workflow.add_node("finalize_turn", self.finalize_turn)

        workflow.add_edge(START, "prepare_turn")
        workflow.add_edge("prepare_turn", "hydrate_context")
        workflow.add_edge("hydrate_context", "understand_request")
        workflow.add_conditional_edges(
            "understand_request",
            self.route_request,
            {
                "tutoring_subgraph": "tutoring_subgraph",
                "quiz_subgraph": "quiz_subgraph",
                "clarification_subgraph": "clarification_subgraph",
            },
        )
        workflow.add_edge("tutoring_subgraph", "verify_response")
        workflow.add_edge("quiz_subgraph", "verify_response")
        workflow.add_edge("clarification_subgraph", "verify_response")
        workflow.add_edge("verify_response", "finalize_turn")
        workflow.add_edge("finalize_turn", END)

        self.compile_graph(workflow)

    def _build_tutoring_subgraph(self):
        workflow = StateGraph(state_schema=TutorState)
        workflow.add_node("plan_execution", self.plan_tutoring_execution)
        workflow.add_node("execute_tutoring_tools", self.tutoring_tool_node)
        workflow.add_node("compose_draft", self.compose_tutoring_draft)
        workflow.add_edge(START, "plan_execution")
        workflow.add_conditional_edges(
            "plan_execution",
            self.route_tutoring_execution,
            {"execute_tools": "execute_tutoring_tools", "compose": "compose_draft"},
        )
        workflow.add_edge("execute_tutoring_tools", "compose_draft")
        workflow.add_edge("compose_draft", END)
        return workflow.compile()

    def _build_quiz_subgraph(self):
        workflow = StateGraph(state_schema=TutorState)
        workflow.add_node("plan_quiz", self.plan_quiz_execution)
        workflow.add_node("execute_quiz", self.quiz_tool_node)
        workflow.add_node("handle_quiz_result", self.handle_quiz_result)
        workflow.add_edge(START, "plan_quiz")
        workflow.add_conditional_edges(
            "plan_quiz",
            self.route_quiz_execution,
            {"execute_tools": "execute_quiz", "handle_result": "handle_quiz_result"},
        )
        workflow.add_edge("execute_quiz", "handle_quiz_result")
        workflow.add_edge("handle_quiz_result", END)
        return workflow.compile()

    def _build_clarification_subgraph(self):
        workflow = StateGraph(state_schema=TutorState)
        workflow.add_node("compose_clarification", self.compose_clarification)
        workflow.add_edge(START, "compose_clarification")
        workflow.add_edge("compose_clarification", END)
        return workflow.compile()

    def _build_system_prompt(
        self,
        language: str = "de",
        personality_config: Optional[dict[str, str]] = None,
    ) -> str:
        config = personality_config or {}
        formality = config.get("formality", "balanced")
        humor = config.get("humor", "light")
        encouragement = config.get("encouragement", "moderate")

        if self.langfuse_client:
            try:
                prompt_name = f"tutor-agent/system-prompt-{language}"
                langfuse_prompt = self.langfuse_client.get_prompt(
                    prompt_name,
                    label="production",
                    type="chat",
                )
                formality_text, humor_text, encouragement_text = self._get_personality_texts(
                    language,
                    formality,
                    humor,
                    encouragement,
                )
                compiled_prompt = langfuse_prompt.compile(
                    formality_text=formality_text,
                    humor_text=humor_text,
                    encouragement_text=encouragement_text,
                )
                if compiled_prompt and isinstance(compiled_prompt, list):
                    system_message = compiled_prompt[0]
                    if isinstance(system_message, dict) and system_message.get("role") == "system":
                        return str(system_message.get("content", ""))
                    if hasattr(system_message, "content"):
                        return str(system_message.content)
            except Exception as exc:
                logger.warning("Failed to load Langfuse tutor prompt: %s", exc)

        return self._build_fallback_system_prompt(language, formality, humor, encouragement)

    def _build_fallback_system_prompt(
        self,
        language: str,
        formality: str,
        humor: str,
        encouragement: str,
    ) -> str:
        formality_text, humor_text, encouragement_text = self._get_personality_texts(
            language,
            formality,
            humor,
            encouragement,
        )
        if language == "de":
            return (
                "Du bist ein praeziser, freundlicher Tutor fuer Vorlesungsmaterial. "
                "Antworte nur mit Aussagen, die durch den aktuellen Kontext, die Seite oder Tool-Ausgaben gestuetzt sind. "
                "Wenn Kontext fehlt oder unsicher ist, stelle eine kurze Rueckfrage statt zu raten. "
                "Erklaere klar, schrittweise und lernorientiert. "
                f"{formality_text} {humor_text} {encouragement_text}"
            )
        return (
            "You are a precise and friendly tutor for lecture materials. "
            "Only make claims that are grounded in the current context, page evidence, or tool output. "
            "If context is missing or uncertain, ask a short clarifying question instead of guessing. "
            "Explain clearly and step by step. "
            f"{formality_text} {humor_text} {encouragement_text}"
        )

    def _get_personality_texts(
        self,
        language: str,
        formality: str,
        humor: str,
        encouragement: str,
    ) -> tuple[str, str, str]:
        if language == "de":
            formality_text = {
                "formal": "Du verwendest eine formelle, akademische Sprache mit korrekten Fachbegriffen.",
                "informal": "Du verwendest eine lockere, freundliche Sprache wie im Gespraech mit einem Kommilitonen.",
                "balanced": "Du verwendest eine ausgewogene Mischung aus formeller und freundlicher Sprache.",
            }.get(formality, "Du verwendest eine ausgewogene Mischung aus formeller und freundlicher Sprache.")
            humor_text = {
                "none": "Du verzichtest auf Humor und bleibst sachlich.",
                "light": "Du verwendest gelegentlich leichten, passenden Humor.",
                "moderate": "Du verwendest passenden Humor und Analogien, wenn sie das Verstaendnis verbessern.",
            }.get(humor, "Du verwendest gelegentlich leichten, passenden Humor.")
            encouragement_text = {
                "reserved": "Du lobst sparsam, aber anerkennend.",
                "moderate": "Du ermutigst regelmaessig und bestaetigst Fortschritte.",
                "enthusiastic": "Du bist sehr ermutigend und motivierend.",
            }.get(encouragement, "Du ermutigst regelmaessig und bestaetigst Fortschritte.")
            return formality_text, humor_text, encouragement_text

        formality_text = {
            "formal": "You use formal, academic language with correct technical terms.",
            "informal": "You use relaxed, friendly language as if talking to a fellow student.",
            "balanced": "You use a balanced mix of formal and friendly language.",
        }.get(formality, "You use a balanced mix of formal and friendly language.")
        humor_text = {
            "none": "You avoid humor and stay factual.",
            "light": "You occasionally use light, appropriate humor.",
            "moderate": "You use appropriate humor and analogies when they improve understanding.",
        }.get(humor, "You occasionally use light, appropriate humor.")
        encouragement_text = {
            "reserved": "You are reserved with praise, but acknowledge progress.",
            "moderate": "You regularly encourage the student and acknowledge progress.",
            "enthusiastic": "You are very encouraging and motivating.",
        }.get(encouragement, "You regularly encourage the student and acknowledge progress.")
        return formality_text, humor_text, encouragement_text

    def prepare_turn(
        self,
        state: TutorState,
        config: Optional[RunnableConfig] = None,
    ) -> dict[str, Any]:
        messages = fix_incomplete_tool_calls(list(state.get("messages") or []))
        current_user_message = self._extract_current_user_message(messages)
        prepared_messages = self._prepare_messages_for_phase(messages)

        normalized_user_id = self._normalize_string(
            state.get("user_id") or self._get_configurable(config).get("user_id")
        )
        normalized_material_id = self._normalize_string(state.get("material_id"))
        normalized_page = self._normalize_page_number(state.get("current_page"))
        normalized_summary = self._normalize_summary(state.get("course_material_summary"))

        return {
            "turn_id": str(uuid4()),
            "user_id": normalized_user_id,
            "material_id": normalized_material_id,
            "current_page": normalized_page,
            "course_material_summary": normalized_summary,
            "current_user_message": current_user_message,
            "prepared_messages": self._serialize_messages(prepared_messages),
            "intent": None,
            "intent_confidence": 0.0,
            "required_capabilities": [],
            "context_bundle": {},
            "draft_answer": None,
            "verification_result": None,
            "execution_plan": None,
            "needs_verification": False,
            "intent_reason": None,
            "verification_attempts": 0,
            "quiz_completed": False,
            "execution_trace": self._append_trace(
                state,
                "prepare_turn",
                {
                    "message_count": len(messages),
                    "prepared_message_count": len(prepared_messages),
                    "material_id": normalized_material_id,
                    "current_page": normalized_page,
                },
            ),
        }

    def hydrate_context(
        self,
        state: TutorState,
        config: Optional[RunnableConfig] = None,
    ) -> dict[str, Any]:
        material_id = self._normalize_string(state.get("material_id"))
        user_id = self._normalize_string(state.get("user_id"))
        current_page = self._normalize_page_number(state.get("current_page"))
        summary = self._normalize_summary(state.get("course_material_summary"))

        missing_context: list[str] = []
        errors: list[str] = []
        page_analysis: dict[str, Any] | None = None

        if not material_id:
            missing_context.append("material_id")
        if not user_id:
            missing_context.append("user_id")
        if current_page is None:
            missing_context.append("current_page")

        if not missing_context:
            try:
                page_analysis_result = get_page_analysis().get(
                    course_material_id=material_id,
                    page_number=current_page,
                    user_id=user_id,
                )
                if isinstance(page_analysis_result, dict):
                    page_analysis = page_analysis_result
                    if page_analysis_result.get("error"):
                        errors.append(str(page_analysis_result["error"]))
                else:
                    errors.append("Page analysis returned an unexpected payload.")
            except Exception as exc:
                errors.append(f"Failed to load page analysis: {exc}")

            if summary is None:
                try:
                    summary_result = get_material().get_summary(
                        course_material_id=material_id,
                        user_id=user_id,
                    )
                    summary = self._normalize_summary(summary_result)
                except Exception as exc:
                    errors.append(f"Failed to load material summary: {exc}")

        context_bundle = {
            "runtime_context": {
                "material_id": material_id,
                "current_page": current_page,
                "user_id": user_id,
            },
            "page_analysis": page_analysis,
            "material_summary": summary,
            "missing_context": missing_context,
            "errors": errors,
        }

        return {
            "context_bundle": context_bundle,
            "course_material_summary": summary,
            "execution_trace": self._append_trace(
                state,
                "hydrate_context",
                {
                    "missing_context": missing_context,
                    "errors": errors,
                    "page_analysis_loaded": bool(page_analysis),
                    "material_summary_loaded": bool(summary),
                },
            ),
        }

    def understand_request(
        self,
        state: TutorState,
        config: Optional[RunnableConfig] = None,
    ) -> dict[str, Any]:
        user_message = (state.get("current_user_message") or "").strip()
        context_bundle = dict(state.get("context_bundle") or {})
        missing_context = list(context_bundle.get("missing_context") or [])
        context_errors = list(context_bundle.get("errors") or [])

        if not user_message:
            decision = TutorIntentDecision(
                intent="clarify_missing_context",
                intent_confidence=1.0,
                required_capabilities=["clarification"],
                needs_verification=False,
                reason="No user message was available for this turn.",
            )
        elif missing_context:
            decision = TutorIntentDecision(
                intent="clarify_missing_context",
                intent_confidence=1.0,
                required_capabilities=["clarification"],
                needs_verification=False,
                reason=f"Missing runtime context: {', '.join(missing_context)}.",
            )
        elif self._is_quiz_request(user_message):
            decision = TutorIntentDecision(
                intent="create_quiz",
                intent_confidence=0.98,
                required_capabilities=["quiz"],
                needs_verification=False,
                reason="The user explicitly asked for a quiz.",
            )
        elif context_errors and not context_bundle.get("page_analysis"):
            decision = TutorIntentDecision(
                intent="clarify_missing_context",
                intent_confidence=0.9,
                required_capabilities=["clarification"],
                needs_verification=False,
                reason="Core tutoring context could not be loaded safely.",
            )
        else:
            decision = self._plan_intent_with_llm(state, config) or self._fallback_intent_decision(state)
            if decision.intent_confidence < 0.45 and decision.intent != "create_quiz":
                decision = TutorIntentDecision(
                    intent="clarify_missing_context",
                    intent_confidence=decision.intent_confidence,
                    required_capabilities=["clarification"],
                    needs_verification=False,
                    reason="Intent confidence was too low for a grounded answer.",
                )

        required_capabilities = list(decision.required_capabilities)
        if decision.intent in {"explain_current_page", "answer_followup", "needs_visual"}:
            required_capabilities.append("page_analysis")
        if decision.intent == "needs_visual" or self._needs_visual_support(user_message):
            required_capabilities.append("page_image")
        if self._needs_overview_support(user_message):
            required_capabilities.append("material_summary")
        required_capabilities = list(dict.fromkeys(required_capabilities))

        needs_verification = decision.needs_verification or any(
            capability in {"page_analysis", "material_summary", "page_image"}
            for capability in required_capabilities
        )

        return {
            "intent": decision.intent,
            "intent_confidence": decision.intent_confidence,
            "required_capabilities": required_capabilities,
            "needs_verification": needs_verification,
            "intent_reason": decision.reason,
            "execution_trace": self._append_trace(
                state,
                "understand_request",
                {
                    "intent": decision.intent,
                    "intent_confidence": decision.intent_confidence,
                    "required_capabilities": required_capabilities,
                    "needs_verification": needs_verification,
                },
            ),
        }

    def route_request(
        self,
        state: TutorState,
    ) -> Literal["tutoring_subgraph", "quiz_subgraph", "clarification_subgraph"]:
        intent = state.get("intent")
        if intent == "create_quiz":
            return "quiz_subgraph"
        if intent == "clarify_missing_context":
            return "clarification_subgraph"
        return "tutoring_subgraph"

    def plan_tutoring_execution(self, state: TutorState) -> dict[str, Any]:
        capabilities = set(state.get("required_capabilities") or [])
        tool_names: list[str] = []

        if state.get("intent") in {"explain_current_page", "answer_followup", "needs_visual"}:
            tool_names.append("get_page_analysis")
        if "page_analysis" in capabilities and "get_page_analysis" not in tool_names:
            tool_names.append("get_page_analysis")
        if "page_image" in capabilities:
            tool_names.append("get_page_image")
        if "material_summary" in capabilities:
            tool_names.append("get_course_material_summary")

        tool_names = list(dict.fromkeys(tool_names))
        plan = TutorExecutionPlan(
            phase="tutoring",
            answer_strategy="tool_augmented" if tool_names else "direct",
            tool_names=tool_names,
            answer_focus=self._build_answer_focus(state),
            answer_constraints=(
                "Use only grounded evidence from the current page, material summary, and tool output. "
                "State uncertainty explicitly if evidence is incomplete."
            ),
        )

        updates: dict[str, Any] = {
            "execution_plan": plan.model_dump(),
            "execution_trace": self._append_trace(
                state,
                "plan_tutoring_execution",
                {"tool_names": tool_names, "answer_focus": plan.answer_focus},
            ),
        }
        if tool_names:
            updates["messages"] = [
                AIMessage(
                    content="",
                    tool_calls=[
                        build_tool_call(
                            name=tool_name,
                            args=self._build_tool_args(tool_name, state),
                            prefix="tutor",
                        )
                        for tool_name in tool_names
                    ],
                )
            ]
        return updates

    def route_tutoring_execution(
        self,
        state: TutorState,
    ) -> Literal["execute_tools", "compose"]:
        last_message = (state.get("messages") or [])[-1] if state.get("messages") else None
        if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
            return "execute_tools"
        return "compose"

    def compose_tutoring_draft(
        self,
        state: TutorState,
        config: Optional[RunnableConfig] = None,
    ) -> dict[str, Any]:
        prepared_messages = self._prepare_messages_for_phase(state.get("messages") or [])
        plan = self._get_execution_plan(state)
        instructions = [
            "Answer the student's latest question directly and clearly.",
            "Use only grounded evidence from the provided context and tool outputs.",
            "Do not invent slide content, definitions, or relationships that are not supported.",
        ]
        if plan and plan.answer_focus:
            instructions.append(f"Focus: {plan.answer_focus}")
        if plan and plan.answer_constraints:
            instructions.append(f"Constraints: {plan.answer_constraints}")

        llm_messages = self._build_phase_messages(
            state,
            prepared_messages,
            phase="tutoring",
            instructions="\n".join(instructions),
        )

        try:
            response = self.response_llm.invoke(
                llm_messages,
                config=self._build_llm_config(state, "tutor-agent/compose-draft", config),
            )
            draft_answer = self._extract_response_text(response).strip()
        except Exception as exc:
            logger.error("Tutor compose_draft failed: %s", exc, exc_info=True)
            draft_answer = ""

        if not draft_answer:
            draft_answer = self._build_cautious_fallback_message(state)

        return {
            "draft_answer": draft_answer,
            "prepared_messages": self._serialize_messages(prepared_messages),
            "execution_trace": self._append_trace(
                state,
                "compose_tutoring_draft",
                {"draft_length": len(draft_answer)},
            ),
        }

    def plan_quiz_execution(self, state: TutorState) -> dict[str, Any]:
        current_page = state.get("current_page") or 1
        if not state.get("material_id") or not state.get("user_id"):
            return {
                "draft_answer": self._build_clarification_message(state),
                "execution_trace": self._append_trace(
                    state,
                    "plan_quiz_execution",
                    {"tool_names": [], "reason": "missing_context"},
                ),
            }

        plan = TutorExecutionPlan(
            phase="quiz",
            answer_strategy="quiz",
            tool_names=["create_quiz"],
            answer_focus="Generate a quiz for the currently grounded page or topic.",
            answer_constraints="Do not send an additional tutor explanation in the same turn after quiz creation succeeds.",
        )
        return {
            "execution_plan": plan.model_dump(),
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        build_tool_call(
                            "create_quiz",
                            {"start_page": current_page, "end_page": current_page},
                            prefix="quiz",
                        )
                    ],
                )
            ],
            "execution_trace": self._append_trace(
                state,
                "plan_quiz_execution",
                {"tool_names": ["create_quiz"], "current_page": current_page},
            ),
        }

    def route_quiz_execution(
        self,
        state: TutorState,
    ) -> Literal["execute_tools", "handle_result"]:
        last_message = (state.get("messages") or [])[-1] if state.get("messages") else None
        if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
            return "execute_tools"
        return "handle_result"

    def handle_quiz_result(self, state: TutorState) -> dict[str, Any]:
        tool_outputs = self._extract_latest_tool_outputs(state.get("messages") or [])
        quiz_output = tool_outputs.get("create_quiz")
        parsed_output = quiz_output.get("parsed") if quiz_output else None
        quiz_id = parsed_output.get("quiz_id") if isinstance(parsed_output, dict) else None

        if quiz_id:
            return {
                "quiz_completed": True,
                "needs_verification": False,
                "execution_trace": self._append_trace(
                    state,
                    "handle_quiz_result",
                    {"quiz_completed": True, "quiz_id": quiz_id},
                ),
            }

        error_message = ""
        if isinstance(parsed_output, dict):
            error_message = str(parsed_output.get("error") or parsed_output.get("message") or "")
        elif quiz_output:
            error_message = self._message_content_to_text(quiz_output.get("content"))

        if self.language == "de":
            draft_answer = (
                "Ich konnte gerade kein Quiz generieren. "
                "Bitte versuche es gleich noch einmal oder gib mir mehr Kontext zur gewuenschten Stelle."
            )
        else:
            draft_answer = (
                "I could not generate a quiz just now. "
                "Please try again in a moment or give me a bit more context."
            )
        if error_message:
            draft_answer = f"{draft_answer} ({error_message})"

        return {
            "quiz_completed": False,
            "draft_answer": draft_answer,
            "needs_verification": False,
            "execution_trace": self._append_trace(
                state,
                "handle_quiz_result",
                {"quiz_completed": False, "error_message": error_message},
            ),
        }

    def compose_clarification(self, state: TutorState) -> dict[str, Any]:
        clarification = self._build_clarification_message(state)
        return {
            "draft_answer": clarification,
            "execution_trace": self._append_trace(
                state,
                "compose_clarification",
                {"message_length": len(clarification)},
            ),
        }

    def verify_response(
        self,
        state: TutorState,
        config: Optional[RunnableConfig] = None,
    ) -> dict[str, Any]:
        draft_answer = (state.get("draft_answer") or "").strip()
        if not draft_answer:
            verification = TutorVerificationResult(
                status="accept",
                reason="No assistant draft was produced for this turn.",
            )
            return {
                "verification_result": verification.model_dump(),
                "execution_trace": self._append_trace(
                    state,
                    "verify_response",
                    {"status": verification.status, "reason": verification.reason},
                ),
            }

        if not state.get("needs_verification"):
            verification = TutorVerificationResult(
                status="accept",
                reason="Verification skipped for a low-risk response.",
            )
            return {
                "verification_result": verification.model_dump(),
                "execution_trace": self._append_trace(
                    state,
                    "verify_response",
                    {"status": verification.status, "reason": verification.reason},
                ),
            }

        first_result = self._run_verifier(state, draft_answer, config)
        if first_result is None:
            verification = TutorVerificationResult(
                status="accept",
                reason="Verifier unavailable; keeping grounded draft as-is.",
            )
            return {
                "verification_result": verification.model_dump(),
                "execution_trace": self._append_trace(
                    state,
                    "verify_response",
                    {"status": verification.status, "reason": verification.reason},
                ),
            }

        if first_result.status == "accept":
            return {
                "verification_result": first_result.model_dump(),
                "execution_trace": self._append_trace(
                    state,
                    "verify_response",
                    {"status": first_result.status, "issues": first_result.issues},
                ),
            }

        if first_result.status == "clarify":
            clarified_answer = self._build_clarification_message(state, first_result.issues)
            return {
                "draft_answer": clarified_answer,
                "verification_result": first_result.model_dump(),
                "execution_trace": self._append_trace(
                    state,
                    "verify_response",
                    {"status": first_result.status, "issues": first_result.issues},
                ),
            }

        repaired_answer = (first_result.revised_answer or "").strip()
        if not repaired_answer:
            repaired_answer = self._repair_draft_answer(state, draft_answer, first_result.issues, config)

        if not repaired_answer:
            fallback_answer = self._build_cautious_fallback_message(state)
            fallback_result = TutorVerificationResult(
                status="clarify",
                issues=first_result.issues,
                reason="Repair pass did not produce a stable grounded answer.",
            )
            return {
                "draft_answer": fallback_answer,
                "verification_result": fallback_result.model_dump(),
                "verification_attempts": 1,
                "execution_trace": self._append_trace(
                    state,
                    "verify_response",
                    {"status": fallback_result.status, "issues": fallback_result.issues},
                ),
            }

        second_result = self._run_verifier(state, repaired_answer, config)
        if second_result and second_result.status == "accept":
            return {
                "draft_answer": repaired_answer,
                "verification_result": second_result.model_dump(),
                "verification_attempts": 1,
                "execution_trace": self._append_trace(
                    state,
                    "verify_response",
                    {"status": second_result.status, "issues": second_result.issues},
                ),
            }

        if second_result and second_result.status == "clarify":
            clarified_answer = self._build_clarification_message(state, second_result.issues)
            return {
                "draft_answer": clarified_answer,
                "verification_result": second_result.model_dump(),
                "verification_attempts": 1,
                "execution_trace": self._append_trace(
                    state,
                    "verify_response",
                    {"status": second_result.status, "issues": second_result.issues},
                ),
            }

        fallback_answer = self._build_cautious_fallback_message(state)
        fallback_result = second_result or TutorVerificationResult(
            status="clarify",
            issues=first_result.issues,
            reason="Repair pass still failed verification.",
        )
        return {
            "draft_answer": fallback_answer,
            "verification_result": fallback_result.model_dump(),
            "verification_attempts": 1,
            "execution_trace": self._append_trace(
                state,
                "verify_response",
                {"status": fallback_result.status, "issues": fallback_result.issues},
            ),
        }

    def finalize_turn(self, state: TutorState) -> dict[str, Any]:
        if state.get("quiz_completed") and not state.get("draft_answer"):
            return {
                "execution_trace": self._append_trace(
                    state,
                    "finalize_turn",
                    {"emitted_message": False, "quiz_completed": True},
                )
            }

        final_answer = (state.get("draft_answer") or "").strip()
        if not final_answer and not state.get("quiz_completed"):
            final_answer = self._build_cautious_fallback_message(state)

        updates: dict[str, Any] = {
            "execution_trace": self._append_trace(
                state,
                "finalize_turn",
                {"emitted_message": bool(final_answer), "quiz_completed": bool(state.get("quiz_completed"))},
            )
        }
        if final_answer:
            updates["messages"] = [AIMessage(content=final_answer)]
        return updates

    def call_model(
        self,
        state: TutorState,
        config: Optional[RunnableConfig] = None,
    ) -> dict[str, Any]:
        messages = self._prepare_messages_for_phase(state.get("messages") or [])
        messages_for_llm = self.add_system_message(messages)
        runtime_context = self._build_runtime_context_text(state)
        if messages_for_llm and isinstance(messages_for_llm[0], SystemMessage):
            messages_for_llm[0] = SystemMessage(
                content=f"{messages_for_llm[0].content}\n\nRUNTIME CONTEXT:\n{runtime_context}"
            )
        messages_for_llm = self._enhance_tool_messages(messages_for_llm)

        response = self.legacy_llm.invoke(
            messages_for_llm,
            config=self._build_llm_config(state, "tutor-agent/legacy-call", config),
        )
        if isinstance(response, AIMessage) and getattr(response, "tool_calls", None) and response.content:
            if any(tool_call.get("name") == "create_quiz" for tool_call in response.tool_calls):
                response = AIMessage(content=self._extract_response_text(response)[:150], tool_calls=response.tool_calls)
        return {"messages": [response]}

    def should_continue(self, state: TutorState) -> Literal["continue", "end"]:
        messages = state.get("messages") or []
        if not messages:
            return "end"

        last_message = messages[-1]
        if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
            return "continue"

        if isinstance(last_message, ToolMessage):
            for previous_message in reversed(messages[:-1]):
                if isinstance(previous_message, AIMessage) and getattr(previous_message, "tool_calls", None):
                    tool_call_id = getattr(last_message, "tool_call_id", None)
                    for tool_call in previous_message.tool_calls:
                        if tool_call.get("id") == tool_call_id and tool_call.get("name") == "create_quiz":
                            return "end"
                    break

        return "end"

    def _plan_intent_with_llm(
        self,
        state: TutorState,
        config: Optional[RunnableConfig] = None,
    ) -> TutorIntentDecision | None:
        if self.intent_llm is None:
            return None

        context_bundle = dict(state.get("context_bundle") or {})
        prompt = (
            "Classify the user's tutoring request into one of these intents: "
            "explain_current_page, answer_followup, needs_visual, create_quiz, clarify_missing_context. "
            "Prefer clarify_missing_context if the request cannot be answered safely from the provided context."
        )
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(
                content=(
                    f"Runtime context:\n{self._build_runtime_context_text(state)}\n\n"
                    f"Current page analysis:\n{self._json_preview(context_bundle.get('page_analysis'))}\n\n"
                    f"Material summary:\n{self._json_preview(context_bundle.get('material_summary'))}\n\n"
                    f"User request:\n{state.get('current_user_message') or ''}"
                )
            ),
        ]
        try:
            raw_result = self.intent_llm.invoke(
                messages,
                config=self._build_llm_config(state, "tutor-agent/understand-request", config),
            )
            if isinstance(raw_result, TutorIntentDecision):
                return raw_result
            return TutorIntentDecision.model_validate(raw_result)
        except Exception as exc:
            logger.warning("Tutor intent planner failed, falling back to heuristics: %s", exc)
            return None

    def _fallback_intent_decision(self, state: TutorState) -> TutorIntentDecision:
        user_message = (state.get("current_user_message") or "").strip()
        if self._needs_visual_support(user_message):
            return TutorIntentDecision(
                intent="needs_visual",
                intent_confidence=0.72,
                required_capabilities=["page_analysis", "page_image"],
                needs_verification=True,
                reason="The user references a visual or layout-based question.",
            )
        if self._looks_like_followup(user_message, state):
            return TutorIntentDecision(
                intent="answer_followup",
                intent_confidence=0.66,
                required_capabilities=["page_analysis"],
                needs_verification=True,
                reason="The request looks like a follow-up grounded in the active slide context.",
            )
        return TutorIntentDecision(
            intent="explain_current_page",
            intent_confidence=0.61,
            required_capabilities=["page_analysis"],
            needs_verification=True,
            reason="Defaulting to a grounded explanation of the current page.",
        )

    def _run_verifier(
        self,
        state: TutorState,
        draft_answer: str,
        config: Optional[RunnableConfig] = None,
    ) -> TutorVerificationResult | None:
        if self.verifier_llm is None:
            return None

        verifier_prompt = (
            "You are a strict verifier for a tutoring assistant. "
            "Return accept if the draft is fully supported by the provided evidence. "
            "Return revise if it can be fixed in one grounded rewrite. "
            "Return clarify if the draft depends on missing or uncertain evidence."
        )
        messages = [
            SystemMessage(content=verifier_prompt),
            HumanMessage(
                content=(
                    f"Runtime context:\n{self._build_runtime_context_text(state)}\n\n"
                    f"Evidence:\n{self._build_evidence_text(state)}\n\n"
                    f"User request:\n{state.get('current_user_message') or ''}\n\n"
                    f"Draft answer:\n{draft_answer}"
                )
            ),
        ]
        try:
            raw_result = self.verifier_llm.invoke(
                messages,
                config=self._build_llm_config(state, "tutor-agent/verify-response", config),
            )
            if isinstance(raw_result, TutorVerificationResult):
                return raw_result
            return TutorVerificationResult.model_validate(raw_result)
        except Exception as exc:
            logger.warning("Tutor verifier failed: %s", exc)
            return None

    def _repair_draft_answer(
        self,
        state: TutorState,
        draft_answer: str,
        issues: list[str],
        config: Optional[RunnableConfig] = None,
    ) -> str:
        prepared_messages = self._prepare_messages_for_phase(state.get("messages") or [])
        messages = self._build_phase_messages(
            state,
            prepared_messages,
            phase="repair",
            instructions=(
                "Revise the draft so that every claim is supported by the evidence. "
                "Remove unsupported claims instead of inventing replacements."
            ),
        )
        messages.append(
            HumanMessage(
                content=(
                    f"Original draft:\n{draft_answer}\n\n"
                    f"Verifier issues:\n- {'\n- '.join(issues or ['Insufficient grounding.'])}"
                )
            )
        )
        try:
            response = self.response_llm.invoke(
                messages,
                config=self._build_llm_config(state, "tutor-agent/repair-draft", config),
            )
            return self._extract_response_text(response).strip()
        except Exception as exc:
            logger.warning("Tutor repair pass failed: %s", exc)
            return ""

    def _build_phase_messages(
        self,
        state: TutorState,
        prepared_messages: list[BaseMessage],
        *,
        phase: str,
        instructions: str,
    ) -> list[BaseMessage]:
        system_sections = [self.system_prompt, f"Current phase: {phase}.", instructions]
        runtime_context = self._build_runtime_context_text(state)
        if runtime_context:
            system_sections.append(f"Runtime context:\n{runtime_context}")
        evidence = self._build_evidence_text(state)
        if evidence:
            system_sections.append(f"Grounding evidence:\n{evidence}")
        return [
            SystemMessage(content="\n\n".join(section for section in system_sections if section))
        ] + self._enhance_tool_messages(prepared_messages)

    def _build_runtime_context_text(self, state: TutorState) -> str:
        context_bundle = dict(state.get("context_bundle") or {})
        runtime_context = dict(context_bundle.get("runtime_context") or {})
        parts = []
        material_id = runtime_context.get("material_id") or state.get("material_id")
        current_page = runtime_context.get("current_page") or state.get("current_page")
        user_id = runtime_context.get("user_id") or state.get("user_id")
        if material_id:
            parts.append(f"material_id={material_id}")
        if current_page is not None:
            parts.append(f"current_page={current_page}")
        if user_id:
            parts.append(f"user_id={user_id}")
        missing_context = context_bundle.get("missing_context") or []
        if missing_context:
            parts.append(f"missing_context={', '.join(missing_context)}")
        errors = context_bundle.get("errors") or []
        if errors:
            parts.append(f"context_errors={'; '.join(errors)}")
        return "\n".join(parts)

    def _build_evidence_text(self, state: TutorState) -> str:
        context_bundle = dict(state.get("context_bundle") or {})
        evidence_parts: list[str] = []
        if context_bundle.get("page_analysis"):
            evidence_parts.append(
                f"Current page analysis:\n{self._json_preview(context_bundle.get('page_analysis'))}"
            )
        if context_bundle.get("material_summary"):
            evidence_parts.append(
                f"Material summary:\n{self._json_preview(context_bundle.get('material_summary'))}"
            )
        for tool_name, output in self._extract_latest_tool_outputs(state.get("messages") or []).items():
            preview_source = output.get("parsed") if output.get("parsed") is not None else output.get("content")
            evidence_parts.append(f"Tool {tool_name} output:\n{self._json_preview(preview_source)}")
        return "\n\n".join(part for part in evidence_parts if part)

    def _build_answer_focus(self, state: TutorState) -> str:
        user_message = (state.get("current_user_message") or "").strip()
        if user_message:
            return user_message
        if self.language == "de":
            return "Erklaere die aktuelle Seite kurz, klar und fachlich korrekt."
        return "Explain the current page clearly and accurately."

    def _build_tool_args(self, tool_name: str, state: TutorState) -> dict[str, Any]:
        page_number = state.get("current_page") or 1
        if tool_name == "create_quiz":
            return {"start_page": page_number, "end_page": page_number}
        if tool_name in {"get_page_analysis", "get_page_image"}:
            return {"page_number": page_number}
        return {}

    def _build_clarification_message(
        self,
        state: TutorState,
        issues: Optional[list[str]] = None,
    ) -> str:
        context_bundle = dict(state.get("context_bundle") or {})
        missing_context = list(context_bundle.get("missing_context") or [])
        issue_text = "; ".join(issues or [])

        if self.language == "de":
            if missing_context:
                if "material_id" in missing_context and "current_page" in missing_context:
                    return "Ich moechte nichts raten. Nenne mir bitte das Material und die Seite, auf die du dich beziehst."
                if "current_page" in missing_context:
                    return "Ich moechte die Antwort sauber an der richtigen Folie verankern. Welche Seite meinst du genau?"
                if "material_id" in missing_context:
                    return "Ich brauche noch das Material, auf das du dich beziehst, damit ich gezielt helfen kann."
                if "user_id" in missing_context:
                    return "Mir fehlt gerade der benoetigte Sitzungskontext. Bitte versuche es noch einmal in derselben Lernsitzung."
            if issue_text:
                return (
                    "Ich moechte die Antwort sauber belegen. Kannst du kurz praezisieren, "
                    f"welche Stelle oder Seite du meinst? ({issue_text})"
                )
            return "Kannst du kurz praezisieren, ob du die aktuelle Seite erklaert haben moechtest oder eine gezielte Rueckfrage dazu hast?"

        if missing_context:
            return "I want to ground the answer correctly. Please tell me which material and page you mean."
        if issue_text:
            return f"I want to ground the answer correctly. Which exact page or passage do you mean? ({issue_text})"
        return "Could you clarify whether you want an explanation of the current page or a specific follow-up question about it?"

    def _build_cautious_fallback_message(self, state: TutorState) -> str:
        context_bundle = dict(state.get("context_bundle") or {})
        page_analysis = context_bundle.get("page_analysis") or {}
        summary = ""
        if isinstance(page_analysis, dict):
            summary = str(page_analysis.get("summary") or "").strip()

        if self.language == "de":
            if summary:
                return (
                    "Ich moechte nichts erfinden. Sicher gestuetzt ist im aktuellen Kontext vor allem dies: "
                    f"{summary}"
                )
            return (
                "Ich moechte nichts erfinden. Im Moment reicht mein gesicherter Kontext nicht fuer eine belastbare Antwort. "
                "Wenn du mir die Seite oder die genaue Stelle nennst, antworte ich praeziser."
            )

        if summary:
            return f"I do not want to invent details. The most strongly supported point in the current context is: {summary}"
        return (
            "I do not want to invent details. The currently verified context is not enough for a reliable answer yet. "
            "If you tell me the page or exact passage, I can answer more precisely."
        )

    def _prepare_messages_for_phase(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        if not messages:
            return []
        non_system_messages = [message for message in messages if not isinstance(message, SystemMessage)]
        
        last_human_idx = -1
        for i, msg in enumerate(non_system_messages):
            if isinstance(msg, HumanMessage):
                last_human_idx = i

        cleaned_messages = []
        for i, msg in enumerate(non_system_messages):
            if i < last_human_idx:
                if isinstance(msg, ToolMessage):
                    continue
                if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                    if msg.content:
                        cleaned_messages.append(AIMessage(content=msg.content))
                    continue
            cleaned_messages.append(msg)

        trimmed_messages = list(cleaned_messages)
        if len(trimmed_messages) > self.MAX_HISTORY_MESSAGES:
            trimmed_messages = trimmed_messages[-self.MAX_HISTORY_MESSAGES :]
        while trimmed_messages and isinstance(trimmed_messages[0], ToolMessage):
            trimmed_messages = trimmed_messages[1:]
        return fix_incomplete_tool_calls(trimmed_messages)

    def _enhance_tool_messages(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        enhanced_messages: list[BaseMessage] = []
        for message in messages:
            if not isinstance(message, ToolMessage):
                enhanced_messages.append(message)
                continue
            try:
                if isinstance(message.content, str) and "image_data" in message.content:
                    content_json = json.loads(message.content)
                    if isinstance(content_json, dict) and content_json.get("status") == "success" and "image_data" in content_json:
                        page_number = content_json.get("page_number", "unknown")
                        prompt_text = (
                            f"Hier ist die visuelle Seite {page_number}. Analysiere sie fuer die Antwort."
                            if self.language == "de"
                            else f"Here is the visual snapshot of page {page_number}. Analyse it for the answer."
                        )
                        enhanced_messages.append(
                            ToolMessage(
                                content=[
                                    {"type": "text", "text": prompt_text},
                                    {"type": "image_url", "image_url": {"url": content_json["image_data"]}},
                                ],
                                tool_call_id=message.tool_call_id,
                                name=message.name,
                            )
                        )
                        continue
            except Exception:
                pass
            enhanced_messages.append(message)
        return enhanced_messages

    def _extract_latest_tool_outputs(self, messages: list[BaseMessage]) -> dict[str, dict[str, Any]]:
        tool_names_by_id: dict[str, str] = {}
        latest_outputs: dict[str, dict[str, Any]] = {}
        for message in messages:
            if isinstance(message, AIMessage) and getattr(message, "tool_calls", None):
                for tool_call in message.tool_calls:
                    tool_call_id = tool_call.get("id") if isinstance(tool_call, dict) else None
                    tool_name = tool_call.get("name") if isinstance(tool_call, dict) else None
                    if tool_call_id and tool_name:
                        tool_names_by_id[tool_call_id] = tool_name
            elif isinstance(message, ToolMessage):
                tool_call_id = getattr(message, "tool_call_id", None)
                tool_name = getattr(message, "name", None) or tool_names_by_id.get(tool_call_id or "", "")
                if not tool_name:
                    continue
                latest_outputs[tool_name] = {
                    "tool_call_id": tool_call_id,
                    "content": message.content,
                    "parsed": self._safe_json_loads(message.content),
                }
        return latest_outputs

    def _append_trace(
        self,
        state: TutorState,
        step: str,
        detail: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        trace = list(state.get("execution_trace") or [])
        entry: dict[str, Any] = {"step": step}
        if state.get("turn_id"):
            entry["turn_id"] = state["turn_id"]
        if detail:
            entry["detail"] = detail
        trace.append(entry)
        return trace

    def _extract_current_user_message(self, messages: list[BaseMessage]) -> str:
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return self._message_content_to_text(message.content).strip()
        return ""

    @staticmethod
    def _message_content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                str(part.get("text", "")) if isinstance(part, dict) else str(part)
                for part in content
            )
        if content is None:
            return ""
        return str(content)

    def _extract_response_text(self, response: Any) -> str:
        if isinstance(response, AIMessage):
            return self._message_content_to_text(response.content)
        if hasattr(response, "content"):
            return self._message_content_to_text(response.content)
        return self._message_content_to_text(response)

    @staticmethod
    def _normalize_string(value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _normalize_page_number(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _normalize_summary(self, summary: Any) -> dict[str, Any] | None:
        if summary is None:
            return None
        if isinstance(summary, dict):
            return summary
        parsed = self._safe_json_loads(summary)
        if isinstance(parsed, dict):
            return parsed
        if parsed is None and isinstance(summary, str):
            return {"summary": summary}
        return None

    def _serialize_messages(self, messages: list[BaseMessage]) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for message in messages:
            if isinstance(message, HumanMessage):
                serialized.append({"type": "human", "content": message.content})
            elif isinstance(message, AIMessage):
                serialized.append(
                    {"type": "ai", "content": message.content, "tool_calls": getattr(message, "tool_calls", None)}
                )
            elif isinstance(message, ToolMessage):
                serialized.append(
                    {
                        "type": "tool",
                        "content": message.content,
                        "tool_call_id": getattr(message, "tool_call_id", None),
                        "name": getattr(message, "name", None),
                    }
                )
            elif isinstance(message, SystemMessage):
                serialized.append({"type": "system", "content": message.content})
        return serialized

    def _deserialize_messages(self, messages: list[dict[str, Any]]) -> list[BaseMessage]:
        deserialized: list[BaseMessage] = []
        for message in messages:
            message_type = message.get("type")
            if message_type == "human":
                deserialized.append(HumanMessage(content=message.get("content", "")))
            elif message_type == "ai":
                deserialized.append(AIMessage(content=message.get("content", ""), tool_calls=message.get("tool_calls") or []))
            elif message_type == "tool":
                deserialized.append(
                    ToolMessage(
                        content=message.get("content", ""),
                        tool_call_id=message.get("tool_call_id", ""),
                        name=message.get("name"),
                    )
                )
            elif message_type == "system":
                deserialized.append(SystemMessage(content=message.get("content", "")))
        return deserialized

    @staticmethod
    def _safe_json_loads(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except Exception:
            return None

    def _json_preview(self, value: Any, limit: int = 1400) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            text = value
        else:
            try:
                text = json.dumps(value, ensure_ascii=False)
            except Exception:
                text = str(value)
        if len(text) <= limit:
            return text
        return f"{text[:limit]}..."

    def _get_execution_plan(self, state: TutorState) -> TutorExecutionPlan | None:
        raw_plan = state.get("execution_plan")
        if not raw_plan:
            return None
        try:
            if isinstance(raw_plan, TutorExecutionPlan):
                return raw_plan
            return TutorExecutionPlan.model_validate(raw_plan)
        except Exception:
            return None

    def _build_llm_config(
        self,
        state: TutorState,
        run_name: str,
        config: Optional[RunnableConfig] = None,
    ) -> dict[str, Any]:
        config_dict = dict(config or {})
        metadata = dict(config_dict.get("metadata") or {})
        metadata.update(
            {
                "langfuse_user_id": state.get("user_id"),
                "langfuse_session_id": state.get("material_id"),
                "material_id": state.get("material_id"),
                "current_page": state.get("current_page"),
                "agent_name": self.name,
                "language": self.language,
                "intent": state.get("intent"),
                "turn_id": state.get("turn_id"),
                "graph_version": self.graph_version,
            }
        )
        config_dict["metadata"] = metadata
        config_dict["run_name"] = run_name

        callback_handler = create_callback_handler()
        if callback_handler:
            callbacks = list(config_dict.get("callbacks") or [])
            callbacks.append(callback_handler)
            config_dict["callbacks"] = callbacks
        return config_dict

    @staticmethod
    def _get_configurable(config: Optional[RunnableConfig]) -> dict[str, Any]:
        if not config:
            return {}
        try:
            configurable = config.get("configurable", {})  # type: ignore[call-arg]
        except Exception:
            return {}
        return dict(configurable or {})

    @staticmethod
    def _is_quiz_request(message: str) -> bool:
        lowered = message.lower()
        keywords = ["quiz", "fragen", "fragebogen", "teste mich", "abfrage", "multiple choice", "uebe"]
        return any(keyword in lowered for keyword in keywords)

    @staticmethod
    def _needs_visual_support(message: str) -> bool:
        lowered = message.lower()
        keywords = ["diagram", "grafik", "abbildung", "chart", "schaubild", "visual", "layout", "auf der folie", "wie sieht", "tabelle"]
        return any(keyword in lowered for keyword in keywords)

    @staticmethod
    def _needs_overview_support(message: str) -> bool:
        lowered = message.lower()
        keywords = ["ueberblick", "einordnung", "zusammenhang", "gesamt", "overall", "overview", "big picture"]
        return any(keyword in lowered for keyword in keywords)

    @staticmethod
    def _looks_like_followup(message: str, state: TutorState) -> bool:
        lowered = message.lower().strip()
        if len(state.get("messages") or []) < 2:
            return False
        markers = ["warum", "wieso", "wie", "nochmal", "genau", "das", "diese", "dieser", "that", "those", "why", "how"]
        return any(marker in lowered for marker in markers)


