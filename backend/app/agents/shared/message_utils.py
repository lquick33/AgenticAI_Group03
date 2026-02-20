"""
Message utilities for Gemini API compliance.

Extracted from TutorAgent._fix_incomplete_tool_calls to be shared
across all agents that interact with the Gemini API.
"""

import logging
from typing import List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

logger = logging.getLogger(__name__)


def fix_incomplete_tool_calls(messages: list) -> list:
    """
    Validate and fix message ordering to comply with Gemini API requirements.

    Gemini API requires strict ordering:
    - User message (HumanMessage)
    - Assistant with tool_calls (AIMessage with tool_calls)
      → MUST come immediately after HumanMessage or ToolMessage
    - Tool responses (ToolMessage)
      → MUST come immediately after AIMessage with tool_calls
    - (Optional) Assistant final response (AIMessage without tool_calls)
    - User message (HumanMessage)

    This function:
    1. Removes any AIMessage with tool_calls that doesn't have
       corresponding ToolMessages
    2. Ensures ToolMessages come immediately after their AIMessage
    3. Removes orphaned ToolMessages (without preceding AIMessage)
    4. Ensures AIMessage with tool_calls only comes after
       HumanMessage or ToolMessage

    Args:
        messages: List of messages to check

    Returns:
        Fixed list of messages that comply with Gemini API requirements
    """
    if not messages:
        return messages

    fixed_messages = []
    i = 0

    while i < len(messages):
        msg = messages[i]

        # Skip SystemMessage — it doesn't affect the turn order
        if isinstance(msg, SystemMessage):
            fixed_messages.append(msg)
            i += 1
            continue

        # Check if this is an AIMessage with tool_calls
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            # CRITICAL: Gemini requires AIMessage with tool_calls to come
            # immediately after HumanMessage or ToolMessage.
            # Check the previous non-SystemMessage.
            prev_msg_index = len(fixed_messages) - 1
            while prev_msg_index >= 0 and isinstance(
                fixed_messages[prev_msg_index], SystemMessage
            ):
                prev_msg_index -= 1

            # Check if previous message is valid (HumanMessage or ToolMessage)
            is_valid_previous = False
            if prev_msg_index >= 0:
                prev_msg = fixed_messages[prev_msg_index]
                if isinstance(prev_msg, (HumanMessage, ToolMessage)):
                    is_valid_previous = True
            elif i > 0:
                # Check original messages list if fixed_messages is empty
                # or only has SystemMessages
                for k in range(i - 1, -1, -1):
                    if not isinstance(messages[k], SystemMessage):
                        if isinstance(messages[k], (HumanMessage, ToolMessage)):
                            is_valid_previous = True
                        break

            if not is_valid_previous:
                logger.warning(
                    f"Invalid message order at index {i}: AIMessage with tool_calls "
                    f"must come immediately after HumanMessage or ToolMessage. "
                    f"Removing to prevent API error."
                )
                i += 1
                continue

            # Collect all tool call IDs from this AIMessage
            tool_call_ids = set()
            for tool_call in msg.tool_calls:
                tool_call_id = (
                    tool_call.get("id")
                    if isinstance(tool_call, dict)
                    else getattr(tool_call, "id", None)
                )
                if tool_call_id:
                    tool_call_ids.add(tool_call_id)

            # Look ahead to find corresponding ToolMessages
            # They should come immediately after the AIMessage
            found_tool_messages = []
            j = i + 1
            while j < len(messages) and isinstance(messages[j], ToolMessage):
                tool_msg = messages[j]
                tool_call_id = getattr(tool_msg, "tool_call_id", None)
                if tool_call_id in tool_call_ids:
                    found_tool_messages.append(tool_msg)
                j += 1

            # Check if all tool calls have corresponding ToolMessages
            found_tool_call_ids = {
                getattr(tm, "tool_call_id", None) for tm in found_tool_messages
            }

            if (
                found_tool_call_ids == tool_call_ids
                and len(found_tool_messages) == len(tool_call_ids)
            ):
                # All tool calls have responses — keep the pair
                fixed_messages.append(msg)
                fixed_messages.extend(found_tool_messages)
                i = j  # Skip past the ToolMessages
            else:
                # Incomplete tool call pair — remove the AIMessage
                logger.warning(
                    f"Incomplete tool call pair detected at index {i}: "
                    f"AIMessage has {len(tool_call_ids)} tool_calls, but only "
                    f"{len(found_tool_messages)} ToolMessages found. "
                    f"Removing incomplete AIMessage to prevent API error."
                )
                i += 1  # Skip the incomplete AIMessage

        elif isinstance(msg, ToolMessage):
            # Orphaned ToolMessage (no preceding AIMessage with tool_calls)
            logger.warning(
                f"Orphaned ToolMessage detected at index {i}, "
                f"removing to prevent API error."
            )
            i += 1

        else:
            # Regular message (HumanMessage, AIMessage without tool_calls)
            fixed_messages.append(msg)
            i += 1

    return fixed_messages
