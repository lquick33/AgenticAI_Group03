"""
Supabase Knowledge Tracking adapter.

Implements KnowledgeTrackingRepository using Supabase Postgres.

Extracted from app.services.storage (lines 2840–3286).
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from supabase import Client

logger = logging.getLogger(__name__)


class SupabaseKnowledgeAdapter:
    """
    Concrete KnowledgeTrackingRepository backed by Supabase Postgres.

    Handles:
      - Course ↔ Anki deck mappings
      - Anki card ↔ flashcard mappings
      - Knowledge snapshots (per-deck stats over time)
      - Anki study history (daily review stats)
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    # -- Deck Mappings ---------------------------------------------------------

    def save_deck_mapping(
        self,
        user_id: str,
        course_id: str,
        deck_name: str,
        course_material_id: Optional[str] = None,
    ) -> dict:
        """Save or update a course-to-deck mapping."""
        data: Dict = {
            "user_id": user_id,
            "course_id": course_id,
            "deck_name": deck_name,
        }
        if course_material_id:
            data["course_material_id"] = course_material_id

        try:
            response = (
                self._client.table("course_deck_mappings")
                .upsert(data, on_conflict="user_id,deck_name")
                .execute()
            )
            return response.data[0] if response.data else data
        except Exception as e:
            logger.error(f"Error saving deck mapping: {e}")
            raise

    def get_deck_mappings_for_course(
        self, user_id: str, course_id: str
    ) -> List[dict]:
        """Get all deck mappings for a course."""
        try:
            response = (
                self._client.table("course_deck_mappings")
                .select("*")
                .eq("user_id", user_id)
                .eq("course_id", course_id)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Error getting deck mappings: {e}")
            return []

    # -- Anki Card Mappings ----------------------------------------------------

    def save_anki_card_mapping(
        self,
        user_id: str,
        anki_note_id: int,
        deck_name: str,
        flashcard_id: Optional[str] = None,
    ) -> dict:
        """Save a mapping between an Anki note and an agent-generated flashcard."""
        data: Dict = {
            "user_id": user_id,
            "anki_note_id": anki_note_id,
            "deck_name": deck_name,
        }
        if flashcard_id:
            data["flashcard_id"] = flashcard_id

        try:
            response = (
                self._client.table("anki_card_mappings")
                .upsert(data, on_conflict="user_id,anki_note_id")
                .execute()
            )
            return response.data[0] if response.data else data
        except Exception as e:
            logger.error(f"Error saving Anki card mapping: {e}")
            raise

    # -- Knowledge Snapshots ---------------------------------------------------

    def save_knowledge_snapshot(
        self,
        user_id: str,
        deck_name: str,
        total_cards: int,
        new_cards: int,
        learning_cards: int,
        young_cards: int,
        mature_cards: int,
        suspended_cards: int = 0,
        avg_ease_factor: Optional[float] = None,
        avg_interval_days: Optional[float] = None,
        retention_rate: Optional[float] = None,
        mastery_score: Optional[float] = None,
        course_id: Optional[str] = None,
        course_material_id: Optional[str] = None,
    ) -> dict:
        """Save a point-in-time knowledge snapshot for a deck."""
        data: Dict = {
            "user_id": user_id,
            "deck_name": deck_name,
            "total_cards": total_cards,
            "new_cards": new_cards,
            "learning_cards": learning_cards,
            "young_cards": young_cards,
            "mature_cards": mature_cards,
            "suspended_cards": suspended_cards,
            "avg_ease_factor": avg_ease_factor,
            "avg_interval_days": avg_interval_days,
            "retention_rate": retention_rate,
            "mastery_score": mastery_score,
        }

        if course_id:
            data["course_id"] = course_id
        if course_material_id:
            data["course_material_id"] = course_material_id

        try:
            response = (
                self._client.table("deck_knowledge_snapshots")
                .insert(data)
                .execute()
            )
            return response.data[0] if response.data else data
        except Exception as e:
            logger.error(f"Error saving knowledge snapshot: {e}")
            raise

    def get_latest_knowledge_snapshot(
        self, user_id: str, deck_name: str
    ) -> Optional[dict]:
        """Get the most recent knowledge snapshot for a deck."""
        try:
            response = (
                self._client.table("deck_knowledge_snapshots")
                .select("*")
                .eq("user_id", user_id)
                .eq("deck_name", deck_name)
                .order("captured_at", desc=True)
                .limit(1)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error getting knowledge snapshot: {e}")
            return None

    def get_knowledge_snapshots_for_course(
        self,
        user_id: str,
        course_id: str,
        limit: int = 30,
    ) -> List[dict]:
        """Get recent knowledge snapshots for all decks in a course."""
        try:
            response = (
                self._client.table("deck_knowledge_snapshots")
                .select("*")
                .eq("user_id", user_id)
                .eq("course_id", course_id)
                .order("captured_at", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(
                f"Error getting course knowledge snapshots: {e}"
            )
            return []

    # -- Anki Study History ----------------------------------------------------

    def upsert_study_history(
        self,
        user_id: str,
        study_date: str,
        cards_reviewed: int,
        time_spent_seconds: int = 0,
        again_count: int = 0,
        hard_count: int = 0,
        good_count: int = 0,
        easy_count: int = 0,
        new_cards: int = 0,
        review_cards: int = 0,
        relearn_cards: int = 0,
        avg_time_per_card_ms: int = 0,
    ) -> Optional[dict]:
        """Insert or update a study history entry for a specific date."""
        try:
            data = {
                "user_id": user_id,
                "study_date": study_date,
                "cards_reviewed": cards_reviewed,
                "time_spent_seconds": time_spent_seconds,
                "again_count": again_count,
                "hard_count": hard_count,
                "good_count": good_count,
                "easy_count": easy_count,
                "new_cards": new_cards,
                "review_cards": review_cards,
                "relearn_cards": relearn_cards,
                "avg_time_per_card_ms": avg_time_per_card_ms,
            }

            response = (
                self._client.table("anki_study_history")
                .upsert(data, on_conflict="user_id,study_date")
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error upserting study history: {e}")
            return None

    def sync_study_history(
        self,
        user_id: str,
        stats_list: list,
    ) -> dict:
        """
        Bulk sync study history from Anki.

        Args:
            stats_list: List of DailyStudyStats objects or dicts
        """
        synced = 0
        errors: List[str] = []

        for stats in stats_list:
            try:
                if hasattr(stats, "date"):
                    data = {
                        "user_id": user_id,
                        "study_date": stats.date,
                        "cards_reviewed": stats.cards_reviewed,
                        "time_spent_seconds": stats.time_spent_seconds,
                        "again_count": stats.again_count,
                        "hard_count": stats.hard_count,
                        "good_count": stats.good_count,
                        "easy_count": stats.easy_count,
                        "new_cards": stats.new_cards,
                        "review_cards": stats.review_cards,
                        "relearn_cards": stats.relearn_cards,
                        "avg_time_per_card_ms": stats.avg_time_per_card_ms,
                    }
                else:
                    data = {
                        "user_id": user_id,
                        "study_date": stats["date"],
                        "cards_reviewed": stats["cards_reviewed"],
                        "time_spent_seconds": stats.get(
                            "time_spent_seconds", 0
                        ),
                        "again_count": stats.get("again_count", 0),
                        "hard_count": stats.get("hard_count", 0),
                        "good_count": stats.get("good_count", 0),
                        "easy_count": stats.get("easy_count", 0),
                        "new_cards": stats.get("new_cards", 0),
                        "review_cards": stats.get("review_cards", 0),
                        "relearn_cards": stats.get("relearn_cards", 0),
                        "avg_time_per_card_ms": stats.get(
                            "avg_time_per_card_ms", 0
                        ),
                    }

                self._client.table("anki_study_history").upsert(
                    data, on_conflict="user_id,study_date"
                ).execute()
                synced += 1
            except Exception as e:
                errors.append(str(e))
                logger.error(
                    f"Error syncing study history for date {stats}: {e}"
                )

        return {"synced": synced, "errors": errors}

    def get_study_history(
        self,
        user_id: str,
        days: int = 90,
    ) -> list:
        """
        Get study history for a user.

        Returns:
            List of study history records sorted by date (oldest first)
        """
        cutoff_date = (
            datetime.now() - timedelta(days=days)
        ).strftime("%Y-%m-%d")

        try:
            response = (
                self._client.table("anki_study_history")
                .select(
                    "study_date, cards_reviewed, time_spent_seconds, "
                    "again_count, hard_count, good_count, easy_count, "
                    "new_cards, review_cards, relearn_cards, "
                    "avg_time_per_card_ms"
                )
                .eq("user_id", user_id)
                .gte("study_date", cutoff_date)
                .order("study_date", desc=False)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Error getting study history: {e}")
            return []
