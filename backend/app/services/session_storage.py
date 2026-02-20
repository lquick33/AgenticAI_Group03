"""
Study session conversation and message storage for Supabase.

This module provides helper functions to manage:
- Study conversations in the `conversations` table
- Chat messages in the `messages` table
- Progress (last_page_number) in conversations.metadata
"""

from typing import Any, Dict, List, Optional, Tuple

from app.adapters.supabase.client import get_supabase_client


SESSION_TYPE_STUDY = "study"


def _build_study_conversation_metadata(
    course_material_id: str,
    last_page_number: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Build metadata payload for a study conversation.

    Args:
        course_material_id: ID of the course material (UUID)
        last_page_number: Optional last visited page

    Returns:
        Dict suitable for the `metadata` JSONB column.
    """
    metadata: Dict[str, Any] = {"course_material_id": course_material_id}
    if last_page_number is not None:
        metadata["last_page_number"] = last_page_number
    return metadata


def get_or_create_study_conversation(
    user_id: str,
    course_material_id: str,
    course_id: Optional[str] = None,
    initial_page: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Get or create a study conversation for a user and course material.

    A conversation is uniquely identified by:
    - user_id
    - session_type = 'study'
    - metadata->>'course_material_id' = course_material_id

    Args:
        user_id: User ID (UUID)
        course_material_id: Course material ID (UUID)
        course_id: Optional course ID (UUID) for easier grouping
        initial_page: Optional initial page number to store in metadata

    Returns:
        Conversation record as dict
    """
    client = get_supabase_client()

    # Try to find existing conversation
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

    # Create new conversation
    metadata = _build_study_conversation_metadata(
        course_material_id=course_material_id,
        last_page_number=initial_page,
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
    """
    Update the last_page_number in a conversation's metadata.

    Args:
        conversation_id: Conversation ID (UUID)
        last_page_number: Last visited page number
    """
    client = get_supabase_client()

    try:
        # Fetch existing metadata to avoid overwriting unrelated fields
        response = (
            client.table("conversations")
            .select("metadata")
            .eq("id", conversation_id)
            .single()
            .execute()
        )

        metadata = response.data.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}

        metadata["last_page_number"] = last_page_number

        client.table("conversations").update({"metadata": metadata}).eq(
            "id", conversation_id
        ).execute()
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
            # Skip invalid messages silently to avoid breaking the flow
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

    Args:
        user_id: User ID (UUID)
        course_material_id: Course material ID (UUID)
        limit: Maximum number of messages to return (most recent first)

    Returns:
        Tuple of (conversation_dict_or_none, messages_list)
        Messages are ordered ascending by created_at (oldest first).
    """
    client = get_supabase_client()

    # Load conversation
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

    # Load messages
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
    # Reverse to oldest-first for UI and agent consumption
    messages.reverse()

    return conversation, messages

