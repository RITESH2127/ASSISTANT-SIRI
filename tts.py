"""
Text-to-speech: uses Microsoft Edge's neural voices (edge-tts) for natural,
human-like Hindi and English speech. Falls back to the fully offline
pyttsx3 engine if there's no internet connection.
"""
import asyncio
import tempfile
import os
import edge_tts
import pygame

VOICES = {
    "en": "en-US-AriaNeural",
    "hi": "hi-IN-SwaraNeural",
}


class TextToSpeech:
    def __init__(self):
        pygame.mixer.init()
        self._offline_engine = None

    async def _synthesize(self, text: str, lang: str, out_path: str):
        voice = VOICES.get(lang, VOICES["en"])
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(out_path)

    def speak(self, text: str, lang: str = "en"):
        if not text.strip():
            return
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                out_path = f.name
            asyncio.run(self._synthesize(text, lang, out_path))
            pygame.mixer.music.load(out_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            os.remove(out_path)
        except Exception:
            self._speak_offline(text)

    def _speak_offline(self, text: str):
        import pyttsx3
        if self._offline_engine is None:
            self._offline_engine = pyttsx3.init()
        self._offline_engine.say(text)
        self._offline_engine.runAndWait()
