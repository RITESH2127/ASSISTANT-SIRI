"""
Local, private memory system.

Three kinds of memory, all in one SQLite file on the user's own disk
(never sent anywhere except the relevant snippets included in LLM prompts):

1. conversation_log  - full transcript history (for "chat history" UI + context)
2. facts             - durable key/value facts learned about the user
                       ("user prefers Hindi in the evening", "user's default
                       browser is Chrome", etc.)
3. reminders         - simple task/reminder store used by the reminder tools
"""
import sqlite3
import time
import json
from pathlib import Path
from .config import DB_PATH


class Memory:
    def __init__(self, db_path: Path = DB_PATH):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self._init_schema()

    def _init_schema(self):
        c = self.conn
        c.execute("""
            CREATE TABLE IF NOT EXISTS conversation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL,
                role TEXT,
                content TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_ts REAL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT,
                due_ts REAL,
                created_ts REAL,
                done INTEGER DEFAULT 0
            )
        """)
        c.commit()

    # ---------- conversation log ----------
    def log_message(self, role: str, content: str):
        self.conn.execute(
            "INSERT INTO conversation_log (ts, role, content) VALUES (?, ?, ?)",
            (time.time(), role, content),
        )
        self.conn.commit()

    def recent_history(self, limit: int = 20):
        rows = self.conn.execute(
            "SELECT role, content FROM conversation_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return list(reversed(rows))

    # ---------- facts / preferences ----------
    def set_fact(self, key: str, value: str):
        self.conn.execute(
            "INSERT INTO facts (key, value, updated_ts) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_ts=excluded.updated_ts",
            (key, value, time.time()),
        )
        self.conn.commit()

    def get_fact(self, key: str):
        row = self.conn.execute("SELECT value FROM facts WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def all_facts(self) -> dict:
        rows = self.conn.execute("SELECT key, value FROM facts").fetchall()
        return {k: v for k, v in rows}

    # ---------- reminders ----------
    def add_reminder(self, text: str, due_ts: float) -> int:
        cur = self.conn.execute(
            "INSERT INTO reminders (text, due_ts, created_ts, done) VALUES (?, ?, ?, 0)",
            (text, due_ts, time.time()),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_reminders(self, include_done: bool = False):
        q = "SELECT id, text, due_ts, done FROM reminders"
        if not include_done:
            q += " WHERE done=0"
        q += " ORDER BY due_ts ASC"
        return self.conn.execute(q).fetchall()

    def mark_reminder_done(self, reminder_id: int):
        self.conn.execute("UPDATE reminders SET done=1 WHERE id=?", (reminder_id,))
        self.conn.commit()

    def due_reminders(self):
        now = time.time()
        rows = self.conn.execute(
            "SELECT id, text, due_ts FROM reminders WHERE done=0 AND due_ts<=?",
            (now,),
        ).fetchall()
        return rows

    def facts_as_prompt_block(self) -> str:
        facts = self.all_facts()
        if not facts:
            return ""
        lines = "\n".join(f"- {k}: {v}" for k, v in facts.items())
        return f"Known facts about the user (from past sessions):\n{lines}"
