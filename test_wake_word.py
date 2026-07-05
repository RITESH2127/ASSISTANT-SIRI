"""
Standalone tester for a trained (or the default) wake word model.
Run this BEFORE turning on WAKE_WORD_ENABLED in the full app, so you can
see live detection scores and pick a good WAKE_WORD_THRESHOLD.

Usage:
    python wake_word_training/test_wake_word.py

Speak your wake phrase a few times and watch the printed score. It should
jump close to 1.0 when you say the phrase clearly, and stay near 0 during
normal conversation/silence. If it's noisy or rarely triggers, adjust
WAKE_WORD_THRESHOLD in .env accordingly (see the README in this folder).

Press Ctrl+C to stop.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import sounddevice as sd
from openwakeword.model import Model

from assistant.config import CONFIG

SAMPLE_RATE = 16000
CHUNK = 1280


def main():
    custom_path = CONFIG.wake_word_model_path
    if custom_path and os.path.exists(custom_path):
        model = Model(wakeword_models=[custom_path], inference_framework="onnx")
        name = os.path.splitext(os.path.basename(custom_path))[0]
        print(f"Testing your CUSTOM model: {custom_path}")
    else:
        model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
        name = "hey_jarvis"
        print("No custom model found at WAKE_WORD_MODEL_PATH — testing the "
              "pretrained 'hey_jarvis' stand-in instead.")

    print(f"Listening for '{name}'... speak naturally. Ctrl+C to stop.\n")
    print(f"{'Score':>8}   {'Bar'}")

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=CHUNK) as stream:
            while True:
                audio, _ = stream.read(CHUNK)
                audio = audio.flatten()
                scores = model.predict(audio)
                score = scores.get(name, 0.0)
                bar = "#" * int(score * 40)
                marker = "  <-- DETECTED" if score > CONFIG.wake_word_threshold else ""
                print(f"{score:8.3f}   {bar}{marker}", end="\r" if not marker else "\n")
                if score > CONFIG.wake_word_threshold:
                    model.reset()
                    time.sleep(0.8)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
