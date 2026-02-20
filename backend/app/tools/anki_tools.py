"""
Anki Tools for Agent Integration

These tools allow the agent to:
- Read study statistics from Anki
- Create flashcards
- Search existing cards
- Sync with AnkiWeb
- Track knowledge levels per deck and course
"""

from dataclasses import asdict
from typing import Optional

from ..services.anki import (
    AnkiClient, 
    AnkiError, 
    AnkiConnectionError,
    KnowledgeService,
    build_deck_name,
)
from ..services.anki.client import print_first_run_instructions
from app.core.adapters import get_course as _get_course, get_knowledge as _get_knowledge


# Global client instance
_anki_client: Optional[AnkiClient] = None
_knowledge_service: Optional[KnowledgeService] = None


def get_anki_client() -> AnkiClient:
    """Get or create the Anki client instance"""
    global _anki_client
    if _anki_client is None:
        _anki_client = AnkiClient()
    return _anki_client


def get_knowledge_service() -> KnowledgeService:
    """Get or create the Knowledge service instance"""
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService(get_anki_client())
    return _knowledge_service


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


# =============================================================================
# Knowledge Level Tools
# =============================================================================

def get_knowledge_levels(save_snapshot: bool = False, user_id: Optional[str] = None) -> dict:
    """
    Get knowledge level per Anki deck with detailed breakdown.
    
    This tool provides comprehensive mastery information for all decks:
    - Mastery score (0.0-1.0) based on card states, ease factors, and retention
    - Card distribution (new, learning, young, mature)
    - Average ease factor and interval
    - Status labels (mastered, progressing, needs_review, not_started)
    - Study recommendations
    
    Use this to understand the user's overall study progress across all topics.
    
    Args:
        save_snapshot: If True, saves the current state to database for trend tracking
        user_id: User ID (required if save_snapshot is True)
        
    Returns:
        Dictionary with:
        - status: "success" or "error"
        - overall_mastery: Weighted average mastery (0.0-1.0)
        - decks: Per-deck breakdown with mastery scores and card counts
        - recommendations: Study suggestions
        
    Example response:
        {
            "status": "success",
            "overall_mastery": 0.72,
            "decks": {
                "Marketing 101::Lecture 1": {
                    "mastery_score": 0.85,
                    "total_cards": 45,
                    "mature_cards": 35,
                    "status": "mastered"
                },
                ...
            },
            "recommendations": ["Focus on 'Lecture 3' - low retention rate"]
        }
    """
    service = get_knowledge_service()
    result = service.get_all_knowledge_levels()
    
    # Optionally save snapshots
    if save_snapshot and user_id and result.get("status") == "success":
        client = get_anki_client()
        try:
            deck_knowledge = client.get_all_decks_knowledge()
            for deck_name, dk in deck_knowledge.items():
                _get_knowledge().save_knowledge_snapshot(
                    user_id=user_id,
                    deck_name=deck_name,
                    total_cards=dk.total_cards,
                    new_cards=dk.new_cards,
                    learning_cards=dk.learning_cards,
                    young_cards=dk.young_cards,
                    mature_cards=dk.mature_cards,
                    suspended_cards=dk.suspended_cards,
                    avg_ease_factor=dk.avg_ease,
                    avg_interval_days=dk.avg_interval,
                    retention_rate=dk.retention_rate,
                    mastery_score=dk.mastery_score,
                )
            result["snapshots_saved"] = True
        except Exception as e:
            result["snapshot_error"] = str(e)
    
    return result


def get_course_knowledge_levels(
    course_id: str, 
    user_id: str,
    save_snapshot: bool = False
) -> dict:
    """
    Get knowledge levels for all lectures within a specific course.
    
    This tool provides per-lecture mastery breakdown for a course:
    - Course-level overall mastery (weighted by card count)
    - Per-lecture mastery scores and card distributions
    - Identifies weakest and strongest lectures
    - Provides targeted study recommendations
    
    Use this before tutoring sessions to understand which topics need attention.
    
    Args:
        course_id: UUID of the course
        user_id: UUID of the user
        save_snapshot: If True, saves snapshots for trend tracking
        
    Returns:
        Dictionary with:
        - status: "success" or "error"
        - course: Course info with overall_mastery
        - lectures: List of per-lecture breakdowns
        - weakest_lecture: Name of lecture needing most attention
        - strongest_lecture: Name of most mastered lecture
        - recommendations: Targeted study suggestions
        
    Example response:
        {
            "status": "success",
            "course": {
                "id": "uuid",
                "title": "Marketing 101",
                "overall_mastery": 0.67
            },
            "lectures": [
                {
                    "name": "Lecture 1 - Introduction",
                    "mastery_score": 0.85,
                    "total_cards": 45,
                    "status": "mastered"
                },
                {
                    "name": "Lecture 2 - Segmentation",
                    "mastery_score": 0.45,
                    "status": "needs_review"
                }
            ],
            "weakest_lecture": "Lecture 2 - Segmentation",
            "recommendations": ["Focus on 'Lecture 2' - 25 new cards waiting"]
        }
    """
    # Get course with materials from database
    course = _get_course().get_with_materials(user_id, course_id)
    
    if not course:
        return {
            "status": "error",
            "error": "Course not found or access denied",
            "course_id": course_id,
        }
    
    course_title = course.get("title", "Unknown Course")
    materials = course.get("materials", [])
    
    if not materials:
        return {
            "status": "success",
            "course": {
                "id": course_id,
                "title": course_title,
                "overall_mastery": 0.0,
                "total_cards": 0,
            },
            "lectures": [],
            "weakest_lecture": None,
            "strongest_lecture": None,
            "recommendations": [
                f"No materials found for '{course_title}'. Upload lecture PDFs to get started."
            ],
        }
    
    # Get knowledge from Anki
    service = get_knowledge_service()
    result = service.get_course_knowledge(
        course_id=course_id,
        course_title=course_title,
        materials=materials,
    )
    
    # Format response
    response = {
        "status": result.status,
        "course": {
            "id": result.course_id,
            "title": result.course_title,
            "overall_mastery": result.overall_mastery,
            "total_cards": result.total_cards,
        },
        "lectures": [asdict(lecture) for lecture in result.lectures],
        "weakest_lecture": result.weakest_lecture,
        "strongest_lecture": result.strongest_lecture,
        "recommendations": result.recommendations,
    }
    
    # Optionally save snapshots
    if save_snapshot and result.status == "success":
        try:
            for lecture in result.lectures:
                if lecture.total_cards > 0:
                    _get_knowledge().save_knowledge_snapshot(
                        user_id=user_id,
                        deck_name=lecture.deck_name,
                        total_cards=lecture.total_cards,
                        new_cards=lecture.new_cards,
                        learning_cards=lecture.learning_cards,
                        young_cards=lecture.young_cards,
                        mature_cards=lecture.mature_cards,
                        suspended_cards=0,
                        avg_ease_factor=lecture.avg_ease,
                        avg_interval_days=lecture.avg_interval_days,
                        retention_rate=lecture.retention_rate,
                        mastery_score=lecture.mastery_score,
                        course_id=course_id,
                        course_material_id=lecture.material_id,
                    )
                    
                    # Also save deck mapping
                    _get_knowledge().save_deck_mapping(
                        user_id=user_id,
                        course_id=course_id,
                        deck_name=lecture.deck_name,
                        course_material_id=lecture.material_id,
                    )
            response["snapshots_saved"] = True
        except Exception as e:
            response["snapshot_error"] = str(e)
    
    return response


def create_course_flashcard(
    course_id: str,
    user_id: str,
    material_id: str,
    question: str,
    answer: str,
    tags: Optional[list[str]] = None,
    sync_immediately: bool = True
) -> dict:
    """
    Create a flashcard with automatic deck naming based on course structure.
    
    The deck name is automatically generated as "Course Title::Lecture Name"
    based on the course and material IDs provided.
    
    Args:
        course_id: UUID of the course
        user_id: UUID of the user
        material_id: UUID of the course material (lecture)
        question: The front side of the card
        answer: The back side of the card
        tags: Optional list of tags
        sync_immediately: If True, sync to AnkiWeb after creating
        
    Returns:
        Dictionary with note_id, deck name, and sync status
    """
    # Get course and material info
    course = _get_course().get_with_materials(user_id, course_id)
    
    if not course:
        return {"status": "error", "error": "Course not found"}
    
    # Find the specific material
    materials = course.get("materials", [])
    material = next((m for m in materials if m.get("id") == material_id), None)
    
    if not material:
        return {"status": "error", "error": "Material not found in course"}
    
    # Build deck name
    course_title = course.get("title", "Unknown Course")
    file_name = material.get("file_name", "Unknown")
    deck_name = build_deck_name(course_title, file_name)
    
    # Create the flashcard
    result = create_flashcard(
        deck=deck_name,
        question=question,
        answer=answer,
        tags=tags,
        sync_immediately=sync_immediately,
    )
    
    # If successful, save the deck mapping and card mapping
    if result.get("status") == "success":
        try:
            # Save deck mapping
            _get_knowledge().save_deck_mapping(
                user_id=user_id,
                course_id=course_id,
                deck_name=deck_name,
                course_material_id=material_id,
            )
            
            # Save card mapping if we have a note_id
            note_id = result.get("note_id")
            if note_id:
                _get_knowledge().save_anki_card_mapping(
                    user_id=user_id,
                    anki_note_id=note_id,
                    deck_name=deck_name,
                )
            
            result["deck_name"] = deck_name
            result["course_title"] = course_title
            result["lecture_name"] = material.get("file_name")
        except Exception as e:
            result["mapping_error"] = str(e)
    
    return result


def create_course_flashcards_batch(
    course_id: str,
    user_id: str,
    material_id: str,
    cards: list[dict],
    sync_after: bool = True
) -> dict:
    """
    Create multiple flashcards for a course material with automatic deck naming.
    
    Args:
        course_id: UUID of the course
        user_id: UUID of the user
        material_id: UUID of the course material (lecture)
        cards: List of card dictionaries with keys:
               - question (required): Front of card
               - answer (required): Back of card
               - tags (optional): List of tags
        sync_after: Sync to AnkiWeb after creating all cards
        
    Returns:
        Dictionary with created note IDs, deck name, and any errors
    """
    # Get course and material info
    course = _get_course().get_with_materials(user_id, course_id)
    
    if not course:
        return {"status": "error", "error": "Course not found"}
    
    # Find the specific material
    materials = course.get("materials", [])
    material = next((m for m in materials if m.get("id") == material_id), None)
    
    if not material:
        return {"status": "error", "error": "Material not found in course"}
    
    # Build deck name
    course_title = course.get("title", "Unknown Course")
    file_name = material.get("file_name", "Unknown")
    deck_name = build_deck_name(course_title, file_name)
    
    # Create flashcards with the deck name
    result = create_flashcards_batch(
        cards=cards,
        default_deck=deck_name,
        sync_after=sync_after,
    )
    
    # If successful, save mappings
    if result.get("status") == "success":
        try:
            # Save deck mapping
            _get_knowledge().save_deck_mapping(
                user_id=user_id,
                course_id=course_id,
                deck_name=deck_name,
                course_material_id=material_id,
            )
            
            # Save card mappings
            note_ids = result.get("note_ids", [])
            for note_id in note_ids:
                if note_id:
                    _get_knowledge().save_anki_card_mapping(
                        user_id=user_id,
                        anki_note_id=note_id,
                        deck_name=deck_name,
                    )
            
            result["deck_name"] = deck_name
            result["course_title"] = course_title
            result["lecture_name"] = material.get("file_name")
        except Exception as e:
            result["mapping_error"] = str(e)
    
    return result
