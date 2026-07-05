"""
Direct laptop system control. Non-destructive actions (volume, brightness,
lock) run immediately. Anything that ends your session (shutdown, restart,
sign-out) requires confirmed=True, same pattern as the other tools.
"""
import platform
import subprocess

IS_WINDOWS = platform.system() == "Windows"


def _get_volume_interface():
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def set_volume(level_percent: int) -> str:
    """level_percent: 0-100"""
    if not IS_WINDOWS:
        return "Volume control is currently implemented for Windows only."
    try:
        level_percent = max(0, min(100, int(level_percent)))
        vol = _get_volume_interface()
        vol.SetMasterVolumeLevelScalar(level_percent / 100.0, None)
        return f"Volume set to {level_percent}%."
    except Exception as e:
        return f"Could not change volume: {e}"


def mute_volume(mute: bool = True) -> str:
    if not IS_WINDOWS:
        return "Volume control is currently implemented for Windows only."
    try:
        vol = _get_volume_interface()
        vol.SetMute(1 if mute else 0, None)
        return "Muted." if mute else "Unmuted."
    except Exception as e:
        return f"Could not change mute state: {e}"


def set_brightness(level_percent: int) -> str:
    try:
        import screen_brightness_control as sbc
        level_percent = max(0, min(100, int(level_percent)))
        sbc.set_brightness(level_percent)
        return f"Screen brightness set to {level_percent}%."
    except Exception as e:
        return f"Could not change brightness (some laptops/monitors don't support software brightness control): {e}"


def lock_computer() -> str:
    try:
        if IS_WINDOWS:
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
        elif platform.system() == "Darwin":
            subprocess.run(["pmset", "displaysleepnow"])
        else:
            subprocess.run(["loginctl", "lock-session"])
        return "Locked the screen."
    except Exception as e:
        return f"Could not lock the screen: {e}"


def shutdown_computer(confirmed: bool = False) -> str:
    if not confirmed:
        return "CONFIRMATION_REQUIRED: shut down the computer now? Ask the user to confirm before calling this again with confirmed=True."
    try:
        if IS_WINDOWS:
            subprocess.run(["shutdown", "/s", "/t", "5"])
        else:
            subprocess.run(["shutdown", "-h", "now"])
        return "Shutting down in 5 seconds."
    except Exception as e:
        return f"Could not shut down: {e}"


def restart_computer(confirmed: bool = False) -> str:
    if not confirmed:
        return "CONFIRMATION_REQUIRED: restart the computer now? Ask the user to confirm before calling this again with confirmed=True."
    try:
        if IS_WINDOWS:
            subprocess.run(["shutdown", "/r", "/t", "5"])
        else:
            subprocess.run(["shutdown", "-r", "now"])
        return "Restarting in 5 seconds."
    except Exception as e:
        return f"Could not restart: {e}"
