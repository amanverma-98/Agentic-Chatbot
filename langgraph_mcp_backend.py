from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool, BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv
import aiosqlite
import requests
import asyncio
import threading
import re
import math
import uuid
import bcrypt
import smtplib
import secrets
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os

load_dotenv()

# Dedicated async loop for backend tasks
_ASYNC_LOOP = asyncio.new_event_loop()
_ASYNC_THREAD = threading.Thread(target=_ASYNC_LOOP.run_forever, daemon=True)
_ASYNC_THREAD.start()


def _submit_async(coro):
    return asyncio.run_coroutine_threadsafe(coro, _ASYNC_LOOP)


def run_async(coro):
    return _submit_async(coro).result()


def submit_async_task(coro):
    """Schedule a coroutine on the backend event loop."""
    return _submit_async(coro)


# -------------------
# 1. LLM
# -------------------
llm = ChatGroq(model = "llama-3.1-8b-instant")

# -------------------
# 2. Tools
# -------------------
search_tool = DuckDuckGoSearchRun(region="us-en")


@tool
def get_stock_price(symbol: str) -> dict:
    """
    Fetch latest stock price for a given symbol (e.g. 'AAPL', 'TSLA')
    using Alpha Vantage with API key in the URL.
    """
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey=C9PE94QUEW9VWGFM"
    r = requests.get(url)
    return r.json()


@tool
def get_weather(location: str) -> dict:
    """
    Get current weather information for a specific location.

    Args:
        location: City name (e.g., "New York", "London")

    Returns:
        Dictionary with temperature, weather conditions, and other info
    """
    try:
        # Using Open-Meteo API (free, no key required)
        # First, get coordinates for the location
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=en&format=json"
        geo_response = requests.get(geo_url)
        geo_data = geo_response.json()

        if "results" not in geo_data or len(geo_data["results"]) == 0:
            return {"error": f"Location '{location}' not found"}

        result = geo_data["results"][0]
        latitude = result["latitude"]
        longitude = result["longitude"]
        place_name = result.get("name", location)
        country = result.get("country", "")

        # Get weather data
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
        weather_response = requests.get(weather_url)
        weather_data = weather_response.json()

        current = weather_data.get("current", {})
        location_str = f"{place_name}, {country}" if country else place_name

        return {
            "location": location_str,
            "temperature": current.get("temperature_2m"),
            "apparent_temperature": current.get("apparent_temperature"),
            "humidity": current.get("relative_humidity_2m"),
            "wind_speed": current.get("wind_speed_10m"),
            "weather_code": current.get("weather_code"),
            "unit": "Celsius"
        }
    except Exception as e:
        return {"error": f"Failed to get weather: {str(e)}"}


@tool
def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression safely.

    Args:
        expression: Mathematical expression (e.g., "2 + 2", "sqrt(16)", "sin(pi/2)")

    Returns:
        The result of the calculation
    """
    try:
        # Remove spaces for cleaner evaluation
        expression = expression.replace(" ", "")

        # Define safe math functions
        safe_dict = {
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "pi": math.pi,
            "e": math.e,
            "log": math.log,
            "log10": math.log10,
            "abs": abs,
            "round": round,
            "ceil": math.ceil,
            "floor": math.floor,
        }

        # Validate expression contains only safe characters
        if not re.match(r'^[0-9+\-*/()\.\,\s\w]+$', expression):
            return "Error: Expression contains invalid characters"

        result = eval(expression, {"__builtins__": {}}, safe_dict)
        return f"Result: {result}"
    except ZeroDivisionError:
        return "Error: Division by zero"
    except ValueError as e:
        return f"Error: Invalid value - {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def extract_url_content(url: str) -> str:
    """
    Fetch and summarize content from a URL.

    Args:
        url: The URL to fetch content from

    Returns:
        The first 1000 characters of the page content
    """
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Remove HTML tags and get text
        import html
        text = response.text
        text = re.sub(r'<[^>]+>', '', text)
        text = html.unescape(text)
        text = ' '.join(text.split())

        return f"Content from {url}:\n\n{text[:1000]}..."
    except requests.exceptions.MissingSchema:
        return "Error: Invalid URL format"
    except requests.exceptions.ConnectionError:
        return "Error: Could not connect to the URL"
    except requests.exceptions.Timeout:
        return "Error: Request timed out"
    except Exception as e:
        return f"Error: Failed to fetch URL - {str(e)}"


client = MultiServerMCPClient(
    {
        "expense": {
            "transport": "streamable_http",
            "url": "https://splendid-gold-dingo.fastmcp.app/mcp"
        }
    }
)


def load_mcp_tools() -> list[BaseTool]:
    try:
        return run_async(client.get_tools())
    except Exception:
        return []


mcp_tools = load_mcp_tools()

tools = [search_tool, get_stock_price, get_weather, calculator, extract_url_content, *mcp_tools]
llm_with_tools = llm.bind_tools(tools) if tools else llm

# -------------------
# 3. State
# -------------------
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

# -------------------
# 4. Nodes
# -------------------
async def chat_node(state: ChatState):
    """LLM node that may answer or request a tool call."""
    messages = state["messages"]
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


tool_node = ToolNode(tools) if tools else None

# -------------------
# 5. Checkpointer
# -------------------


async def _init_checkpointer():
    conn = await aiosqlite.connect(database="chatbot.db")
    return AsyncSqliteSaver(conn)


checkpointer = run_async(_init_checkpointer())

# -------------------
# 6. Thread Metadata Database
# -------------------
_db_conn = None

async def _get_db_conn():
    """Get or create database connection for thread metadata"""
    global _db_conn
    if _db_conn is None:
        _db_conn = await aiosqlite.connect(database="chatbot.db")
    return _db_conn


async def _init_thread_metadata_table():
    """Initialize thread_metadata table if it doesn't exist"""
    try:
        conn = await _get_db_conn()
        # Create with user_id column
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS thread_metadata (
                thread_id TEXT,
                user_id TEXT NOT NULL,
                thread_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (thread_id, user_id)
            )
        """)
        await conn.commit()
    except Exception as e:
        print(f"Error initializing thread metadata table: {e}")


async def _save_thread_name(user_id: str, thread_id: str, thread_name: str):
    """Save or update thread name in database"""
    try:
        conn = await _get_db_conn()
        await conn.execute(
            """
            INSERT INTO thread_metadata (thread_id, user_id, thread_name)
            VALUES (?, ?, ?)
            ON CONFLICT(thread_id, user_id) DO UPDATE SET thread_name = ?
            """,
            (str(thread_id), str(user_id), thread_name, thread_name)
        )
        await conn.commit()
    except Exception as e:
        print(f"Error saving thread name: {e}")


async def _get_thread_name(user_id: str, thread_id: str) -> str:
    """Get thread name from database"""
    try:
        conn = await _get_db_conn()
        cursor = await conn.execute(
            "SELECT thread_name FROM thread_metadata WHERE thread_id = ? AND user_id = ?",
            (str(thread_id), str(user_id))
        )
        row = await cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"Error getting thread name: {e}")
        return None


async def _generate_thread_title(first_message: str) -> str:
    """Generate a concise title from the first user message using LLM"""
    try:
        response = await llm.ainvoke(
            f"Generate a concise 5-10 word title for this conversation starting with: '{first_message[:100]}'. "
            f"Reply with ONLY the title, nothing else."
        )
        title = response.content.strip()
        # Clean up the title
        title = title.strip('"\'')
        return title[:50]  # Limit to 50 characters
    except Exception as e:
        print(f"Error generating title: {e}")
        # Fallback: use first 30 characters of message
        return first_message[:30] + "..." if len(first_message) > 30 else first_message


def save_thread_name(user_id: str, thread_id: str, thread_name: str):
    """Wrapper to save thread name from sync context"""
    return run_async(_save_thread_name(user_id, thread_id, thread_name))


def get_thread_name(user_id: str, thread_id: str) -> str:
    """Wrapper to get thread name from sync context"""
    return run_async(_get_thread_name(user_id, thread_id))


def generate_thread_title(first_message: str) -> str:
    """Wrapper to generate title from sync context"""
    return run_async(_generate_thread_title(first_message))


# Initialize thread metadata table on startup
run_async(_init_thread_metadata_table())

# -------------------
# 7. User Authentication
# -------------------
async def _init_users_table():
    """Initialize users table if it doesn't exist"""
    try:
        conn = await _get_db_conn()
        # Create table with new columns
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

        # Add columns to existing table if they don't exist
        try:
            await conn.execute("ALTER TABLE users ADD COLUMN email TEXT UNIQUE")
        except:
            pass  # Column likely already exists

        try:
            await conn.execute("ALTER TABLE users ADD COLUMN password_reset_token TEXT")
        except:
            pass

        try:
            await conn.execute("ALTER TABLE users ADD COLUMN token_expiry TIMESTAMP")
        except:
            pass

        await conn.commit()
    except Exception as e:
        print(f"Error initializing users table: {e}")


async def _register_user(username: str, password: str, email: str) -> tuple[bool, str]:
    """Register a new user. Returns (success, message/user_id)"""
    try:
        # Validate username
        if not username or len(username) < 3:
            return False, "Username must be at least 3 characters"

        if not password or len(password) < 6:
            return False, "Password must be at least 6 characters"

        if not email or '@' not in email:
            return False, "Please enter a valid email address"

        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Create user
        conn = await _get_db_conn()
        user_id = str(uuid.uuid4())

        await conn.execute(
            "INSERT INTO users (user_id, username, password, email) VALUES (?, ?, ?, ?)",
            (user_id, username, hashed_password, email.lower())
        )
        await conn.commit()
        return True, user_id
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            if "username" in str(e):
                return False, "Username already exists"
            elif "email" in str(e):
                return False, "Email already registered"
        return False, f"Registration failed: {str(e)}"


async def _authenticate_user(username: str, password: str) -> tuple[bool, str]:
    """Authenticate user. Returns (success, user_id/error_message)"""
    try:
        conn = await _get_db_conn()
        cursor = await conn.execute(
            "SELECT user_id, password FROM users WHERE username = ?",
            (username,)
        )
        row = await cursor.fetchone()

        if not row:
            return False, "Username or password incorrect"

        user_id, stored_password = row

        # Verify password
        if bcrypt.checkpw(password.encode('utf-8'), stored_password):
            return True, user_id
        else:
            return False, "Username or password incorrect"
    except Exception as e:
        return False, f"Authentication failed: {str(e)}"


async def _user_exists(username: str) -> bool:
    """Check if username exists"""
    try:
        conn = await _get_db_conn()
        cursor = await conn.execute(
            "SELECT user_id FROM users WHERE username = ?",
            (username,)
        )
        return await cursor.fetchone() is not None
    except Exception:
        return False


# Sync wrappers for authentication
def register_user(username: str, password: str, email: str) -> tuple[bool, str]:
    """Register a new user"""
    return run_async(_register_user(username, password, email))


def authenticate_user(username: str, password: str) -> tuple[bool, str]:
    """Authenticate user"""
    return run_async(_authenticate_user(username, password))


def user_exists(username: str) -> bool:
    """Check if user exists"""
    return run_async(_user_exists(username))


# -------------------
# Password Recovery Functions
# -------------------

def _send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email using Gmail SMTP"""
    try:
        gmail_address = os.getenv("GMAIL_ADDRESS")
        gmail_password = os.getenv("GMAIL_PASSWORD")

        if not gmail_address or not gmail_password:
            print("Email credentials not configured in .env")
            return False

        msg = MIMEMultipart()
        msg['From'] = gmail_address
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(os.getenv("SMTP_SERVER", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", 587)))
        server.starttls()
        server.login(gmail_address, gmail_password)
        server.send_message(msg)
        server.quit()

        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def _hash_token(token: str) -> str:
    """Hash token for storage"""
    return hashlib.sha256(token.encode()).hexdigest()


async def _create_password_reset(user_email: str) -> tuple[bool, str]:
    """Create password reset token and send email. Returns (success, message)"""
    try:
        email_lower = user_email.lower()

        # Check if user exists
        conn = await _get_db_conn()
        cursor = await conn.execute(
            "SELECT user_id, username FROM users WHERE email = ?",
            (email_lower,)
        )
        row = await cursor.fetchone()

        if not row:
            # Don't reveal if email exists (security)
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
        token = secrets.token_urlsafe(32)
        hashed_token = _hash_token(token)
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
        reset_link = f"http://localhost:8501/?page=reset&token={token}&email={email_lower}"
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


async def _verify_reset_token(user_email: str, token: str) -> tuple[bool, str]:
    """Verify reset token. Returns (success, message/user_id)"""
    try:
        email_lower = user_email.lower()
        hashed_token = _hash_token(token)

        conn = await _get_db_conn()
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


async def _reset_password(user_email: str, token: str, new_password: str) -> tuple[bool, str]:
    """Reset user password. Returns (success, message)"""
    try:
        # Validate new password
        if not new_password or len(new_password) < 6:
            return False, "Password must be at least 6 characters"

        # Verify token
        success, result = await _verify_reset_token(user_email, token)
        if not success:
            return False, result

        user_id = result

        # Hash new password
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

        # Update password and clear token
        conn = await _get_db_conn()
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


# Sync wrappers for password recovery
def create_password_reset(user_email: str) -> tuple[bool, str]:
    """Create password reset request"""
    return run_async(_create_password_reset(user_email))


def verify_reset_token(user_email: str, token: str) -> tuple[bool, str]:
    """Verify reset token"""
    return run_async(_verify_reset_token(user_email, token))


def reset_password(user_email: str, token: str, new_password: str) -> tuple[bool, str]:
    """Reset user password"""
    return run_async(_reset_password(user_email, token, new_password))


# Initialize users table on startup
run_async(_init_users_table())

# -------------------
# 8. Graph
# -------------------
graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_edge(START, "chat_node")

if tool_node:
    graph.add_node("tools", tool_node)
    graph.add_conditional_edges("chat_node", tools_condition)
    graph.add_edge("tools", "chat_node")
else:
    graph.add_edge("chat_node", END)

chatbot = graph.compile(checkpointer=checkpointer)

# -------------------
# 9. Helper
# -------------------
async def _alist_threads(user_id: str):
    all_threads = {}
    async for checkpoint in checkpointer.alist(None):
        thread_id = checkpoint.config["configurable"]["thread_id"]
        thread_name = await _get_thread_name(user_id, thread_id)
        if thread_name:  # Only include if user owns the thread
            all_threads[thread_id] = thread_name
    return all_threads


def retrieve_all_threads(user_id: str):
    """Return dict of {thread_id: thread_name} for a specific user"""
    return run_async(_alist_threads(user_id))