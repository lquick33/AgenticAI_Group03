"""
Unified StateAwareToolNode.

Merges the duplicated implementations from TutorAgent and QuickChatAgent
into a single class that handles all tool types. Adopts the QuickChat
pattern of global user_id injection, plus per-tool overrides for
course_material_id and page_number.

Design rationale:
    LLMs frequently hallucinate UUID values when calling tools that
    expect ID parameters. This node intercepts tool calls from the LLM
    and replaces parameter values with the actual state values, ensuring
    correctness without relying on the LLM's memory.
"""

from typing import Optional, Any, Dict, List
import logging

from langchain_core.messages import AIMessage
from langgraph.prebuilt import ToolNode

logger = logging.getLogger(__name__)


# Tools that need course_material_id injected from state
_TOOLS_NEEDING_MATERIAL_ID = {
    "get_page_analysis",
    "get_course_material_summary",
    "create_quiz",
    "get_page_image",
}

# Tools that need page_number injected from state (only if not explicitly set by LLM)
_TOOLS_NEEDING_PAGE_NUMBER = {
    "get_page_analysis",
    "get_page_image",
}

# Tools that only need user_id (already handled by global injection)
_TOOLS_USER_ID_ONLY = {
    "search_topic",
    "get_user_courses",
    "text_to_speech",
    "get_course_knowledge",
}


def _inject_state_into_tool_calls(
    tool_calls: list,
    state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Inject state values into tool call arguments.

    This is the core logic shared between invoke() and ainvoke().

    Args:
        tool_calls: Raw tool calls from the LLM's AIMessage
        state: Current agent state containing material_id, user_id, etc.

    Returns:
        Modified tool calls with injected state values
    """
    modified_tool_calls = []

    for tool_call in tool_calls:
        # Extract tool call fields (handles both dict and object forms)
        if isinstance(tool_call, dict):
            tool_name = tool_call.get("name", "")
            tool_id = tool_call.get("id", "")
            args = dict(tool_call.get("args", {}) or {})
        else:
            tool_name = getattr(tool_call, "name", "")
            tool_id = getattr(tool_call, "id", "")
            args = dict(getattr(tool_call, "args", {}) or {})

        # ALWAYS inject user_id from state — never trust the LLM's value.
        # The LLM often generates placeholder values like "test-user-id"
        if state.get("user_id"):
            args["user_id"] = state["user_id"]

        # Inject course_material_id for tools that need it
        if tool_name in _TOOLS_NEEDING_MATERIAL_ID:
            if state.get("material_id"):
                args["course_material_id"] = state["material_id"]

        # Inject page_number only if NOT explicitly provided by LLM
        # (LLM might intentionally specify a different page, like page 30)
        if tool_name in _TOOLS_NEEDING_PAGE_NUMBER:
            if "page_number" not in args or args.get("page_number") is None:
                if state.get("current_page") is not None:
                    args["page_number"] = state["current_page"]

        modified_tool_calls.append({
            "id": tool_id,
            "name": tool_name,
            "args": args,
        })

    return modified_tool_calls


def _modify_last_message(messages: list, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    If the last message has tool calls, create a modified state with
    injected tool call arguments.

    Returns:
        Tuple of (modified_state_or_None, should_use_modified)
    """
    if not messages:
        return None

    last_message = messages[-1]

    if not (hasattr(last_message, "tool_calls") and last_message.tool_calls):
        return None

    modified_tool_calls = _inject_state_into_tool_calls(
        last_message.tool_calls, state
    )

    modified_message = AIMessage(
        content=last_message.content if hasattr(last_message, "content") else "",
        tool_calls=modified_tool_calls,
    )

    modified_messages = messages[:-1] + [modified_message]
    return {**state, "messages": modified_messages}


class StateAwareToolNode(ToolNode):
    """
    ToolNode that automatically injects state values into tool calls.

    Prevents the LLM from hallucinating IDs (material_id, user_id,
    page_number) by overriding tool call arguments with authoritative
    values from the agent state.

    Handles ALL tool types across all agents:
        - Tutor: get_page_analysis, get_course_material_summary,
                 create_quiz, get_page_image
        - QuickChat: search_topic, get_user_courses (+ all tutor tools)
        - Shared: text_to_speech, get_course_knowledge
    """

    def invoke(self, input: Dict[str, Any], config: Optional[Any] = None) -> Dict[str, Any]:
        """Execute tools with automatic state injection."""
        messages = input.get("messages", [])
        modified_state = _modify_last_message(messages, input)

        if modified_state is not None:
            return super().invoke(modified_state, config)

        return super().invoke(input, config)

    async def ainvoke(self, input: Dict[str, Any], config: Optional[Any] = None) -> Dict[str, Any]:
        """Execute tools asynchronously with automatic state injection."""
        messages = input.get("messages", [])
        modified_state = _modify_last_message(messages, input)

        if modified_state is not None:
            return await super().ainvoke(modified_state, config)

        return await super().ainvoke(input, config)
