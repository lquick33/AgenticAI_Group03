"""
Chat service for agent orchestration and SSE streaming.

This service keeps HTTP handlers thin by centralizing:
- Tutor/QuickChat agent lifecycle management
- Shared checkpointers and in-memory agent caches
- Streaming of graph updates as SSE events
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Callable, Dict, Optional

import redis.asyncio as redis
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from app.core.config import settings

from app.agents.quickchat import QuickChatAgent
from app.agents.shared.message_utils import fix_incomplete_tool_calls
from app.agents.tutor import TutorAgent
from app.services.analyzer import get_gemini_model
from app.services.chat_checkpoint_service import (
    get_chat_checkpoint_backend,
    get_chat_checkpointer,
)
from app.services.tutor_rollout import TutorGraphVersion

logger = logging.getLogger(__name__)


class ChatService:
    """Application service for conversational agent orchestration."""

    def __init__(self) -> None:
        shared_checkpointer = get_chat_checkpointer()
        self._checkpointer = shared_checkpointer
        self._quickchat_checkpointer = shared_checkpointer
        self._checkpoint_backend = get_chat_checkpoint_backend()
        self._llm = None
        self._redis_client: Optional[redis.Redis] = None

    def _get_llm(self):
        if self._llm is None:
            self._llm = get_gemini_model()
        return self._llm

    @staticmethod
    def _sse(payload: Any) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    @staticmethod
    def _message_id(prefix: str = "msg") -> str:
        return f"{prefix}-{uuid.uuid4()}"

    @staticmethod
    def _as_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        parts.append(str(part.get("text", "")))
                    else:
                        parts.append(str(part.get("text", "")))
                else:
                    parts.append(str(part))
            return "".join(parts)
        if content is None:
            return ""
        return str(content)

    @staticmethod
    def _stored_to_message(stored: dict[str, Any]):
        role = stored.get("role")
        content = stored.get("content", "")
        if not content:
            return None
        if role == "user":
            return HumanMessage(content=content)
        if role == "assistant":
            return AIMessage(content=content)
        if role == "system":
            return SystemMessage(content=content)
        return None

    @staticmethod
    async def _run_callback(
        callback: Optional[Callable[[str], Any]],
        assistant_text: str,
    ) -> None:
        if callback is None:
            return
        try:
            result = callback(assistant_text)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            logger.error("ChatService completion callback failed: %s", exc, exc_info=True)

    def _get_redis(self) -> redis.Redis:
        if self._redis_client is None:
            redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
            if redis_url.startswith("rediss://"):
                self._redis_client = redis.from_url(redis_url, ssl_cert_reqs="required")
            else:
                self._redis_client = redis.from_url(redis_url)
        return self._redis_client

    def _create_tutor_agent(self, graph_version: TutorGraphVersion) -> TutorAgent:
        return TutorAgent(
            llm=self._get_llm(),
            checkpointer=self._checkpointer,
            graph_version=graph_version,
        )

    def _create_quickchat_agent(self) -> QuickChatAgent:
        llm = self._get_llm()
        return QuickChatAgent(
            llm=llm,
            checkpointer=self._quickchat_checkpointer,
            keyword_extraction_llm=llm,
        )

    def get_tutor_agent(
        self,
        graph_version: TutorGraphVersion,
    ) -> TutorAgent:
        return self._create_tutor_agent(graph_version)

    def get_quickchat_agent(self) -> QuickChatAgent:
        return self._create_quickchat_agent()

    def create_quickchat_session(self, user_id: str) -> dict[str, str]:
        thread_id = f"quickchat-{user_id}-{uuid.uuid4()}"
        greeting = (
            "Hallo! Ich bin dein Lernassistent. "
            "Frag mich einfach nach einem Thema, und ich zeige dir, "
            "wo es in deinen Vorlesungen behandelt wird!"
        )
        return {"greeting": greeting, "thread_id": thread_id, "mode": "discovery"}

    async def warmup_quickchat_agent(self, thread_id: str) -> dict[str, str]:
        # Stateless backend: fast instantiation natively, pre-warm acts as simple ack
        return {"status": "warmed", "thread_id": thread_id}

    async def _remember_pending_navigation(
        self, thread_id: str, nav_data: dict[str, Any]
    ) -> None:
        nav_data["_timestamp"] = time.time()
        redis_client = self._get_redis()
        # 5 minute TTL matching the old staleness cleanup
        await redis_client.setex(
            f"pending_nav:{thread_id}", 
            300, 
            json.dumps(nav_data, ensure_ascii=False)
        )

    async def _get_pending_navigation(self, thread_id: str) -> Optional[dict[str, Any]]:
        redis_client = self._get_redis()
        data = await redis_client.get(f"pending_nav:{thread_id}")
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                pass
        return None
        
    async def _clear_pending_navigation(self, thread_id: str) -> None:
        redis_client = self._get_redis()
        await redis_client.delete(f"pending_nav:{thread_id}")

    @staticmethod
    def _is_confirmation_message(message: str) -> bool:
        confirmation_words = [
            "ja",
            "yes",
            "ok",
            "bitte",
            "gerne",
            "mach das",
            "navigiere",
            "oeffne",
            "zeig",
            "switch",
            "wechsel",
        ]
        message_lower = message.lower().strip()
        return (
            any(word in message_lower for word in confirmation_words)
            and len(message_lower) < 50
        )

    @staticmethod
    def _sanitize_tool_response_for_frontend(tool_content: Any) -> str:
        if not isinstance(tool_content, str):
            return str(tool_content)

        try:
            parsed_json = json.loads(tool_content)
            if isinstance(parsed_json, dict) and "image_data" in parsed_json:
                frontend_json = parsed_json.copy()
                image_data = str(frontend_json.get("image_data", ""))
                if len(image_data) > 100:
                    frontend_json["image_data"] = (
                        f"{image_data[:50]}...[truncated]...{image_data[-20:]}"
                    )
                return json.dumps(frontend_json, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pass

        return tool_content

    def stream_tutor(
        self,
        *,
        thread_id: str,
        conversation_id: str,
        user_id: str,
        material_id: str,
        user_message: str,
        graph_version: TutorGraphVersion,
        rollout_source: str,
        current_page: Optional[int] = None,
        course_material_summary: Optional[dict[str, Any]] = None,
        bootstrap_messages: Optional[list[dict[str, Any]]] = None,
        on_complete: Optional[Callable[[str], Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream tutor graph execution as SSE.

        The caller decides how to build user prompts and where to persist results.
        """

        async def event_generator() -> AsyncGenerator[str, None]:
            agent = self.get_tutor_agent(graph_version)
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "checkpoint_ns": f"tutor:{graph_version}",
                },
                "metadata": {
                    "thread_id": thread_id,
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "material_id": material_id,
                    "current_page": current_page,
                    "graph_version": graph_version,
                    "rollout_source": rollout_source,
                    "checkpoint_backend": self._checkpoint_backend,
                },
            }

            base_messages = []
            last_sent_content = ""
            tool_call_count = 0
            tool_response_count = 0
            seen_tool_call_ids: set[str] = set()
            seen_tool_response_ids: set[str] = set()
            started_at = time.perf_counter()
            final_status = "completed"

            try:
                snapshot = agent.graph.get_state(config)
                is_new_thread = (
                    snapshot is None
                    or not snapshot.values
                    or not snapshot.values.get("messages")
                )
            except Exception:
                is_new_thread = True

            if is_new_thread and bootstrap_messages:
                for stored in bootstrap_messages:
                    msg = self._stored_to_message(stored)
                    if msg is not None:
                        base_messages.append(msg)
                base_messages = fix_incomplete_tool_calls(base_messages)

            initial_messages = base_messages + [HumanMessage(content=user_message)]
            initial_state: dict[str, Any] = {
                "messages": initial_messages,
                "material_id": material_id,
                "user_id": user_id,
            }
            if current_page is not None:
                initial_state["current_page"] = current_page
            if course_material_summary is not None:
                initial_state["course_material_summary"] = course_material_summary

            try:
                async for chunk in agent.graph.astream(
                    initial_state,
                    config,
                    stream_mode="updates",
                ):
                    chunk_data: dict[str, Any] = {}

                    for node_name, node_data in chunk.items():
                        if "messages" not in node_data:
                            continue

                        node_messages: list[dict[str, Any]] = []
                        for msg in node_data["messages"]:
                            if isinstance(msg, ToolMessage):
                                tool_call_id = getattr(msg, "tool_call_id", None) or getattr(
                                    msg, "name", None
                                )
                                tool_content = getattr(msg, "content", "")
                                if tool_call_id and tool_content:
                                    if tool_call_id in seen_tool_response_ids:
                                        continue
                                    seen_tool_response_ids.add(tool_call_id)
                                    tool_response_count += 1
                                    yield self._sse(
                                        {
                                            "type": "tool_response",
                                            "tool_call_id": tool_call_id,
                                            "result": self._sanitize_tool_response_for_frontend(
                                                tool_content
                                            ),
                                            "message_id": self._message_id(),
                                        }
                                    )
                                continue

                            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                                tool_calls_data = []
                                for tool_call in msg.tool_calls:
                                    if isinstance(tool_call, dict):
                                        tool_id = tool_call.get("id", "")
                                        tool_name = tool_call.get("name", "")
                                        tool_args = tool_call.get("args", {})
                                    else:
                                        tool_id = getattr(tool_call, "id", "")
                                        tool_name = getattr(tool_call, "name", "")
                                        tool_args = getattr(tool_call, "args", {})
                                    if tool_id and tool_name:
                                        tool_calls_data.append(
                                            {
                                                "id": tool_id,
                                                "name": tool_name,
                                                "args": tool_args
                                                if isinstance(tool_args, dict)
                                                else {},
                                            }
                                        )
                                if tool_calls_data:
                                    unique_tool_calls = [
                                        tool_call
                                        for tool_call in tool_calls_data
                                        if tool_call["id"] not in seen_tool_call_ids
                                    ]
                                    for tool_call in unique_tool_calls:
                                        seen_tool_call_ids.add(tool_call["id"])
                                    if unique_tool_calls:
                                        tool_call_count += len(unique_tool_calls)
                                        yield self._sse(
                                            {
                                                "type": "tool_call",
                                                "tool_calls": unique_tool_calls,
                                                "message_id": self._message_id(),
                                            }
                                        )

                            role = "assistant"
                            if isinstance(msg, HumanMessage):
                                role = "user"
                            elif isinstance(msg, SystemMessage):
                                role = "system"

                            content_text = self._as_text(getattr(msg, "content", ""))

                            if role == "assistant":
                                has_tool_calls = isinstance(msg, AIMessage) and bool(
                                    getattr(msg, "tool_calls", None)
                                )
                                if has_tool_calls and not content_text:
                                    continue

                                if content_text and content_text != last_sent_content:
                                    if (
                                        last_sent_content
                                        and content_text.startswith(last_sent_content)
                                    ):
                                        delta = content_text[len(last_sent_content) :]
                                        if delta:
                                            yield self._sse(
                                                {
                                                    "type": "delta",
                                                    "role": "assistant",
                                                    "delta": delta,
                                                    "content": content_text,
                                                }
                                            )
                                    else:
                                        node_messages.append(
                                            {"role": role, "content": content_text}
                                        )
                                    last_sent_content = content_text
                            else:
                                if content_text:
                                    node_messages.append(
                                        {"role": role, "content": content_text}
                                    )

                        if node_messages:
                            chunk_data[node_name] = {"messages": node_messages}

                    if chunk_data:
                        yield self._sse(chunk_data)

                await self._run_callback(on_complete, last_sent_content.strip())
                yield "data: [DONE]\n\n"
            except Exception as exc:
                final_status = "error"
                logger.error("Error in tutor stream: %s", exc, exc_info=True)
                yield self._sse({"error": "An internal AI orchestration error occurred. Please try again."})
                yield "data: [DONE]\n\n"
            finally:
                assistant_chars = len(last_sent_content.strip())
                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                logger.info(
                    "Tutor stream finished thread_id=%s conversation_id=%s user_id=%s material_id=%s current_page=%s graph_version=%s rollout_source=%s checkpoint_backend=%s duration_ms=%s tool_call_count=%s tool_response_count=%s assistant_chars=%s final_status=%s",
                    thread_id,
                    conversation_id,
                    user_id,
                    material_id,
                    current_page,
                    graph_version,
                    rollout_source,
                    self._checkpoint_backend,
                    duration_ms,
                    tool_call_count,
                    tool_response_count,
                    assistant_chars,
                    final_status,
                )

        return event_generator()

    def stream_quickchat_message(
        self,
        *,
        user_id: str,
        message: str,
        thread_id: Optional[str] = None,
        material_id: Optional[str] = None,
        page_number: Optional[int] = None,
        course_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream quickchat events as SSE."""

        resolved_thread_id = thread_id or f"quickchat-{user_id}"
        mode = "tutoring" if material_id else "discovery"
        agent = self.get_quickchat_agent()

        async def event_generator() -> AsyncGenerator[str, None]:
            try:
                config = {
                    "configurable": {
                        "thread_id": resolved_thread_id,
                        "user_id": user_id,
                        "checkpoint_ns": "quickchat",
                    }
                }

                pending_nav = await self._get_pending_navigation(resolved_thread_id)
                if pending_nav and mode == "tutoring" and self._is_confirmation_message(
                    message
                ):
                    open_data = {
                        "type": "open_material",
                        "course_id": pending_nav.get("course_id"),
                        "course_title": pending_nav.get("course_title"),
                        "material_id": pending_nav.get("material_id"),
                        "material_name": pending_nav.get("material_name"),
                        "page_number": pending_nav.get("page_number"),
                    }
                    yield self._sse(open_data)
                    await self._clear_pending_navigation(resolved_thread_id)
                    yield self._sse(
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": (
                                f"Alles klar! Ich oeffne jetzt "
                                f"{open_data.get('material_name', 'das Material')} "
                                f"auf Seite {open_data.get('page_number', 1)}."
                            ),
                        }
                    )
                    yield "data: [DONE]\n\n"
                    return

                initial_state: dict[str, Any] = {
                    "messages": [HumanMessage(content=message)],
                    "mode": mode,
                    "user_id": user_id,
                }
                if material_id:
                    initial_state["material_id"] = material_id
                    initial_state["current_page"] = page_number
                    initial_state["course_id"] = course_id

                last_sent_content = ""
                async for event in agent.graph.astream(
                    initial_state, config=config, stream_mode="updates"
                ):
                    for node_name, node_output in event.items():
                        if node_name == "agent":
                            for msg in node_output.get("messages", []):
                                if not isinstance(msg, AIMessage):
                                    continue

                                if getattr(msg, "tool_calls", None):
                                    for tool_call in msg.tool_calls:
                                        if isinstance(tool_call, dict):
                                            tool_name = tool_call.get("name", "")
                                        else:
                                            tool_name = getattr(tool_call, "name", "")
                                        yield self._sse(
                                            {"type": "tool_call", "tool": tool_name}
                                        )

                                content_text = self._as_text(getattr(msg, "content", ""))
                                if content_text and content_text != last_sent_content:
                                    if (
                                        last_sent_content
                                        and content_text.startswith(last_sent_content)
                                    ):
                                        delta = content_text[len(last_sent_content) :]
                                        if delta:
                                            yield self._sse(
                                                {
                                                    "type": "delta",
                                                    "role": "assistant",
                                                    "delta": delta,
                                                    "content": content_text,
                                                }
                                            )
                                    else:
                                        yield self._sse(
                                            {
                                                "type": "message",
                                                "role": "assistant",
                                                "content": content_text,
                                            }
                                        )
                                    last_sent_content = content_text

                        elif node_name == "tools":
                            for msg in node_output.get("messages", []):
                                if not isinstance(msg, ToolMessage):
                                    continue
                                try:
                                    tool_result = json.loads(str(msg.content))
                                except (json.JSONDecodeError, TypeError):
                                    continue

                                if not (
                                    isinstance(tool_result, dict)
                                    and tool_result.get("found")
                                    and tool_result.get("results")
                                ):
                                    continue

                                first_result = tool_result["results"][0]
                                nav_data = {
                                    "course_id": first_result.get("course", {}).get("id"),
                                    "course_title": first_result.get("course", {}).get(
                                        "title"
                                    ),
                                    "material_id": first_result.get("material", {}).get(
                                        "id"
                                    ),
                                    "material_name": first_result.get("material", {}).get(
                                        "name"
                                    ),
                                    "page_number": first_result.get("page_number"),
                                }

                                if mode == "discovery":
                                    yield self._sse({"type": "open_material", **nav_data})
                                else:
                                    await self._remember_pending_navigation(
                                        resolved_thread_id, dict(nav_data)
                                    )
                                    yield self._sse(
                                        {"type": "pending_navigation", **nav_data}
                                    )

                yield "data: [DONE]\n\n"
            except Exception as exc:
                logger.error("Error in quickchat stream: %s", exc, exc_info=True)
                yield self._sse({"error": "An internal AI orchestration error occurred. Please try again."})
                yield "data: [DONE]\n\n"

        return event_generator()


_chat_service = ChatService()


def get_chat_service() -> ChatService:
    return _chat_service
