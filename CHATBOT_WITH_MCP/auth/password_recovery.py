"""Password recovery and reset functionality."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from database.connection import get_db_connection
from core.async_utils import run_async
from core.config import get_config
from auth.security import generate_token, hash_token
from typing import Tuple


def _send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email via Gmail SMTP.

    Args:
        to_email: Recipient email
        subject: Email subject
        body: Email body (plain text)

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        config = get_config()
        gmail_address = config.get("gmail_address")
        gmail_password = config.get("gmail_password")
        smtp_server = config.get("smtp_server", "smtp.gmail.com")
        smtp_port = config.get("smtp_port", 587)

        if not gmail_address or not gmail_password:
            print("Email credentials not configured in .env")
            return False

        msg = MIMEMultipart()
        msg['From'] = gmail_address
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(gmail_address, gmail_password)
        server.send_message(msg)
        server.quit()

        return True

    except Exception as e:
        print(f"Error sending email: {e}")
        return False


async def _create_password_reset_async(user_email: str) -> Tuple[bool, str]:
    """Create password reset token and send email (async).

    Args:
        user_email: Email address of user

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        email_lower = user_email.lower()
        conn = get_db_connection()

        # Check if user exists
        cursor = await conn.execute(
            "SELECT user_id, username FROM users WHERE email = ?",
            (email_lower,)
        )
        row = await cursor.fetchone()

        if not row:
            # Don't reveal if email exists (security best practice)
            return True, "If an account exists with this email, a reset link has been sent"

        user_id, username = row

        # Check rate limiting: max 3 attempts per 15 minutes
        cursor = await conn.execute(
            """SELECT COUNT(*) FROM users
               WHERE email = ? AND token_expiry > datetime('now', '-15 minutes')""",
            (email_lower,)
        )
        count_row = await cursor.fetchone()
        if count_row and count_row[0] >= 3:
            return True, "Too many reset attempts. Please try again later."

        # Generate reset token
        token = generate_token(32)
        hashed_token = hash_token(token)
        expiry = datetime.utcnow() + timedelta(minutes=30)

        # Store hashed token
        await conn.execute(
            """UPDATE users
               SET password_reset_token = ?, token_expiry = ?
               WHERE user_id = ?""",
            (hashed_token, expiry.isoformat(), user_id)
        )
        await conn.commit()

        # Send email
        config = get_config()
        reset_link_domain = config.get("reset_link_domain", "http://localhost:8501")
        reset_link = f"{reset_link_domain}/?page=reset&token={token}&email={email_lower}"

        email_body = f"""Hello {username},

You requested to reset your password. Click the link below:

{reset_link}

This link expires in 30 minutes.

If you didn't request this, ignore this email. Your password is still secure.

---
LangGraph MCP Chatbot Team"""

        _send_email(user_email, "Password Reset Request", email_body)

        return True, "If an account exists with this email, a reset link has been sent"

    except Exception as e:
        print(f"Error in password reset: {e}")
        return True, "If an account exists with this email, a reset link has been sent"


async def _verify_reset_token_async(user_email: str, token: str) -> Tuple[bool, str]:
    """Verify reset token (async).

    Args:
        user_email: Email address
        token: Reset token from email link

    Returns:
        Tuple of (success: bool, user_id_or_error: str)
    """
    try:
        email_lower = user_email.lower()
        hashed_token = hash_token(token)

        conn = get_db_connection()
        cursor = await conn.execute(
            """SELECT user_id, token_expiry FROM users
               WHERE email = ? AND password_reset_token = ?""",
            (email_lower, hashed_token)
        )
        row = await cursor.fetchone()

        if not row:
            return False, "Invalid or expired reset link"

        user_id, token_expiry_str = row

        # Check if token expired
        if datetime.fromisoformat(token_expiry_str) < datetime.utcnow():
            return False, "Reset link has expired. Please request a new one."

        return True, user_id

    except Exception as e:
        print(f"Error verifying token: {e}")
        return False, "Error processing reset"


async def _reset_password_async(
    user_email: str, token: str, new_password: str
) -> Tuple[bool, str]:
    """Reset user password (async).

    Args:
        user_email: Email address
        token: Reset token
        new_password: New password (6+ characters)

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Validate new password
        if not new_password or len(new_password) < 6:
            return False, "Password must be at least 6 characters"

        # Verify token
        success, result = await _verify_reset_token_async(user_email, token)
        if not success:
            return False, result

        user_id = result

        # Hash new password
        from auth.security import hash_password
        hashed_password = hash_password(new_password)

        # Update password and clear token
        conn = get_db_connection()
        await conn.execute(
            """UPDATE users
               SET password = ?, password_reset_token = NULL, token_expiry = NULL
               WHERE user_id = ?""",
            (hashed_password, user_id)
        )
        await conn.commit()

        # Send confirmation email
        cursor = await conn.execute(
            "SELECT username FROM users WHERE user_id = ?",
            (user_id,)
        )
        username_row = await cursor.fetchone()
        username = username_row[0] if username_row else "User"

        confirmation_body = f"""Hello {username},

Your password has been successfully updated.

If this wasn't you, please reset your password immediately.

---
LangGraph MCP Chatbot Team"""

        _send_email(user_email, "Password Changed Successfully", confirmation_body)

        return True, "Password reset successfully!"

    except Exception as e:
        print(f"Error resetting password: {e}")
        return False, "Error resetting password"


# Sync wrappers for use from Streamlit
def create_password_reset(user_email: str) -> Tuple[bool, str]:
    """Create password reset request (sync wrapper)."""
    return run_async(_create_password_reset_async(user_email))


def verify_reset_token(user_email: str, token: str) -> Tuple[bool, str]:
    """Verify reset token (sync wrapper)."""
    return run_async(_verify_reset_token_async(user_email, token))


def reset_password(user_email: str, token: str, new_password: str) -> Tuple[bool, str]:
    """Reset user password (sync wrapper)."""
    return run_async(_reset_password_async(user_email, token, new_password))
