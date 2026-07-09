"""
Entry point for the Personal AI Assistant desktop app.

Run with:  python main.py
Or, after building with PyInstaller, just double-click the .exe.
"""
import sys
import tkinter as tk

from assistant.gui import AssistantGUI
from assistant.tray import run_tray


def main():
    root = tk.Tk()
    app = AssistantGUI(root)

    def show_window():
        root.deiconify()
        root.lift()

    def quit_app():
        try:
            app.scheduler.stop()
        except Exception:
            pass
        try:
            if app.wake_listener:
                app.wake_listener.stop()
        except Exception:
            pass
        root.destroy()
        sys.exit(0)

    # Minimize to tray instead of closing when the window's X is clicked
    def on_close():
        root.withdraw()

    root.protocol("WM_DELETE_WINDOW", on_close)
    run_tray(show_window, quit_app)

    root.mainloop()


if __name__ == "__main__":
    main()
