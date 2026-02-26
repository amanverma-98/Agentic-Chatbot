"""Configuration and environment variable management."""

import os
from dotenv import load_dotenv
from typing import Optional

# Load environment variables at module import time
load_dotenv()


def get_env(key: str, default: Optional[str] = None) -> str:
    """Get an environment variable.

    Args:
        key: Environment variable name
        default: Default value if not found

    Returns:
        Environment variable value or default
    """
    return os.getenv(key, default)


def load_config() -> dict:
    """Load and validate configuration from environment.

    Returns:
        Dictionary with configuration values

    Raises:
        ValueError: If critical environment variables are missing
    """
    config = {
        # LLM Configuration
        "groq_api_key": get_env("GROQ_API_KEY"),
        "llm_model": get_env("LLM_MODEL", "llama-3.1-8b-instant"),

        # Database Configuration
        "database_file": get_env("DATABASE_FILE", "chatbot.db"),

        # Email Configuration
        "gmail_address": get_env("GMAIL_ADDRESS"),
        "gmail_password": get_env("GMAIL_PASSWORD"),
        "smtp_server": get_env("SMTP_SERVER", "smtp.gmail.com"),
        "smtp_port": int(get_env("SMTP_PORT", "587")),

        # App Configuration
        "reset_link_domain": get_env("RESET_LINK_DOMAIN", "http://localhost:8501"),
    }

    # Validate critical settings
    if not config["groq_api_key"]:
        raise ValueError("GROQ_API_KEY environment variable is required")

    return config


# Load configuration at startup
_CONFIG = load_config()


def get_config() -> dict:
    """Get the loaded configuration."""
    return _CONFIG
