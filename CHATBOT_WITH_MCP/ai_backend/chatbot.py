"""LangGraph chatbot implementation."""

from typing import TypedDict, Annotated, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from ai_backend.llm_config import get_llm
from ai_backend.tools import get_all_tools
from storage.checkpointer import get_checkpointer
from core.async_utils import submit_async_task


# Define chat state
class ChatState(TypedDict):
    """State for chat graph."""
    messages: Annotated[list[BaseMessage], add_messages]


_CHATBOT = None
_TOOLS = None
_TOOL_NODE = None


def _build_chatbot():
    """Build the LangGraph chatbot (called once on startup)."""
    global _CHATBOT, _TOOLS, _TOOL_NODE

    if _CHATBOT is not None:
        return _CHATBOT

    # Get LLM and tools
    llm = get_llm()
    _TOOLS = get_all_tools()
    llm_with_tools = llm.bind_tools(_TOOLS) if _TOOLS else llm

    # Define nodes
    async def chat_node(state: ChatState):
        """LLM node that may answer or request a tool call."""
        messages = state["messages"]
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    # Create tool node if tools are available
    if _TOOLS:
        _TOOL_NODE = ToolNode(_TOOLS)

    # Build graph
    graph = StateGraph(ChatState)
    graph.add_node("chat_node", chat_node)
    graph.add_edge(START, "chat_node")

    if _TOOL_NODE:
        graph.add_node("tools", _TOOL_NODE)
        graph.add_conditional_edges("chat_node", tools_condition)
        graph.add_edge("tools", "chat_node")
    else:
        graph.add_edge("chat_node", END)

    # Compile with checkpointer
    checkpointer = get_checkpointer()
    _CHATBOT = graph.compile(checkpointer=checkpointer)

    return _CHATBOT


def get_chatbot():
    """Get the compiled chatbot.

    Returns:
        Compiled LangGraph chatbot
    """
    global _CHATBOT

    if _CHATBOT is None:
        _CHATBOT = _build_chatbot()

    return _CHATBOT
