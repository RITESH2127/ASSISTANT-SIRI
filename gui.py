"""
Simple, clean desktop GUI built with Tkinter (ships with Python, no extra
GUI framework needed). Provides:
  - a chat/transcript view (doubles as "chat history")
  - a mic button + Space-bar push-to-talk
  - a Settings tab (language, wake word toggle, assistant name)
  - status bar showing what the assistant is doing
"""
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from .config import CONFIG
from .memory import Memory
from .llm import Agent
from .stt import SpeechToText
from .tts import TextToSpeech
from .scheduler import ProactiveScheduler
from .wake_word import WakeWordListener
from .error_handling import log_error


class AssistantGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Personal AI Assistant")
        self.root.geometry("640x760")

        if not self._check_pin_lock():
            self.root.destroy()
            return

        self.memory = Memory()
        self.agent = Agent(self.memory)
        self.tts = TextToSpeech()
        self.stt_engine = None  # lazy-loaded (model download/load takes a few seconds)
        self.busy = False

        self._build_ui()
        self._load_history_into_view()
        threading.Thread(target=self._preload_stt, daemon=True).start()

        self.scheduler = ProactiveScheduler(self.memory, on_announce=self._proactive_announce)
        self.scheduler.start()

        self.wake_listener = None
        if CONFIG.wake_word_enabled:
            threading.Thread(target=self._start_wake_word, daemon=True).start()

        problems = CONFIG.validate()
        if problems:
            messagebox.showwarning("Setup needed", "\n".join(problems))

    def _start_wake_word(self):
        try:
            self.wake_listener = WakeWordListener()
            label = ("your trained wake word" if self.wake_listener.using_custom_model
                      else "'Hey Jarvis' (train your own — see README)")
            self.root.after(0, lambda: self.status_var.set(f"Always-on mode active — say {label}."))
            self.wake_listener.start_background_listener(self._on_wake_word_detected)
        except Exception as e:
            log_error(f"Could not start wake word listener: {e}")
            self.root.after(0, lambda: self.status_var.set(
                "Wake word mode failed to start — falling back to push-to-talk (see assistant.log)."
            ))

    def _on_wake_word_detected(self):
        # Called from the wake-word background thread, not the Tk thread.
        if self.busy or self.stt_engine is None:
            return
        threading.Thread(target=self._listen_and_handle, daemon=True).start()

    def _check_pin_lock(self) -> bool:
        """Optional privacy gate: if APP_PIN is set in .env, require it before
        the assistant (and all its memory/tools) becomes accessible."""
        if not CONFIG.app_pin:
            return True
        for _ in range(3):
            entered = simpledialog.askstring("Locked", "Enter PIN to unlock the assistant:", show="*")
            if entered is None:
                return False
            if entered == CONFIG.app_pin:
                return True
            messagebox.showerror("Incorrect PIN", "Try again.")
        return False

    def _proactive_announce(self, text: str):
        """Called by the background scheduler (from a non-GUI thread) when
        it wants to speak up unprompted — a due reminder or the daily
        briefing. Must hop back onto the Tk main thread to touch widgets."""
        def _do():
            self._append_transcript("assistant", text)
            self.status_var.set("Speaking...")
            self.tts.speak(text, lang="en")
            self.status_var.set("Ready.")
        self.root.after(0, _do)

    # ---------- UI construction ----------
    def _build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)

        chat_tab = ttk.Frame(notebook)
        settings_tab = ttk.Frame(notebook)
        notebook.add(chat_tab, text="Assistant")
        notebook.add(settings_tab, text="Settings")

        # --- Chat tab ---
        self.transcript = tk.Text(chat_tab, wrap="word", state="disabled", font=("Segoe UI", 11))
        self.transcript.pack(fill="both", expand=True, padx=10, pady=10)

        input_frame = ttk.Frame(chat_tab)
        input_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.text_entry = ttk.Entry(input_frame, font=("Segoe UI", 11))
        self.text_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.text_entry.bind("<Return>", lambda e: self._on_type_submit())

        send_btn = ttk.Button(input_frame, text="Send", command=self._on_type_submit)
        send_btn.pack(side="left", padx=(0, 8))

        self.mic_btn = ttk.Button(input_frame, text="🎤 Hold Space or Click to Talk", command=self._on_mic_click)
        self.mic_btn.pack(side="left", padx=(0, 8))

        briefing_btn = ttk.Button(input_frame, text="📋 Daily Briefing", command=self._on_briefing_click)
        briefing_btn.pack(side="left")

        self.status_var = tk.StringVar(value="Ready.")
        status_bar = ttk.Label(chat_tab, textvariable=self.status_var, anchor="w")
        status_bar.pack(fill="x", padx=10, pady=(0, 6))

        self.root.bind("<space>", self._on_space_pushtotalk)

        # --- Settings tab ---
        row = 0
        ttk.Label(settings_tab, text="Assistant name:").grid(row=row, column=0, sticky="w", padx=10, pady=8)
        self.name_var = tk.StringVar(value=CONFIG.assistant_name)
        ttk.Entry(settings_tab, textvariable=self.name_var).grid(row=row, column=1, padx=10, pady=8)
        row += 1

        ttk.Label(settings_tab, text="Language:").grid(row=row, column=0, sticky="w", padx=10, pady=8)
        self.lang_var = tk.StringVar(value=CONFIG.default_language)
        ttk.Combobox(settings_tab, textvariable=self.lang_var,
                     values=["auto", "en", "hi"], state="readonly").grid(row=row, column=1, padx=10, pady=8)
        row += 1

        apply_btn = ttk.Button(settings_tab, text="Apply", command=self._apply_settings)
        apply_btn.grid(row=row, column=0, columnspan=2, pady=16)
        row += 1

        ttk.Separator(settings_tab, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        wake_status = "off (push-to-talk only)"
        if CONFIG.wake_word_enabled:
            wake_status = f"on — model: {CONFIG.wake_word_model_path or 'hey_jarvis (pretrained stand-in)'}"
        ttk.Label(settings_tab, text="Wake word mode:").grid(row=row, column=0, sticky="w", padx=10, pady=4)
        ttk.Label(settings_tab, text=wake_status).grid(row=row, column=1, sticky="w", padx=10, pady=4)
        row += 1
        ttk.Label(settings_tab, text="Change wake word settings in .env (WAKE_WORD_ENABLED,\nWAKE_WORD_MODEL_PATH) and restart the app to apply.",
                  foreground="#666").grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 8))

    def _preload_stt(self):
        self.status_var.set("Loading speech recognition model (first run only)...")
        self.stt_engine = SpeechToText()
        self.status_var.set("Ready.")

    def _apply_settings(self):
        CONFIG.assistant_name = self.name_var.get() or "Assistant"
        CONFIG.default_language = self.lang_var.get()
        messagebox.showinfo("Settings", "Settings applied for this session.")

    def _load_history_into_view(self):
        for role, content in self.memory.recent_history(limit=30):
            self._append_transcript(role, content)

    def _append_transcript(self, role: str, content: str):
        self.transcript.configure(state="normal")
        speaker = CONFIG.assistant_name if role == "assistant" else "You"
        self.transcript.insert("end", f"{speaker}: {content}\n\n")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    # ---------- interaction handlers ----------
    def _on_type_submit(self):
        text = self.text_entry.get().strip()
        if not text or self.busy:
            return
        self.text_entry.delete(0, "end")
        self._append_transcript("user", text)
        threading.Thread(target=self._handle_turn, args=(text, "en"), daemon=True).start()

    def _on_mic_click(self):
        if self.busy or self.stt_engine is None:
            return
        threading.Thread(target=self._listen_and_handle, daemon=True).start()

    def _on_space_pushtotalk(self, event):
        self._on_mic_click()

    def _on_briefing_click(self):
        threading.Thread(target=self.scheduler.trigger_daily_briefing_now, daemon=True).start()

    def _listen_and_handle(self):
        self.busy = True
        if self.wake_listener:
            self.wake_listener.pause()
        try:
            self.status_var.set("Listening...")
            audio = self.stt_engine.record_until_silence()
            self.status_var.set("Thinking...")
            text, lang = self.stt_engine.transcribe(audio)
            if not text:
                self.status_var.set("Didn't catch that — try again.")
                self.busy = False
                return
            self._append_transcript("user", text)
            self._handle_turn(text, lang)
        finally:
            if self.wake_listener:
                self.wake_listener.resume()

    def _handle_turn(self, text: str, lang: str):
        self.busy = True
        self.status_var.set("Thinking...")
        try:
            reply = self.agent.respond(text)
        except Exception as e:
            log_error(f"Agent turn failed: {e}")
            reply = "Sorry, something went wrong on my end. I've logged the error — please try again."
        self._append_transcript("assistant", reply)
        self.status_var.set("Speaking...")
        speak_lang = "hi" if lang == "hi" else "en"
        self.tts.speak(reply, lang=speak_lang)
        self.status_var.set("Ready.")
        self.busy = False


def launch():
    root = tk.Tk()
    AssistantGUI(root)
    root.mainloop()
