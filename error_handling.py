"""
Centralized error handling so failures degrade gracefully instead of
crashing the assistant:
  - log_error(...) writes to ~/.ai_assistant/assistant.log with a timestamp
  - safe_call(...) wraps a function so exceptions are logged, not raised
  - retry(...) adds exponential-backoff retries for flaky network calls
    (e.g. the Claude API, Google Calendar, email) — used in llm.py
"""
import time
import traceback
import functools
from datetime import datetime
from .config import LOG_PATH


def log_error(message: str):
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass  # logging must never itself crash the app
    print(line.strip())


def safe_call(func):
    """Wrap a zero-arg callable so scheduled jobs never take down the
    background thread; any exception is logged instead."""
    @functools.wraps(func)
    def wrapper():
        try:
            return func()
        except Exception:
            log_error(f"Error in {func.__name__}:\n{traceback.format_exc()}")
    return wrapper


def retry(max_attempts: int = 3, base_delay: float = 1.5):
    """Decorator: retries a function with exponential backoff on exception.
    Use for network-dependent calls (LLM API, calendar, email)."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    log_error(f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {e}")
                    if attempt < max_attempts:
                        time.sleep(base_delay * (2 ** (attempt - 1)))
            raise last_exc
        return wrapper
    return decorator
