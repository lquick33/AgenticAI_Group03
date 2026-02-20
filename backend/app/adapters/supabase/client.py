"""
Supabase client infrastructure.

Provides the singleton Supabase client factory and the retry decorator
used by all adapter modules. This is the single source of truth for
connection management.

Extracted from app.services.storage (lines 1–97, 250–266).
"""

import errno
import logging
from functools import wraps
from time import sleep
from typing import Callable, Optional, TypeVar

from supabase import create_client, Client

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Retry Logic for Transient Network Errors
# =============================================================================


def retry_on_resource_unavailable(
    max_retries: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    exponential_base: float = 2.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that retries a function on transient network errors.

    Handles [Errno 35] Resource temporarily unavailable (EAGAIN/EWOULDBLOCK)
    which can occur with long-running HTTP clients when connection pools
    become stale or exhausted.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_str = str(e)
                    is_resource_unavailable = (
                        "Resource temporarily unavailable" in error_str
                        or f"[Errno {errno.EAGAIN}]" in error_str
                        or f"[Errno {errno.EWOULDBLOCK}]" in error_str
                        or "[Errno 35]" in error_str  # macOS-specific
                        or "[WinError 10035]" in error_str  # Windows-specific
                    )

                    if is_resource_unavailable and attempt < max_retries:
                        delay = min(
                            base_delay * (exponential_base**attempt), max_delay
                        )
                        logger.warning(
                            f"Transient error in {func.__name__} "
                            f"(attempt {attempt + 1}/{max_retries + 1}): "
                            f"{error_str}. Retrying in {delay:.2f}s..."
                        )
                        sleep(delay)
                        last_exception = e
                    else:
                        raise

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


# =============================================================================
# Supabase Client Singleton
# =============================================================================

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Get or create Supabase client instance.

    Returns:
        Configured Supabase client

    Postconditions:
        - Client is connected to the URL/key from settings
        - Same instance returned on subsequent calls (singleton)
    """
    global _supabase_client

    if _supabase_client is None:
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY,
        )

    return _supabase_client
