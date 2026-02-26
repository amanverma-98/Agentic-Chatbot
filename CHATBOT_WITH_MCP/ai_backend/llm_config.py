"""LLM configuration and initialization."""

from langchain_groq import ChatGroq
from core.config import get_config
from typing import Optional


_LLM: Optional[ChatGroq] = None


def get_llm() -> ChatGroq:
    """Get or initialize the LLM instance.

    Returns:
        ChatGroq LLM instance
    """
    global _LLM

    if _LLM is not None:
        return _LLM

    config = get_config()
    api_key = config.get("groq_api_key")
    model = config.get("llm_model", "llama-3.1-8b-instant")

    if not api_key:
        raise ValueError("GROQ_API_KEY not configured in environment")

    _LLM = ChatGroq(model=model, api_key=api_key)
    return _LLM
