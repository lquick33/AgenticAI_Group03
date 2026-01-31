#!/usr/bin/env python3
"""
Test script for Anki integration.
Run this to verify the Anki integration is working correctly.
"""

import sys
sys.path.insert(0, '.')

from app.services.anki import AnkiClient, AnkiError
from app.services.anki.client import AnkiConnectionError, print_first_run_instructions

def test_client():
    """Test the AnkiClient class directly"""
    print("=" * 60)
    print("ANKI CLIENT TESTS")
    print("=" * 60)
    print()
    
    client = AnkiClient()
    
    # Test is_running
    print(f"1. is_running(): {client.is_running()}")
    
    if not client.is_running():
        print("\nAnki is not running!")
        print("Please start Anki and ensure AnkiConnect add-on is installed.")
        print("Add-on code: 2055492159")
        return False
    
    # Test get_version
    print(f"2. get_version(): {client.get_version()}")
    
    # Test get_deck_names
    decks = client.get_deck_names()
    print(f"3. get_deck_names(): {len(decks)} decks")
    
    # Test get_deck_stats
    stats = client.get_deck_stats()
    print(f"4. get_deck_stats(): {len(stats)} decks with stats")
    
    # Test get_cards_reviewed_today
    reviewed = client.get_cards_reviewed_today()
    print(f"5. get_cards_reviewed_today(): {reviewed}")
    
    # Test get_review_stats
    review_stats = client.get_review_stats()
    print(f"6. get_review_stats(): {review_stats.cards_reviewed_today} today")
    
    # Test create_deck
    deck_id = client.create_deck("Integration Test Deck")
    print(f"7. create_deck(): Created deck ID {deck_id}")
    
    # Test add_note
    note_id = client.add_note(
        deck="Integration Test Deck",
        front="Integration test question",
        back="Integration test answer",
        tags=["integration-test"]
    )
    print(f"8. add_note(): Created note ID {note_id}")
    
    # Test find_notes
    notes = client.find_notes('tag:integration-test')
    print(f"9. find_notes(): Found {len(notes)} notes")
    
    # Test sync
    print("10. sync(): Syncing...")
    client.sync()
    print("    Sync complete!")
    
    print()
    print("=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    return True


def test_tools():
    """Test the agent tools"""
    print()
    print("=" * 60)
    print("AGENT TOOLS TESTS")
    print("=" * 60)
    print()
    
    # We need to test these directly since they have relative imports
    from app.services.anki import AnkiClient
    
    client = AnkiClient()
    
    # Simulate get_anki_stats
    print("1. get_anki_stats() simulation:")
    deck_stats = client.get_deck_stats()
    review_stats = client.get_review_stats()
    print(f"   Cards reviewed today: {review_stats.cards_reviewed_today}")
    print(f"   Decks: {len(deck_stats)}")
    
    # Simulate create_flashcard
    print("2. create_flashcard() simulation:")
    client.create_deck("Agent Test")
    note_id = client.add_note(
        deck="Agent Test",
        front="Agent test Q",
        back="Agent test A",
        tags=["agent-test"]
    )
    print(f"   Created note ID: {note_id}")
    
    # Simulate search_anki_cards
    print("3. search_anki_cards() simulation:")
    notes = client.find_notes('tag:agent-test')
    print(f"   Found {len(notes)} notes")
    
    # Simulate sync_anki
    print("4. sync_anki() simulation:")
    client.sync()
    print("   Synced!")
    
    print()
    print("=" * 60)
    print("AGENT TOOLS SIMULATION PASSED!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = True
    
    try:
        success = test_client() and success
    except Exception as e:
        print(f"Client test failed: {e}")
        success = False
    
    try:
        success = test_tools() and success
    except Exception as e:
        print(f"Tools test failed: {e}")
        success = False
    
    sys.exit(0 if success else 1)
