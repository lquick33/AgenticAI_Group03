"""
Supabase Flashcard adapter.

Implements FlashcardRepository using Supabase Postgres.

Extracted from app.services.storage (lines 1842–2430).
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from supabase import Client

logger = logging.getLogger(__name__)


class SupabaseFlashcardAdapter:
    """
    Concrete FlashcardRepository backed by Supabase Postgres.

    Handles:
      - Flashcard CRUD (save, get by material, get by course)
      - Flashcard cache (Anki-aligned deduplication layer)
      - Anki ↔ cache sync
      - Deck rename propagation on course / material rename
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    # -- FlashcardRepository: core CRUD ----------------------------------------

    def save_flashcards(
        self,
        flashcards: List[dict],
        user_id: str,
        course_id: str,
    ) -> None:
        """
        Batch-insert flashcards.

        Args:
            flashcards: Dicts with front, back, tags, source_page_analysis_id
            user_id: Owner UUID
            course_id: Course UUID
        """
        if not flashcards:
            return

        try:
            records = []
            for card in flashcards:
                tags = card.get("tags", [])
                if isinstance(tags, list):
                    tags_str = " ".join(str(tag) for tag in tags)
                else:
                    tags_str = str(tags) if tags else ""

                record = {
                    "course_id": course_id,
                    "user_id": user_id,
                    "front": card.get("front", ""),
                    "back": card.get("back", ""),
                }

                if card.get("source_page_analysis_id"):
                    record["source_page_analysis_id"] = card[
                        "source_page_analysis_id"
                    ]

                records.append(record)

            self._client.table("flashcards").insert(records).execute()
        except Exception as e:
            raise Exception(f"Failed to save flashcards: {str(e)}")

    def get_for_material(
        self,
        course_material_id: str,
        user_id: str,
        page_analysis_ids: List[str],
    ) -> List[dict]:
        """
        Get flashcards linked to page analyses of a material.

        Args:
            course_material_id: Material UUID (for semantic clarity)
            user_id: Owner UUID
            page_analysis_ids: Pre-fetched page analysis IDs from
                PageAnalysisAdapter.get_all_for_material
        """
        if not page_analysis_ids:
            return []

        try:
            response = (
                self._client.table("flashcards")
                .select(
                    "id, front, back, source_page_analysis_id, "
                    "created_at, course_id, user_id"
                )
                .eq("user_id", user_id)
                .in_("source_page_analysis_id", page_analysis_ids)
                .order("created_at", desc=False)
                .execute()
            )
            return response.data if response.data else []
        except Exception as e:
            raise Exception(
                f"Failed to get flashcards for material: {str(e)}"
            )

    # -- Flashcard Cache (Anki-aligned) ----------------------------------------

    def cache_flashcards(
        self,
        cards: List[dict],
        anki_note_ids: List[int],
        user_id: str,
        deck_name: str,
        course_id: Optional[str] = None,
        synced_to_ankiweb: bool = False,
    ) -> None:
        """
        Cache flashcards after adding to Anki.

        Tags already contain metadata (page:N, source:uuid).
        """
        if not cards or not anki_note_ids:
            return

        records = []
        for card, note_id in zip(cards, anki_note_ids):
            if note_id:
                records.append(
                    {
                        "user_id": user_id,
                        "anki_note_id": note_id,
                        "deck_name": deck_name,
                        "front": card["front"],
                        "back": card["back"],
                        "tags": card.get("tags", []),
                        "course_id": course_id,
                        "synced_to_ankiweb": synced_to_ankiweb,
                    }
                )

        if records:
            try:
                self._client.table("flashcard_cache").upsert(
                    records, on_conflict="user_id,anki_note_id"
                ).execute()
            except Exception as e:
                logger.warning(f"Failed to cache flashcards: {e}")

    def get_cached_for_material(
        self, deck_name: str, user_id: str
    ) -> List[dict]:
        """Get cached flashcards for a specific lecture deck."""
        try:
            response = (
                self._client.table("flashcard_cache")
                .select("id, anki_note_id, front, back, tags, created_at")
                .eq("user_id", user_id)
                .eq("deck_name", deck_name)
                .order("created_at", desc=False)
                .execute()
            )
            return response.data if response.data else []
        except Exception as e:
            raise Exception(f"Failed to get cached flashcards: {str(e)}")

    def get_cached_for_course(
        self, course_id: str, user_id: str
    ) -> List[dict]:
        """Get all cached flashcards for a course (all lectures)."""
        try:
            response = (
                self._client.table("flashcard_cache")
                .select("id, anki_note_id, deck_name, front, back, tags")
                .eq("user_id", user_id)
                .eq("course_id", course_id)
                .execute()
            )
            return response.data if response.data else []
        except Exception as e:
            raise Exception(
                f"Failed to get cached flashcards for course: {str(e)}"
            )

    def get_cached_by_deck_pattern(
        self, deck_pattern: str, user_id: str
    ) -> List[dict]:
        """Get cached flashcards matching a deck name pattern."""
        try:
            response = (
                self._client.table("flashcard_cache")
                .select("id, anki_note_id, deck_name, front, back, tags")
                .eq("user_id", user_id)
                .like("deck_name", deck_pattern)
                .execute()
            )
            return response.data if response.data else []
        except Exception as e:
            raise Exception(
                f"Failed to get cached flashcards by pattern: {str(e)}"
            )

    def delete_cached_for_deck(
        self, deck_name: str, user_id: str
    ) -> int:
        """Delete cached flashcards for a specific deck."""
        try:
            response = (
                self._client.table("flashcard_cache")
                .delete()
                .eq("user_id", user_id)
                .eq("deck_name", deck_name)
                .execute()
            )
            return len(response.data) if response.data else 0
        except Exception as e:
            raise Exception(f"Failed to delete cached flashcards: {str(e)}")

    def update_cached_deck_names(
        self,
        old_pattern: str,
        new_prefix: str,
        old_prefix: str,
        user_id: str,
    ) -> int:
        """Update deck names in cache when course or material is renamed."""
        try:
            response = (
                self._client.table("flashcard_cache")
                .select("id, deck_name")
                .eq("user_id", user_id)
                .like("deck_name", old_pattern)
                .execute()
            )

            if not response.data:
                return 0

            count = 0
            batch_size = 50
            for record in response.data:
                old_deck = record["deck_name"]
                new_deck = old_deck.replace(old_prefix, new_prefix, 1)
                self._client.table("flashcard_cache").update(
                    {"deck_name": new_deck}
                ).eq("id", record["id"]).execute()
                count += 1

            return count
        except Exception as e:
            raise Exception(
                f"Failed to update cached deck names: {str(e)}"
            )

    def get_unsynced_count(self, user_id: str) -> int:
        """Get count of flashcards not yet synced to AnkiWeb."""
        try:
            response = (
                self._client.table("flashcard_cache")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .eq("synced_to_ankiweb", False)
                .execute()
            )
            return response.count if response.count else 0
        except Exception as e:
            logger.warning(f"Failed to get unsynced flashcard count: {e}")
            return 0

    def mark_as_synced(self, user_id: str) -> int:
        """Mark all unsynced flashcards as synced to AnkiWeb."""
        try:
            response = (
                self._client.table("flashcard_cache")
                .update({"synced_to_ankiweb": True})
                .eq("user_id", user_id)
                .eq("synced_to_ankiweb", False)
                .execute()
            )
            return len(response.data) if response.data else 0
        except Exception as e:
            logger.warning(f"Failed to mark flashcards as synced: {e}")
            return 0

    def sync_cache_from_anki(
        self,
        parent_deck: str,
        user_id: str,
        course_id: Optional[str] = None,
    ) -> dict:
        """
        Pull changes from Anki into flashcard_cache.
        Anki integration is DISABLED. Returns empty stats.
        """
        return {
            "inserted": 0,
            "updated": 0,
            "deleted": 0,
            "unchanged": 0,
            "errors": [],
        }

    # -- Deck rename handlers --------------------------------------------------

    def on_course_renamed(
        self,
        course_id: str,
        old_title: str,
        new_title: str,
        user_id: str,
    ) -> dict:
        """
        Handle course rename — update all lecture decks in Anki and cache.
        """
        result: Dict = {
            "anki_decks_renamed": 0,
            "cache_entries_updated": 0,
            "errors": [],
        }

        try:
            materials_response = (
                self._client.table("course_materials")
                .select("id, file_name")
                .eq("course_id", course_id)
                .eq("user_id", user_id)
                .execute()
            )
            materials = materials_response.data or []

            # Anki integration disabled

            try:
                updated = self.update_cached_deck_names(
                    old_pattern=f"{old_title}::%",
                    new_prefix=new_title,
                    old_prefix=old_title,
                    user_id=user_id,
                )
                result["cache_entries_updated"] = updated
            except Exception as e:
                result["errors"].append(f"Cache update failed: {e}")

            logger.info(
                f"Course renamed: {old_title} -> {new_title}, "
                f"Anki: {result['anki_decks_renamed']}, "
                f"Cache: {result['cache_entries_updated']}"
            )

        except Exception as e:
            result["errors"].append(f"Course rename failed: {e}")

        return result

    def on_material_renamed(
        self,
        material_id: str,
        old_file_name: str,
        new_file_name: str,
        user_id: str,
    ) -> dict:
        """
        Handle lecture file rename — update deck name in Anki and cache.
        """
        result: Dict = {
            "anki_deck_renamed": False,
            "cache_entries_updated": 0,
            "errors": [],
        }

        try:
            material_response = (
                self._client.table("course_materials")
                .select("course_id")
                .eq("id", material_id)
                .single()
                .execute()
            )

            if not material_response.data:
                result["errors"].append("Material not found")
                return result

            course_id = material_response.data["course_id"]

            course_response = (
                self._client.table("courses")
                .select("title")
                .eq("id", course_id)
                .single()
                .execute()
            )

            if not course_response.data:
                result["errors"].append("Course not found")
                return result

            course_title = course_response.data["title"]
            old_lecture = Path(old_file_name).stem
            new_lecture = Path(new_file_name).stem

            old_deck = f"{course_title}::{old_lecture}"
            new_deck = f"{course_title}::{new_lecture}"

            # Anki integration disabled

            try:
                updated = self.update_cached_deck_names(
                    old_pattern=old_deck,
                    new_prefix=new_deck,
                    old_prefix=old_deck,
                    user_id=user_id,
                )
                result["cache_entries_updated"] = updated
            except Exception as e:
                result["errors"].append(f"Cache update failed: {e}")

            logger.info(
                f"Material renamed: {old_deck} -> {new_deck}, "
                f"Anki: {result['anki_deck_renamed']}, "
                f"Cache: {result['cache_entries_updated']}"
            )

        except Exception as e:
            result["errors"].append(f"Material rename failed: {e}")

        return result

    # -- Tag helpers -----------------------------------------------------------

    @staticmethod
    def extract_source_from_tags(tags: List[str]) -> Optional[str]:
        """Extract page_analysis_id from tags (source:uuid format)."""
        if not tags:
            return None
        for tag in tags:
            if tag.startswith("source:"):
                return tag[7:]
        return None

    @staticmethod
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
