from __future__ import annotations

import atexit
import logging
from contextlib import ExitStack

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

from app.services.db_migration_helper import get_postgres_connection_string

logger = logging.getLogger(__name__)

_chat_checkpointer: BaseCheckpointSaver | None = None
_chat_checkpointer_stack: ExitStack | None = None
_chat_checkpoint_backend = "memory"


def _close_chat_checkpointer_stack() -> None:
    global _chat_checkpointer
    global _chat_checkpointer_stack
    global _chat_checkpoint_backend

    if _chat_checkpointer_stack is not None:
        _chat_checkpointer_stack.close()
        _chat_checkpointer_stack = None

    _chat_checkpointer = None
    _chat_checkpoint_backend = "memory"


def get_chat_checkpointer() -> BaseCheckpointSaver:
    global _chat_checkpointer
    global _chat_checkpointer_stack
    global _chat_checkpoint_backend

    if _chat_checkpointer is not None:
        return _chat_checkpointer

    try:
        conn_string = get_postgres_connection_string()
        stack = ExitStack()
        saver = stack.enter_context(PostgresSaver.from_conn_string(conn_string))
        try:
            saver.setup()
            logger.info("PostgresSaver tables initialized successfully for chat agents")
        except Exception as setup_error:
            logger.warning(
                "PostgresSaver.setup() failed for chat agents (may be normal if tables already exist): %s",
                setup_error,
            )
        _chat_checkpointer = saver
        _chat_checkpointer_stack = stack
        _chat_checkpoint_backend = "postgres"
        logger.info("Using PostgresSaver for chat agent checkpointing")
    except Exception as exc:
        logger.warning(
            "Failed to initialize PostgresSaver for chat agents, falling back to MemorySaver: %s",
            exc,
        )
        _close_chat_checkpointer_stack()
        _chat_checkpointer = MemorySaver()
        _chat_checkpoint_backend = "memory"
        logger.info("Using MemorySaver for chat agent checkpointing (fallback)")

    return _chat_checkpointer


def get_chat_checkpoint_backend() -> str:
    get_chat_checkpointer()
    return _chat_checkpoint_backend


def reset_chat_checkpointer_for_tests() -> None:
    _close_chat_checkpointer_stack()


atexit.register(_close_chat_checkpointer_stack)

