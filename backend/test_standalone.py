"""
Standalone Pre-Migration Tests

Tests the core logic WITHOUT importing app modules that require heavy dependencies.
Tests deduplication function and tag extraction by copying the implementations.

Run with: python test_standalone.py
"""

import sys
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
# Copy of the functions we want to test (from flashcard_agent.py)
# =============================================================================

def deduplicate_flashcards(
    new_cards: List[Dict[str, Any]],
    existing_fronts: List[str],
    similarity_threshold: float = 0.85
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Remove cards with fronts similar to existing cards or each other.
    """
    unique_cards = []
    all_fronts = list(existing_fronts)
    
    for card in new_cards:
        card_front_lower = card["front"].lower().strip()
        is_duplicate = False
        
        for existing_front in all_fronts:
            ratio = SequenceMatcher(None, card_front_lower, existing_front.lower().strip()).ratio()
            if ratio >= similarity_threshold:
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_cards.append(card)
            all_fronts.append(card["front"])
    
    removed_count = len(new_cards) - len(unique_cards)
    return unique_cards, removed_count


# =============================================================================
# Copy of tag extraction functions (from storage.py)
# =============================================================================

def extract_source_from_tags(tags: List[str]) -> Optional[str]:
    """Extract page_analysis_id from tags (source:uuid format)."""
    if not tags:
        return None
    for tag in tags:
        if tag.startswith("source:"):
            return tag[7:]
    return None


def extract_page_from_tags(tags: List[str]) -> Optional[int]:
    """Extract page number from tags (page:N format)."""
    if not tags:
        return None
    for tag in tags:
        if tag.startswith("page:"):
            try:
                return int(tag[5:])
            except ValueError:
                pass
    return None


# =============================================================================
# Tests for deduplicate_flashcards
# =============================================================================

@test("deduplicate_flashcards - exact duplicates removed")
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


@test("deduplicate_flashcards - similar duplicates removed (>85% similarity)")
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


@test("deduplicate_flashcards - case insensitive matching")
def test_dedup_case_insensitive():
    existing = ["WHAT IS PYTHON?"]
    new_cards = [
        {"front": "what is python?", "back": "A language"},
        {"front": "What Is Python?", "back": "A language"},
    ]
    
    unique, removed = deduplicate_flashcards(new_cards, existing)
    
    assert removed == 2, f"Expected 2 removed (case insensitive), got {removed}"
    print(f"   - Case-insensitive matching works: removed {removed}")


@test("deduplicate_flashcards - self-deduplication within batch")
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


@test("deduplicate_flashcards - whitespace handling")
def test_dedup_whitespace():
    existing = ["  What is Python?  "]
    new_cards = [
        {"front": "What is Python?", "back": "Lang"},  # Should match (stripped)
    ]
    
    unique, removed = deduplicate_flashcards(new_cards, existing)
    
    assert removed == 1, f"Expected 1 removed (whitespace stripped), got {removed}"
    print("   - Whitespace stripping works")


@test("deduplicate_flashcards - empty inputs")
def test_dedup_empty():
    # Empty new cards
    unique1, removed1 = deduplicate_flashcards([], ["existing"])
    assert len(unique1) == 0 and removed1 == 0
    
    # Empty existing
    new_cards = [{"front": "Test", "back": "Test"}]
    unique2, removed2 = deduplicate_flashcards(new_cards, [])
    assert len(unique2) == 1 and removed2 == 0
    
    print("   - Empty inputs handled correctly")


@test("deduplicate_flashcards - custom threshold")
def test_dedup_threshold():
    # "France" vs "Germany" is ~89% similar, so we need different test strings
    existing = ["What is photosynthesis?"]
    new_cards = [
        {"front": "How does mitochondria work?", "back": "..."},  # Very different
    ]
    
    # Check similarity first
    ratio = SequenceMatcher(None, existing[0].lower(), new_cards[0]["front"].lower()).ratio()
    print(f"   - Similarity: {ratio:.2f}")
    
    # With 0.85 threshold, should NOT be removed (very different questions)
    unique_85, removed_85 = deduplicate_flashcards(new_cards, existing, similarity_threshold=0.85)
    assert removed_85 == 0, f"Should not remove at 0.85 threshold, ratio is {ratio:.2f}"
    
    # Test with a very similar string
    existing2 = ["What is the definition of photosynthesis?"]
    new_cards2 = [
        {"front": "What is the definition of photosynthesis", "back": "..."},  # Missing ?
    ]
    
    # Should be removed at 0.85 (very similar)
    unique2, removed2 = deduplicate_flashcards(new_cards2, existing2, similarity_threshold=0.85)
    assert removed2 == 1, "Should remove near-identical strings"
    
    print("   - Custom thresholds work correctly")


@test("deduplicate_flashcards - preserves card data")
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
# Tests for tag extraction
# =============================================================================

@test("extract_source_from_tags - valid source")
def test_extract_source_valid():
    tags = ["page:5", "source:abc-123-def", "topic:math"]
    result = extract_source_from_tags(tags)
    assert result == "abc-123-def", f"Expected 'abc-123-def', got {result}"
    print(f"   - Extracted source: {result}")


@test("extract_source_from_tags - no source tag")
def test_extract_source_missing():
    result = extract_source_from_tags(["page:1", "topic:science"])
    assert result is None
    print("   - Returns None when no source tag")


@test("extract_source_from_tags - empty/None")
def test_extract_source_empty():
    assert extract_source_from_tags([]) is None
    assert extract_source_from_tags(None) is None
    print("   - Handles empty/None correctly")


@test("extract_page_from_tags - valid page")
def test_extract_page_valid():
    tags = ["page:42", "source:uuid", "topic:history"]
    result = extract_page_from_tags(tags)
    assert result == 42, f"Expected 42, got {result}"
    print(f"   - Extracted page: {result}")


@test("extract_page_from_tags - no page tag")
def test_extract_page_missing():
    result = extract_page_from_tags(["source:uuid", "topic:science"])
    assert result is None
    print("   - Returns None when no page tag")


@test("extract_page_from_tags - invalid page number")
def test_extract_page_invalid():
    result = extract_page_from_tags(["page:abc"])
    assert result is None
    print("   - Handles invalid page number gracefully")


@test("extract_page_from_tags - page zero")
def test_extract_page_zero():
    result = extract_page_from_tags(["page:0"])
    assert result == 0
    print("   - Handles page 0 correctly")


# =============================================================================
# Test similarity calculation directly
# =============================================================================

@test("SequenceMatcher similarity scores")
def test_similarity_scores():
    test_cases = [
        ("What is Python?", "What is Python?", 1.0),
        ("What is Python?", "what is python?", 1.0),  # Case insensitive
        ("What is Python?", "What is Python", 0.96),  # Missing ?
        ("What is the capital of France?", "What is the capital of Germany?", 0.82),
        ("Hello world", "Goodbye universe", 0.22),
    ]
    
    for s1, s2, expected_min in test_cases:
        ratio = SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
        print(f"   - '{s1[:30]}' vs '{s2[:30]}': {ratio:.2f}")
        if expected_min == 1.0:
            assert ratio == 1.0, f"Expected exactly 1.0 for identical strings"
        else:
            assert abs(ratio - expected_min) < 0.1, f"Expected ~{expected_min}, got {ratio}"


# =============================================================================
# Run All Tests
# =============================================================================

def main():
    print("\n" + "="*60)
    print("STANDALONE PRE-MIGRATION TESTS")
    print("Testing deduplication & tag extraction logic")
    print("(No app imports - pure Python)")
    print("="*60)
    
    tests = [
        # Deduplication
        test_dedup_exact,
        test_dedup_similar,
        test_dedup_case_insensitive,
        test_dedup_self,
        test_dedup_whitespace,
        test_dedup_empty,
        test_dedup_threshold,
        test_dedup_preserves_data,
        
        # Tag extraction
        test_extract_source_valid,
        test_extract_source_missing,
        test_extract_source_empty,
        test_extract_page_valid,
        test_extract_page_missing,
        test_extract_page_invalid,
        test_extract_page_zero,
        
        # Similarity
        test_similarity_scores,
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
        print("\n🎉 All standalone tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
