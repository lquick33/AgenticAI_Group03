"""
Supabase Message adapter.

Implements MessageRepository for conversation message persistence.

Extracted from app.services.storage (lines 1693–1839).
"""

import logging
from typing import Dict, List

from supabase import Client

logger = logging.getLogger(__name__)


class SupabaseMessageAdapter:
    """
    Concrete MessageRepository backed by Supabase Postgres.

    Handles message retrieval by page context with ownership validation
    via conversation join.
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    # -- MessageRepository Protocol --------------------------------------------

    def get_for_page(
        self,
        page_analysis_id: str,
        user_id: str,
    ) -> List[dict]:
        """
        Get all messages associated with a specific page analysis.

        Messages are filtered by context_page_id and validated to ensure
        they belong to a conversation owned by the user.

        Args:
            page_analysis_id: Page analysis ID (UUID)
            user_id: User ID for authorization (RLS)

        Returns:
            List of message dicts ordered chronologically (oldest first)

        Raises:
            Exception: If database operation fails
        """
        try:
            response = (
                self._client.table("messages")
                .select("id, role, content, created_at, context_page_id, conversation_id")
                .eq("context_page_id", page_analysis_id)
                .execute()
            )

            if not response.data:
                return []

            # Collect unique conversation IDs for ownership validation
            conversation_ids = list(set(
                msg.get("conversation_id")
                for msg in response.data
                if msg.get("conversation_id")
            ))

            if not conversation_ids:
                return []

            # Validate ownership in a single query
            conv_response = (
                self._client.table("conversations")
                .select("id")
                .in_("id", conversation_ids)
                .eq("user_id", user_id)
                .execute()
            )

            valid_conversation_ids = {
                conv["id"] for conv in (conv_response.data or [])
            }

            # Filter to messages from valid (owned) conversations
            filtered_messages = [
                msg
                for msg in response.data
                if msg.get("conversation_id") in valid_conversation_ids
            ]

            # Sort by created_at (oldest first)
            filtered_messages.sort(key=lambda x: x.get("created_at", ""))

            return filtered_messages
        except Exception as e:
            raise Exception(f"Failed to get messages for page: {str(e)}")

    def get_for_pages_batch(
        self,
        page_ids: List[str],
        user_id: str,
    ) -> Dict[str, List[dict]]:
        """
        Batch fetch messages for multiple pages in a single query.

        Performance optimization: Replaces N+1 queries with 2 queries total.
        Used during flashcard generation to prefetch all messages upfront.

        Args:
            page_ids: List of page analysis IDs (UUIDs)
            user_id: User ID for authorization (RLS)

        Returns:
            Dict mapping page_id -> list of message dicts
            Messages are ordered chronologically within each page

        Raises:
            Exception: If database operation fails
        """
        if not page_ids:
            return {}

        try:
            response = (
                self._client.table("messages")
                .select("id, role, content, created_at, context_page_id, conversation_id")
                .in_("context_page_id", page_ids)
                .execute()
            )

            if not response.data:
                return {}

            # Get all unique conversation IDs
            conversation_ids = list(set(
                msg.get("conversation_id")
                for msg in response.data
                if msg.get("conversation_id")
            ))

            if not conversation_ids:
                return {}

            # Validate ownership for all conversations in a single query
            conv_response = (
                self._client.table("conversations")
                .select("id")
                .in_("id", conversation_ids)
                .eq("user_id", user_id)
                .execute()
            )

            valid_conversation_ids = {
                conv["id"] for conv in (conv_response.data or [])
            }

            # Group messages by page_id, filtering for valid conversations
            messages_by_page: Dict[str, List[dict]] = {}

            for msg in response.data:
                if msg.get("conversation_id") not in valid_conversation_ids:
                    continue

                page_id = msg.get("context_page_id")
                if page_id:
                    if page_id not in messages_by_page:
                        messages_by_page[page_id] = []
                    messages_by_page[page_id].append(msg)

            # Sort messages within each page by created_at (oldest first)
            for page_id in messages_by_page:
                messages_by_page[page_id].sort(
                    key=lambda x: x.get("created_at", "")
                )

            return messages_by_page

        except Exception as e:
            raise Exception(f"Failed to batch fetch messages for pages: {str(e)}")
