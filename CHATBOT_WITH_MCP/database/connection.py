"""Database connection management with singleton pattern."""

import aiosqlite
from typing import Optional
from core.config import get_config
from core.async_utils import run_async

# Global connection singleton
_DB_CONNECTION: Optional[aiosqlite.Connection] = None


async def _get_db_connection_async() -> aiosqlite.Connection:
    """Get or create database connection (async).

    Uses a singleton pattern to ensure only one connection is used.
    """
    global _DB_CONNECTION

    if _DB_CONNECTION is not None:
        return _DB_CONNECTION

    config = get_config()
    db_file = config["database_file"]

    _DB_CONNECTION = await aiosqlite.connect(db_file)
    # Enable foreign keys
    await _DB_CONNECTION.execute("PRAGMA foreign_keys = ON")
    await _DB_CONNECTION.commit()

    return _DB_CONNECTION


def get_db_connection() -> aiosqlite.Connection:
    """Get database connection from sync context.

    This is the main entry point for all database operations.
    """
    global _DB_CONNECTION

    if _DB_CONNECTION is None:
        _DB_CONNECTION = run_async(_get_db_connection_async())

    return _DB_CONNECTION


async def close_database():
    """Close database connection."""
    global _DB_CONNECTION

    if _DB_CONNECTION is not None:
        await _DB_CONNECTION.close()
        _DB_CONNECTION = None
