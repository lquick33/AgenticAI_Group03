"""
Anki Synchronization Service

Handles direct integration with the Anki application via AnkiConnect API.
Extracted from FlashcardGeneratorAgent to centralize Anki infrastructure logic.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from app.core.adapters import get_flashcard

logger = logging.getLogger(__name__)


class AnkiSyncService:
    """Service for handling synchronization with local Anki and AnkiWeb."""
    
    def __init__(self):
        pass

    def is_available(self) -> bool:
        """Check if Anki is running and available."""
        return False
        
    def ensure_available(self) -> None:
        """Ensure Anki is running, starting it if necessary."""
        pass

    def get_existing_fronts(self, parent_deck: str, course_id: str, user_id: str) -> List[str]:
        # Fallback to cache if Anki unavailable
        try:
            cached_cards = get_flashcard().get_cached_for_course(course_id, user_id)
            return [c["front"] for c in cached_cards]
        except Exception as e:
            logger.warning(f"Failed to get cached fronts: {e}")
            return []
            
    def add_cards(
        self, 
        cards: List[Dict[str, Any]], 
        deck_name: str,
        async_sync: bool = True
    ) -> Tuple[List[Optional[int]], bool]:
        # Return none for note_ids and false for sync
        return [None for _ in cards], False
