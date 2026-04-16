from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.config import settings

TutorGraphVersion = Literal["legacy", "v2"]
VALID_TUTOR_GRAPH_VERSIONS: tuple[TutorGraphVersion, TutorGraphVersion] = ("legacy", "v2")


@dataclass(frozen=True)
class TutorGraphResolution:
    graph_version: TutorGraphVersion
    source: str


def normalize_tutor_graph_version(value: str | None) -> TutorGraphVersion | None:
    if value not in VALID_TUTOR_GRAPH_VERSIONS:
        return None
    return value


def resolve_tutor_graph_default_version() -> TutorGraphVersion:
    configured = normalize_tutor_graph_version(settings.TUTOR_GRAPH_DEFAULT_VERSION)
    if configured:
        return configured
    return "v2" if settings.TUTOR_GRAPH_V2_ENABLED else "legacy"


def resolve_tutor_graph_version(
    request_version: str | None,
    stored_version: str | None,
    *,
    allow_request_override: bool = True,
) -> TutorGraphResolution:
    normalized_request = normalize_tutor_graph_version(request_version)
    normalized_stored = normalize_tutor_graph_version(stored_version)

    if allow_request_override and normalized_request:
        return TutorGraphResolution(graph_version=normalized_request, source="request")
    if normalized_stored:
        return TutorGraphResolution(graph_version=normalized_stored, source="metadata")

    configured_default = normalize_tutor_graph_version(settings.TUTOR_GRAPH_DEFAULT_VERSION)
    if configured_default:
        return TutorGraphResolution(
            graph_version=configured_default,
            source="config_default",
        )

    return TutorGraphResolution(
        graph_version="v2" if settings.TUTOR_GRAPH_V2_ENABLED else "legacy",
        source="legacy_flag_fallback",
    )
