"""LangGraph checkpointer for state persistence."""

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from database.connection import get_db_connection
from core.async_utils import run_async
from typing import Optional


_CHECKPOINTER: Optional[AsyncSqliteSaver] = None


async def _get_checkpointer_async() -> AsyncSqliteSaver:
    """Initialize and get checkpointer (async)."""
    global _CHECKPOINTER

    if _CHECKPOINTER is not None:
        return _CHECKPOINTER

    # Get the connection (already established)
    conn = get_db_connection()
    _CHECKPOINTER = AsyncSqliteSaver(conn)

    return _CHECKPOINTER


def get_checkpointer() -> AsyncSqliteSaver:
    """Get checkpointer for LangGraph (sync wrapper)."""
    global _CHECKPOINTER

    if _CHECKPOINTER is None:
        _CHECKPOINTER = run_async(_get_checkpointer_async())

    return _CHECKPOINTER
