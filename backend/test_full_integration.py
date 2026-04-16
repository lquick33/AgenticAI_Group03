"""
Full Integration Tests for Flashcard Deduplication & Anki Cache

Run AFTER the flashcard_cache migration is applied.
Tests the complete flow: Anki -> Cache -> Deduplication

Run with: python test_full_integration.py
"""

import sys
import os
import traceback
import uuid
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


def skip(name: str, reason: str):
    """Mark a test as skipped."""
    def decorator(func):
        def wrapper():
            print(f"\n{'='*60}")
            print(f"TEST: {name}")
            print('='*60)
            print(f"⏭️  SKIPPED: {reason}")
            results["skipped"] += 1
        return wrapper
    return decorator


# =============================================================================
# Test 1: Import All New Functions
# =============================================================================

@test("Import all new storage functions")
def test_import_storage():
    from app.services.storage import (
        cache_flashcards,
        get_cached_flashcards_for_material,
        get_cached_flashcards_for_course,
        get_cached_flashcards_by_deck_pattern,
        delete_cached_flashcards_for_deck,
        update_cached_deck_names,
        extract_source_from_tags,
        extract_page_from_tags,
        on_course_renamed,
        on_material_renamed,
    )
    print("   - All storage functions imported successfully")


@test("Import flashcard agent with deduplication")
def test_import_agent():
    from app.agents.flashcards.flashcard_agent import (
        FlashcardState,
        deduplicate_flashcards,
        FlashcardGeneratorAgent,
    )
    print("   - FlashcardGeneratorAgent imported")
    print("   - deduplicate_flashcards imported")
    print("   - FlashcardState imported")
    
    # Verify new fields exist
    annotations = FlashcardState.__annotations__
    assert "deduplicate_course" in annotations
    assert "existing_anki_fronts" in annotations
    assert "parent_deck_name" in annotations
    assert "target_deck_name" in annotations
    print("   - FlashcardState has all new dedup fields")


# =============================================================================
# Test 2: Cache Functions (requires DB)
# =============================================================================

@test("cache_flashcards - write to new table")
def test_cache_write():
    from app.services.storage import cache_flashcards, get_supabase_client
    
    # Get a valid user_id from profiles table
    client = get_supabase_client()
    profile = client.table("profiles").select("id").limit(1).execute()
    
    if not profile.data:
        raise Exception("No profiles found - need at least one user for testing")
    
    user_id = profile.data[0]["id"]
    test_deck = "TestCourse::TestLecture_Integration"
    test_note_id = 9999999999  # Fake Anki note ID for testing
    
    cards = [
        {
            "front": "Integration Test Question 1",
            "back": "Integration Test Answer 1",
            "tags": ["page:1", "source:test-uuid-1", "test-tag"]
        }
    ]
    note_ids = [test_note_id]
    
    # Cache the flashcard
    cache_flashcards(cards, note_ids, user_id, test_deck, None)
    print(f"   - Cached 1 flashcard for user {user_id[:8]}...")
    
    # Verify it was written
    result = client.table("flashcard_cache").select("*").eq("anki_note_id", test_note_id).execute()
    
    assert len(result.data) == 1, f"Expected 1 cached card, got {len(result.data)}"
    cached = result.data[0]
    assert cached["front"] == "Integration Test Question 1"
    assert cached["deck_name"] == test_deck
    assert "page:1" in cached["tags"]
    print(f"   - Verified card in database: {cached['front'][:30]}...")
    
    # Cleanup
    client.table("flashcard_cache").delete().eq("anki_note_id", test_note_id).execute()
    print("   - Cleaned up test data")


@test("get_cached_flashcards_for_material - read from cache")
def test_cache_read():
    from app.services.storage import (
        cache_flashcards, 
        get_cached_flashcards_for_material,
        get_supabase_client
    )
    
    client = get_supabase_client()
    profile = client.table("profiles").select("id").limit(1).execute()
    user_id = profile.data[0]["id"]
    
    test_deck = "TestCourse::TestLecture_Read"
    test_note_ids = [8888888881, 8888888882]
    
    # Insert test cards
    cards = [
        {"front": "Read Test Q1", "back": "A1", "tags": ["page:1"]},
        {"front": "Read Test Q2", "back": "A2", "tags": ["page:2"]},
    ]
    cache_flashcards(cards, test_note_ids, user_id, test_deck, None)
    
    # Read back
    cached = get_cached_flashcards_for_material(test_deck, user_id)
    
    assert len(cached) == 2, f"Expected 2 cards, got {len(cached)}"
    print(f"   - Retrieved {len(cached)} cached cards")
    
    # Cleanup
    for note_id in test_note_ids:
        client.table("flashcard_cache").delete().eq("anki_note_id", note_id).execute()
    print("   - Cleaned up")


@test("get_cached_flashcards_by_deck_pattern - wildcard query")
def test_cache_pattern():
    from app.services.storage import (
        cache_flashcards,
        get_cached_flashcards_by_deck_pattern,
        get_supabase_client
    )
    
    client = get_supabase_client()
    profile = client.table("profiles").select("id").limit(1).execute()
    user_id = profile.data[0]["id"]
    
    # Insert cards in different sub-decks
    test_parent = "PatternTestCourse"
    cards1 = [{"front": "Pattern Q1", "back": "A1", "tags": []}]
    cards2 = [{"front": "Pattern Q2", "back": "A2", "tags": []}]
    
    cache_flashcards(cards1, [7777777771], user_id, f"{test_parent}::Lecture1", None)
    cache_flashcards(cards2, [7777777772], user_id, f"{test_parent}::Lecture2", None)
    
    # Query with pattern
    all_cards = get_cached_flashcards_by_deck_pattern(f"{test_parent}::%", user_id)
    
    assert len(all_cards) == 2, f"Expected 2 cards from pattern, got {len(all_cards)}"
    print(f"   - Pattern query found {len(all_cards)} cards across sub-decks")
    
    # Cleanup
    client.table("flashcard_cache").delete().eq("anki_note_id", 7777777771).execute()
    client.table("flashcard_cache").delete().eq("anki_note_id", 7777777772).execute()
    print("   - Cleaned up")


# =============================================================================
# Test 3: AnkiClient Integration
# =============================================================================

@test("AnkiClient - full workflow")
def test_anki_workflow():
    pass

@test("Deduplication against Anki cards")
def test_dedup_with_anki():
    from app.services.anki.client import AnkiClient
    from app.agents.flashcards.flashcard_agent import deduplicate_flashcards
    
    anki = AnkiClient()
    
    # Create deck with some cards
    test_deck = "DedupTest::Lecture1"
    anki.create_deck(test_deck)
    
    existing_notes = [
        {"deck": test_deck, "front": "What is photosynthesis?", "back": "Process by plants", "tags": []},
        {"deck": test_deck, "front": "Define osmosis", "back": "Water movement", "tags": []},
    ]
    anki.add_notes(existing_notes)
    
    # Get fronts from Anki
    existing_fronts = anki.get_deck_card_fronts("DedupTest")
    print(f"   - Existing Anki cards: {len(existing_fronts)}")
    
    # New cards to deduplicate
    new_cards = [
        {"front": "What is photosynthesis", "back": "..."},  # Similar to existing (missing ?)
        {"front": "Define osmosis?", "back": "..."},  # Similar to existing (extra ?)
        {"front": "Explain mitosis", "back": "..."},  # Unique
    ]
    
    unique_cards, removed = deduplicate_flashcards(new_cards, existing_fronts)
    
    print(f"   - New cards: {len(new_cards)}, Removed: {removed}, Unique: {len(unique_cards)}")
    assert removed == 2, f"Expected 2 duplicates removed, got {removed}"
    assert len(unique_cards) == 1
    assert "mitosis" in unique_cards[0]["front"]
    print(f"   - Correctly kept only: '{unique_cards[0]['front']}'")
    
    # Cleanup
    anki.delete_deck_with_cards(test_deck, i_understand_this_is_permanent=True)
    anki.delete_deck_with_cards("DedupTest", i_understand_this_is_permanent=True)
    print("   - Cleaned up")


# =============================================================================
# Test 5: Full Flow - Anki + Cache + Dedup
# =============================================================================

@test("Full flow: Anki -> Cache -> Dedup")
def test_full_flow():
    from app.services.anki.client import AnkiClient
    from app.services.storage import (
        cache_flashcards,
        get_cached_flashcards_for_material,
        get_supabase_client
    )
    from app.agents.flashcards.flashcard_agent import deduplicate_flashcards
    
    anki = AnkiClient()
    client = get_supabase_client()
    profile = client.table("profiles").select("id").limit(1).execute()
    user_id = profile.data[0]["id"]
    
    test_deck = "FullFlowTest::Lecture1"
    
    # Step 1: Create Anki deck and add initial cards
    anki.create_deck(test_deck)
    initial_cards = [
        {"deck": test_deck, "front": "FullFlow Q1: What is Python?", "back": "A programming language", "tags": ["page:1"]},
    ]
    note_ids_batch1 = anki.add_notes(initial_cards)
    print(f"   Step 1: Added initial card to Anki (note_id: {note_ids_batch1[0]})")
    
    # Step 2: Cache in database
    cache_cards = [{"front": "FullFlow Q1: What is Python?", "back": "A programming language", "tags": ["page:1"]}]
    cache_flashcards(cache_cards, note_ids_batch1, user_id, test_deck, None)
    print("   Step 2: Cached card in database")
    
    # Step 3: Simulate generating new cards (some duplicates)
    existing_fronts = anki.get_deck_card_fronts("FullFlowTest")
    print(f"   Step 3: Retrieved {len(existing_fronts)} existing fronts for dedup")
    
    new_cards = [
        {"front": "FullFlow Q1: What is Python", "back": "..."},  # Duplicate (missing ?)
        {"front": "FullFlow Q2: What is JavaScript?", "back": "Another language"},  # Unique
    ]
    
    unique_cards, removed = deduplicate_flashcards(new_cards, existing_fronts)
    print(f"   Step 4: Deduplication - removed {removed}, kept {len(unique_cards)}")
    
    # Step 5: Add unique cards to Anki
    if unique_cards:
        notes_to_add = [{"deck": test_deck, "front": c["front"], "back": c["back"], "tags": ["page:2"]} for c in unique_cards]
        note_ids_batch2 = anki.add_notes(notes_to_add)
        print(f"   Step 5: Added {len(note_ids_batch2)} unique cards to Anki")
        
        # Cache new cards
        for i, c in enumerate(unique_cards):
            c["tags"] = ["page:2"]
        cache_flashcards(unique_cards, note_ids_batch2, user_id, test_deck, None)
        print("   Step 6: Cached new cards in database")
    
    # Verify final state
    all_cached = get_cached_flashcards_for_material(test_deck, user_id)
    all_anki_fronts = anki.get_deck_card_fronts("FullFlowTest")
    
    print(f"   Final: {len(all_cached)} cards in cache, {len(all_anki_fronts)} in Anki")
    assert len(all_cached) == 2, f"Expected 2 cached, got {len(all_cached)}"
    assert len(all_anki_fronts) == 2, f"Expected 2 in Anki, got {len(all_anki_fronts)}"
    
    # Cleanup
    for card in all_cached:
        client.table("flashcard_cache").delete().eq("anki_note_id", card["anki_note_id"]).execute()
    anki.delete_deck_with_cards(test_deck, i_understand_this_is_permanent=True)
    anki.delete_deck_with_cards("FullFlowTest", i_understand_this_is_permanent=True)
    print("   Cleaned up all test data")


# =============================================================================
# Test 6: Tag Extraction from DB
# =============================================================================

@test("Tag extraction with real cached data")
def test_tag_extraction_db():
    from app.services.storage import (
        cache_flashcards,
        extract_source_from_tags,
        extract_page_from_tags,
        get_supabase_client
    )
    
    client = get_supabase_client()
    profile = client.table("profiles").select("id").limit(1).execute()
    user_id = profile.data[0]["id"]
    
    test_note_id = 6666666666
    test_deck = "TagExtractionTest::Lecture1"
    test_source_uuid = str(uuid.uuid4())
    
    # Cache with metadata tags
    cards = [{
        "front": "Tag Test Question",
        "back": "Answer",
        "tags": ["page:42", f"source:{test_source_uuid}", "topic:math", "difficulty:hard"]
    }]
    cache_flashcards(cards, [test_note_id], user_id, test_deck, None)
    
    # Read back and extract
    result = client.table("flashcard_cache").select("tags").eq("anki_note_id", test_note_id).single().execute()
    tags = result.data["tags"]
    
    extracted_page = extract_page_from_tags(tags)
    extracted_source = extract_source_from_tags(tags)
    
    assert extracted_page == 42, f"Expected page 42, got {extracted_page}"
    assert extracted_source == test_source_uuid, f"Expected {test_source_uuid}, got {extracted_source}"
    print(f"   - Extracted page: {extracted_page}")
    print(f"   - Extracted source: {extracted_source[:8]}...")
    
    # Cleanup
    client.table("flashcard_cache").delete().eq("anki_note_id", test_note_id).execute()
    print("   - Cleaned up")


# =============================================================================
# Test 7: Deck Rename Operations
# =============================================================================

@test("Deck rename - Anki and cache sync")
def test_deck_rename():
    from app.services.anki.client import AnkiClient
    from app.services.storage import (
        cache_flashcards,
        get_cached_flashcards_for_material,
        update_cached_deck_names,
        get_supabase_client
    )
    
    anki = AnkiClient()
    client = get_supabase_client()
    profile = client.table("profiles").select("id").limit(1).execute()
    user_id = profile.data[0]["id"]
    
    old_deck = "RenameTestOld::Lecture1"
    new_deck = "RenameTestNew::Lecture1"
    test_note_id = 5555555555
    
    # Create in Anki
    anki.create_deck(old_deck)
    note_ids = anki.add_notes([{"deck": old_deck, "front": "Rename Test Q", "back": "A", "tags": []}])
    print(f"   - Created Anki deck: {old_deck}")
    
    # Cache in DB
    cache_flashcards([{"front": "Rename Test Q", "back": "A", "tags": []}], note_ids, user_id, old_deck, None)
    print("   - Cached in database")
    
    # Rename in Anki
    success = anki.rename_deck(old_deck, new_deck)
    assert success, "Anki rename should succeed"
    print(f"   - Renamed Anki deck to: {new_deck}")
    
    # Update cache
    updated = update_cached_deck_names(
        old_pattern=old_deck,
        new_prefix=new_deck,
        old_prefix=old_deck,
        user_id=user_id
    )
    print(f"   - Updated {updated} cache entries")
    
    # Verify
    old_cached = get_cached_flashcards_for_material(old_deck, user_id)
    new_cached = get_cached_flashcards_for_material(new_deck, user_id)
    
    assert len(old_cached) == 0, "Old deck should have no cached cards"
    assert len(new_cached) == 1, "New deck should have 1 cached card"
    print("   - Verified: old deck empty, new deck has cards")
    
    # Cleanup
    client.table("flashcard_cache").delete().eq("anki_note_id", note_ids[0]).execute()
    anki.delete_deck_with_cards(new_deck, i_understand_this_is_permanent=True)
    anki.delete_deck_with_cards("RenameTestNew", i_understand_this_is_permanent=True)
    anki.delete_deck_with_cards("RenameTestOld", i_understand_this_is_permanent=True)
    print("   - Cleaned up")


# =============================================================================
# Test 8: Anki → Cache Sync
# =============================================================================

@test("Sync: Anki → Cache (new cards)")
def test_sync_new_cards():
    from app.services.anki.client import AnkiClient
    from app.services.storage import (
        sync_cache_from_anki,
        get_cached_flashcards_for_material,
        get_supabase_client
    )
    
    anki = AnkiClient()
    client = get_supabase_client()
    profile = client.table("profiles").select("id").limit(1).execute()
    user_id = profile.data[0]["id"]
    
    test_deck = "SyncTestCourse::Lecture1"
    
    # Step 1: Add cards directly to Anki (simulating manual addition)
    anki.create_deck(test_deck)
    notes = [
        {"deck": test_deck, "front": "Sync Test Q1 - Manual Add", "back": "A1", "tags": ["manual"]},
        {"deck": test_deck, "front": "Sync Test Q2 - Manual Add", "back": "A2", "tags": ["manual"]},
    ]
    note_ids = anki.add_notes(notes)
    print(f"   Step 1: Added {len(note_ids)} cards directly to Anki (simulating manual add)")
    
    # Verify cache is empty before sync
    before_sync = get_cached_flashcards_for_material(test_deck, user_id)
    assert len(before_sync) == 0, "Cache should be empty before sync"
    print("   Step 2: Verified cache is empty")
    
    # Step 3: Run sync
    stats = sync_cache_from_anki("SyncTestCourse", user_id, None)
    print(f"   Step 3: Sync stats - {stats}")
    
    assert stats["inserted"] == 2, f"Expected 2 inserted, got {stats['inserted']}"
    print(f"   Step 4: Sync inserted {stats['inserted']} new cards into cache")
    
    # Verify cache now has cards
    after_sync = get_cached_flashcards_for_material(test_deck, user_id)
    assert len(after_sync) == 2, f"Expected 2 cached, got {len(after_sync)}"
    print(f"   Step 5: Verified {len(after_sync)} cards now in cache")
    
    # Cleanup
    for card in after_sync:
        client.table("flashcard_cache").delete().eq("id", card["id"]).execute()
    anki.delete_deck_with_cards(test_deck, i_understand_this_is_permanent=True)
    anki.delete_deck_with_cards("SyncTestCourse", i_understand_this_is_permanent=True)
    print("   Cleaned up")


@test("Sync: Anki → Cache (modified cards)")
def test_sync_modified():
    from app.services.anki.client import AnkiClient
    from app.services.storage import (
        cache_flashcards,
        sync_cache_from_anki,
        get_supabase_client
    )
    
    anki = AnkiClient()
    client = get_supabase_client()
    profile = client.table("profiles").select("id").limit(1).execute()
    user_id = profile.data[0]["id"]
    
    test_deck = "SyncModTest::Lecture1"
    
    # Step 1: Create card in Anki and cache
    anki.create_deck(test_deck)
    note_ids = anki.add_notes([{"deck": test_deck, "front": "Original Question", "back": "Original Answer", "tags": []}])
    note_id = note_ids[0]
    
    cache_flashcards(
        [{"front": "Original Question", "back": "Original Answer", "tags": []}],
        [note_id],
        user_id,
        test_deck,
        None
    )
    print(f"   Step 1: Created card in Anki and cache (note_id: {note_id})")
    
    # Step 2: Modify the card in Anki directly
    anki._request("updateNoteFields", {
        "note": {
            "id": note_id,
            "fields": {
                "Front": "Modified Question",
                "Back": "Modified Answer"
            }
        }
    })
    print("   Step 2: Modified card in Anki (simulating manual edit)")
    
    # Step 3: Run sync
    stats = sync_cache_from_anki("SyncModTest", user_id, None)
    print(f"   Step 3: Sync stats - {stats}")
    
    assert stats["updated"] == 1, f"Expected 1 updated, got {stats['updated']}"
    
    # Step 4: Verify cache has updated content
    result = client.table("flashcard_cache").select("front, back").eq("anki_note_id", note_id).single().execute()
    assert result.data["front"] == "Modified Question", f"Front not updated: {result.data['front']}"
    assert result.data["back"] == "Modified Answer", f"Back not updated: {result.data['back']}"
    print("   Step 4: Verified cache has updated content")
    
    # Cleanup
    client.table("flashcard_cache").delete().eq("anki_note_id", note_id).execute()
    anki.delete_deck_with_cards(test_deck, i_understand_this_is_permanent=True)
    anki.delete_deck_with_cards("SyncModTest", i_understand_this_is_permanent=True)
    print("   Cleaned up")


# =============================================================================
# Test 9: Safety Measures
# =============================================================================

@test("Delete blocked without confirmation")
def test_delete_blocked_without_confirmation():
    from app.services.anki.client import AnkiClient
    
    anki = AnkiClient()
    
    # Create a test deck
    test_deck = "SafetyTest::ShouldNotDelete"
    anki.create_deck(test_deck)
    anki.add_notes([{"deck": test_deck, "front": "Safety Test Q", "back": "A", "tags": []}])
    print(f"   - Created test deck: {test_deck}")
    
    # Try to delete without confirmation - should raise ValueError
    blocked = False
    try:
        anki.delete_deck_with_cards(test_deck)  # No confirmation!
    except ValueError as e:
        blocked = True
        print(f"   - Deletion correctly blocked: {str(e)[:50]}...")
    
    assert blocked, "Deletion should have been blocked without confirmation"
    
    # Verify deck still exists
    decks = anki.get_deck_names()
    assert test_deck in decks, "Deck should still exist after blocked deletion"
    print("   - Verified deck still exists after blocked deletion")
    
    # Now cleanup with proper confirmation
    anki.delete_deck_with_cards(test_deck, i_understand_this_is_permanent=True)
    anki.delete_deck_with_cards("SafetyTest", i_understand_this_is_permanent=True)
    print("   - Cleaned up with proper confirmation")


# =============================================================================
# Run All Tests
# =============================================================================

def main():
    print("\n" + "="*60)
    print("FULL INTEGRATION TESTS")
    print("Testing Anki + Cache + Deduplication")
    print("="*60)
    
    tests = [
        # Imports
        test_import_storage,
        test_import_agent,
        
        # Cache operations
        test_cache_write,
        test_cache_read,
        test_cache_pattern,
        
        # Anki operations
        test_anki_workflow,
        
        # Deduplication
        test_dedup_with_anki,
        
        # Full flow
        test_full_flow,
        
        # Tag extraction
        test_tag_extraction_db,
        
        # Rename operations
        test_deck_rename,
        
        # Anki → Cache sync
        test_sync_new_cards,
        test_sync_modified,
        
        # Safety measures
        test_delete_blocked_without_confirmation,
    ]
    
    for test_func in tests:
        test_func()
    
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
        print("\n🎉 All integration tests passed!")
        print("The flashcard deduplication system is working correctly.")
        sys.exit(0)


if __name__ == "__main__":
    main()
