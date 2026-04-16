"""
Flashcard Deduplication Service

Handles deduplication of flashcards to prevent duplicates within a batch
and across a course.
"""

import hashlib
import logging
from difflib import SequenceMatcher
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, collapse whitespace."""
    return ' '.join(text.lower().split())


class FlashcardDeduplicationService:
    """Service handling flashcard deduplication."""

    @staticmethod
    def deduplicate(
        new_cards: List[Dict[str, Any]],
        existing_fronts: List[str],
        similarity_threshold: float = 0.85
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Remove cards with fronts similar to existing cards or each other.
        
        Optimized two-phase approach:
        1. Phase 1 (O(n)): Exact match via normalized hash - catches identical cards
        2. Phase 2 (O(k*m)): Fuzzy match for non-exact matches against ALL existing fronts
        
        The hash-based exact matching in Phase 1 catches most duplicates in O(1),
        reducing the number of expensive fuzzy comparisons needed in Phase 2.
        Fuzzy matching still checks against all existing cards to ensure complete
        course-wide deduplication.
        
        Args:
            new_cards: Newly generated cards to filter
            existing_fronts: Fronts of existing cards (from Anki or session) - all cards in course
            similarity_threshold: Minimum similarity ratio to consider duplicate (0-1)
                                 Default 0.85 catches near-duplicates while avoiding false positives.
        
        Returns:
            Tuple of (unique_cards, removed_count)
        """
        if not new_cards:
            return [], 0
        
        # Phase 1: Build hash index for O(1) exact match lookup
        existing_normalized = set()
        existing_hashes = set()
        
        # Pre-normalize all existing fronts for faster fuzzy comparison
        existing_fronts_normalized = []
        for front in existing_fronts:
            normalized = _normalize_text(front)
            existing_normalized.add(normalized)
            existing_hashes.add(hashlib.md5(normalized.encode()).hexdigest())
            existing_fronts_normalized.append(normalized)
        
        unique_cards = []
        new_normalized = set()  # Track normalized fronts of newly added cards
        new_fronts_normalized = []  # For fuzzy checking against new cards
        
        for card in new_cards:
            card_front = card["front"]
            normalized_front = _normalize_text(card_front)
            card_hash = hashlib.md5(normalized_front.encode()).hexdigest()
            
            # Phase 1: Exact match check (O(1))
            if card_hash in existing_hashes or normalized_front in existing_normalized:
                logger.debug(f"Exact duplicate detected: '{card_front[:50]}...'")
                continue
            
            # Also check against already-added new cards (exact)
            if normalized_front in new_normalized:
                logger.debug(f"Duplicate within batch: '{card_front[:50]}...'")
                continue
            
            # Phase 2: Fuzzy match against ALL existing fronts in the course
            is_duplicate = False
            
            # Check against all existing fronts (using pre-normalized versions)
            for existing_normalized_front in existing_fronts_normalized:
                ratio = SequenceMatcher(None, normalized_front, existing_normalized_front).ratio()
                if ratio >= similarity_threshold:
                    is_duplicate = True
                    logger.debug(f"Fuzzy duplicate (ratio={ratio:.2f}): '{card_front[:50]}...'")
                    break
            
            # Check against already-added new cards (fuzzy)
            if not is_duplicate:
                for added_normalized in new_fronts_normalized:
                    ratio = SequenceMatcher(None, normalized_front, added_normalized).ratio()
                    if ratio >= similarity_threshold:
                        is_duplicate = True
                        logger.debug(f"Fuzzy duplicate within batch (ratio={ratio:.2f}): '{card_front[:50]}...'")
                        break
            
            if not is_duplicate:
                unique_cards.append(card)
                new_normalized.add(normalized_front)
                new_fronts_normalized.append(normalized_front)
                existing_hashes.add(card_hash)  # Add to prevent exact duplicates in subsequent iterations
        
        removed_count = len(new_cards) - len(unique_cards)
        if removed_count > 0:
            logger.info(f"Deduplication: removed {removed_count} cards ({len(unique_cards)} unique)")
        
        return unique_cards, removed_count
