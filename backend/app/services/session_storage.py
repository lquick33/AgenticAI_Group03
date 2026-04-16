"""
Study session conversation and message storage for Supabase.

This module provides helper functions to manage:
- Study conversations in the `conversations` table
- Chat messages in the `messages` table
- Progress and rollout metadata in conversations.metadata
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.adapters.supabase.client import get_supabase_client
from app.services.tutor_rollout import TutorGraphVersion, normalize_tutor_graph_version

SESSION_TYPE_STUDY = "study"
TUTOR_GRAPH_VERSION_METADATA_KEY = "tutor_graph_version"


def _build_study_conversation_metadata(
    course_material_id: str,
    last_page_number: Optional[int] = None,
    tutor_graph_version: TutorGraphVersion | None = None,
) -> Dict[str, Any]:
    """Build metadata payload for a study conversation."""
    metadata: Dict[str, Any] = {"course_material_id": course_material_id}
    if last_page_number is not None:
        metadata["last_page_number"] = last_page_number
    if tutor_graph_version is not None:
        metadata[TUTOR_GRAPH_VERSION_METADATA_KEY] = tutor_graph_version
    return metadata


def get_conversation_metadata(conversation_id: str) -> Dict[str, Any]:
    client = get_supabase_client()
    try:
        response = (
            client.table("conversations")
            .select("metadata")
            .eq("id", conversation_id)
            .single()
            .execute()
        )
    except Exception as e:
        raise Exception(f"Failed to load conversation metadata: {str(e)}")

    metadata = (response.data or {}).get("metadata") or {}
    if not isinstance(metadata, dict):
        return {}
    return metadata


def update_conversation_metadata(
    conversation_id: str,
    metadata_updates: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge metadata updates into the existing conversation metadata."""
    client = get_supabase_client()

    try:
        metadata = get_conversation_metadata(conversation_id)
        metadata.update(metadata_updates)
        client.table("conversations").update({"metadata": metadata}).eq(
            "id", conversation_id
        ).execute()
        return metadata
    except Exception as e:
        raise Exception(f"Failed to update conversation metadata: {str(e)}")


def get_tutor_graph_version_from_metadata(metadata: Any) -> TutorGraphVersion | None:
    if not isinstance(metadata, dict):
        return None
    return normalize_tutor_graph_version(metadata.get(TUTOR_GRAPH_VERSION_METADATA_KEY))


def set_conversation_tutor_graph_version(
    conversation_id: str,
    graph_version: TutorGraphVersion,
) -> Dict[str, Any]:
    return update_conversation_metadata(
        conversation_id,
        {TUTOR_GRAPH_VERSION_METADATA_KEY: graph_version},
    )


def get_or_create_study_conversation(
    user_id: str,
    course_material_id: str,
    course_id: Optional[str] = None,
    initial_page: Optional[int] = None,
    tutor_graph_version: TutorGraphVersion | None = None,
) -> Dict[str, Any]:
    """
    Get or create a study conversation for a user and course material.

    A conversation is uniquely identified by:
    - user_id
    - session_type = 'study'
    - metadata->>'course_material_id' = course_material_id
    """
    client = get_supabase_client()

    try:
        response = (
            client.table("conversations")
            .select("*")
            .eq("user_id", user_id)
            .eq("session_type", SESSION_TYPE_STUDY)
            .contains("metadata", {"course_material_id": course_material_id})
            .limit(1)
            .execute()
        )

        if response.data:
            return response.data[0]
    except Exception as e:
        raise Exception(f"Failed to load study conversation: {str(e)}")

    metadata = _build_study_conversation_metadata(
        course_material_id=course_material_id,
        last_page_number=initial_page,
        tutor_graph_version=tutor_graph_version,
    )

    insert_data: Dict[str, Any] = {
        "user_id": user_id,
        "session_type": SESSION_TYPE_STUDY,
        "metadata": metadata,
    }
    if course_id:
        insert_data["course_id"] = course_id

    try:
        insert_response = client.table("conversations").insert(insert_data).execute()
        if insert_response.data and len(insert_response.data) > 0:
            return insert_response.data[0]
        raise Exception("Failed to create study conversation")
    except Exception as e:
        raise Exception(f"Failed to create study conversation: {str(e)}")


def update_conversation_progress(
    conversation_id: str,
    last_page_number: int,
) -> None:
    """Update the last_page_number in a conversation's metadata."""
    try:
        update_conversation_metadata(
            conversation_id,
            {"last_page_number": last_page_number},
        )
    except Exception as e:
        raise Exception(f"Failed to update conversation progress: {str(e)}")


def append_messages(
    conversation_id: str,
    messages_with_roles: List[Dict[str, Any]],
) -> None:
    """
    Append messages to the messages table for a conversation.

    Args:
        conversation_id: Conversation ID (UUID)
        messages_with_roles: List of dicts with:
            - role: 'user' | 'assistant' | 'system'
            - content: message text
            - context_page_id: optional page_analyses.id
    """
    if not messages_with_roles:
        return

    client = get_supabase_client()

    records: List[Dict[str, Any]] = []
    for msg in messages_with_roles:
        role = msg.get("role")
        content = msg.get("content")
        context_page_id = msg.get("context_page_id")

        if not role or not content:
            continue

        record: Dict[str, Any] = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
        }
        if context_page_id:
            record["context_page_id"] = context_page_id

        records.append(record)

    if not records:
        return

    try:
        client.table("messages").insert(records).execute()
    except Exception as e:
        raise Exception(f"Failed to append messages: {str(e)}")


def load_conversation_with_messages(
    user_id: str,
    course_material_id: str,
    limit: int = 50,
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Load a study conversation and its messages for a user and course material.

    Returns:
        Tuple of (conversation_dict_or_none, messages_list)
        Messages are ordered ascending by created_at (oldest first).
    """
    client = get_supabase_client()

    try:
        conv_response = (
            client.table("conversations")
            .select("*")
            .eq("user_id", user_id)
            .eq("session_type", SESSION_TYPE_STUDY)
            .contains("metadata", {"course_material_id": course_material_id})
            .limit(1)
            .execute()
        )
    except Exception as e:
        raise Exception(f"Failed to load study conversation: {str(e)}")

    if not conv_response.data:
        return None, []

    conversation = conv_response.data[0]
    conversation_id = conversation["id"]

    try:
        msg_response = (
            client.table("messages")
            .select("id, role, content, created_at, context_page_id")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as e:
        raise Exception(f"Failed to load messages: {str(e)}")

    messages = msg_response.data or []
    messages.reverse()

    return conversation, messages
