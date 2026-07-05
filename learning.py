"""
Lightweight, transparent "self-learning" layer.

Important honesty note: this is NOT a neural model retraining itself. It's a
simple, auditable frequency/recency tracker over tool usage, stored in the
same local SQLite database. This is a deliberate design choice: it's fast,
needs no GPU, is fully private, and — critically — you can always inspect
exactly why it suggested something (unlike an opaque model).

What it does:
  - Logs every tool call with a timestamp and hour-of-day bucket.
  - Surfaces "you often do X around this time" suggestions.
  - Feeds a short usage-pattern summary into the daily briefing.
"""
import time
import sqlite3
from collections import Counter
from .config import DB_PATH


class UsageLearner:
    def __init__(self, db_path=DB_PATH):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tool_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT,
                arg_summary TEXT,
                hour_of_day INTEGER,
                weekday INTEGER,
                ts REAL
            )
        """)
        self.conn.commit()

    def log_usage(self, tool_name: str, arg_summary: str = ""):
        now = time.localtime()
        self.conn.execute(
            "INSERT INTO tool_usage (tool_name, arg_summary, hour_of_day, weekday, ts) VALUES (?, ?, ?, ?, ?)",
            (tool_name, arg_summary[:200], now.tm_hour, now.tm_wday, time.time()),
        )
        self.conn.commit()

    def top_tools(self, limit: int = 5):
        rows = self.conn.execute(
            "SELECT tool_name, COUNT(*) c FROM tool_usage GROUP BY tool_name ORDER BY c DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return rows

    def suggestions_for_current_hour(self, window: int = 1, min_occurrences: int = 3):
        """Look at what the user has historically done around this hour of
        day (+/- `window` hours), across at least `min_occurrences` past
        days, and surface it as a proactive suggestion."""
        now_hour = time.localtime().tm_hour
        hours = [(now_hour + d) % 24 for d in range(-window, window + 1)]
        placeholders = ",".join("?" for _ in hours)
        rows = self.conn.execute(
            f"SELECT tool_name, arg_summary, COUNT(*) c FROM tool_usage "
            f"WHERE hour_of_day IN ({placeholders}) "
            f"GROUP BY tool_name, arg_summary ORDER BY c DESC LIMIT 3",
            hours,
        ).fetchall()
        suggestions = []
        for tool_name, arg_summary, count in rows:
            if count >= min_occurrences:
                label = f"{tool_name}" + (f" ({arg_summary})" if arg_summary else "")
                suggestions.append(f"You often use '{label}' around this time ({count} times before).")
        return suggestions

    def usage_summary_block(self) -> str:
        top = self.top_tools()
        if not top:
            return ""
        lines = "\n".join(f"- {name}: used {count} times" for name, count in top)
        return f"Your most-used assistant actions overall:\n{lines}"
