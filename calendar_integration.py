"""
Real Google Calendar integration (not a local stand-in). Uses OAuth so the
assistant reads/writes your actual calendar.

Setup (also in README):
  1. https://console.cloud.google.com/ -> new project -> enable "Google Calendar API"
  2. Create OAuth Client ID (type: Desktop app) -> download JSON
  3. Save it as credentials.json in the project root
On first calendar use, a browser window opens for you to grant access once;
after that, a token is cached locally in ~/.ai_assistant/calendar_token.json
so you don't have to log in again.

If credentials.json is missing, every function here fails gracefully with a
clear message instead of crashing the assistant.
"""
import datetime
from pathlib import Path

from .config import CONFIG, APP_DIR

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_PATH = APP_DIR / "calendar_token.json"


def _get_service():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            cred_file = Path(CONFIG.google_calendar_credentials)
            if not cred_file.exists():
                raise FileNotFoundError(
                    f"'{cred_file}' not found. Follow the Google Calendar setup steps in README.md."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(cred_file), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def list_upcoming_events(max_results: int = 10) -> str:
    try:
        service = _get_service()
        now = datetime.datetime.utcnow().isoformat() + "Z"
        events_result = service.events().list(
            calendarId="primary", timeMin=now, maxResults=max_results,
            singleEvents=True, orderBy="startTime",
        ).execute()
        events = events_result.get("items", [])
        if not events:
            return "No upcoming events on your calendar."
        lines = []
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date"))
            lines.append(f"- {e.get('summary', '(no title)')} at {start}")
        return "Upcoming calendar events:\n" + "\n".join(lines)
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Could not read calendar: {e}"


def add_calendar_event(summary: str, start_iso: str, end_iso: str = None, confirmed: bool = False) -> str:
    if not confirmed:
        return (f"CONFIRMATION_REQUIRED: add '{summary}' to your Google Calendar at {start_iso}? "
                f"Ask the user to confirm before calling this again with confirmed=True.")
    try:
        service = _get_service()
        if not end_iso:
            start_dt = datetime.datetime.fromisoformat(start_iso)
            end_iso = (start_dt + datetime.timedelta(hours=1)).isoformat()
        event = {
            "summary": summary,
            "start": {"dateTime": start_iso},
            "end": {"dateTime": end_iso},
        }
        created = service.events().insert(calendarId="primary", body=event).execute()
        return f"Added '{summary}' to your calendar: {created.get('htmlLink')}"
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Could not add calendar event: {e}"
