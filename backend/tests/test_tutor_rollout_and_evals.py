import asyncio
import pathlib
import sys
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import app.agents.tutor.tutor_agent as tutor_agent_module
import app.api.routers.chat as chat_router
import app.services.chat_checkpoint_service as checkpoint_service_module
import app.services.chat_service as chat_service_module
from app.agents.shared import TutorIntentDecision, TutorVerificationResult
from app.services.tutor_rollout import resolve_tutor_graph_version
from evals.tutor_eval import (
    TutorEvalCase,
    TutorEvalDataset,
    TutorEvalRunner,
    load_tutor_eval_dataset,
    prepare_langfuse_upload_payload,
    summarize_dataset_categories,
)
from upload_langfuse_dataset import prepare_upload_payload


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
        return queue.pop(0)


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
        if isinstance(result, AIMessage):
            return result
        return AIMessage(content=str(result))


class FakeSaver:
    def __init__(self):
        self.setup_called = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def setup(self):
        self.setup_called = True


class FakeGraph:
    def __init__(self, snapshot_has_messages):
        self.snapshot_has_messages = snapshot_has_messages
        self.initial_states = []
        self.configs = []
        self.stream_modes = []

    def get_state(self, config):
        self.configs.append(config)
        if self.snapshot_has_messages:
            return SimpleNamespace(values={"messages": [AIMessage(content="Persisted state")]})
        return SimpleNamespace(values={})

    async def astream(self, initial_state, config, stream_mode=None):
        self.initial_states.append(initial_state)
        self.configs.append(config)
        self.stream_modes.append(stream_mode)
        yield {"finalize_turn": {"messages": [AIMessage(content="Antwort aus dem Stream")]}}


@pytest.fixture
def minimal_eval_case():
    return TutorEvalCase.model_validate(
        {
            "id": "case-1",
            "category": "current_page_explain",
            "history": [],
            "user_message": "Erklaer mir bitte die aktuelle Seite.",
            "runtime_context": {
                "material_id": "mat-1",
                "user_id": "user-1",
                "current_page": 5,
            },
            "fixtures": {
                "page_analysis": {
                    "summary": "Die Seite erklaert Gradientenabstieg.",
                    "key_terms": ["Gradientenabstieg"],
                    "diagram_description": "Kein Diagramm",
                },
                "material_summary": {
                    "summary": "ML Grundlagen",
                },
            },
            "expected": {
                "intent": "explain_current_page",
                "tool_names": ["get_page_analysis"],
                "completion_mode": "answer",
                "required_phrases": [],
                "forbidden_claims": [],
            },
        }
    )


def test_tutor_eval_dataset_counts_and_langfuse_payload():
    dataset_path = pathlib.Path(__file__).resolve().parents[1] / "evals" / "tutor_gold_v1.json"
    dataset = load_tutor_eval_dataset()
    assert len(dataset.cases) == 42
    assert summarize_dataset_categories(dataset) == {
        "current_page_explain": 10,
        "follow_up": 8,
        "visual_question": 6,
        "quiz_request": 6,
        "missing_context": 6,
        "tool_error": 6,
    }

    payload = prepare_langfuse_upload_payload(dataset)
    assert payload["dataset_name"] == "tutor-v2-gold-evals"
    assert len(payload["items"]) == 42
    assert payload["items"][0]["metadata"]["case_id"].startswith("current-page-explain")

    upload_payload = prepare_upload_payload(dataset_path)
    assert upload_payload["dataset_name"] == payload["dataset_name"]
    assert len(upload_payload["items"]) == 42


def test_tutor_eval_runner_builds_comparison_report(minimal_eval_case, monkeypatch):
    monkeypatch.setattr(tutor_agent_module, "get_langfuse_client", lambda: None)
    monkeypatch.setattr(tutor_agent_module, "create_callback_handler", lambda: None)
    dataset = TutorEvalDataset(
        dataset_name="test-dataset",
        schema_version="1.0.0",
        description="Test dataset",
        cases=[minimal_eval_case],
    )

    def llm_factory(case, version):
        if version == "legacy":
            return DummyLLM(
                chat_responses=[
                    AIMessage(
                        content="",
                        tool_calls=[{"id": "call-1", "name": "get_page_analysis", "args": {}}],
                    ),
                    AIMessage(content="Legacy Antwort"),
                ]
            )
        return DummyLLM(
            chat_responses=[AIMessage(content="V2 Antwort")],
            structured_responses={
                TutorIntentDecision: [
                    TutorIntentDecision(
                        intent="explain_current_page",
                        intent_confidence=0.95,
                        required_capabilities=["page_analysis"],
                        needs_verification=True,
                        reason="Current page explanation",
                    )
                ],
                TutorVerificationResult: [
                    TutorVerificationResult(status="accept", reason="Grounded")
                ],
            },
        )

    runner = TutorEvalRunner(dataset, llm_factory=llm_factory)
    report = runner.run(mode="both")

    assert len(report.results) == 2
    assert report.summary["by_version"]["legacy"]["contract_passed"] == 1
    assert report.summary["by_version"]["v2"]["contract_passed"] == 1
    assert report.comparisons[0].case_id == "case-1"
    assert "intent" in report.comparisons[0].differing_fields
    assert "## Diffs" in report.to_markdown()


def test_resolve_tutor_graph_version_honors_precedence(monkeypatch):
    monkeypatch.setattr(chat_router, "set_conversation_tutor_graph_version", lambda *args, **kwargs: {"tutor_graph_version": "v2"})
    conversation = {"id": "conv-1", "metadata": {"tutor_graph_version": "legacy"}}
    resolution = chat_router._resolve_initiate_graph_version(conversation, "v2")
    assert resolution.graph_version == "v2"
    assert resolution.source == "request"
    assert conversation["metadata"]["tutor_graph_version"] == "v2"


def test_message_resolution_ignores_conflicting_override(monkeypatch):
    monkeypatch.setattr(
        chat_router,
        "set_conversation_tutor_graph_version",
        lambda *args, **kwargs: pytest.fail("Should not persist when thread metadata already exists"),
    )
    conversation = {"id": "conv-2", "metadata": {"tutor_graph_version": "legacy"}}
    resolution = chat_router._resolve_message_graph_version(conversation, "v2")
    assert resolution.graph_version == "legacy"
    assert resolution.source == "metadata"


def test_message_resolution_backfills_missing_metadata(monkeypatch):
    monkeypatch.setattr(chat_router, "set_conversation_tutor_graph_version", lambda conversation_id, graph_version: {"course_material_id": "mat-1", "tutor_graph_version": graph_version})
    monkeypatch.setattr(chat_service_module, "get_chat_checkpoint_backend", lambda: "memory")
    monkeypatch.setattr(chat_router.resolve_tutor_graph_version.__globals__["settings"], "TUTOR_GRAPH_DEFAULT_VERSION", "v2")
    monkeypatch.setattr(chat_router.resolve_tutor_graph_version.__globals__["settings"], "TUTOR_GRAPH_V2_ENABLED", False)
    conversation = {"id": "conv-3", "metadata": {"course_material_id": "mat-1"}}
    resolution = chat_router._resolve_message_graph_version(conversation, None)
    assert resolution.graph_version == "v2"
    assert resolution.source == "config_default"
    assert conversation["metadata"]["tutor_graph_version"] == "v2"


def test_chat_service_creates_tutor_agent_for_requested_variant(monkeypatch):
    monkeypatch.setattr(chat_service_module, "get_chat_checkpointer", lambda: MemorySaver())
    monkeypatch.setattr(chat_service_module, "get_chat_checkpoint_backend", lambda: "memory")
    service = chat_service_module.ChatService()

    created_versions = []

    def fake_create(graph_version):
        created_versions.append(graph_version)
        return SimpleNamespace(graph_version=graph_version)

    monkeypatch.setattr(service, "_create_tutor_agent", fake_create)

    legacy_agent = service.get_tutor_agent("legacy")
    v2_agent = service.get_tutor_agent("v2")

    assert legacy_agent.graph_version == "legacy"
    assert v2_agent.graph_version == "v2"
    assert created_versions == ["legacy", "v2"]


def test_chat_checkpointer_uses_postgres_when_available(monkeypatch):
    checkpoint_service_module.reset_chat_checkpointer_for_tests()
    fake_saver = FakeSaver()
    monkeypatch.setattr(checkpoint_service_module, "get_postgres_connection_string", lambda: "postgresql://example")
    monkeypatch.setattr(checkpoint_service_module.PostgresSaver, "from_conn_string", lambda conn_string: fake_saver)

    saver = checkpoint_service_module.get_chat_checkpointer()

    assert saver is fake_saver
    assert fake_saver.setup_called is True
    assert checkpoint_service_module.get_chat_checkpoint_backend() == "postgres"


def test_chat_checkpointer_falls_back_to_memory(monkeypatch):
    checkpoint_service_module.reset_chat_checkpointer_for_tests()
    monkeypatch.setattr(checkpoint_service_module, "get_postgres_connection_string", lambda: (_ for _ in ()).throw(ValueError("missing db")))

    saver = checkpoint_service_module.get_chat_checkpointer()

    assert isinstance(saver, MemorySaver)
    assert checkpoint_service_module.get_chat_checkpoint_backend() == "memory"


@pytest.mark.asyncio
async def test_stream_tutor_bootstraps_only_when_checkpoint_absent(monkeypatch):
    monkeypatch.setattr(chat_service_module, "get_chat_checkpointer", lambda: MemorySaver())
    monkeypatch.setattr(chat_service_module, "get_chat_checkpoint_backend", lambda: "memory")
    service = chat_service_module.ChatService()

    graph_without_checkpoint = FakeGraph(snapshot_has_messages=False)
    graph_with_checkpoint = FakeGraph(snapshot_has_messages=True)

    fresh_agent = SimpleNamespace(graph=graph_without_checkpoint, graph_version="v2")
    resumed_agent = SimpleNamespace(graph=graph_with_checkpoint, graph_version="v2")

    call_count = {"value": 0}

    def fake_get_tutor_agent(graph_version):
        call_count["value"] += 1
        return fresh_agent if call_count["value"] == 1 else resumed_agent

    monkeypatch.setattr(service, "get_tutor_agent", fake_get_tutor_agent)

    bootstrap_messages = [{"role": "assistant", "content": "Vorherige Antwort"}]

    first_stream = service.stream_tutor(
        thread_id="thread-1",
        conversation_id="conv-1",
        user_id="user-1",
        material_id="mat-1",
        user_message="Neue Frage",
        graph_version="v2",
        rollout_source="metadata",
        bootstrap_messages=bootstrap_messages,
    )
    second_stream = service.stream_tutor(
        thread_id="thread-1",
        conversation_id="conv-1",
        user_id="user-1",
        material_id="mat-1",
        user_message="Noch eine Frage",
        graph_version="v2",
        rollout_source="metadata",
        bootstrap_messages=bootstrap_messages,
    )

    async for _ in first_stream:
        pass
    async for _ in second_stream:
        pass

    first_messages = graph_without_checkpoint.initial_states[0]["messages"]
    second_messages = graph_with_checkpoint.initial_states[0]["messages"]

    assert len(first_messages) == 2
    assert isinstance(first_messages[0], AIMessage)
    assert graph_without_checkpoint.configs[0]["configurable"]["checkpoint_ns"] == "tutor:v2"
    assert graph_without_checkpoint.stream_modes[0] == "updates"
    assert graph_with_checkpoint.stream_modes[0] == "updates"
    assert len(second_messages) == 1
    assert isinstance(second_messages[0], HumanMessage)



class DuplicateEventGraph:
    def get_state(self, config):
        return SimpleNamespace(values={})

    async def astream(self, initial_state, config, stream_mode=None):
        tool_call_message = AIMessage(
            content="",
            tool_calls=[{"id": "call-1", "name": "get_page_analysis", "args": {}}],
        )
        tool_response_message = ToolMessage(
            content='{"summary": "Antwort"}',
            tool_call_id="call-1",
            name="get_page_analysis",
        )
        yield {"planner": {"messages": [tool_call_message]}}
        yield {"planner": {"messages": [tool_call_message]}}
        yield {"tools": {"messages": [tool_response_message]}}
        yield {"tools": {"messages": [tool_response_message]}}


@pytest.mark.asyncio
async def test_stream_tutor_dedupes_repeated_tool_events(monkeypatch):
    monkeypatch.setattr(chat_service_module, "get_chat_checkpointer", lambda: MemorySaver())
    monkeypatch.setattr(chat_service_module, "get_chat_checkpoint_backend", lambda: "memory")
    service = chat_service_module.ChatService()
    agent = SimpleNamespace(graph=DuplicateEventGraph(), graph_version="v2")
    monkeypatch.setattr(service, "get_tutor_agent", lambda graph_version: agent)

    events = []
    async for event in service.stream_tutor(
        thread_id="thread-dedupe",
        conversation_id="conv-dedupe",
        user_id="user-1",
        material_id="mat-1",
        user_message="Neue Frage",
        graph_version="v2",
        rollout_source="metadata",
    ):
        events.append(event)

    tool_call_events = [event for event in events if '"type": "tool_call"' in event]
    tool_response_events = [event for event in events if '"type": "tool_response"' in event]

    assert len(tool_call_events) == 1
    assert len(tool_response_events) == 1
