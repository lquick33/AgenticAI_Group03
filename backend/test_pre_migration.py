"""
Pre-Migration Tests for Flashcard Deduplication & Anki Integration

Tests that can run BEFORE the flashcard_cache migration is applied.
Run with: python test_pre_migration.py

Tests:
1. deduplicate_flashcards() - pure Python string similarity
2. Tag extraction functions - pure Python
3. AnkiClient new methods - requires Anki Docker running
4. Import checks - verify all modules load correctly
"""

import sys
import traceback
from typing import List, Dict, Any

# Track test results
results = {"passed": 0, "failed": 0, "skipped": 0}


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
                traceback.print_exc()
        return wrapper
    return decorator


# =============================================================================
# Test 1: Import Checks
# =============================================================================

@test("Import flashcard_agent module")
def test_import_flashcard_agent():
    from app.agents.flashcards.flashcard_agent import (
        FlashcardState,
        deduplicate_flashcards,
        FlashcardGeneratorAgent,
    )
    assert deduplicate_flashcards is not None
    print("   - deduplicate_flashcards imported")
    print("   - FlashcardState imported")
    print("   - FlashcardGeneratorAgent imported")


@test("Import storage module with new cache functions")
def test_import_storage():
    from app.services.storage import (
        cache_flashcards,
        get_cached_flashcards_for_material,
        get_cached_flashcards_for_course,
        extract_source_from_tags,
        extract_page_from_tags,
        on_course_renamed,
        on_material_renamed,
    )
    print("   - cache_flashcards imported")
    print("   - get_cached_flashcards_for_material imported")
    print("   - get_cached_flashcards_for_course imported")
    print("   - extract_source_from_tags imported")
    print("   - extract_page_from_tags imported")
    print("   - on_course_renamed imported")
    print("   - on_material_renamed imported")


@test("Import AnkiClient with new methods")
def test_import_anki_client():
    from app.services.anki.client import AnkiClient
    
    # Check new methods exist
    assert hasattr(AnkiClient, 'get_deck_card_fronts')
    assert hasattr(AnkiClient, 'rename_deck')
    assert hasattr(AnkiClient, 'delete_deck_with_cards')
    print("   - AnkiClient.get_deck_card_fronts exists")
    print("   - AnkiClient.rename_deck exists")
    print("   - AnkiClient.delete_deck_with_cards exists")


# =============================================================================
# Test 2: deduplicate_flashcards() Function
# =============================================================================

@test("deduplicate_flashcards - exact duplicates removed")
def test_dedup_exact():
    from app.agents.flashcards.flashcard_agent import deduplicate_flashcards
    
    existing = ["What is Python?", "What is JavaScript?"]
    new_cards = [
        {"front": "What is Python?", "back": "A programming language"},  # Exact dup
        {"front": "What is Rust?", "back": "A systems language"},  # Unique
    ]
    
    unique, removed = deduplicate_flashcards(new_cards, existing)
    
    assert removed == 1, f"Expected 1 removed, got {removed}"
    assert len(unique) == 1, f"Expected 1 unique, got {len(unique)}"
    assert unique[0]["front"] == "What is Rust?"
    print(f"   - Removed {removed} exact duplicate(s)")
    print(f"   - Kept {len(unique)} unique card(s)")


@test("deduplicate_flashcards - similar duplicates removed (>85% similarity)")
def test_dedup_similar():
    from app.agents.flashcards.flashcard_agent import deduplicate_flashcards
    
    existing = ["What is the capital of France?"]
    new_cards = [
        {"front": "What is the capital of France", "back": "Paris"},  # 97% similar (missing ?)
        {"front": "What is the capital of Germany?", "back": "Berlin"},  # ~85% similar
        {"front": "Explain photosynthesis", "back": "..."},  # Unique
    ]
    
    unique, removed = deduplicate_flashcards(new_cards, existing, similarity_threshold=0.85)
    
    print(f"   - Input: {len(new_cards)} cards, Existing: {len(existing)} fronts")
    print(f"   - Removed: {removed}, Kept: {len(unique)}")
    
    # The first two should be caught as similar
    assert removed >= 1, f"Expected at least 1 removed, got {removed}"


@test("deduplicate_flashcards - case insensitive matching")
def test_dedup_case_insensitive():
    from app.agents.flashcards.flashcard_agent import deduplicate_flashcards
    
    existing = ["WHAT IS PYTHON?"]
    new_cards = [
        {"front": "what is python?", "back": "A language"},  # Same, different case
        {"front": "What Is Python?", "back": "A language"},  # Same, different case
    ]
    
    unique, removed = deduplicate_flashcards(new_cards, existing)
    
    assert removed == 2, f"Expected 2 removed (case insensitive), got {removed}"
    print(f"   - Case-insensitive matching works: removed {removed}")


@test("deduplicate_flashcards - self-deduplication within batch")
def test_dedup_self():
    from app.agents.flashcards.flashcard_agent import deduplicate_flashcards
    
    existing = []  # No existing cards
    new_cards = [
        {"front": "What is AI?", "back": "Artificial Intelligence"},
        {"front": "What is AI?", "back": "Machine learning subset"},  # Dup of first
        {"front": "What is ML?", "back": "Machine Learning"},
    ]
    
    unique, removed = deduplicate_flashcards(new_cards, existing)
    
    assert removed == 1, f"Expected 1 self-duplicate removed, got {removed}"
    assert len(unique) == 2
    print(f"   - Self-deduplication works: removed {removed} from batch")


@test("deduplicate_flashcards - empty inputs")
def test_dedup_empty():
    from app.agents.flashcards.flashcard_agent import deduplicate_flashcards
    
    # Empty new cards
    unique1, removed1 = deduplicate_flashcards([], ["existing"])
    assert len(unique1) == 0 and removed1 == 0
    
    # Empty existing
    new_cards = [{"front": "Test", "back": "Test"}]
    unique2, removed2 = deduplicate_flashcards(new_cards, [])
    assert len(unique2) == 1 and removed2 == 0
    
    print("   - Empty inputs handled correctly")


# =============================================================================
# Test 3: Tag Extraction Functions
# =============================================================================

@test("extract_source_from_tags")
def test_extract_source():
    from app.services.storage import extract_source_from_tags
    
    # Valid source tag
    tags = ["page:5", "source:abc-123-def", "topic:math"]
    result = extract_source_from_tags(tags)
    assert result == "abc-123-def", f"Expected 'abc-123-def', got {result}"
    print(f"   - Extracted source: {result}")
    
    # No source tag
    result2 = extract_source_from_tags(["page:1", "topic:science"])
    assert result2 is None
    print("   - Returns None when no source tag")
    
    # Empty/None
    assert extract_source_from_tags([]) is None
    assert extract_source_from_tags(None) is None
    print("   - Handles empty/None correctly")


@test("extract_page_from_tags")
def test_extract_page():
    from app.services.storage import extract_page_from_tags
    
    # Valid page tag
    tags = ["page:42", "source:uuid", "topic:history"]
    result = extract_page_from_tags(tags)
    assert result == 42, f"Expected 42, got {result}"
    print(f"   - Extracted page: {result}")
    
    # No page tag
    result2 = extract_page_from_tags(["source:uuid", "topic:science"])
    assert result2 is None
    print("   - Returns None when no page tag")
    
    # Invalid page number
    result3 = extract_page_from_tags(["page:abc"])
    assert result3 is None
    print("   - Handles invalid page number gracefully")


# =============================================================================
# Test 4: AnkiClient Methods (requires Anki running)
# =============================================================================

@test("AnkiClient connection and version")
def test_anki_connection():
    from app.services.anki.client import AnkiClient
    
    anki = AnkiClient()
    version = anki.get_version()
    
    assert version is not None
    print(f"   - AnkiConnect version: {version}")


@test("AnkiClient.get_deck_card_fronts - query existing deck")
def test_anki_get_fronts():
    from app.services.anki.client import AnkiClient
    
    anki = AnkiClient()
    
    # Get all deck names first
    decks = anki.get_deck_names()
    print(f"   - Found {len(decks)} decks: {decks[:5]}..." if len(decks) > 5 else f"   - Found decks: {decks}")
    
    # Try to get fronts from Default deck (usually exists)
    if "Default" in decks:
        fronts = anki.get_deck_card_fronts("Default")
        print(f"   - Default deck has {len(fronts)} card fronts")
    
    # Test with non-existent deck
    fronts_empty = anki.get_deck_card_fronts("NonExistentDeck12345")
    assert fronts_empty == [], f"Expected empty list for non-existent deck, got {fronts_empty}"
    print("   - Non-existent deck returns empty list")


@test("AnkiClient.create_deck and add_notes")
def test_anki_create_and_add():
    from app.services.anki.client import AnkiClient
    
    anki = AnkiClient()
    
    # Create test deck
    test_deck = "TestDeck_PreMigration_Test"
    deck_id = anki.create_deck(test_deck)
    print(f"   - Created deck '{test_deck}' with ID: {deck_id}")
    
    # Add a test note
    notes = [{
        "deck": test_deck,
        "front": "Test Question - Pre Migration",
        "back": "Test Answer",
        "tags": ["test", "pre-migration", "page:1", "source:test-uuid"]
    }]
    
    note_ids = anki.add_notes(notes)
    print(f"   - Added note with ID: {note_ids}")
    
    # Verify we can get the front back
    fronts = anki.get_deck_card_fronts(test_deck)
    assert len(fronts) >= 1
    assert "Test Question - Pre Migration" in fronts
    print(f"   - Verified card front retrievable: {fronts[0][:30]}...")
    
    # Cleanup - delete the test deck
    anki.delete_deck_with_cards(test_deck, i_understand_this_is_permanent=True)
    print(f"   - Cleaned up test deck")


@test("AnkiClient.rename_deck")
def test_anki_rename():
    from app.services.anki.client import AnkiClient
    
    anki = AnkiClient()
    
    # Create and populate test deck
    old_name = "TestDeck_RenameTest_Old"
    new_name = "TestDeck_RenameTest_New"
    
    anki.create_deck(old_name)
    anki.add_notes([{
        "deck": old_name,
        "front": "Rename Test Card",
        "back": "Answer",
        "tags": ["rename-test"]
    }])
    print(f"   - Created deck '{old_name}' with 1 card")
    
    # Rename
    success = anki.rename_deck(old_name, new_name)
    assert success, "Rename should return True"
    print(f"   - Renamed to '{new_name}'")
    
    # Verify card is in new deck
    fronts = anki.get_deck_card_fronts(new_name)
    assert "Rename Test Card" in fronts
    print("   - Card preserved in renamed deck")
    
    # Cleanup
    anki.delete_deck_with_cards(new_name, i_understand_this_is_permanent=True)
    print("   - Cleaned up")


# =============================================================================
# Test 5: FlashcardState TypedDict
# =============================================================================

@test("FlashcardState has new deduplication fields")
def test_flashcard_state_fields():
    from app.agents.flashcards.flashcard_agent import FlashcardState
    
    # Check the annotations include new fields
    annotations = FlashcardState.__annotations__
    
    required_fields = [
        "deduplicate_course",
        "existing_anki_fronts", 
        "parent_deck_name",
        "target_deck_name"
    ]
    
    for field in required_fields:
        assert field in annotations, f"Missing field: {field}"
        print(f"   - {field}: {annotations[field]}")


# =============================================================================
# Run All Tests
# =============================================================================

def main():
    print("\n" + "="*60)
    print("PRE-MIGRATION TESTS")
    print("Testing flashcard deduplication & Anki integration")
    print("="*60)
    
    # Collect all test functions
    tests = [
        # Import checks
        test_import_flashcard_agent,
        test_import_storage,
        test_import_anki_client,
        
        # Deduplication logic
        test_dedup_exact,
        test_dedup_similar,
        test_dedup_case_insensitive,
        test_dedup_self,
        test_dedup_empty,
        
        # Tag extraction
        test_extract_source,
        test_extract_page,
        
        # FlashcardState
        test_flashcard_state_fields,
        
        # Anki integration (requires Anki running)
        test_anki_connection,
        test_anki_get_fronts,
        test_anki_create_and_add,
        test_anki_rename,
    ]
    
    # Run tests
    for test_func in tests:
        test_func()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"⏭️  Skipped: {results['skipped']}")
    print("="*60)
    
    if results['failed'] > 0:
        print("\n⚠️  Some tests failed. Review errors above.")
        sys.exit(1)
    else:
        print("\n🎉 All pre-migration tests passed!")
        print("You can safely apply the migration.")
        sys.exit(0)


if __name__ == "__main__":
    main()
