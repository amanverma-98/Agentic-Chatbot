"""Thread metadata storage and management."""

from database.connection import get_db_connection
from core.async_utils import run_async
from typing import Dict, Optional
import uuid


async def _save_thread_name_async(user_id: str, thread_id: str, thread_name: str):
    """Save or update thread name in database (async)."""
    try:
        conn = get_db_connection()
        await conn.execute(
            """INSERT INTO thread_metadata (thread_id, user_id, thread_name)
               VALUES (?, ?, ?)
               ON CONFLICT(thread_id, user_id) DO UPDATE SET thread_name = ?""",
            (str(thread_id), str(user_id), thread_name, thread_name)
        )
        await conn.commit()
    except Exception as e:
        print(f"Error saving thread name: {e}")


async def _get_thread_name_async(user_id: str, thread_id: str) -> Optional[str]:
    """Get thread name from database (async)."""
    try:
        conn = get_db_connection()
        cursor = await conn.execute(
            "SELECT thread_name FROM thread_metadata WHERE thread_id = ? AND user_id = ?",
            (str(thread_id), str(user_id))
        )
        row = await cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"Error getting thread name: {e}")
        return None


async def _generate_thread_title_async(first_message: str) -> str:
    """Generate a concise title from the first user message using LLM (async)."""
    try:
        # Import here to avoid circular imports
        from ai_backend.llm_config import get_llm

        llm = get_llm()
        response = await llm.ainvoke(
            f"Generate a concise 5-10 word title for this conversation starting with: '{first_message[:100]}'. "
            f"Reply with ONLY the title, nothing else."
        )
        title = response.content.strip()
        # Clean up the title
        title = title.strip('\"\'')
        return title[:50]  # Limit to 50 characters
    except Exception as e:
        print(f"Error generating title: {e}")
        # Fallback: use first 30 characters of message
        return first_message[:30] + "..." if len(first_message) > 30 else first_message


async def _retrieve_all_threads_async(user_id: str) -> Dict[str, str]:
    """Get all threads for a specific user (async).

    Returns:
        Dict of {thread_id: thread_name} for user's threads
    """
    try:
        all_threads = {}
        conn = get_db_connection()
        cursor = await conn.execute(
            "SELECT thread_id, thread_name FROM thread_metadata WHERE user_id = ? ORDER BY created_at DESC",
            (str(user_id),)
        )
        rows = await cursor.fetchall()
        for thread_id, thread_name in rows:
            all_threads[str(thread_id)] = thread_name
        return all_threads
    except Exception as e:
        print(f"Error retrieving threads: {e}")
        return {}


# Sync wrappers
def save_thread_name(user_id: str, thread_id: str, thread_name: str):
    """Save thread name (sync wrapper)."""
    return run_async(_save_thread_name_async(user_id, thread_id, thread_name))


def get_thread_name(user_id: str, thread_id: str) -> Optional[str]:
    """Get thread name (sync wrapper)."""
    return run_async(_get_thread_name_async(user_id, thread_id))


def generate_thread_title(first_message: str) -> str:
    """Generate thread title (sync wrapper)."""
    return run_async(_generate_thread_title_async(first_message))


def retrieve_all_threads(user_id: str) -> Dict[str, str]:
    """Retrieve all threads for user (sync wrapper)."""
    return run_async(_retrieve_all_threads_async(user_id))
