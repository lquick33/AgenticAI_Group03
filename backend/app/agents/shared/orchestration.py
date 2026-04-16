"""
Shared orchestration primitives for explicit graph-based agents.

These models are intentionally generic enough to be reused by future
agent refactors (for example QuickChat discovery/navigation flows),
while still matching the Tutor Graph V2 needs today.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


TutorIntent = Literal[
    "explain_current_page",
    "answer_followup",
    "needs_visual",
    "create_quiz",
    "clarify_missing_context",
]

TutorCapability = Literal[
    "page_analysis",
    "material_summary",
    "page_image",
    "quiz",
    "clarification",
]

TutorExecutionStrategy = Literal[
    "tool_augmented",
    "quiz",
    "clarify",
    "direct",
]

TutorVerificationStatus = Literal["accept", "revise", "clarify"]

TutorToolName = Literal[
    "get_page_analysis",
    "get_course_material_summary",
    "get_page_image",
    "create_quiz",
]


class TutorIntentDecision(BaseModel):
    """Structured planner output for a tutor turn."""

    intent: TutorIntent
    intent_confidence: float = Field(ge=0.0, le=1.0)
    required_capabilities: list[TutorCapability] = Field(default_factory=list)
    needs_verification: bool = False
    reason: str = Field(min_length=1)


class TutorExecutionPlan(BaseModel):
    """Structured execution contract passed into explicit subgraphs."""

    phase: Literal["tutoring", "quiz", "clarification"]
    answer_strategy: TutorExecutionStrategy
    tool_names: list[TutorToolName] = Field(default_factory=list)
    answer_focus: str = ""
    answer_constraints: str = ""


class TutorVerificationResult(BaseModel):
    """Verifier output for draft tutor responses."""

    status: TutorVerificationStatus
    issues: list[str] = Field(default_factory=list)
    reason: str = ""
    revised_answer: str | None = None


class PhaseScopedToolRegistry:
    """Maps phases to tool subsets for explicit graph nodes."""

    def __init__(
        self,
        tools_by_name: dict[str, Any],
        phase_map: dict[str, list[str]],
    ) -> None:
        self._tools_by_name = dict(tools_by_name)
        self._phase_map = {phase: list(tool_names) for phase, tool_names in phase_map.items()}

    def get_tools_for_phase(self, phase: str) -> list[Any]:
        return [
            self._tools_by_name[name]
            for name in self._phase_map.get(phase, [])
            if name in self._tools_by_name
        ]

    def get_tool_names_for_phase(self, phase: str) -> list[str]:
        return list(self._phase_map.get(phase, []))


def build_tool_call(
    name: str,
    args: dict[str, Any] | None = None,
    prefix: str = "tool",
) -> dict[str, Any]:
    """Create a LangChain-compatible tool call dict."""

    return {
        "id": f"{prefix}-{uuid4()}",
        "name": name,
        "args": args or {},
        "type": "tool_call",
    }
