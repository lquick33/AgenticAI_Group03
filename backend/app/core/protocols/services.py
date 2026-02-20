"""
Service Protocol definitions.

These Protocols define contracts for cross-cutting services
(LLM invocation, observability, caching, SSE events) that are
used across the application but should be swappable.
"""

from typing import Protocol, Optional, List, Dict, Any, Callable, AsyncGenerator, runtime_checkable


@runtime_checkable
class LLMService(Protocol):
    """
    Contract: LLM invocation with usage tracking.

    Consumers: Agents, Analyzer, Classifier
    """

    def invoke(
        self, messages: List[Any], config: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Synchronous LLM invocation.

        Postconditions:
            - Returns an AIMessage-compatible object with .content
        """
        ...

    async def ainvoke(
        self, messages: List[Any], config: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Asynchronous LLM invocation.

        Postconditions:
            - Returns an AIMessage-compatible object with .content
        """
        ...

    def get_structured(self, output_schema: type) -> "LLMService":
        """
        Return a version of this service that outputs structured data
        matching the given Pydantic schema.
        """
        ...


@runtime_checkable
class ObservabilityService(Protocol):
    """
    Contract: tracing and monitoring.

    Consumers: All agents and services that need observability
    """

    def create_callback(self, **metadata: Any) -> Optional[Any]:
        """
        Create a callback handler for tracing (e.g., Langfuse).

        Postconditions:
            - Returns a callback handler or None if not configured
        """
        ...

    def flush(self) -> None:
        """Flush any pending traces/spans."""
        ...


@runtime_checkable
class CacheService(Protocol):
    """
    Contract: generic TTL cache.

    Consumers: Services that need to cache expensive computations
    (prompt caching, embedding lookups, search results)
    """

    def get(self, key: str) -> Optional[Any]:
        """
        Get a cached value.

        Postconditions:
            - Returns None if key doesn't exist or has expired
        """
        ...

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        """
        Set a cached value with TTL.

        Preconditions:
            - ttl_seconds > 0
        """
        ...

    def invalidate(self, key: str) -> None:
        """Remove a specific key from cache."""
        ...

    def invalidate_pattern(self, pattern: str) -> None:
        """
        Remove all keys matching a glob pattern.

        Example: invalidate_pattern("material:abc-*")
        """
        ...


@runtime_checkable
class EventEmitter(Protocol):
    """
    Contract: Server-Sent Events emission.

    Consumers: ChatService (streaming agent responses to frontend)
    """

    async def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Emit a single SSE event.

        Preconditions:
            - event_type in {'message', 'quiz', 'navigation', 'tts',
                             'sources', 'error', 'done'}
        """
        ...

    async def emit_done(self) -> None:
        """
        Emit the 'done' event to signal stream completion.

        Postconditions:
            - No more events should be emitted after this
        """
        ...

    async def emit_error(
        self, error: str, code: str = "INTERNAL_ERROR"
    ) -> None:
        """
        Emit an error event.

        Postconditions:
            - Stream should terminate after error emission
        """
        ...
