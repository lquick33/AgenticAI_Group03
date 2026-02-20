"""
Prompt caching utilities.

Extracted from TutorAgent._compute_state_hash for reuse across
agents that need to detect when their enhanced system prompt
needs to be rebuilt.
"""

import hashlib
from typing import Any, Optional


def compute_state_hash(
    material_id: Optional[str] = None,
    current_page: Optional[Any] = None,
    user_id: Optional[str] = None,
    summary: Optional[Any] = None,
) -> str:
    """
    Compute a hash of state values relevant for prompt caching.

    Used to detect when the enhanced prompt needs to be rebuilt.
    If hash matches cached hash, the cached prompt can be reused,
    avoiding expensive prompt reconstruction.

    TOKEN OPTIMIZATION: Only rebuilds the enhanced system prompt when
    the state actually changes (page navigation, material switch, etc.)

    Args:
        material_id: Current material UUID
        current_page: Current page number
        user_id: Current user UUID
        summary: Material summary (only first 100 chars are hashed)

    Returns:
        MD5 hex digest of the relevant state values
    """
    summary_preview = str(summary)[:100] if summary else ""

    hash_input = (
        f"{material_id or ''}|"
        f"{current_page or ''}|"
        f"{user_id or ''}|"
        f"{summary_preview}"
    )
    return hashlib.md5(hash_input.encode()).hexdigest()
