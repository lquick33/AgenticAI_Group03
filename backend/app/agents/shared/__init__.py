"""
Shared agent utilities.

Provides unified, deduplicated components used across multiple agents:
- StateAwareToolNode: Prevents LLM hallucination of IDs in tool calls
- fix_incomplete_tool_calls: Fixes Gemini message ordering violations
- compute_state_hash: Prompt caching optimization
"""

from app.agents.shared.state_aware_tool_node import StateAwareToolNode
from app.agents.shared.message_utils import fix_incomplete_tool_calls
from app.agents.shared.prompt_cache import compute_state_hash

__all__ = [
    "StateAwareToolNode",
    "fix_incomplete_tool_calls",
    "compute_state_hash",
]
