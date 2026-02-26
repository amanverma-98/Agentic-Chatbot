"""User registration and authentication."""

import uuid
from database.connection import get_db_connection
from core.async_utils import run_async
from auth.security import hash_password, verify_password
from typing import Tuple


async def _register_user_async(
    username: str, password: str, email: str
) -> Tuple[bool, str]:
    """Register a new user (async).

    Args:
        username: Username (3+ characters)
        password: Password (6+ characters)
        email: Email address

    Returns:
        Tuple of (success: bool, message_or_user_id: str)
    """
    try:
        # Validate inputs
        if not username or len(username) < 3:
            return False, "Username must be at least 3 characters"

        if not password or len(password) < 6:
            return False, "Password must be at least 6 characters"

        if not email or '@' not in email:
            return False, "Please enter a valid email address"

        # Hash password
        hashed_password = hash_password(password)

        # Create user
        conn = get_db_connection()
        user_id = str(uuid.uuid4())

        await conn.execute(
            "INSERT INTO users (user_id, username, password, email) VALUES (?, ?, ?, ?)",
            (user_id, username, hashed_password, email.lower())
        )
        await conn.commit()

        return True, user_id

    except Exception as e:
        error_msg = str(e)
        if "UNIQUE constraint failed" in error_msg:
            if "username" in error_msg:
                return False, "Username already exists"
            elif "email" in error_msg:
                return False, "Email already registered"
        return False, f"Registration failed: {error_msg}"


async def _authenticate_user_async(
    username: str, password: str
) -> Tuple[bool, str]:
    """Authenticate user credentials (async).

    Args:
        username: Username to authenticate
        password: Password to verify

    Returns:
        Tuple of (success: bool, user_id_or_error: str)
    """
    try:
        conn = get_db_connection()
        cursor = await conn.execute(
            "SELECT user_id, password FROM users WHERE username = ?",
            (username,)
        )
        row = await cursor.fetchone()

        if not row:
            return False, "Username or password incorrect"

        user_id, stored_password = row

        # Verify password
        if verify_password(password, stored_password):
            return True, user_id
        else:
            return False, "Username or password incorrect"

    except Exception as e:
        return False, f"Authentication failed: {str(e)}"


async def _user_exists_async(username: str) -> bool:
    """Check if username exists (async).

    Args:
        username: Username to check

    Returns:
        True if user exists, False otherwise
    """
    try:
        conn = get_db_connection()
        cursor = await conn.execute(
            "SELECT user_id FROM users WHERE username = ?",
            (username,)
        )
        return await cursor.fetchone() is not None
    except Exception:
        return False


# Sync wrappers for use from Streamlit
def register_user(username: str, password: str, email: str) -> Tuple[bool, str]:
    """Register a new user (sync wrapper)."""
    return run_async(_register_user_async(username, password, email))


def authenticate_user(username: str, password: str) -> Tuple[bool, str]:
    """Authenticate user (sync wrapper)."""
    return run_async(_authenticate_user_async(username, password))


def user_exists(username: str) -> bool:
    """Check if user exists (sync wrapper)."""
    return run_async(_user_exists_async(username))
