"""
System tray icon so the assistant can run in the background (minimized to
tray) instead of always showing a window, similar to how Alexa/Cortana-style
apps behave.
"""
import threading
from PIL import Image, ImageDraw
import pystray


def _make_icon_image():
    img = Image.new("RGB", (64, 64), "white")
    draw = ImageDraw.Draw(img)
    draw.ellipse((8, 8, 56, 56), fill="#4A7CFE")
    draw.ellipse((24, 20, 40, 36), fill="white")
    return img


def run_tray(on_show, on_quit):
    icon = pystray.Icon(
        "ai_assistant",
        _make_icon_image(),
        "Personal AI Assistant",
        menu=pystray.Menu(
            pystray.MenuItem("Show", lambda: on_show()),
            pystray.MenuItem("Quit", lambda: (on_quit(), icon.stop())),
        ),
    )
    threading.Thread(target=icon.run, daemon=True).start()
    return icon
