"""
Anki Integration Service

Provides AnkiConnect API wrapper for:
- Reading study statistics
- Creating flashcards
- Syncing with AnkiWeb
- Managing the headless Anki Docker container
- Tracking knowledge levels per deck and course
"""

from .client import (
    AnkiClient, 
    AnkiError, 
    AnkiConnectionError,
    DeckStats,
    ReviewStats,
    CardKnowledge,
    DeckKnowledge,
    CourseKnowledge,
)
from .knowledge_service import (
    KnowledgeService,
    LectureKnowledge,
    CourseKnowledgeResult,
    build_deck_name,
    parse_deck_name,
)

__all__ = [
    # Client
    "AnkiClient", 
    "AnkiError",
    "AnkiConnectionError",
    # Data classes
    "DeckStats",
    "ReviewStats",
    "CardKnowledge",
    "DeckKnowledge",
    "CourseKnowledge",
    # Knowledge service
    "KnowledgeService",
    "LectureKnowledge",
    "CourseKnowledgeResult",
    "build_deck_name",
    "parse_deck_name",
]
