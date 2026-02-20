"""
Supabase adapter package — concrete implementations of all repository Protocols.

Usage:
    from app.adapters.supabase import (
        get_supabase_client,
        SupabaseFileStorageAdapter,
        SupabaseMessageAdapter,
        SupabaseCourseAdapter,
        SupabaseMaterialAdapter,
        SupabasePageAnalysisAdapter,
        SupabaseFlashcardAdapter,
        SupabaseKnowledgeAdapter,
    )

All adapters accept a ``supabase.Client`` via constructor injection.
"""

from app.adapters.supabase.client import get_supabase_client
from app.adapters.supabase.file_storage_adapter import SupabaseFileStorageAdapter
from app.adapters.supabase.message_adapter import SupabaseMessageAdapter
from app.adapters.supabase.course_adapter import SupabaseCourseAdapter
from app.adapters.supabase.material_adapter import SupabaseMaterialAdapter
from app.adapters.supabase.page_analysis_adapter import SupabasePageAnalysisAdapter
from app.adapters.supabase.flashcard_adapter import SupabaseFlashcardAdapter
from app.adapters.supabase.knowledge_adapter import SupabaseKnowledgeAdapter

__all__ = [
    "get_supabase_client",
    "SupabaseFileStorageAdapter",
    "SupabaseMessageAdapter",
    "SupabaseCourseAdapter",
    "SupabaseMaterialAdapter",
    "SupabasePageAnalysisAdapter",
    "SupabaseFlashcardAdapter",
    "SupabaseKnowledgeAdapter",
]
