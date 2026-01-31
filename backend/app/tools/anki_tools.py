"""
Anki Tools for Agent Integration

These tools allow the agent to:
- Read study statistics from Anki
- Create flashcards
- Search existing cards
- Sync with AnkiWeb
"""

from typing import Optional

from ..services.anki import AnkiClient, AnkiError
from ..services.anki.client import AnkiConnectionError, print_first_run_instructions


# Global client instance
_anki_client: Optional[AnkiClient] = None


def get_anki_client() -> AnkiClient:
    """Get or create the Anki client instance"""
    global _anki_client
    if _anki_client is None:
        _anki_client = AnkiClient()
    return _anki_client


# =============================================================================
# Agent Tools
# =============================================================================

def get_anki_stats() -> dict:
    """
    Get the user's Anki study statistics.
    
    Returns information about:
    - Cards reviewed today
    - Cards due per deck
    - New/learning/review card counts
    - Historical review data
    
    Use this to understand the user's study progress and tailor recommendations.
    
    Returns:
        Dictionary with deck stats and review counts
    """
    client = get_anki_client()
    
    try:
        client.ensure_running()
    except AnkiConnectionError as e:
        return {"error": str(e), "status": "container_not_running"}
    
    # Check if first run
    if client.is_first_run():
        print_first_run_instructions()
        return {
            "error": "First run - AnkiWeb login required",
            "status": "first_run",
            "instructions": "User needs to login to AnkiWeb via VNC at localhost:5900"
        }
    
    try:
        deck_stats = client.get_deck_stats()
        review_stats = client.get_review_stats()
        
        return {
            "status": "success",
            "cards_reviewed_today": review_stats.cards_reviewed_today,
            "decks": {
                name: {
                    "total_cards": stats.total_cards,
                    "new_cards": stats.new_cards,
                    "learning_cards": stats.learning_cards,
                    "review_cards": stats.review_cards,
                }
                for name, stats in deck_stats.items()
            },
            "reviews_by_day": review_stats.reviews_by_day
        }
    except AnkiError as e:
        return {"error": str(e), "status": "anki_error"}


def create_flashcard(
    deck: str,
    question: str,
    answer: str,
    tags: Optional[list[str]] = None,
    sync_immediately: bool = True
) -> dict:
    """
    Create a new Anki flashcard.
    
    Args:
        deck: Name of the deck to add the card to. 
              Use "::" for nested decks (e.g., "Languages::Spanish")
        question: The front side of the card (what to ask)
        answer: The back side of the card (the answer)
        tags: Optional list of tags for organization
        sync_immediately: If True, sync to AnkiWeb after creating
    
    Returns:
        Dictionary with note_id and sync status
        
    Example:
        create_flashcard(
            deck="AI Course",
            question="What is backpropagation?",
            answer="An algorithm for computing gradients in neural networks...",
            tags=["neural-networks", "fundamentals"]
        )
    """
    client = get_anki_client()
    
    try:
        client.ensure_running()
    except AnkiConnectionError as e:
        return {"error": str(e), "status": "container_not_running"}
    
    if client.is_first_run():
        print_first_run_instructions()
        return {
            "error": "First run - AnkiWeb login required before creating cards",
            "status": "first_run"
        }
    
    try:
        # Create the deck if it doesn't exist
        client.create_deck(deck)
        
        # Add the note
        note_id = client.add_note(
            deck=deck,
            front=question,
            back=answer,
            tags=tags
        )
        
        result = {
            "status": "success",
            "note_id": note_id,
            "deck": deck,
            "synced": False
        }
        
        # Sync to AnkiWeb
        if sync_immediately:
            try:
                client.sync()
                result["synced"] = True
            except AnkiError as e:
                result["sync_error"] = str(e)
                result["sync_message"] = "Card created locally but sync failed. User may need to login to AnkiWeb."
        
        return result
        
    except AnkiError as e:
        return {"error": str(e), "status": "anki_error"}


def create_flashcards_batch(
    cards: list[dict],
    default_deck: str = "Agent Generated",
    sync_after: bool = True
) -> dict:
    """
    Create multiple flashcards in batch.
    
    Args:
        cards: List of card dictionaries with keys:
               - question (required): Front of card
               - answer (required): Back of card
               - deck (optional): Override default deck
               - tags (optional): List of tags
        default_deck: Deck to use if not specified per card
        sync_after: Sync to AnkiWeb after creating all cards
    
    Returns:
        Dictionary with created note IDs and any errors
        
    Example:
        create_flashcards_batch([
            {"question": "What is Python?", "answer": "A programming language"},
            {"question": "What is JavaScript?", "answer": "A scripting language"},
        ], default_deck="Programming")
    """
    client = get_anki_client()
    
    try:
        client.ensure_running()
    except AnkiConnectionError as e:
        return {"error": str(e), "status": "container_not_running"}
    
    if client.is_first_run():
        print_first_run_instructions()
        return {"error": "First run - AnkiWeb login required", "status": "first_run"}
    
    try:
        # Ensure default deck exists
        client.create_deck(default_deck)
        
        # Also create any custom decks
        custom_decks = set(card.get("deck") for card in cards if card.get("deck"))
        for deck in custom_decks:
            client.create_deck(deck)
        
        # Format cards for batch add
        formatted = [
            {
                "front": card["question"],
                "back": card["answer"],
                "deck": card.get("deck", default_deck),
                "tags": card.get("tags", [])
            }
            for card in cards
        ]
        
        note_ids = client.add_notes(formatted, deck=default_deck)
        
        # Count successes/failures
        successful = [nid for nid in note_ids if nid is not None]
        failed = len(note_ids) - len(successful)
        
        result = {
            "status": "success",
            "created": len(successful),
            "failed": failed,
            "note_ids": successful,
            "synced": False
        }
        
        if sync_after and successful:
            try:
                client.sync()
                result["synced"] = True
            except AnkiError as e:
                result["sync_error"] = str(e)
        
        return result
        
    except AnkiError as e:
        return {"error": str(e), "status": "anki_error"}


def search_anki_cards(query: str) -> dict:
    """
    Search existing Anki cards.
    
    Args:
        query: Search query using Anki's search syntax:
               - "deck:DeckName" - cards in a specific deck
               - "tag:tagname" - cards with a tag
               - "front:*keyword*" - cards with keyword in front
               - "is:due" - cards that are due for review
               - "is:new" - new cards
               - "-is:suspended" - not suspended
               
    Returns:
        Dictionary with matching cards
        
    Example:
        search_anki_cards("deck:Programming tag:python")
    """
    client = get_anki_client()
    
    try:
        client.ensure_running()
    except AnkiConnectionError as e:
        return {"error": str(e), "status": "container_not_running"}
    
    try:
        notes = client.search_notes(query)
        
        return {
            "status": "success",
            "count": len(notes),
            "cards": [
                {
                    "note_id": note["noteId"],
                    "deck": note.get("deckName", "Unknown"),
                    "tags": note.get("tags", []),
                    "fields": {
                        field_name: field_data.get("value", "")
                        for field_name, field_data in note.get("fields", {}).items()
                    }
                }
                for note in notes
            ]
        }
    except AnkiError as e:
        return {"error": str(e), "status": "anki_error"}


def sync_anki() -> dict:
    """
    Manually trigger a sync with AnkiWeb.
    
    This pushes any locally created cards to AnkiWeb,
    making them available on the user's phone and other devices.
    
    Returns:
        Dictionary with sync status
    """
    client = get_anki_client()
    
    try:
        client.ensure_running()
    except AnkiConnectionError as e:
        return {"error": str(e), "status": "container_not_running"}
    
    try:
        client.sync()
        return {"status": "success", "message": "Synced with AnkiWeb"}
    except AnkiError as e:
        error_msg = str(e)
        if "auth" in error_msg.lower() or "login" in error_msg.lower():
            print_first_run_instructions()
            return {
                "error": error_msg,
                "status": "auth_required",
                "message": "AnkiWeb login required. Use VNC at localhost:5900 to login."
            }
        return {"error": error_msg, "status": "sync_error"}


def get_anki_deck_list() -> dict:
    """
    Get list of all available decks.
    
    Returns:
        Dictionary with deck names
    """
    client = get_anki_client()
    
    try:
        client.ensure_running()
    except AnkiConnectionError as e:
        return {"error": str(e), "status": "container_not_running"}
    
    try:
        decks = client.get_deck_names()
        return {"status": "success", "decks": decks}
    except AnkiError as e:
        return {"error": str(e), "status": "anki_error"}
