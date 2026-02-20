"""
Repository Protocol definitions.

These Protocols define the contracts for all data access operations.
Concrete implementations (e.g., SupabaseCourseAdapter) satisfy
these contracts structurally via Python's Protocol typing.

Design by Contract:
    - Preconditions are documented in docstrings
    - Postconditions are enforced by return type annotations
    - Invariants are enforced by @runtime_checkable for isinstance() checks

NOTE: These protocols are aligned to the actual Supabase adapter
      implementations extracted from the production codebase.
"""

from typing import Protocol, Optional, List, Dict, Any, Tuple, runtime_checkable


# ---------------------------------------------------------------------------
# Page Analysis
# ---------------------------------------------------------------------------

@runtime_checkable
class PageAnalysisReader(Protocol):
    """
    Contract: read-only access to page analysis data.

    Consumers: TutorAgent, QuickChatAgent, Tools (get_page_analysis)
    Implementor: SupabasePageAnalysisAdapter
    """

    def get(
        self, course_material_id: str, page_number: int, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve analysis for a specific page.

        Preconditions:
            - course_material_id is a valid UUID string
            - page_number >= 1
            - user_id is a valid UUID string (ownership check)

        Postconditions:
            - Returns dict with keys {id, summary, key_terms, ...} or raises ValueError
        """
        ...

    def get_id(
        self, course_material_id: str, page_number: int, user_id: str
    ) -> Optional[str]:
        """Get page analysis ID (UUID) or None if not found."""
        ...

    def get_all_for_material(
        self, course_material_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all page analyses for a material, ordered by page_number.

        Postconditions:
            - Returns list ordered by page_number ascending
            - Empty list if material has no analyses
        """
        ...

    def get_for_range(
        self, course_material_id: str, user_id: str,
        start_page: int, end_page: int,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve analyses for a page range [start_page, end_page] inclusive.

        Preconditions:
            - 1 <= start_page <= end_page
        """
        ...


@runtime_checkable
class PageAnalysisWriter(Protocol):
    """
    Contract: write access to page analysis data.

    Consumers: PDFProcessor, EmbeddingService
    Implementor: SupabasePageAnalysisAdapter
    """

    def save(
        self,
        course_material_id: str,
        page_number: int,
        analysis: Any,  # SlideAnalysis Pydantic model
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Persist a page analysis.

        Postconditions:
            - Returns the created page_analysis record as dict
            - Row exists in page_analyses table
        """
        ...


@runtime_checkable
class PageAnalysisSearcher(Protocol):
    """
    Contract: semantic/hybrid search across page analyses.

    Consumers: QuickChatAgent (SearchTopicTool)
    Implementor: SupabasePageAnalysisAdapter
    """

    def search(
        self,
        user_id: str,
        query: str,
        language: str = "auto",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Multi-tier keyword search across page analyses."""
        ...

    def search_multi(
        self,
        user_id: str,
        queries: List[str],
        language: str = "auto",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Multi-keyword OR search with deduplication and score aggregation."""
        ...

    def search_hybrid(
        self,
        user_id: str,
        query: str,
        query_embedding: List[float],
        language: str = "auto",
        limit: int = 10,
        vector_weight: float = 0.6,
        keyword_weight: float = 0.4,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining vector similarity and full-text search.

        Postconditions:
            - Returns list of results ranked by RRF fusion score
            - Each result contains {material_id, page_number, summary, score, ...}
            - len(results) <= limit
        """
        ...

    def has_embeddings(self, user_id: str) -> bool:
        """Check if any page analyses for this user have embeddings."""
        ...


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------

@runtime_checkable
class CourseRepository(Protocol):
    """
    Contract: read operations for courses.

    Consumers: CourseRouter, agents needing course context
    Implementor: SupabaseCourseAdapter
    """

    def validate_user_exists(self, user_id: str) -> bool:
        """Validate that user exists in profiles table."""
        ...

    def get(self, user_id: str, course_id: str) -> Dict[str, Any]:
        """
        Get a single course by ID, scoped to user.

        Raises:
            ValueError: If course doesn't exist or doesn't belong to user
        """
        ...

    def get_with_materials(
        self, user_id: str, course_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a course with all its materials, or None if not found."""
        ...

    def get_counts(self, user_id: str) -> Tuple[int, int]:
        """Get (course_count, material_count) for a user."""
        ...

    def get_all_with_materials(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all courses and their materials for a user."""
        ...


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

@runtime_checkable
class MaterialRepository(Protocol):
    """
    Contract: CRUD + status management for course materials (PDFs).

    Consumers: MaterialRouter, PDFProcessor
    Implementor: SupabaseMaterialAdapter
    """

    def create(
        self,
        course_id: str,
        filename: str,
        file_path: str,
        user_id: str,
        page_count: int,
        file_type: str = "pdf",
    ) -> Dict[str, Any]:
        """
        Create a material record with status 'pending'.

        Postconditions:
            - Returns dict with {id, file_name, status: 'pending', ...}
        """
        ...

    def update_status(
        self, material_id: str, status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update processing status.

        Preconditions:
            - status in {'uploading', 'processing', 'completed', 'error'}
        """
        ...

    def update_summary(self, material_id: str, summary: str) -> None:
        """Update the global summary field of a course material."""
        ...

    def update_filename(self, material_id: str, filename: str) -> None:
        """Update the file_name field in the course_materials table."""
        ...

    def get_filename(
        self, material_id: str, user_id: str
    ) -> Optional[str]:
        """Get current filename for a material."""
        ...

    def get_for_naming(
        self, course_id: str, user_id: str,
        exclude_material_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get materials for context-aware naming."""
        ...

    def get_summary(
        self, course_material_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get material summary with caching."""
        ...

    def get_classification(
        self, material_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get material classification with caching."""
        ...

    def update_classification(
        self, material_id: str, classification: str,
        confidence: float, reasoning: str,
        override: bool = False,
    ) -> Dict[str, Any]:
        """Update material classification."""
        ...

    def delete(
        self, material_id: str, user_id: str,
        get_all_page_analyses_fn: Any = None,
    ) -> Dict[str, Any]:
        """Delete material and associated analyses/flashcards."""
        ...


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@runtime_checkable
class MessageRepository(Protocol):
    """
    Contract: message retrieval for page-scoped conversations.

    Consumers: FlashcardAgent, TutorAgent
    Implementor: SupabaseMessageAdapter
    """

    def get_for_page(
        self, page_analysis_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        """Get messages associated with a specific page analysis."""
        ...

    def get_for_pages_batch(
        self, page_ids: List[str], user_id: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Batch fetch messages for multiple pages in a single query.

        Performance optimization: Replaces N+1 queries with 2 queries total.
        """
        ...


# ---------------------------------------------------------------------------
# Flashcards
# ---------------------------------------------------------------------------

@runtime_checkable
class FlashcardRepository(Protocol):
    """
    Contract: flashcard CRUD and Anki cache operations.

    Consumers: FlashcardAgent, FlashcardRouter, endpoints.py
    Implementor: SupabaseFlashcardAdapter
    """

    def save_flashcards(
        self, flashcards: List[dict], user_id: str, course_id: str
    ) -> None:
        """Batch-insert flashcards."""
        ...

    def get_for_material(
        self, course_material_id: str, user_id: str,
        page_analysis_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """Get flashcards linked to page analyses of a material."""
        ...

    def cache_flashcards(
        self, cards: List[dict], anki_note_ids: List[int],
        user_id: str, deck_name: str,
        course_id: Optional[str] = None,
        synced_to_ankiweb: bool = False,
    ) -> None:
        """Cache flashcards after adding to Anki."""
        ...

    def get_cached_for_material(
        self, deck_name: str, user_id: str
    ) -> List[Dict[str, Any]]:
        """Get cached flashcards for a specific lecture deck."""
        ...

    def get_cached_for_course(
        self, course_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        """Get all cached flashcards for a course (all lectures)."""
        ...

    def get_cached_by_deck_pattern(
        self, deck_pattern: str, user_id: str
    ) -> List[Dict[str, Any]]:
        """Get cached flashcards matching a deck name pattern."""
        ...

    def delete_cached_for_deck(
        self, deck_name: str, user_id: str
    ) -> int:
        """Delete cached flashcards for a specific deck. Returns count."""
        ...

    def update_cached_deck_names(
        self, old_pattern: str, new_prefix: str,
        old_prefix: str, user_id: str,
    ) -> int:
        """Update deck names in cache when course or material is renamed."""
        ...

    def get_unsynced_count(self, user_id: str) -> int:
        """Get count of flashcards not yet synced to AnkiWeb."""
        ...

    def mark_as_synced(self, user_id: str) -> int:
        """Mark all unsynced flashcards as synced. Returns count."""
        ...

    def sync_cache_from_anki(
        self, parent_deck: str, user_id: str,
        course_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Pull changes from Anki into flashcard_cache."""
        ...

    def on_course_renamed(
        self, course_id: str, old_title: str,
        new_title: str, user_id: str,
    ) -> Dict[str, Any]:
        """Handle course rename — update all lecture decks in Anki and cache."""
        ...

    def on_material_renamed(
        self, material_id: str, old_file_name: str,
        new_file_name: str, user_id: str,
    ) -> Dict[str, Any]:
        """Handle material rename — update deck name in Anki and cache."""
        ...


# ---------------------------------------------------------------------------
# Quizzes
# ---------------------------------------------------------------------------

@runtime_checkable
class QuizRepository(Protocol):
    """
    Contract: quiz persistence and results.

    Consumers: QuizService, CreateQuizTool
    """

    def save(
        self,
        quiz_data: Any,  # QuizData Pydantic model
        material_id: str,
        user_id: str,
        **meta: Any,
    ) -> str:
        """
        Persist a quiz.

        Postconditions:
            - Returns the created quiz ID
        """
        ...

    def get(self, quiz_id: str) -> Optional[Dict[str, Any]]:
        """Get quiz by ID."""
        ...

    def save_result(self, quiz_id: str, result: Any) -> str:
        """
        Save a quiz submission result.

        Postconditions:
            - Returns the created quiz_result ID
        """
        ...


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@runtime_checkable
class ConversationRepository(Protocol):
    """
    Contract: conversation lifecycle management.

    Consumers: ChatService, SessionService
    """

    def get_or_create(
        self,
        user_id: str,
        session_type: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Get existing conversation or create a new one.

        Postconditions:
            - Returns dict with {id, user_id, session_type, metadata, ...}
            - Conversation always exists after call
        """
        ...

    def update_progress(
        self, conversation_id: str, last_page: int
    ) -> None:
        """
        Update the last visited page in conversation metadata.

        Preconditions:
            - last_page >= 1
        """
        ...


# ---------------------------------------------------------------------------
# File Storage
# ---------------------------------------------------------------------------

@runtime_checkable
class FileStorageRepository(Protocol):
    """
    Contract: binary file storage (PDFs, images, exports).

    Consumers: MaterialRouter, PDFProcessor
    Implementor: SupabaseFileStorageAdapter
    """

    def upload(
        self, file_bytes: bytes, filename: str, user_id: str,
        bucket_name: str = "course_materials",
    ) -> str:
        """
        Upload binary data to storage.

        Postconditions:
            - Returns the storage path of the uploaded file
        """
        ...

    def download(
        self, path: str, bucket_name: str = "course_materials"
    ) -> bytes:
        """Download file contents as bytes."""
        ...


# ---------------------------------------------------------------------------
# Knowledge Tracking (Anki integration, study history, deck mappings)
# ---------------------------------------------------------------------------

@runtime_checkable
class KnowledgeTrackingRepository(Protocol):
    """
    Contract: knowledge tracking, Anki deck/card mappings, and study history.

    Consumers: FlashcardAgent, FlashcardTaskService, AnkiRouter, endpoints.py
    Implementor: SupabaseKnowledgeAdapter
    """

    def save_deck_mapping(
        self,
        user_id: str,
        course_id: str,
        deck_name: str,
        course_material_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Save or update a course-to-deck mapping.

        Postconditions:
            - Returns the created/updated mapping record
            - Upserts on (user_id, deck_name) uniqueness
        """
        ...

    def get_deck_mappings_for_course(
        self, user_id: str, course_id: str
    ) -> List[Dict[str, Any]]:
        """Get all deck mappings for a course."""
        ...

    def save_anki_card_mapping(
        self,
        user_id: str,
        anki_note_id: int,
        deck_name: str,
        flashcard_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save a mapping between an Anki note and an agent-generated flashcard."""
        ...

    def save_knowledge_snapshot(
        self,
        user_id: str,
        deck_name: str,
        total_cards: int,
        new_cards: int,
        learning_cards: int,
        young_cards: int,
        mature_cards: int,
        suspended_cards: int = 0,
        avg_ease_factor: Optional[float] = None,
        avg_interval_days: Optional[float] = None,
        retention_rate: Optional[float] = None,
        mastery_score: Optional[float] = None,
        course_id: Optional[str] = None,
        course_material_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Save a knowledge snapshot for a deck.

        Postconditions:
            - Returns the created snapshot record
        """
        ...

    def get_latest_knowledge_snapshot(
        self, user_id: str, deck_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent knowledge snapshot for a deck."""
        ...

    def get_knowledge_snapshots_for_course(
        self, user_id: str, course_id: str, limit: int = 30
    ) -> List[Dict[str, Any]]:
        """Get recent knowledge snapshots for all decks in a course."""
        ...

    def upsert_study_history(
        self,
        user_id: str,
        study_date: str,
        cards_reviewed: int,
        time_spent_seconds: int = 0,
        again_count: int = 0,
        hard_count: int = 0,
        good_count: int = 0,
        easy_count: int = 0,
        new_cards: int = 0,
        review_cards: int = 0,
        relearn_cards: int = 0,
        avg_time_per_card_ms: int = 0,
    ) -> Dict[str, Any]:
        """
        Insert or update a study history entry for a specific date.

        Preconditions:
            - study_date in "yyyy-MM-dd" format
        """
        ...

    def sync_study_history(
        self, user_id: str, stats_list: list
    ) -> Dict[str, Any]:
        """
        Bulk sync study history from Anki.

        Postconditions:
            - Returns dict with {synced: int, errors: list}
        """
        ...

    def get_study_history(
        self, user_id: str, days: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Get study history for a user.

        Postconditions:
            - Returns list sorted by date ascending
            - len(result) <= days
        """
        ...
