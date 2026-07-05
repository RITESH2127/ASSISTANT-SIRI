# Personal AI Voice Assistant — v1

A private, voice-driven assistant that runs on your own Windows laptop. It understands
Hindi, English, and Hinglish; talks back with natural neural voices; remembers
things about you across sessions; and can open apps, search files, send email,
manage reminders, and browse the web — with confirmation before anything
destructive.

**Read this first, honestly:** this is a real, working v1 you can run today —
not a mockup. It is *not* the same scale of engineering as Siri/Alexa (those are
built by hundred-person teams over years). Treat this as a solid foundation you
can extend. The biggest limitations right now: it needs your own Anthropic API
key (so it needs internet for the "thinking" part, even though speech
recognition runs locally), and the wake-word/system-control features are basic
and Windows-focused.

---

## 1. System Requirements

- Windows 10 or 11, 64-bit
- 8 GB RAM minimum (16 GB recommended — the local speech model needs some headroom)
- ~3 GB free disk space (speech-recognition model + dependencies)
- A working microphone and speakers
- Internet connection (for the Claude API and for the neural TTS voices)
- Python 3.10 or 3.11 installed (see step 2)

## 2. Install Required Software

1. **Install Python**
   - Download from https://www.python.org/downloads/ (3.10 or 3.11)
   - During install, check **"Add Python to PATH"**
   - Verify: open Command Prompt and run `python --version`

2. **Install Git (optional, only if you want version control)**
   - https://git-scm.com/download/win

3. **Get an Anthropic API key**
   - Sign up at https://console.anthropic.com/
   - Create an API key — this is what powers the assistant's "brain" (Claude)
   - Note: API usage is billed by Anthropic based on how much you use it;
     check current pricing at https://docs.claude.com

## 3. Setup Process

1. Copy the whole `ai-assistant` folder onto your laptop, e.g. `C:\ai-assistant`.

2. Open Command Prompt in that folder:
   ```
   cd C:\ai-assistant
   ```

3. Create a virtual environment (keeps dependencies isolated):
   ```
   python -m venv venv
   venv\Scripts\activate
   ```

4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
   This will take a few minutes the first time (it downloads the speech
   recognition libraries).

## 4. API / Model Configuration

1. Copy `.env.example` to `.env`:
   ```
   copy .env.example .env
   ```
2. Open `.env` in Notepad and fill in:
   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
   ```
3. **Optional — email sending:** if you want the assistant to send emails,
   fill in `SMTP_EMAIL` and `SMTP_APP_PASSWORD`. For Gmail:
   - Go to your Google Account → Security → 2-Step Verification → App Passwords
   - Generate an app password specifically for this assistant (don't use your real password)
4. **Optional — wake word:** set `WAKE_WORD_ENABLED=on` if you want
   always-listening mode with the phrase "Hey Jarvis" (a stand-in wake word —
   see `assistant/wake_word.py` for how to train your own later). Leave it
   `off` to use push-to-talk (hold Space bar or click the mic button) — this
   is more private and uses less CPU, so it's the recommended default.

## 5. How to Launch the Assistant

**During development / testing:**
```
venv\Scripts\activate
python main.py
```

**As an installed app (.exe):**
Build it once on your machine (I can't compile a Windows binary from here,
but this step is quick and only needs to be done once):
```
pip install pyinstaller
pyinstaller build.spec
```
This produces `dist\PersonalAssistant\PersonalAssistant.exe`. You can:
- Double-click it to launch, or
- Right-click → "Send to → Desktop (create shortcut)" for a desktop icon, or
- Put a shortcut in `shell:startup` (Win+R → type `shell:startup` → Enter)
  so it launches automatically when Windows starts, minimized to the system tray.

## 6. How to Use Voice Commands

- Click the mic button (or hold **Space**) and speak naturally — no need for
  fixed command phrases. Examples:
  - "Open Notepad and start a new note"
  - "Mujhe kal shaam 6 baje meeting ka reminder set karo" (Hinglish)
  - "Search my documents for the battery project report"
  - "Search the web for the latest AI news"
  - "Email Priya at priya@example.com saying I'll be 10 minutes late"
    → it will ask you to confirm before actually sending
  - "What reminders do I have?"
  - "Remember that I prefer replies in Hindi after 7pm"
- You can also just type into the text box — everything works either way.
- Sensitive actions (closing an app, deleting a file, sending email, running
  a raw system command) always get a spoken/written confirmation step first.
  Just say "yes" / "haan, kar do" to proceed, or "no" to cancel.

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| "ANTHROPIC_API_KEY is missing" popup | Check `.env` has a real key, no quotes, no trailing spaces |
| No sound on replies | Check Windows default playback device; try `pip install --upgrade pygame` |
| Mic not detected | Check Windows Sound settings → Input; make sure another app isn't holding the mic |
| Speech recognition is slow | First run downloads the Whisper model — subsequent runs are fast. On an old laptop, edit `assistant/stt.py` and change `model_size="small"` to `"base"` for more speed (slightly less accuracy) |
| "Could not open [app]" | Add the app's exact `.exe` name to `APP_MAP` in `assistant/tools.py` |
| Email fails to send | Gmail requires an **App Password**, not your normal password; also confirm 2FA is enabled on the account |
| .exe won't build | Make sure you ran `pyinstaller build.spec` from inside the activated venv, in the project folder |
| Antivirus flags the .exe | This is common/expected for unsigned PyInstaller executables; you'll need to allow it locally, or get a code-signing certificate for wider distribution |

---

## Training your own wake word

Out of the box, always-on mode uses openWakeWord's pretrained **"Hey Jarvis"**
model as a placeholder so the feature works immediately. This section trains
a real model on *your* chosen phrase (e.g. "Hey Ritesh") and wires it in
properly — the code already supports this fully, you just need the model file.

**Easiest path — browser-based trainer (no local setup, no GPU needed):**

1. Go to https://openwakeword.com/train
2. Enter your wake phrase — pick something 3-4 syllables long and not a
   common word, e.g. "Hey Ritesh" or "Assistant Online" (this reduces false
   triggers). Avoid single short words.
3. Let it generate the synthetic training dataset and train the model
   (typically a few minutes)
4. Download the resulting `.onnx` file

**Alternative — official Colab notebook (more control, needs a free Google account):**

1. Open the notebook linked from https://github.com/dscripka/openWakeWord
   (see "automatic_model_training.ipynb" under `notebooks/`)
2. Follow the notebook: set your target phrase in the YAML config it
   generates, run all cells (uses a free GPU runtime in Colab; takes roughly
   20-60 minutes since it also pulls background/negative audio from
   HuggingFace to make the model robust against false triggers)
3. Download the trained `.onnx` file at the end

**Wiring it into this app (same for either method above):**

1. Drop your downloaded file into the `wake_word_training/` folder in this
   project (already included), e.g.:
   ```
   ai-assistant/wake_word_training/hey_ritesh.onnx
   ```
2. In `.env`, set:
   ```
   WAKE_WORD_ENABLED=on
   WAKE_WORD_MODEL_PATH=wake_word_training/hey_ritesh.onnx
   ```
3. **Test it standalone first** (recommended) before turning on the full
   app's always-on mode:
   ```
   python wake_word_training/test_wake_word.py
   ```
   This prints a live detection score as you speak, so you can confirm it
   works and pick a good `WAKE_WORD_THRESHOLD` before relying on it.
4. Restart the app. The Settings tab will show "Wake word mode: on — model:
   wake_word_training/hey_ritesh.onnx" confirming your custom model loaded
   instead of the pretrained stand-in.
5. Say your phrase — the assistant starts listening automatically, the same
   as clicking the mic button. Test in a few different rooms/times of day
   and re-train with a stricter phrase if you get false triggers.

**Notes:**
- If `WAKE_WORD_MODEL_PATH` is blank or the file doesn't exist, the app
  automatically falls back to "Hey Jarvis" rather than crashing.
- `WAKE_WORD_THRESHOLD` in `.env` (0-1, default 0.5) trades off sensitivity
  vs. false triggers — raise it if it fires too easily, lower it if it
  misses you.
- While always-on mode is listening, it politely steps aside during an
  active recording (so it isn't fighting your STT for the microphone) and
  resumes right after.

## What's genuinely built (v2)

- Voice loop: mic → local Whisper STT (Hindi/English/Hinglish) → Claude agent
  with real tool-calling → neural TTS
- Persistent SQLite memory: facts/preferences, full chat history, reminders
- **Proactive scheduler**: speaks up unprompted — announces reminders the
  moment they're due, and delivers an automatic daily briefing (today's
  reminders + real Google Calendar events + a usage-pattern suggestion) at
  the time you set in `.env`. There's also a manual "📋 Daily Briefing" button.
- **Real Google Calendar integration** (OAuth, not a stand-in) — list and add
  events on your actual calendar
- **System control**: volume, mute, screen brightness, lock screen, shutdown/
  restart (destructive ones gated behind confirmation, same as file/app actions)
- **Usage-pattern learning**: every tool call is logged with time-of-day, so
  the assistant can say "you often open X around this time" — deliberately
  simple and inspectable rather than an opaque model, so you can always see
  exactly why a suggestion appeared (check `~/.ai_assistant/memory.db`,
  `tool_usage` table)
- **Hardened error handling**: all Claude API calls retry automatically with
  backoff on transient failures; all background scheduler jobs and tool
  calls are wrapped so one failure can't crash the app; everything gets
  logged to `~/.ai_assistant/assistant.log` for troubleshooting
- **Optional PIN lock**: set `APP_PIN` in `.env` to require a PIN before the
  assistant (and your memory/data) is accessible — basic local privacy gate,
  not enterprise-grade auth
- App launching, file search, web search/browsing, email sending,
  confirmation-gated destructive actions, chat history UI, settings panel,
  system tray background mode

## Setting up Google Calendar (optional but recommended)

1. Go to https://console.cloud.google.com/ and create a project
2. In "APIs & Services" → "Library", enable the **Google Calendar API**
3. In "APIs & Services" → "Credentials", create an **OAuth Client ID**,
   application type **Desktop app**
4. Download the JSON and save it as `credentials.json` in the project's root
   folder (same folder as `main.py`)
5. The first time the assistant touches your calendar, a browser window will
   open asking you to log in and grant access once. After that, it's cached
   locally in `~/.ai_assistant/calendar_token.json` — no browser popups after
   the first time.

If you skip this, calendar-related requests will just tell you it's not
configured; nothing else breaks.

## Honest limits, still

This is a strong, genuinely working personal project — not a promise of
zero bugs. Things to know:
- It still needs internet for the "thinking" part (Claude API calls) and for
  the neural TTS voices; only speech-to-text and memory are fully local.
- Windows system control (volume/brightness) depends on `pycaw` and
  `screen-brightness-control`, which don't behave identically across every
  laptop/monitor combination — if brightness control fails on your hardware,
  the assistant reports that clearly instead of pretending it worked.
- The wake word is a stand-in pretrained phrase ("Hey Jarvis"), not a custom
  one trained on your voice/name yet.
- "Self-learning" here is a transparent frequency tracker, not a model that
  retrains itself — I designed it this way on purpose for privacy, speed,
  and auditability, but it's worth knowing what it is and isn't.

---

## Project structure

```
ai-assistant/
├── main.py                # entry point (window + tray)
├── requirements.txt
├── build.spec              # PyInstaller config
├── .env.example            # copy to .env and fill in your key
└── assistant/
    ├── config.py            # loads .env, app-wide settings
    ├── memory.py            # SQLite: conversation log, facts, reminders
    ├── tools.py             # the actual automation functions
    ├── llm.py               # Claude tool-calling agent loop + system prompt
    ├── stt.py               # local speech-to-text (faster-whisper)
    ├── tts.py               # neural text-to-speech (edge-tts + offline fallback)
    ├── wake_word.py          # optional always-listening mode
    ├── gui.py               # Tkinter chat window + settings
    ├── tray.py              # system tray icon / background mode
    ├── system_control.py     # volume, brightness, lock, shutdown/restart
    ├── calendar_integration.py  # real Google Calendar OAuth integration
    ├── learning.py            # transparent usage-pattern tracking/suggestions
    ├── scheduler.py           # proactive daily briefing + reminder alerts
    └── error_handling.py      # logging, retry-with-backoff, safe_call wrapper
```
