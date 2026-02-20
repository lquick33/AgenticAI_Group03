"""
Adapter Registry — centralised lazy singletons for all repository adapters.

Every adapter is created **once** on first access using the shared Supabase
client.  Consumers import the accessor they need::

    from app.core.adapters import get_page_analysis, get_course
    result = get_page_analysis().get(material_id, page, user_id)

For tests, call ``reset()`` to clear all cached instances so that mocks
or alternative implementations can be injected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.adapters.supabase.file_storage_adapter import SupabaseFileStorageAdapter
    from app.adapters.supabase.course_adapter import SupabaseCourseAdapter
    from app.adapters.supabase.material_adapter import SupabaseMaterialAdapter
    from app.adapters.supabase.page_analysis_adapter import SupabasePageAnalysisAdapter
    from app.adapters.supabase.message_adapter import SupabaseMessageAdapter
    from app.adapters.supabase.flashcard_adapter import SupabaseFlashcardAdapter
    from app.adapters.supabase.knowledge_adapter import SupabaseKnowledgeAdapter

# ---------------------------------------------------------------------------
# Internal cache
# ---------------------------------------------------------------------------
_instances: dict[str, object] = {}


def _make(key: str):
    """Lazily construct an adapter and cache it."""
    if key not in _instances:
        from app.adapters.supabase.client import get_supabase_client
        from app.adapters.supabase import (
            SupabaseFileStorageAdapter,
            SupabaseCourseAdapter,
            SupabaseMaterialAdapter,
            SupabasePageAnalysisAdapter,
            SupabaseMessageAdapter,
            SupabaseFlashcardAdapter,
            SupabaseKnowledgeAdapter,
        )
        _constructors = {
            "file_storage": SupabaseFileStorageAdapter,
            "course": SupabaseCourseAdapter,
            "material": SupabaseMaterialAdapter,
            "page_analysis": SupabasePageAnalysisAdapter,
            "message": SupabaseMessageAdapter,
            "flashcard": SupabaseFlashcardAdapter,
            "knowledge": SupabaseKnowledgeAdapter,
        }
        client = get_supabase_client()
        _instances[key] = _constructors[key](client)
    return _instances[key]


# ---------------------------------------------------------------------------
# Public accessors (one per adapter)
# ---------------------------------------------------------------------------

def get_file_storage() -> "SupabaseFileStorageAdapter":
    return _make("file_storage")  # type: ignore[return-value]


def get_course() -> "SupabaseCourseAdapter":
    return _make("course")  # type: ignore[return-value]


def get_material() -> "SupabaseMaterialAdapter":
    return _make("material")  # type: ignore[return-value]


def get_page_analysis() -> "SupabasePageAnalysisAdapter":
    return _make("page_analysis")  # type: ignore[return-value]


def get_message() -> "SupabaseMessageAdapter":
    return _make("message")  # type: ignore[return-value]


def get_flashcard() -> "SupabaseFlashcardAdapter":
    return _make("flashcard")  # type: ignore[return-value]


def get_knowledge() -> "SupabaseKnowledgeAdapter":
    return _make("knowledge")  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Test helper
# ---------------------------------------------------------------------------

def reset() -> None:
    """Clear all cached adapter instances (call from test fixtures)."""
    _instances.clear()
