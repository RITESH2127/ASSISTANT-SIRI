"""
Central configuration loader.
Reads from .env (via python-dotenv) and exposes a single Config object
used across the whole assistant.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

APP_DIR = Path.home() / ".ai_assistant"
APP_DIR.mkdir(exist_ok=True)

DB_PATH = APP_DIR / "memory.db"
LOG_PATH = APP_DIR / "assistant.log"

# Load .env from the project root (or the frozen exe's folder)
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


class Config:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

    smtp_email: str = os.getenv("SMTP_EMAIL", "")
    smtp_password: str = os.getenv("SMTP_APP_PASSWORD", "")
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))

    default_language: str = os.getenv("DEFAULT_LANGUAGE", "auto")
    wake_word_enabled: bool = os.getenv("WAKE_WORD_ENABLED", "off").lower() == "on"
    wake_word_model_path: str = os.getenv("WAKE_WORD_MODEL_PATH", "").strip()
    wake_word_threshold: float = float(os.getenv("WAKE_WORD_THRESHOLD", "0.5"))

    proactive_enabled: bool = os.getenv("PROACTIVE_ENABLED", "on").lower() == "on"
    daily_briefing_time: str = os.getenv("DAILY_BRIEFING_TIME", "08:30")

    google_calendar_credentials: str = os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "credentials.json")
    app_pin: str = os.getenv("APP_PIN", "").strip()
    briefing_city: str = os.getenv("BRIEFING_CITY", "Delhi")

    assistant_name: str = "Assistant"

    def validate(self) -> list[str]:
        problems = []
        if not self.anthropic_api_key or self.anthropic_api_key == "your_api_key_here":
            problems.append(
                "ANTHROPIC_API_KEY is missing. Get one at https://console.anthropic.com/ "
                "and put it in your .env file."
            )
        return problems


CONFIG = Config()
