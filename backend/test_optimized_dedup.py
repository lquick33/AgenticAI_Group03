"""
Tests for Optimized Flashcard Deduplication

This tests the new hash-based deduplication that was added for performance optimization.
Run with: python test_optimized_dedup.py
"""

import sys
import hashlib
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional, Tuple

# Track test results
results = {"passed": 0, "failed": 0}


def test(name: str):
    """Decorator for test functions."""
    def decorator(func):
        def wrapper():
            try:
                print(f"\n{'='*60}")
                print(f"TEST: {name}")
                print('='*60)
                func()
                results["passed"] += 1
                print(f"✅ PASSED: {name}")
            except Exception as e:
                results["failed"] += 1
                print(f"❌ FAILED: {name}")
                print(f"   Error: {e}")
                import traceback
                traceback.print_exc()
        return wrapper
    return decorator


# =============================================================================
# Copy of the OPTIMIZED deduplication function (from flashcard_agent.py)
# =============================================================================

import logging
logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, collapse whitespace."""
    return ' '.join(text.lower().split())


def deduplicate_flashcards(
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
            print(f"   [DEBUG] Exact duplicate detected: '{card_front[:50]}...'")
            continue
        
        # Also check against already-added new cards (exact)
        if normalized_front in new_normalized:
            print(f"   [DEBUG] Duplicate within batch: '{card_front[:50]}...'")
            continue
        
        # Phase 2: Fuzzy match against ALL existing fronts in the course
        is_duplicate = False
        
        # Check against all existing fronts (using pre-normalized versions)
        for existing_normalized_front in existing_fronts_normalized:
            ratio = SequenceMatcher(None, normalized_front, existing_normalized_front).ratio()
            if ratio >= similarity_threshold:
                is_duplicate = True
                print(f"   [DEBUG] Fuzzy duplicate (ratio={ratio:.2f}): '{card_front[:50]}...'")
                break
        
        # Check against already-added new cards (fuzzy)
        if not is_duplicate:
            for added_normalized in new_fronts_normalized:
                ratio = SequenceMatcher(None, normalized_front, added_normalized).ratio()
                if ratio >= similarity_threshold:
                    is_duplicate = True
                    print(f"   [DEBUG] Fuzzy duplicate within batch (ratio={ratio:.2f}): '{card_front[:50]}...'")
                    break
        
        if not is_duplicate:
            unique_cards.append(card)
            new_normalized.add(normalized_front)
            new_fronts_normalized.append(normalized_front)
            existing_hashes.add(card_hash)  # Add to prevent exact duplicates in subsequent iterations
    
    removed_count = len(new_cards) - len(unique_cards)
    if removed_count > 0:
        print(f"   [INFO] Deduplication: removed {removed_count} cards ({len(unique_cards)} unique)")
    
    return unique_cards, removed_count


# =============================================================================
# Basic Tests (same as before, but using new implementation)
# =============================================================================

@test("Exact duplicates removed")
def test_dedup_exact():
    existing = ["What is Python?", "What is JavaScript?"]
    new_cards = [
        {"front": "What is Python?", "back": "A programming language"},
        {"front": "What is Rust?", "back": "A systems language"},
    ]
    
    unique, removed = deduplicate_flashcards(new_cards, existing)
    
    assert removed == 1, f"Expected 1 removed, got {removed}"
    assert len(unique) == 1, f"Expected 1 unique, got {len(unique)}"
    assert unique[0]["front"] == "What is Rust?"
    print(f"   - Removed {removed} exact duplicate(s)")
    print(f"   - Kept {len(unique)} unique card(s)")


@test("Similar duplicates removed (>85% similarity)")
def test_dedup_similar():
    existing = ["What is the capital of France?"]
    new_cards = [
        {"front": "What is the capital of France", "back": "Paris"},  # 97% similar
        {"front": "Explain photosynthesis", "back": "..."},  # Unique
    ]
    
    unique, removed = deduplicate_flashcards(new_cards, existing, similarity_threshold=0.85)
    
    print(f"   - Input: {len(new_cards)} cards, Existing: {len(existing)} fronts")
    print(f"   - Removed: {removed}, Kept: {len(unique)}")
    
    assert removed == 1, f"Expected 1 similar removed, got {removed}"
    assert len(unique) == 1
    assert "photosynthesis" in unique[0]["front"]


@test("Case insensitive matching")
def test_dedup_case_insensitive():
    existing = ["WHAT IS PYTHON?"]
    new_cards = [
        {"front": "what is python?", "back": "A language"},
        {"front": "What Is Python?", "back": "A language"},
    ]
    
    unique, removed = deduplicate_flashcards(new_cards, existing)
    
    assert removed == 2, f"Expected 2 removed (case insensitive), got {removed}"
    print(f"   - Case-insensitive matching works: removed {removed}")


@test("Self-deduplication within batch")
def test_dedup_self():
    existing = []
    new_cards = [
        {"front": "What is AI?", "back": "Artificial Intelligence"},
        {"front": "What is AI?", "back": "Machine learning subset"},
        {"front": "What is ML?", "back": "Machine Learning"},
    ]
    
    unique, removed = deduplicate_flashcards(new_cards, existing)
    
    assert removed == 1, f"Expected 1 self-duplicate removed, got {removed}"
    assert len(unique) == 2
    print(f"   - Self-deduplication works: removed {removed} from batch")


@test("Whitespace handling with normalization")
def test_dedup_whitespace():
    existing = ["  What   is   Python?  "]  # Extra whitespace
    new_cards = [
        {"front": "What is Python?", "back": "Lang"},  # Should match (normalized)
    ]
    
    unique, removed = deduplicate_flashcards(new_cards, existing)
    
    assert removed == 1, f"Expected 1 removed (whitespace normalized), got {removed}"
    print("   - Whitespace normalization works")


@test("Empty inputs")
def test_dedup_empty():
    # Empty new cards
    unique1, removed1 = deduplicate_flashcards([], ["existing"])
    assert len(unique1) == 0 and removed1 == 0
    
    # Empty existing
    new_cards = [{"front": "Test", "back": "Test"}]
    unique2, removed2 = deduplicate_flashcards(new_cards, [])
    assert len(unique2) == 1 and removed2 == 0
    
    print("   - Empty inputs handled correctly")


@test("Preserves card data")
def test_dedup_preserves_data():
    existing = []
    new_cards = [
        {
            "front": "Test Question",
            "back": "Test Answer",
            "tags": ["tag1", "page:5", "source:abc-123"],
            "source_page_analysis_id": "abc-123"
        }
    ]
    
    unique, removed = deduplicate_flashcards(new_cards, existing)
    
    assert len(unique) == 1
    assert unique[0]["back"] == "Test Answer"
    assert unique[0]["tags"] == ["tag1", "page:5", "source:abc-123"]
    assert unique[0]["source_page_analysis_id"] == "abc-123"
    print("   - All card data preserved correctly")


# =============================================================================
# Course-Wide Deduplication Tests (ensuring ALL lectures are checked)
# =============================================================================

@test("Deduplication checks against ALL existing cards (not just recent)")
def test_dedup_checks_all_cards():
    """
    Verify that deduplication checks against ALL existing cards,
    not just the last N. This is crucial for course-wide deduplication.
    """
    # Simulate 500 existing cards from various lectures
    existing = [f"Lecture {i} Question {j}" for i in range(1, 6) for j in range(1, 101)]
    print(f"   - Simulating {len(existing)} existing cards across 5 lectures")
    
    # New card that's similar to a card from the FIRST lecture (position 0)
    new_cards = [
        {"front": "Lecture 1 Question 1", "back": "..."},  # Duplicate of first card
        {"front": "Lecture 5 Question 100", "back": "..."},  # Duplicate of last card
        {"front": "Brand new question", "back": "..."},  # Unique
    ]
    
    unique, removed = deduplicate_flashcards(new_cards, existing)
    
    assert removed == 2, f"Expected 2 removed (first and last), got {removed}"
    assert len(unique) == 1
    assert unique[0]["front"] == "Brand new question"
    print(f"   - Correctly detected duplicates from first AND last cards")
    print(f"   - Course-wide deduplication working correctly")


@test("Fuzzy matching works across all lectures")
def test_fuzzy_match_all_lectures():
    """
    Verify that fuzzy matching (not just exact) works across all lectures.
    """
    existing = [
        "What is the definition of osmosis?",  # From Lecture 1
        "Explain the process of photosynthesis",  # From Lecture 50
        "What are the key components of a cell?",  # From Lecture 100
    ]
    
    new_cards = [
        {"front": "What is the definition of osmosis", "back": "..."},  # 98% similar (missing ?)
        {"front": "Explain the process of photosynthesis?", "back": "..."},  # 99% similar (extra ?)
        {"front": "What are the key components of a cell", "back": "..."},  # 98% similar (missing ?)
        {"front": "Define the structure of mitochondria and its functions", "back": "..."},  # Truly unique
    ]
    
    unique, removed = deduplicate_flashcards(new_cards, existing, similarity_threshold=0.85)
    
    assert removed == 3, f"Expected 3 fuzzy duplicates removed, got {removed}"
    assert len(unique) == 1
    assert "mitochondria" in unique[0]["front"]
    print(f"   - Fuzzy matching works across all existing cards")


@test("Large dataset performance (1000+ cards)")
def test_large_dataset():
    """
    Test with a large dataset to ensure the optimization doesn't break functionality.
    """
    import time
    import random
    import string
    
    # 1000 existing cards with varied content
    existing = [f"Existing card {i}: What is the definition of concept-{i}?" for i in range(1000)]
    
    # Generate truly unique strings using random content
    random.seed(42)  # For reproducibility
    def random_string():
        words = ['analyze', 'explain', 'describe', 'compare', 'contrast', 'define', 
                 'structure', 'function', 'mechanism', 'process', 'system', 'method']
        topics = ['biology', 'chemistry', 'physics', 'math', 'history', 'geography',
                  'economics', 'psychology', 'sociology', 'literature', 'art', 'music']
        return f"{random.choice(words).capitalize()} the {random.choice(topics)} of {random.choice(words)}ing"
    
    # 50 new cards - mix of duplicates and truly unique
    new_cards = []
    for i in range(25):
        # 25 exact duplicates (should be caught by hash)
        new_cards.append({"front": f"Existing card {i}: What is the definition of concept-{i}?", "back": "..."})
    for i in range(25):
        # 25 truly unique cards with very different content
        new_cards.append({"front": f"{random_string()} #{i}: {random_string()}", "back": "..."})
    
    start_time = time.time()
    unique, removed = deduplicate_flashcards(new_cards, existing)
    elapsed = time.time() - start_time
    
    assert removed == 25, f"Expected 25 duplicates removed, got {removed}"
    assert len(unique) == 25, f"Expected 25 unique, got {len(unique)}"
    
    print(f"   - Processed {len(new_cards)} new cards against {len(existing)} existing in {elapsed:.3f}s")
    print(f"   - Removed {removed} duplicates, kept {len(unique)} unique")


# =============================================================================
# Edge Cases
# =============================================================================

@test("Hash-based exact match vs fuzzy match distinction")
def test_hash_vs_fuzzy():
    """
    Ensure that hash-based exact matching catches exact duplicates,
    and only truly different cards are kept.
    """
    existing = ["What is the definition of photosynthesis in plant biology?"]
    new_cards = [
        {"front": "What is the definition of photosynthesis in plant biology?", "back": "..."},  # Exact duplicate
        {"front": "Explain how quantum mechanics affects particle behavior", "back": "..."},  # Completely different
    ]
    
    unique, removed = deduplicate_flashcards(new_cards, existing)
    
    assert removed == 1, f"Expected 1 removed, got {removed}"
    assert len(unique) == 1
    assert "quantum" in unique[0]["front"]
    print("   - Hash-based matching correctly identifies exact duplicates")
    print("   - Completely different cards are correctly kept")


@test("Unicode and special characters")
def test_unicode():
    """Test handling of unicode and special characters."""
    existing = ["Was ist die Hauptstadt von Deutschland?", "什么是机器学习?"]
    new_cards = [
        {"front": "Was ist die Hauptstadt von Deutschland", "back": "Berlin"},  # Similar
        {"front": "什么是机器学习", "back": "Machine Learning"},  # Similar
        {"front": "Quelle est la capitale de la France?", "back": "Paris"},  # Unique
    ]
    
    unique, removed = deduplicate_flashcards(new_cards, existing, similarity_threshold=0.85)
    
    assert removed == 2, f"Expected 2 removed, got {removed}"
    assert len(unique) == 1
    print("   - Unicode characters handled correctly")


# =============================================================================
# Run All Tests
# =============================================================================

def main():
    print("\n" + "="*60)
    print("OPTIMIZED DEDUPLICATION TESTS")
    print("Testing hash-based optimization + course-wide deduplication")
    print("="*60)
    
    tests = [
        # Basic tests
        test_dedup_exact,
        test_dedup_similar,
        test_dedup_case_insensitive,
        test_dedup_self,
        test_dedup_whitespace,
        test_dedup_empty,
        test_dedup_preserves_data,
        
        # Course-wide tests (critical!)
        test_dedup_checks_all_cards,
        test_fuzzy_match_all_lectures,
        test_large_dataset,
        
        # Edge cases
        test_hash_vs_fuzzy,
        test_unicode,
    ]
    
    for test_func in tests:
        test_func()
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print("="*60)
    
    if results['failed'] > 0:
        print("\n⚠️  Some tests failed.")
        sys.exit(1)
    else:
        print("\n🎉 All optimized deduplication tests passed!")
        print("Course-wide deduplication is working correctly.")
        sys.exit(0)


if __name__ == "__main__":
    main()
