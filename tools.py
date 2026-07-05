"""
Laptop automation tools.

Each function here maps 1:1 to a "tool" the LLM can call (see llm.py for the
tool schema). Every function returns a short string describing the result,
which gets fed back to the model.

SAFETY: any tool that is destructive or hard to undo (delete_file,
close_application, change_system_setting) requires `confirmed=True` to
actually execute. The agent is instructed (in llm.py's system prompt) to
always ask the user out loud for confirmation first, then call the tool
again with confirmed=True only after the user says yes.
"""
import os
import sys
import glob
import subprocess
import smtplib
import webbrowser
import time
import platform
from email.mime.text import MIMEText
from dateutil import parser as dateparser

from .config import CONFIG
from .memory import Memory

IS_WINDOWS = platform.system() == "Windows"

# Common Windows app name -> launch command mapping. Extend as needed.
APP_MAP = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "vscode": "code",
    "visual studio code": "code",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "settings": "ms-settings:",
    "spotify": "spotify.exe",
}


def open_application(app_name: str) -> str:
    key = app_name.strip().lower()
    cmd = APP_MAP.get(key, app_name)
    try:
        if IS_WINDOWS:
            if cmd.startswith("ms-settings:"):
                os.startfile(cmd)
            else:
                subprocess.Popen(cmd, shell=True)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-a", app_name])
        else:
            subprocess.Popen([cmd])
        return f"Opened {app_name}."
    except Exception as e:
        return f"Could not open {app_name}: {e}"


def close_application(app_name: str, confirmed: bool = False) -> str:
    if not confirmed:
        return f"CONFIRMATION_REQUIRED: closing '{app_name}' will end any unsaved work in it. Ask the user to confirm."
    key = app_name.strip().lower()
    exe = APP_MAP.get(key, app_name)
    if not exe.endswith(".exe"):
        exe = exe + ".exe"
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/IM", exe, "/F"], capture_output=True)
        else:
            subprocess.run(["pkill", "-f", app_name], capture_output=True)
        return f"Closed {app_name}."
    except Exception as e:
        return f"Could not close {app_name}: {e}"


def search_files(query: str, search_path: str = None, max_results: int = 15) -> str:
    root = search_path or str(Path_home())
    matches = []
    pattern = f"*{query}*"
    for dirpath, dirnames, filenames in os.walk(root):
        # skip noisy system dirs for speed
        dirnames[:] = [d for d in dirnames if d.lower() not in
                        ("windows", "$recycle.bin", "node_modules", ".git", "appdata")]
        for fn in filenames:
            if glob.fnmatch.fnmatch(fn.lower(), pattern.lower()):
                matches.append(os.path.join(dirpath, fn))
                if len(matches) >= max_results:
                    break
        if len(matches) >= max_results:
            break
    if not matches:
        return f"No files found matching '{query}' under {root}."
    return "Found files:\n" + "\n".join(matches)


def Path_home():
    return os.path.expanduser("~")


def delete_file(file_path: str, confirmed: bool = False) -> str:
    if not confirmed:
        return f"CONFIRMATION_REQUIRED: deleting '{file_path}' is permanent. Ask the user to confirm before calling this again with confirmed=True."
    try:
        os.remove(file_path)
        return f"Deleted {file_path}."
    except Exception as e:
        return f"Could not delete {file_path}: {e}"


def web_search(query: str) -> str:
    url = "https://www.google.com/search?q=" + query.replace(" ", "+")
    webbrowser.open(url)
    return f"Opened a web search for '{query}' in your browser."


def open_website(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opened {url} in your browser."


def send_email(to: str, subject: str, body: str, confirmed: bool = False) -> str:
    if not confirmed:
        return (f"CONFIRMATION_REQUIRED: send an email to {to} with subject "
                f"'{subject}'? Ask the user to confirm before calling this again with confirmed=True.")
    if not CONFIG.smtp_email or not CONFIG.smtp_password:
        return "Email is not configured. Add SMTP_EMAIL and SMTP_APP_PASSWORD to your .env file."
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = CONFIG.smtp_email
        msg["To"] = to
        with smtplib.SMTP(CONFIG.smtp_host, CONFIG.smtp_port) as server:
            server.starttls()
            server.login(CONFIG.smtp_email, CONFIG.smtp_password)
            server.send_message(msg)
        return f"Email sent to {to}."
    except Exception as e:
        return f"Failed to send email: {e}"


def add_reminder(memory: Memory, text: str, when: str) -> str:
    try:
        due_dt = dateparser.parse(when, fuzzy=True)
        due_ts = due_dt.timestamp()
    except Exception:
        return f"Could not understand the time '{when}'. Try something like 'tomorrow 6pm' or '2026-07-06 18:00'."
    memory.add_reminder(text, due_ts)
    return f"Reminder set: '{text}' at {due_dt.strftime('%Y-%m-%d %H:%M')}."


def list_reminders(memory: Memory) -> str:
    rows = memory.list_reminders()
    if not rows:
        return "You have no upcoming reminders."
    lines = []
    for rid, text, due_ts, done in rows:
        t = time.strftime("%Y-%m-%d %H:%M", time.localtime(due_ts))
        lines.append(f"[{rid}] {text} — {t}")
    return "Upcoming reminders:\n" + "\n".join(lines)


def take_note(memory: Memory, note: str) -> str:
    memory.set_fact(f"note_{int(time.time())}", note)
    return "Noted."


def remember_preference(memory: Memory, key: str, value: str) -> str:
    memory.set_fact(key, value)
    return f"Got it, I'll remember that {key} = {value}."


def run_shell_command(command: str, confirmed: bool = False) -> str:
    """
    Generic escape hatch for power users. Disabled by default via the
    confirmation gate; the agent's system prompt tells it to only use this
    for things no other tool covers, and always confirm first.
    """
    if not confirmed:
        return f"CONFIRMATION_REQUIRED: run this command on the system: `{command}`? Ask the user to confirm."
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=20)
        out = (result.stdout or "") + (result.stderr or "")
        return out[:2000] if out else "Command ran with no output."
    except Exception as e:
        return f"Command failed: {e}"
