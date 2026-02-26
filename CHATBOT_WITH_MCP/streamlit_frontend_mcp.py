import queue
import uuid

import streamlit as st
from langgraph_mcp_backend import (
    chatbot, retrieve_all_threads, submit_async_task,
    save_thread_name, generate_thread_title,
    register_user, authenticate_user, user_exists
)
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

# =========================== Utilities ===========================
def generate_thread_id():
    return uuid.uuid4()


def reset_chat():
    thread_id = generate_thread_id()
    st.session_state["thread_id"] = thread_id
    st.session_state["is_new_thread"] = True
    st.session_state["message_history"] = []


def load_conversation(thread_id):
    state = chatbot.get_state(config={"configurable": {"thread_id": thread_id}})
    return state.values.get("messages", [])


# ======================= Session Initialization ===================
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None

if "username" not in st.session_state:
    st.session_state["username"] = None

if "message_history" not in st.session_state:
    st.session_state["message_history"] = []

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = None

if "is_new_thread" not in st.session_state:
    st.session_state["is_new_thread"] = False

if "chat_threads" not in st.session_state:
    st.session_state["chat_threads"] = {}

if "show_auth_page" not in st.session_state:
    st.session_state["show_auth_page"] = False

# ============================ Authentication Page ============================
if st.session_state["user_id"] is None:
    st.set_page_config(page_title="LangGraph MCP Chatbot", layout="centered")
    st.title("🔐 LangGraph MCP Chatbot")

    auth_tab1, auth_tab2 = st.tabs(["Login", "Register"])

    with auth_tab1:
        st.subheader("Login to Your Account")
        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login", key="login_btn", use_container_width=True):
            if not login_username or not login_password:
                st.error("Please enter both username and password")
            else:
                success, result = authenticate_user(login_username, login_password)
                if success:
                    st.session_state["user_id"] = result
                    st.session_state["username"] = login_username
                    st.session_state["chat_threads"] = retrieve_all_threads(result) or {}
                    if not st.session_state["chat_threads"]:
                        reset_chat()
                    st.success("Login successful! Redirecting...")
                    st.rerun()
                else:
                    st.error(result)

    with auth_tab2:
        st.subheader("Create a New Account")
        register_username = st.text_input("Username", key="register_username")
        register_password = st.text_input("Password", type="password", key="register_password")
        register_confirm = st.text_input("Confirm Password", type="password", key="register_confirm")

        if st.button("Register", key="register_btn", use_container_width=True):
            if not register_username or not register_password:
                st.error("Please fill in all fields")
            elif register_password != register_confirm:
                st.error("Passwords do not match")
            else:
                success, result = register_user(register_username, register_password)
                if success:
                    st.session_state["user_id"] = result
                    st.session_state["username"] = register_username
                    st.session_state["chat_threads"] = {}
                    reset_chat()
                    st.success("Account created successfully! Logging in...")
                    st.rerun()
                else:
                    st.error(result)

# ============================ Main Chat Interface ============================
else:
    st.set_page_config(page_title="LangGraph MCP Chatbot", layout="wide")

    # Top bar with theme and logout
    col1, col2, col3 = st.columns([1, 4, 1])
    with col1:
        st.write(f"👤 {st.session_state['username']}")
    with col3:
        if st.button("Logout", key="logout_btn"):
            st.session_state["user_id"] = None
            st.session_state["username"] = None
            st.session_state["message_history"] = []
            st.session_state["chat_threads"] = {}
            st.session_state["thread_id"] = None
            st.rerun()

    # ============================ Sidebar ============================
    st.sidebar.title("LangGraph MCP Chatbot")

    if st.sidebar.button("+ New Chat"):
        reset_chat()
        st.rerun()

    st.sidebar.header("My Conversations")

    # Display threads in reverse order (newest first)
    sorted_threads = sorted(
        st.session_state["chat_threads"].items(),
        key=lambda x: x[1] if isinstance(x[1], str) else str(x[1]),
        reverse=True
    )

    for thread_id, thread_name in sorted_threads:
        # Use columns for button and rename button
        col1, col2 = st.sidebar.columns([0.9, 0.1])

        with col1:
            if st.button(
                thread_name or "New Chat",
                key=f"thread_{thread_id}",
                use_container_width=True
            ):
                st.session_state["thread_id"] = thread_id
                st.session_state["is_new_thread"] = False
                messages = load_conversation(thread_id)

                temp_messages = []
                for msg in messages:
                    role = "user" if isinstance(msg, HumanMessage) else "assistant"
                    temp_messages.append({"role": role, "content": msg.content})
                st.session_state["message_history"] = temp_messages
                st.rerun()

        with col2:
            if st.button("✏️", key=f"rename_{thread_id}", help="Rename thread"):
                st.session_state["rename_thread_id"] = thread_id
                st.session_state["show_rename_modal"] = True

    # Rename Modal
    if st.session_state.get("show_rename_modal", False):
        rename_thread_id = st.session_state.get("rename_thread_id")
        current_name = st.session_state["chat_threads"].get(rename_thread_id, "New Chat")

        st.sidebar.divider()
        st.sidebar.subheader("Rename Thread")
        new_name = st.sidebar.text_input(
            "New name:",
            value=current_name,
            key="rename_input"
        )

        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("Save", key="save_rename"):
                if new_name.strip():
                    save_thread_name(st.session_state["user_id"], rename_thread_id, new_name.strip())
                    st.session_state["chat_threads"][rename_thread_id] = new_name.strip()
                    st.session_state["show_rename_modal"] = False
                    st.rerun()
        with col2:
            if st.button("Cancel", key="cancel_rename"):
                st.session_state["show_rename_modal"] = False
                st.rerun()

    # ============================ Main UI ============================

    # Ensure we have a current thread
    if not st.session_state["thread_id"]:
        reset_chat()

    # Render history
    for message in st.session_state["message_history"]:
        with st.chat_message(message["role"]):
            st.text(message["content"])

    user_input = st.chat_input("Type here")

    if user_input:
        # Generate title on first message if it's a new thread
        if st.session_state.get("is_new_thread", False):
            title = generate_thread_title(user_input)
            save_thread_name(st.session_state["user_id"], st.session_state["thread_id"], title)
            st.session_state["chat_threads"][st.session_state["thread_id"]] = title
            st.session_state["is_new_thread"] = False

        # Show user's message
        st.session_state["message_history"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.text(user_input)

        CONFIG = {
            "configurable": {"thread_id": st.session_state["thread_id"]},
            "metadata": {"thread_id": st.session_state["thread_id"]},
            "run_name": "chat_turn",
        }

        # Assistant streaming block
        with st.chat_message("assistant"):
            # Use a mutable holder so the generator can set/modify it
            status_holder = {"box": None}

            def ai_only_stream():
                event_queue: queue.Queue = queue.Queue()

                async def run_stream():
                    try:
                        async for message_chunk, metadata in chatbot.astream(
                            {"messages": [HumanMessage(content=user_input)]},
                            config=CONFIG,
                            stream_mode="messages",
                        ):
                            event_queue.put((message_chunk, metadata))
                    except Exception as exc:
                        event_queue.put(("error", exc))
                    finally:
                        event_queue.put(None)

                submit_async_task(run_stream())

                while True:
                    item = event_queue.get()
                    if item is None:
                        break
                    message_chunk, metadata = item
                    if message_chunk == "error":
                        raise metadata

                    # Lazily create & update the SAME status container when any tool runs
                    if isinstance(message_chunk, ToolMessage):
                        tool_name = getattr(message_chunk, "name", "tool")
                        if status_holder["box"] is None:
                            status_holder["box"] = st.status(
                                f"🔧 Using `{tool_name}` …", expanded=True
                            )
                        else:
                            status_holder["box"].update(
                                label=f"🔧 Using `{tool_name}` …",
                                state="running",
                                expanded=True,
                            )

                    # Stream ONLY assistant tokens
                    if isinstance(message_chunk, AIMessage):
                        yield message_chunk.content

            ai_message = st.write_stream(ai_only_stream())

            # Finalize only if a tool was actually used
            if status_holder["box"] is not None:
                status_holder["box"].update(
                    label="✅ Tool finished", state="complete", expanded=False
                )

        # Save assistant message
        st.session_state["message_history"].append(
            {"role": "assistant", "content": ai_message}
        )
