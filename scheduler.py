"""
Runs in a background thread and makes the assistant proactive instead of
purely reactive:
  1. Fires a "due" check every 30 seconds for reminders -> speaks/announces
     them the moment they're due, then marks them done.
  2. Fires a daily briefing once a day at CONFIG.daily_briefing_time,
     combining: today's calendar events, open reminders, and a usage-pattern
     suggestion.

Any error in a scheduled job is caught and logged rather than crashing the
background thread (see error_handling.py).
"""
import threading
import time
import schedule

from .config import CONFIG
from .memory import Memory
from .learning import UsageLearner
from . import calendar_integration as cal
from .error_handling import log_error, safe_call


class ProactiveScheduler:
    def __init__(self, memory: Memory, on_announce):
        """
        on_announce: callback(text: str) -> None, called whenever the
        assistant wants to proactively say something (the GUI wires this to
        both the transcript view and TTS).
        """
        self.memory = memory
        self.learner = UsageLearner()
        self.on_announce = on_announce
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if not CONFIG.proactive_enabled:
            return
        schedule.every(30).seconds.do(safe_call(self._check_due_reminders))
        schedule.every().day.at(CONFIG.daily_briefing_time).do(safe_call(self._daily_briefing))
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run_loop(self):
        while not self._stop.is_set():
            try:
                schedule.run_pending()
            except Exception as e:
                log_error(f"scheduler loop error: {e}")
            time.sleep(1)

    def _check_due_reminders(self):
        due = self.memory.due_reminders()
        for rid, text, due_ts in due:
            self.on_announce(f"Reminder: {text}")
            self.memory.mark_reminder_done(rid)

    def trigger_daily_briefing_now(self):
        """Lets the GUI expose a manual 'Daily Briefing' button too."""
        self._daily_briefing()

    def _daily_briefing(self):
        parts = ["Good day! Here's your briefing."]

        reminders = self.memory.list_reminders()
        if reminders:
            parts.append(f"You have {len(reminders)} upcoming reminder(s).")

        cal_text = cal.list_upcoming_events(max_results=5)
        if cal_text and "not found" not in cal_text.lower() and "could not" not in cal_text.lower():
            parts.append(cal_text)

        suggestions = self.learner.suggestions_for_current_hour()
        parts.extend(suggestions)

        briefing = " ".join(parts)
        self.memory.log_message("assistant", briefing)
        self.on_announce(briefing)
