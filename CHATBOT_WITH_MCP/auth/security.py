"""Security utilities for password hashing and token generation."""

import bcrypt
import secrets
import hashlib


def hash_password(password: str) -> bytes:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password (bytes)
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt)


def verify_password(password: str, hashed: bytes) -> bool:
    """Verify a password against its hash.

    Args:
        password: Plain text password to verify
        hashed: Hashed password from database

    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(password.encode('utf-8'), hashed)


def generate_token(length: int = 32) -> str:
    """Generate a secure random token.

    Args:
        length: Length of token in bytes (default 32)

    Returns:
        URL-safe random token
    """
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """Hash a token for secure storage.

    Args:
        token: Plain text token

    Returns:
        SHA256 hash of token (hex string)
    """
    return hashlib.sha256(token.encode()).hexdigest()
