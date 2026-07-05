"""
Speech-to-text using faster-whisper, running fully locally (no audio ever
leaves the laptop). Whisper's multilingual model handles Hindi, English, and
Hinglish reasonably well out of the box.
"""
import queue
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from .config import CONFIG

SAMPLE_RATE = 16000


class SpeechToText:
    def __init__(self, model_size: str = "small"):
        # "small" is a good accuracy/speed balance on a laptop CPU.
        # Use "base" for faster/lower-accuracy, "medium" for slower/higher-accuracy.
        compute_type = "int8"  # fast on CPU; use "float16" if you have a CUDA GPU
        device = "cpu"
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def record_until_silence(self, max_seconds: int = 12, silence_seconds: float = 1.2) -> np.ndarray:
        """Record from the default mic until the user stops talking."""
        q = queue.Queue()

        def callback(indata, frames, time_info, status):
            q.put(indata.copy())

        frames = []
        silence_chunks = 0
        chunk_seconds = 0.2
        chunks_needed_for_silence = int(silence_seconds / chunk_seconds)
        max_chunks = int(max_seconds / chunk_seconds)

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                             blocksize=int(SAMPLE_RATE * chunk_seconds), callback=callback):
            for _ in range(max_chunks):
                chunk = q.get()
                frames.append(chunk)
                volume = np.abs(chunk).mean()
                if volume < 0.01:
                    silence_chunks += 1
                else:
                    silence_chunks = 0
                if silence_chunks >= chunks_needed_for_silence and len(frames) > 3:
                    break

        audio = np.concatenate(frames, axis=0).flatten()
        return audio

    def transcribe(self, audio: np.ndarray) -> tuple[str, str]:
        """Returns (text, detected_language_code)."""
        lang = None if CONFIG.default_language == "auto" else CONFIG.default_language
        segments, info = self.model.transcribe(audio, language=lang, beam_size=5, vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return text, info.language
