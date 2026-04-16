from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal
from unittest.mock import patch

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field

import app.agents.tutor.tutor_agent as tutor_agent_module
from app.agents.tutor import TutorAgent
from app.services.analyzer import get_gemini_model
from app.services.tutor_rollout import TutorGraphVersion
from app.tools.course_material_tool import GetCourseMaterialSummaryTool
from app.tools.page_analysis_tool import GetPageAnalysisTool
from app.tools.page_image_tool import GetPageImageTool
from app.tools.quiz_tool import CreateQuizTool

DEFAULT_DATASET_PATH = Path(__file__).with_name("tutor_gold_v1.json")
EvalMode = Literal["legacy", "v2", "both"]
CompletionMode = Literal["answer", "clarify", "quiz"]
TutorEvalCategory = Literal[
    "current_page_explain",
    "follow_up",
    "visual_question",
    "quiz_request",
    "missing_context",
    "tool_error",
]


class TutorEvalExpected(BaseModel):
    intent: str | None = None
    tool_names: list[str] = Field(default_factory=list)
    completion_mode: CompletionMode
    required_phrases: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    judge_notes: str | None = None


class TutorEvalFixtures(BaseModel):
    page_analysis: dict[str, Any] | None = None
    material_summary: dict[str, Any] | None = None
    page_image: dict[str, Any] | None = None
    quiz_result: dict[str, Any] | None = None
    tool_errors: dict[str, str] = Field(default_factory=dict)


class TutorEvalCase(BaseModel):
    id: str
    category: TutorEvalCategory
    history: list[dict[str, str]] = Field(default_factory=list)
    user_message: str
    runtime_context: dict[str, Any] = Field(default_factory=dict)
    fixtures: TutorEvalFixtures = Field(default_factory=TutorEvalFixtures)
    expected: TutorEvalExpected


class TutorEvalDataset(BaseModel):
    dataset_name: str
    schema_version: str
    description: str
    cases: list[TutorEvalCase]


class TutorEvalCaseResult(BaseModel):
    case_id: str
    category: TutorEvalCategory
    graph_version: TutorGraphVersion
    observed_intent: str | None = None
    observed_tool_names: list[str] = Field(default_factory=list)
    observed_completion_mode: str
    assistant_text: str = ""
    contract_passed: bool
    contract_failures: list[str] = Field(default_factory=list)


class TutorEvalComparison(BaseModel):
    case_id: str
    category: TutorEvalCategory
    differing_fields: list[str] = Field(default_factory=list)
    legacy_contract_passed: bool | None = None
    v2_contract_passed: bool | None = None


class TutorEvalReport(BaseModel):
    dataset_name: str
    schema_version: str
    mode: EvalMode
    generated_at: str
    summary: dict[str, Any]
    results: list[TutorEvalCaseResult]
    comparisons: list[TutorEvalComparison] = Field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            f"# {self.dataset_name}",
            "",
            f"- Schema-Version: `{self.schema_version}`",
            f"- Modus: `{self.mode}`",
            f"- Generiert: `{self.generated_at}`",
            f"- Gesamtfaelle: `{self.summary.get('total_cases', 0)}`",
            "",
            "## Summary",
            "",
        ]
        for version, stats in self.summary.get("by_version", {}).items():
            lines.append(
                f"- `{version}`: {stats.get('contract_passed', 0)}/{stats.get('total', 0)} Contract-Paesse"
            )
        if self.comparisons:
            lines.extend(["", "## Diffs", ""])
            for comparison in self.comparisons:
                differing = ", ".join(comparison.differing_fields) or "none"
                lines.append(
                    f"- `{comparison.case_id}` ({comparison.category}): differing_fields={differing}, "
                    f"legacy_pass={comparison.legacy_contract_passed}, v2_pass={comparison.v2_contract_passed}"
                )
        return "\n".join(lines) + "\n"


class _FrozenPageAnalysisAdapter:
    def __init__(self, payload: dict[str, Any] | None):
        self.payload = payload or {}

    def get(self, course_material_id: str, page_number: int, user_id: str) -> dict[str, Any]:
        return self.payload


class _FrozenMaterialAdapter:
    def __init__(self, payload: dict[str, Any] | None):
        self.payload = payload or {}

    def get_summary(self, course_material_id: str, user_id: str) -> dict[str, Any]:
        return self.payload


class FrozenTutorEnvironment:
    def __init__(self, case: TutorEvalCase):
        self.case = case
        self._patches: list[Any] = []

    def __enter__(self):
        fixtures = self.case.fixtures

        def fake_quiz_init(self, quiz_agent=None):
            self.name = "create_quiz"
            self.description = "Create a quiz."

        def tool_json(tool_name: str, payload: dict[str, Any] | None) -> str:
            error = fixtures.tool_errors.get(tool_name)
            if error:
                return json.dumps(
                    {
                        "error": error,
                        "status": "error",
                        "tool_name": tool_name,
                    },
                    ensure_ascii=False,
                )
            return json.dumps(payload or {}, ensure_ascii=False)

        self._patches = [
            patch.object(tutor_agent_module, "get_page_analysis", lambda: _FrozenPageAnalysisAdapter(fixtures.page_analysis)),
            patch.object(tutor_agent_module, "get_material", lambda: _FrozenMaterialAdapter(fixtures.material_summary)),
            patch.object(CreateQuizTool, "__init__", fake_quiz_init),
            patch.object(
                GetPageAnalysisTool,
                "_run",
                lambda self, course_material_id, page_number, user_id: tool_json(
                    "get_page_analysis", fixtures.page_analysis
                ),
            ),
            patch.object(
                GetCourseMaterialSummaryTool,
                "_run",
                lambda self, course_material_id, user_id: tool_json(
                    "get_course_material_summary", fixtures.material_summary
                ),
            ),
            patch.object(
                GetPageImageTool,
                "_run",
                lambda self, course_material_id, page_number, user_id: tool_json(
                    "get_page_image", fixtures.page_image
                ),
            ),
            patch.object(
                CreateQuizTool,
                "_run",
                lambda self, start_page, end_page, course_material_id, user_id: tool_json(
                    "create_quiz", fixtures.quiz_result
                ),
            ),
        ]
        for active_patch in self._patches:
            active_patch.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        for active_patch in reversed(self._patches):
            active_patch.stop()
        return False


def load_tutor_eval_dataset(dataset_path: Path | None = None) -> TutorEvalDataset:
    resolved_path = dataset_path or DEFAULT_DATASET_PATH
    with resolved_path.open("r", encoding="utf-8") as handle:
        raw_data = json.load(handle)
    return TutorEvalDataset.model_validate(raw_data)


def summarize_dataset_categories(dataset: TutorEvalDataset) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in dataset.cases:
        counts[case.category] = counts.get(case.category, 0) + 1
    return counts


def prepare_langfuse_upload_payload(
    dataset: TutorEvalDataset,
) -> dict[str, Any]:
    items = []
    for case in dataset.cases:
        items.append(
            {
                "input": {
                    "history": case.history,
                    "user_message": case.user_message,
                    "runtime_context": case.runtime_context,
                    "fixtures": case.fixtures.model_dump(),
                },
                "metadata": {
                    "case_id": case.id,
                    "category": case.category,
                    "expected_intent": case.expected.intent,
                    "expected_tool_names": case.expected.tool_names,
                    "expected_completion_mode": case.expected.completion_mode,
                    "judge_notes": case.expected.judge_notes,
                    "schema_version": dataset.schema_version,
                },
            }
        )
    return {
        "dataset_name": dataset.dataset_name,
        "description": dataset.description,
        "items": items,
    }


class TutorEvalRunner:
    def __init__(
        self,
        dataset: TutorEvalDataset,
        llm_factory: Callable[[TutorEvalCase, TutorGraphVersion], Any] | None = None,
    ) -> None:
        self.dataset = dataset
        self.llm_factory = llm_factory or (lambda case, version: get_gemini_model())

    def run(self, mode: EvalMode = "both") -> TutorEvalReport:
        versions: list[TutorGraphVersion]
        if mode == "both":
            versions = ["legacy", "v2"]
        else:
            versions = [mode]

        results: list[TutorEvalCaseResult] = []
        for case in self.dataset.cases:
            for version in versions:
                results.append(self._run_case(case, version))

        return TutorEvalReport(
            dataset_name=self.dataset.dataset_name,
            schema_version=self.dataset.schema_version,
            mode=mode,
            generated_at=datetime.now(timezone.utc).isoformat(),
            summary=self._build_summary(results),
            results=results,
            comparisons=self._build_comparisons(results) if mode == "both" else [],
        )

    def write_report(self, report: TutorEvalReport, output_dir: Path) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "tutor_eval_report.json"
        markdown_path = output_dir / "tutor_eval_report.md"
        json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        markdown_path.write_text(report.to_markdown(), encoding="utf-8")
        return {"json": json_path, "markdown": markdown_path}

    def _run_case(self, case: TutorEvalCase, graph_version: TutorGraphVersion) -> TutorEvalCaseResult:
        llm = self.llm_factory(case, graph_version)
        with FrozenTutorEnvironment(case):
            agent = TutorAgent(llm=llm, language="de", graph_version=graph_version)
            result = agent.graph.invoke(self._build_initial_state(case))

        messages = result.get("messages") or []
        assistant_text = self._extract_assistant_text(messages)
        observed_tool_names = self._flatten_tool_names(messages)
        observed_intent = result.get("intent") if graph_version == "v2" else None
        observed_completion_mode = self._infer_completion_mode(
            result,
            assistant_text,
            observed_tool_names,
        )
        failures = self._validate_contract(
            case,
            graph_version,
            observed_intent,
            observed_tool_names,
            observed_completion_mode,
            assistant_text,
        )
        return TutorEvalCaseResult(
            case_id=case.id,
            category=case.category,
            graph_version=graph_version,
            observed_intent=observed_intent,
            observed_tool_names=observed_tool_names,
            observed_completion_mode=observed_completion_mode,
            assistant_text=assistant_text,
            contract_passed=not failures,
            contract_failures=failures,
        )

    @staticmethod
    def _build_initial_state(case: TutorEvalCase) -> dict[str, Any]:
        initial_messages = [
            *[_history_entry_to_message(entry) for entry in case.history],
            HumanMessage(content=case.user_message),
        ]
        state = {
            "messages": initial_messages,
            "material_id": case.runtime_context.get("material_id", "eval-material"),
            "user_id": case.runtime_context.get("user_id", "eval-user"),
        }
        current_page = case.runtime_context.get("current_page")
        if current_page is not None:
            state["current_page"] = current_page
        if case.runtime_context.get("course_material_summary") is not None:
            state["course_material_summary"] = case.runtime_context["course_material_summary"]
        return state

    @staticmethod
    def _extract_assistant_text(messages: list[BaseMessage]) -> str:
        for message in reversed(messages):
            if isinstance(message, AIMessage) and not getattr(message, "tool_calls", None):
                return _message_text(message)
        return ""

    @staticmethod
    def _flatten_tool_names(messages: list[BaseMessage]) -> list[str]:
        tool_names: list[str] = []
        for message in messages:
            if not isinstance(message, AIMessage) or not getattr(message, "tool_calls", None):
                continue
            for tool_call in message.tool_calls:
                if isinstance(tool_call, dict):
                    tool_names.append(str(tool_call.get("name", "")))
                else:
                    tool_names.append(str(getattr(tool_call, "name", "")))
        return [name for name in tool_names if name]

    @staticmethod
    def _infer_completion_mode(
        result: dict[str, Any],
        assistant_text: str,
        observed_tool_names: list[str],
    ) -> str:
        if "create_quiz" in observed_tool_names:
            return "quiz"
        if result.get("intent") == "clarify_missing_context":
            return "clarify"
        if result.get("verification_result", {}).get("status") == "clarify":
            return "clarify"
        if assistant_text.strip().endswith("?") and not observed_tool_names:
            return "clarify"
        return "answer"

    @staticmethod
    def _validate_contract(
        case: TutorEvalCase,
        graph_version: TutorGraphVersion,
        observed_intent: str | None,
        observed_tool_names: list[str],
        observed_completion_mode: str,
        assistant_text: str,
    ) -> list[str]:
        failures: list[str] = []
        expected = case.expected
        assistant_lower = assistant_text.lower()

        if expected.intent and not (graph_version == "legacy" and observed_intent is None):
            if observed_intent != expected.intent:
                failures.append(
                    f"intent mismatch: expected={expected.intent} observed={observed_intent}"
                )
        if observed_tool_names != expected.tool_names:
            failures.append(
                f"tool_names mismatch: expected={expected.tool_names} observed={observed_tool_names}"
            )
        if observed_completion_mode != expected.completion_mode:
            failures.append(
                f"completion_mode mismatch: expected={expected.completion_mode} observed={observed_completion_mode}"
            )
        for phrase in expected.required_phrases:
            if phrase.lower() not in assistant_lower:
                failures.append(f"required phrase missing: {phrase}")
        for phrase in expected.forbidden_claims:
            if phrase.lower() in assistant_lower:
                failures.append(f"forbidden claim present: {phrase}")
        return failures

    @staticmethod
    def _build_summary(results: list[TutorEvalCaseResult]) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "total_cases": len({result.case_id for result in results}),
            "total_runs": len(results),
            "by_version": {},
        }
        for version in ("legacy", "v2"):
            version_results = [result for result in results if result.graph_version == version]
            if not version_results:
                continue
            summary["by_version"][version] = {
                "total": len(version_results),
                "contract_passed": sum(1 for result in version_results if result.contract_passed),
            }
        return summary

    @staticmethod
    def _build_comparisons(results: list[TutorEvalCaseResult]) -> list[TutorEvalComparison]:
        indexed: dict[tuple[str, str], TutorEvalCaseResult] = {
            (result.case_id, result.graph_version): result for result in results
        }
        comparisons: list[TutorEvalComparison] = []
        case_ids = sorted({result.case_id for result in results})
        for case_id in case_ids:
            legacy = indexed.get((case_id, "legacy"))
            v2 = indexed.get((case_id, "v2"))
            if legacy is None or v2 is None:
                continue
            differing_fields: list[str] = []
            if legacy.observed_tool_names != v2.observed_tool_names:
                differing_fields.append("tool_names")
            if legacy.observed_completion_mode != v2.observed_completion_mode:
                differing_fields.append("completion_mode")
            if legacy.contract_passed != v2.contract_passed:
                differing_fields.append("contract_passed")
            if legacy.observed_intent != v2.observed_intent:
                differing_fields.append("intent")
            comparisons.append(
                TutorEvalComparison(
                    case_id=case_id,
                    category=legacy.category,
                    differing_fields=differing_fields,
                    legacy_contract_passed=legacy.contract_passed,
                    v2_contract_passed=v2.contract_passed,
                )
            )
        return comparisons


def _history_entry_to_message(entry: dict[str, str]) -> BaseMessage:
    role = entry.get("role")
    content = entry.get("content", "")
    if role == "assistant":
        return AIMessage(content=content)
    if role == "system":
        return SystemMessage(content=content)
    return HumanMessage(content=content)


def _message_text(message: BaseMessage) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Tutor graph evaluations.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--mode", choices=["legacy", "v2", "both"], default="both")
    parser.add_argument("--output-dir", type=Path, default=Path("eval_outputs") / "tutor")
    args = parser.parse_args()

    dataset = load_tutor_eval_dataset(args.dataset)
    runner = TutorEvalRunner(dataset)
    report = runner.run(mode=args.mode)
    paths = runner.write_report(report, args.output_dir)

    print(report.to_markdown())
    print(f"JSON report: {paths['json']}")
    print(f"Markdown report: {paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
