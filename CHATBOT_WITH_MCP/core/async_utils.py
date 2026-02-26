"""Async utilities for managing event loop and bridging sync/async code."""

import asyncio
import threading
from typing import Any, Coroutine

# Dedicated async loop for backend tasks
_ASYNC_LOOP = asyncio.new_event_loop()
_ASYNC_THREAD = threading.Thread(target=_ASYNC_LOOP.run_forever, daemon=True)
_ASYNC_THREAD.start()


def get_event_loop() -> asyncio.AbstractEventLoop:
    """Get the dedicated event loop for background tasks."""
    return _ASYNC_LOOP


def _submit_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Submit a coroutine to run on the background event loop."""
    return asyncio.run_coroutine_threadsafe(coro, _ASYNC_LOOP)


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run a coroutine synchronously on the background event loop.

    This blocks until the coroutine completes.
    """
    return _submit_async(coro).result()


def submit_async_task(coro: Coroutine[Any, Any, Any]) -> Any:
    """Schedule a coroutine on the backend event loop (non-blocking).

    Returns a Future that can be awaited later.
    """
    return _submit_async(coro)
