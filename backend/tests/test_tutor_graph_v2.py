import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import app.agents.tutor.tutor_agent as tutor_agent_module
from app.agents.shared import TutorIntentDecision, TutorVerificationResult
from app.agents.tutor import TutorAgent
from app.tools.course_material_tool import GetCourseMaterialSummaryTool
from app.tools.page_analysis_tool import GetPageAnalysisTool
from app.tools.page_image_tool import GetPageImageTool
from app.tools.quiz_tool import CreateQuizTool


class DummyStructuredLLM:
    def __init__(self, parent, schema):
        self.parent = parent
        self.schema = schema

    def with_config(self, _config):
        return self

    def invoke(self, _messages, config=None):
        queue = self.parent.structured_responses.setdefault(self.schema, [])
        if not queue:
            raise AssertionError(f"No structured response queued for {self.schema.__name__}")
        result = queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class DummyLLM:
    def __init__(self, chat_responses=None, structured_responses=None):
        self.chat_responses = list(chat_responses or [])
        self.structured_responses = {
            key: list(value)
            for key, value in (structured_responses or {}).items()
        }
        self.bound_tools = []

    def bind_tools(self, tools):
        self.bound_tools = list(tools)
        return self

    def with_config(self, _config):
        return self

    def with_structured_output(self, schema):
        return DummyStructuredLLM(self, schema)

    def invoke(self, _messages, config=None):
        if not self.chat_responses:
            raise AssertionError("No chat response queued")
        result = self.chat_responses.pop(0)
        if isinstance(result, Exception):
            raise result
        if isinstance(result, AIMessage):
            return result
        return AIMessage(content=str(result))


class FakePageAnalysisAdapter:
    def __init__(self, payload):
        self.payload = payload

    def get(self, course_material_id, page_number, user_id):
        return self.payload


class FakeMaterialAdapter:
    def __init__(self, payload):
        self.payload = payload

    def get_summary(self, course_material_id, user_id):
        return self.payload


@pytest.fixture
def patch_tutor_dependencies(monkeypatch):
    monkeypatch.setattr(tutor_agent_module.settings, "TUTOR_GRAPH_V2_ENABLED", True)
    monkeypatch.setattr(tutor_agent_module, "get_langfuse_client", lambda: None)
    monkeypatch.setattr(tutor_agent_module, "create_callback_handler", lambda: None)
    monkeypatch.setattr(
        tutor_agent_module,
        "get_page_analysis",
        lambda: FakePageAnalysisAdapter(
            {
                "summary": "Die Seite erklaert Gradientenabstieg.",
                "key_terms": ["Gradient", "Optimierung"],
                "diagram_description": "Kurve mit Tal und Pfeilrichtung.",
            }
        ),
    )
    monkeypatch.setattr(
        tutor_agent_module,
        "get_material",
        lambda: FakeMaterialAdapter(
            {
                "summary": "Vorlesung zu Machine Learning Grundlagen.",
                "topics": ["Optimierung", "Modelle"],
            }
        ),
    )

    def fake_quiz_init(self, quiz_agent=None):
        self.name = "create_quiz"
        self.description = "Create a quiz."

    monkeypatch.setattr(CreateQuizTool, "__init__", fake_quiz_init)
    monkeypatch.setattr(
        GetPageAnalysisTool,
        "_run",
        lambda self, course_material_id, page_number, user_id: json.dumps(
            {
                "summary": f"Analyse fuer Seite {page_number}",
                "key_terms": ["Gradient", "Lernrate"],
            }
        ),
    )
    monkeypatch.setattr(
        GetCourseMaterialSummaryTool,
        "_run",
        lambda self, course_material_id, user_id: json.dumps(
            {"summary": "Gesamtueberblick ueber das Material."}
        ),
    )
    monkeypatch.setattr(
        GetPageImageTool,
        "_run",
        lambda self, course_material_id, page_number, user_id: json.dumps(
            {
                "status": "success",
                "image_data": "data:image/png;base64,AAA",
                "page_number": page_number,
            }
        ),
    )
    monkeypatch.setattr(
        CreateQuizTool,
        "_run",
        lambda self, start_page, end_page, course_material_id, user_id: json.dumps(
            {
                "quiz_id": "quiz-123",
                "topic": "Gradientenabstieg",
                "question_count": 3,
            }
        ),
    )


def make_agent(*, chat_responses=None, structured_responses=None):
    llm = DummyLLM(chat_responses=chat_responses, structured_responses=structured_responses)
    return TutorAgent(llm=llm, language="de")


def flatten_tool_names(messages):
    tool_names = []
    for message in messages:
        if isinstance(message, AIMessage) and getattr(message, "tool_calls", None):
            tool_names.extend(tool_call["name"] for tool_call in message.tool_calls)
    return tool_names


def test_tutoring_graph_calls_page_analysis_and_returns_answer(patch_tutor_dependencies):
    agent = make_agent(
        chat_responses=[AIMessage(content="Gradientenabstieg minimiert schrittweise die Fehlerfunktion.")],
        structured_responses={
            TutorIntentDecision: [
                TutorIntentDecision(
                    intent="explain_current_page",
                    intent_confidence=0.91,
                    required_capabilities=["page_analysis"],
                    needs_verification=True,
                    reason="The user wants an explanation of the current slide.",
                )
            ],
            TutorVerificationResult: [
                TutorVerificationResult(status="accept", reason="Grounded by the page analysis.")
            ],
        },
    )

    result = agent.graph.invoke(
        {
            "messages": [HumanMessage(content="Erklaer mir bitte die aktuelle Seite.")],
            "material_id": "mat-1",
            "user_id": "user-1",
            "current_page": 5,
        }
    )

    assert "get_page_analysis" in flatten_tool_names(result["messages"])
    assert isinstance(result["messages"][-1], AIMessage)
    assert result["messages"][-1].content == "Gradientenabstieg minimiert schrittweise die Fehlerfunktion."


def test_visual_question_triggers_page_image_tool(patch_tutor_dependencies):
    agent = make_agent(
        chat_responses=[AIMessage(content="Das Diagramm zeigt eine Bewegung entlang des steilsten Abstiegs.")],
        structured_responses={
            TutorIntentDecision: [
                TutorIntentDecision(
                    intent="needs_visual",
                    intent_confidence=0.88,
                    required_capabilities=["page_analysis", "page_image"],
                    needs_verification=True,
                    reason="The question depends on the diagram.",
                )
            ],
            TutorVerificationResult: [
                TutorVerificationResult(status="accept", reason="Grounded by page analysis and page image.")
            ],
        },
    )

    result = agent.graph.invoke(
        {
            "messages": [HumanMessage(content="Was zeigt das Diagramm auf der Folie?")],
            "material_id": "mat-1",
            "user_id": "user-1",
            "current_page": 5,
        }
    )

    tool_names = flatten_tool_names(result["messages"])
    assert "get_page_analysis" in tool_names
    assert "get_page_image" in tool_names
    assert result["messages"][-1].content.startswith("Das Diagramm zeigt")


def test_missing_context_graph_returns_clarification(patch_tutor_dependencies):
    agent = make_agent(chat_responses=[])

    result = agent.graph.invoke(
        {
            "messages": [HumanMessage(content="Erklaer mir das bitte.")],
            "material_id": "mat-1",
            "user_id": "user-1",
        }
    )

    assert isinstance(result["messages"][-1], AIMessage)
    assert "Seite" in result["messages"][-1].content


def test_quiz_graph_success_has_no_extra_assistant_message(patch_tutor_dependencies):
    agent = make_agent(chat_responses=[])

    result = agent.graph.invoke(
        {
            "messages": [HumanMessage(content="Mach bitte ein Quiz zur aktuellen Seite.")],
            "material_id": "mat-1",
            "user_id": "user-1",
            "current_page": 5,
        }
    )

    assistant_messages = [
        message
        for message in result["messages"]
        if isinstance(message, AIMessage) and not getattr(message, "tool_calls", None)
    ]
    assert assistant_messages == []
    assert isinstance(result["messages"][-1], ToolMessage)


def test_verify_response_repairs_once(patch_tutor_dependencies):
    agent = make_agent(
        chat_responses=[AIMessage(content="Gradientenabstieg folgt lokal der Richtung des negativen Gradienten.")],
        structured_responses={
            TutorVerificationResult: [
                TutorVerificationResult(
                    status="revise",
                    issues=["The draft introduced an unsupported global optimum claim."],
                    reason="One sentence overreaches the evidence.",
                ),
                TutorVerificationResult(
                    status="accept",
                    reason="The repaired draft is fully grounded.",
                ),
            ]
        },
    )

    updates = agent.verify_response(
        {
            "messages": [HumanMessage(content="Was ist Gradientenabstieg?")],
            "current_user_message": "Was ist Gradientenabstieg?",
            "draft_answer": "Gradientenabstieg findet immer das globale Minimum.",
            "needs_verification": True,
            "material_id": "mat-1",
            "user_id": "user-1",
            "current_page": 5,
            "context_bundle": {
                "runtime_context": {"material_id": "mat-1", "user_id": "user-1", "current_page": 5},
                "page_analysis": {"summary": "Die Seite erklaert den negativen Gradienten als Suchrichtung."},
                "material_summary": {"summary": "Machine Learning Grundlagen."},
                "missing_context": [],
                "errors": [],
            },
            "execution_trace": [],
        }
    )

    assert updates["draft_answer"] == "Gradientenabstieg folgt lokal der Richtung des negativen Gradienten."
    assert updates["verification_attempts"] == 1
    assert updates["verification_result"]["status"] == "accept"


