"""
Always-listening wake word detector using openWakeWord.

Loads a custom-trained model if one is configured (WAKE_WORD_MODEL_PATH),
falling back to openWakeWord's pretrained "hey_jarvis" phrase if none is
found — so the feature works out of the box, and upgrades automatically
the moment you drop in your own trained .onnx model.

See wake_word_training/README.md for how to actually train your own model
(it needs a GPU, so it's done for free on Google Colab, not on this laptop).

If WAKE_WORD_ENABLED=off (the default), the app just uses push-to-talk
(Space bar / mic button) instead — simpler, more private, no extra
background CPU use.
"""
import os
import time
import threading
import numpy as np
import sounddevice as sd
from openwakeword.model import Model

from .config import CONFIG
from .error_handling import log_error

SAMPLE_RATE = 16000
CHUNK = 1280  # openWakeWord expects 80ms chunks at 16kHz


class WakeWordListener:
    def __init__(self, threshold: float = None):
        self.threshold = threshold if threshold is not None else CONFIG.wake_word_threshold
        self.using_custom_model = False
        self.model_name, self.model = self._load_model()

        self._stop_event = threading.Event()
        self._paused_event = threading.Event()  # set = paused (don't trigger)
        self._thread = None

    def _load_model(self):
        custom_path = CONFIG.wake_word_model_path
        if custom_path and os.path.exists(custom_path):
            try:
                model = Model(wakeword_models=[custom_path], inference_framework="onnx")
                name = os.path.splitext(os.path.basename(custom_path))[0]
                self.using_custom_model = True
                log_error(f"Wake word: loaded custom model '{name}' from {custom_path}")
                return name, model
            except Exception as e:
                log_error(f"Wake word: failed to load custom model at {custom_path}: {e}. Falling back to default.")

        # Fallback: openWakeWord's pretrained stand-in phrase
        model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
        return "hey_jarvis", model

    # ---------- public control API (used by the GUI) ----------
    def start_background_listener(self, on_wake):
        """Starts a daemon thread that listens continuously and calls
        on_wake() (no args) every time the phrase is detected. Non-blocking —
        returns immediately."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, args=(on_wake,), daemon=True)
        self._thread.start()

    def pause(self):
        """Temporarily stop triggering (e.g. while the assistant is already
        listening/speaking) without tearing down the mic stream."""
        self._paused_event.set()

    def resume(self):
        self._paused_event.clear()

    def stop(self):
        self._stop_event.set()

    # ---------- internals ----------
    def _run_loop(self, on_wake):
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=CHUNK) as stream:
                while not self._stop_event.is_set():
                    audio, _ = stream.read(CHUNK)
                    audio = audio.flatten()

                    if self._paused_event.is_set():
                        # Still read the mic (keeps the stream healthy) but
                        # skip prediction/triggering while paused.
                        continue

                    try:
                        scores = self.model.predict(audio)
                    except Exception as e:
                        log_error(f"Wake word prediction error: {e}")
                        time.sleep(0.2)
                        continue

                    score = scores.get(self.model_name, 0.0)
                    if score > self.threshold:
                        self.model.reset()  # clear internal buffers to avoid an instant re-trigger
                        try:
                            on_wake()
                        except Exception as e:
                            log_error(f"Wake word on_wake callback failed: {e}")
                        # Brief cooldown so the same utterance can't double-fire
                        time.sleep(1.0)
        except Exception as e:
            log_error(f"Wake word listener thread crashed: {e}")
