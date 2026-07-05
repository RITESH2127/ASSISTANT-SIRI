"""
The agent's "brain": wraps the Anthropic API, defines the tool schema,
and runs the tool-calling loop (call model -> execute tools -> feed results
back -> repeat until the model returns a final text answer).
"""
import json
from anthropic import Anthropic
from .config import CONFIG
from .memory import Memory
from . import tools as T
from . import system_control as SC
from . import calendar_integration as CAL
from .learning import UsageLearner
from .error_handling import retry, log_error

TOOLS = [
    {
        "name": "open_application",
        "description": "Open/launch an application on the laptop, e.g. Notepad, Chrome, VS Code, Word.",
        "input_schema": {
            "type": "object",
            "properties": {"app_name": {"type": "string"}},
            "required": ["app_name"],
        },
    },
    {
        "name": "close_application",
        "description": "Close/force-quit a running application. Destructive: requires confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string"},
                "confirmed": {"type": "boolean", "description": "Set true only after the user has explicitly confirmed."},
            },
            "required": ["app_name"],
        },
    },
    {
        "name": "search_files",
        "description": "Search for files/folders on disk by (partial) name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "search_path": {"type": "string", "description": "Optional root folder to search from; defaults to the user's home folder."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "delete_file",
        "description": "Permanently delete a file. Destructive: requires confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "web_search",
        "description": "Search the web for information and open the results in the browser.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "open_website",
        "description": "Open a specific URL/website in the default browser.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "send_email",
        "description": "Send an email on the user's behalf. Requires confirmation before it actually sends.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "add_reminder",
        "description": "Create a reminder/task for the user at a specific time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "when": {"type": "string", "description": "Natural language time, e.g. 'tomorrow 6pm' or '2026-07-06 18:00'."},
            },
            "required": ["text", "when"],
        },
    },
    {
        "name": "list_reminders",
        "description": "List the user's upcoming reminders/tasks.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "take_note",
        "description": "Save a free-form note for later.",
        "input_schema": {
            "type": "object",
            "properties": {"note": {"type": "string"}},
            "required": ["note"],
        },
    },
    {
        "name": "remember_preference",
        "description": "Store a durable fact/preference about the user for future sessions (e.g. preferred language, default apps, work schedule).",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "run_shell_command",
        "description": "Run an arbitrary system command. Only use this when no other tool fits. Destructive/risky: requires confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "set_volume",
        "description": "Set the system speaker volume to a specific percentage (0-100).",
        "input_schema": {
            "type": "object",
            "properties": {"level_percent": {"type": "integer"}},
            "required": ["level_percent"],
        },
    },
    {
        "name": "mute_volume",
        "description": "Mute or unmute the system speakers.",
        "input_schema": {
            "type": "object",
            "properties": {"mute": {"type": "boolean"}},
            "required": ["mute"],
        },
    },
    {
        "name": "set_brightness",
        "description": "Set the screen brightness to a specific percentage (0-100).",
        "input_schema": {
            "type": "object",
            "properties": {"level_percent": {"type": "integer"}},
            "required": ["level_percent"],
        },
    },
    {
        "name": "lock_computer",
        "description": "Lock the screen immediately (not destructive, safe to run without confirmation).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "shutdown_computer",
        "description": "Shut down the computer. Destructive: requires confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {"confirmed": {"type": "boolean"}},
        },
    },
    {
        "name": "restart_computer",
        "description": "Restart the computer. Destructive: requires confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {"confirmed": {"type": "boolean"}},
        },
    },
    {
        "name": "list_calendar_events",
        "description": "List the user's upcoming Google Calendar events.",
        "input_schema": {
            "type": "object",
            "properties": {"max_results": {"type": "integer"}},
        },
    },
    {
        "name": "add_calendar_event",
        "description": "Add an event to the user's Google Calendar. Requires confirmation before actually creating it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "start_iso": {"type": "string", "description": "ISO 8601 datetime, e.g. 2026-07-06T18:00:00"},
                "end_iso": {"type": "string", "description": "Optional ISO 8601 datetime; defaults to start + 1 hour."},
                "confirmed": {"type": "boolean"},
            },
            "required": ["summary", "start_iso"],
        },
    },
]

SYSTEM_PROMPT_TEMPLATE = """You are {name}, a private, on-device personal voice assistant running on the user's own laptop.

Personality: warm, concise, capable — like a sharp human assistant, not a scripted bot. Speak naturally; you may mix Hindi and English (Hinglish) if the user does.

Rules:
1. You can control the laptop via tools. Use them whenever the user's request maps to one, rather than just describing what they could do.
2. Any tool result that starts with "CONFIRMATION_REQUIRED" means you must STOP, explain in plain language what you're about to do, and ask the user to confirm out loud. Only call that same tool again with confirmed=true after the user clearly says yes in their next message. Never assume confirmation.
3. Never invent file paths, email addresses, or results — only report what tools actually returned.
4. Keep spoken replies short and natural (this gets read aloud by text-to-speech). Save long detail for when the user asks for it.
5. Use remember_preference proactively when the user states a lasting preference (e.g. "I prefer Hindi in the evening", "always open VS Code for coding tasks").
6. If you're not sure what the user meant, ask a brief clarifying question instead of guessing at a destructive action.
7. shutdown_computer and restart_computer end the user's session — always double-check by repeating back what will happen before confirming.

{facts_block}

{usage_block}
"""


class Agent:
    def __init__(self, memory: Memory):
        self.memory = memory
        self.client = Anthropic(api_key=CONFIG.anthropic_api_key)
        self.learner = UsageLearner()
        self.tool_dispatch = {
            "open_application": lambda i: T.open_application(i["app_name"]),
            "close_application": lambda i: T.close_application(i["app_name"], i.get("confirmed", False)),
            "search_files": lambda i: T.search_files(i["query"], i.get("search_path")),
            "delete_file": lambda i: T.delete_file(i["file_path"], i.get("confirmed", False)),
            "web_search": lambda i: T.web_search(i["query"]),
            "open_website": lambda i: T.open_website(i["url"]),
            "send_email": lambda i: T.send_email(i["to"], i["subject"], i["body"], i.get("confirmed", False)),
            "add_reminder": lambda i: T.add_reminder(self.memory, i["text"], i["when"]),
            "list_reminders": lambda i: T.list_reminders(self.memory),
            "take_note": lambda i: T.take_note(self.memory, i["note"]),
            "remember_preference": lambda i: T.remember_preference(self.memory, i["key"], i["value"]),
            "run_shell_command": lambda i: T.run_shell_command(i["command"], i.get("confirmed", False)),
            "set_volume": lambda i: SC.set_volume(i["level_percent"]),
            "mute_volume": lambda i: SC.mute_volume(i.get("mute", True)),
            "set_brightness": lambda i: SC.set_brightness(i["level_percent"]),
            "lock_computer": lambda i: SC.lock_computer(),
            "shutdown_computer": lambda i: SC.shutdown_computer(i.get("confirmed", False)),
            "restart_computer": lambda i: SC.restart_computer(i.get("confirmed", False)),
            "list_calendar_events": lambda i: CAL.list_upcoming_events(i.get("max_results", 10)),
            "add_calendar_event": lambda i: CAL.add_calendar_event(
                i["summary"], i["start_iso"], i.get("end_iso"), i.get("confirmed", False)
            ),
        }

    def _system_prompt(self) -> str:
        return SYSTEM_PROMPT_TEMPLATE.format(
            name=CONFIG.assistant_name,
            facts_block=self.memory.facts_as_prompt_block(),
            usage_block=self.learner.usage_summary_block(),
        )

    @retry(max_attempts=3, base_delay=1.5)
    def _call_model(self, messages):
        return self.client.messages.create(
            model=CONFIG.claude_model,
            max_tokens=1024,
            system=self._system_prompt(),
            tools=TOOLS,
            messages=messages,
        )

    def respond(self, user_text: str) -> str:
        """Run one full agent turn (including any tool-calling round trips)
        and return the final natural-language reply."""
        self.memory.log_message("user", user_text)

        history = self.memory.recent_history(limit=20)
        messages = [{"role": role, "content": content} for role, content in history]

        final_text = ""
        # Tool-use loop: keep calling the model until it stops requesting tools
        for _ in range(6):  # hard cap to avoid infinite loops
            try:
                resp = self._call_model(messages)
            except Exception as e:
                log_error(f"Claude API call failed after retries: {e}")
                final_text = ("Sorry, I couldn't reach the AI service just now. "
                              "Check your internet connection and API key, then try again.")
                break

            text_parts = [b.text for b in resp.content if b.type == "text"]
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            final_text = "\n".join(text_parts).strip()

            if not tool_uses:
                break

            # Append the assistant's turn (including tool_use blocks) then
            # run each tool and append the results, then loop again.
            messages.append({"role": "assistant", "content": resp.content})
            tool_results = []
            for call in tool_uses:
                fn = self.tool_dispatch.get(call.name)
                try:
                    result = fn(call.input) if fn else f"Unknown tool: {call.name}"
                    if not str(result).startswith("CONFIRMATION_REQUIRED"):
                        arg_summary = ", ".join(f"{k}={v}" for k, v in (call.input or {}).items() if k != "confirmed")
                        self.learner.log_usage(call.name, arg_summary)
                except Exception as e:
                    result = f"Tool '{call.name}' failed: {e}"
                    log_error(f"Tool '{call.name}' raised: {e}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": str(result),
                })
            messages.append({"role": "user", "content": tool_results})

        self.memory.log_message("assistant", final_text)
        return final_text
