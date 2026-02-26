"""Data models for chatbot."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """User account model."""

    user_id: str
    username: str
    email: str
    created_at: datetime
    password_reset_token: Optional[str] = None
    token_expiry: Optional[datetime] = None

    @classmethod
    def from_db_row(cls, row: tuple) -> 'User':
        """Create User from database row."""
        user_id, username, email, created_at, reset_token, token_expiry = row
        return cls(
            user_id=user_id,
            username=username,
            email=email,
            created_at=datetime.fromisoformat(created_at) if isinstance(created_at, str) else created_at,
            password_reset_token=reset_token,
            token_expiry=datetime.fromisoformat(token_expiry) if isinstance(token_expiry, str) else token_expiry,
        )


@dataclass
class Thread:
    """Chat thread model."""

    thread_id: str
    user_id: str
    thread_name: str
    created_at: datetime

    @classmethod
    def from_db_row(cls, row: tuple) -> 'Thread':
        """Create Thread from database row."""
        thread_id, user_id, thread_name, created_at = row
        return cls(
            thread_id=thread_id,
            user_id=user_id,
            thread_name=thread_name,
            created_at=datetime.fromisoformat(created_at) if isinstance(created_at, str) else created_at,
        )
