"""Database schema definitions."""

from database.connection import get_db_connection
from core.async_utils import run_async


async def _create_tables_async():
    """Create all database tables (async)."""
    conn = get_db_connection()

    # Create migrations table first (for tracking applied migrations)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Users table - core authentication
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE,
            password_reset_token TEXT,
            token_expiry TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Thread metadata - for storing chat thread names and ownership
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS thread_metadata (
            thread_id TEXT,
            user_id TEXT NOT NULL,
            thread_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (thread_id, user_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    await conn.commit()


def initialize_schema():
    """Initialize database schema (sync wrapper)."""
    run_async(_create_tables_async())
