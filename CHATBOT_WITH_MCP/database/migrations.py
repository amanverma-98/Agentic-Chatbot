"""Database migration system for schema versioning and updates."""

import aiosqlite
from database.connection import get_db_connection
from core.async_utils import run_async
from typing import List, Tuple


async def _record_migration_async(name: str, conn: aiosqlite.Connection):
    """Record that a migration has been applied."""
    await conn.execute(
        "INSERT INTO _migrations (name) VALUES (?)",
        (name,)
    )
    await conn.commit()


async def _get_applied_migrations_async(conn: aiosqlite.Connection) -> List[str]:
    """Get list of already applied migrations."""
    try:
        cursor = await conn.execute("SELECT name FROM _migrations ORDER BY id")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
    except:
        # Migrations table might not exist yet
        return []


async def _migration_001_create_users_table(conn: aiosqlite.Connection):
    """Migration 001: Create users table with username and password."""
    # Check if table already exists
    cursor = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    )
    if await cursor.fetchone() is not None:
        return  # Table already exists, skip

    await conn.execute("""
        CREATE TABLE users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await conn.commit()


async def _migration_002_add_email_to_users(conn: aiosqlite.Connection):
    """Migration 002: Add email and password recovery fields to users table."""
    # Check if email column already exists
    cursor = await conn.execute("PRAGMA table_info(users)")
    columns = await cursor.fetchall()
    column_names = [col[1] for col in columns]

    if "email" not in column_names:
        print("Adding email column to users table...")
        await conn.execute(
            "ALTER TABLE users ADD COLUMN email TEXT UNIQUE"
        )

    if "password_reset_token" not in column_names:
        print("Adding password_reset_token column to users table...")
        await conn.execute(
            "ALTER TABLE users ADD COLUMN password_reset_token TEXT"
        )

    if "token_expiry" not in column_names:
        print("Adding token_expiry column to users table...")
        await conn.execute(
            "ALTER TABLE users ADD COLUMN token_expiry TIMESTAMP"
        )

    await conn.commit()


async def _migration_003_create_thread_metadata(conn: aiosqlite.Connection):
    """Migration 003: Create thread_metadata table for storing thread names."""
    # Check if table already exists
    cursor = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='thread_metadata'"
    )
    if await cursor.fetchone() is not None:
        return  # Table already exists, skip

    await conn.execute("""
        CREATE TABLE thread_metadata (
            thread_id TEXT,
            user_id TEXT NOT NULL,
            thread_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (thread_id, user_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    await conn.commit()


# List of all migrations in order
MIGRATIONS = [
    ("001_create_users_table", _migration_001_create_users_table),
    ("002_add_email_to_users", _migration_002_add_email_to_users),
    ("003_create_thread_metadata", _migration_003_create_thread_metadata),
]


async def _apply_migrations_async():
    """Apply all pending database migrations (async)."""
    conn = get_db_connection()

    # Create migrations table if it doesn't exist
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.commit()
    except Exception as e:
        print(f"Error creating migrations table: {e}")

    # Get list of applied migrations
    applied = await _get_applied_migrations_async(conn)

    # Apply pending migrations
    for migration_name, migration_func in MIGRATIONS:
        if migration_name not in applied:
            try:
                print(f"Applying migration: {migration_name}")
                await migration_func(conn)
                await _record_migration_async(migration_name, conn)
                print(f"✓ Migration {migration_name} applied successfully")
            except Exception as e:
                print(f"✗ Error applying migration {migration_name}: {e}")
                raise


def apply_migrations():
    """Apply database migrations (sync wrapper).

    This should be called at application startup to ensure the database
    schema is up to date.
    """
    run_async(_apply_migrations_async())
