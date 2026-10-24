"""
Project ORION - J.A.R.V.I.S.-style British Butler Text-to-Speech (TTS) Voice Engine
Features edge-tts neural voice synthesis, offline pyttsx3 fallback,
non-blocking playback with barge-in interruption via pygame.mixer.
"""

import asyncio
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from config import config

# Initialize Pygame mixer safely
_pygame_available = False
try:
    import pygame
    if not pygame.mixer.get_init():
        pygame.mixer.init(frequency=24000, size=-16, channels=2, buffer=512)
    _pygame_available = True
except Exception:
    _pygame_available = False


def clean_for_speech(text: str) -> str:
    """
    Sanitizes LLM outputs for high-fidelity speech synthesis:
    - Removes code blocks and inline backticks
    - Strips markdown formatting (*, _, #, >, ~)
    - Expands symbols and path slashes to natural English words
    - Normalizes honorifics and whitespace
    """
    if not text:
        return ""

    # 1. Remove code blocks
    text = re.sub(r"```[\s\S]*?```", " [code block omitted] ", text)

    # 2. Remove markdown links: [label](url) -> label
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

    # 3. Clean inline backticks: `variable` -> variable
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # 4. Remove bold/italics/strikethrough/headers
    text = re.sub(r"[*_~#]+", " ", text)

    # 5. Clean file paths for verbal clarity: e.g. "buggy_calc.py" -> "buggy calc dot py"
    text = re.sub(r"([a-zA-Z0-9_\-]+)\.([a-zA-Z0-9]+)", r"\1 dot \2", text)
    text = text.replace("_", " ")
    text = text.replace("\\", " slash ").replace("/", " slash ")

    # 6. Expand common technical abbreviations and operators
    text = text.replace("!=", " is not equal to ")
    text = text.replace("==", " equals ")
    text = text.replace("<=", " is less than or equal to ")
    text = text.replace(">=", " is greater than or equal to ")
    text = text.replace("->", " returns ")
    text = text.replace("&", " and ")

    # 7. Collapse extra whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


class JarvisVoiceEngine:
    """
    Thread-safe British Butler Voice Engine for Project ORION.
    Uses edge-tts (neural en-GB-RyanNeural) by default with instant barge-in support.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._is_speaking = False
        self._stop_event = threading.Event()
        self._current_thread: Optional[threading.Thread] = None
        self._temp_dir = Path(tempfile.gettempdir()) / "orion_tts"
        self._temp_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def stop(self) -> None:
        """
        Immediately stops any active speech playback (Barge-In).
        Triggered when user presses push-to-talk or cancels.
        """
        self._stop_event.set()
        if _pygame_available:
            try:
                import pygame
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
            except Exception:
                pass
        self._is_speaking = False

    async def _synthesize_edge_tts(self, text: str, output_path: Path) -> bool:
        """Synthesizes high-definition neural speech using Microsoft edge-tts."""
        try:
            import edge_tts

            communicator = edge_tts.Communicate(
                text=text,
                voice=config.ORION_TTS_VOICE,
                rate=config.ORION_TTS_RATE,
                pitch=config.ORION_TTS_PITCH,
            )
            await communicator.save(str(output_path))
            return output_path.exists() and output_path.stat().st_size > 0
        except Exception:
            return False

    def _synthesize_offline_pyttsx3(self, text: str, output_path: Path) -> bool:
        """Offline fallback using pyttsx3."""
        try:
            import pyttsx3

            engine = pyttsx3.init()
            # Try finding a British or pleasant voice if present
            voices = engine.getProperty("voices")
            for v in voices:
                if "george" in v.name.lower() or "hazel" in v.name.lower() or "uk" in v.id.lower():
                    engine.setProperty("voice", v.id)
                    break
            engine.save_to_file(text, str(output_path))
            engine.runAndWait()
            return output_path.exists() and output_path.stat().st_size > 0
        except Exception:
            return False

    def _play_audio_file(
        self,
        audio_file: Path,
        on_start: Optional[Callable[[], None]] = None,
        on_finish: Optional[Callable[[], None]] = None,
    ) -> None:
        """Plays audio file on background thread with barge-in polling."""
        try:
            self._is_speaking = True
            if on_start and not self._stop_event.is_set():
                on_start()

            if _pygame_available:
                import pygame
                pygame.mixer.music.load(str(audio_file))
                pygame.mixer.music.play()

                while pygame.mixer.music.get_busy():
                    if self._stop_event.is_set():
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.05)
            else:
                # Windows winsound fallback for WAV or fallback message
                if audio_file.suffix.lower() == ".wav":
                    try:
                        import winsound
                        winsound.PlaySound(str(audio_file), winsound.SND_FILENAME)
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            self._is_speaking = False
            if on_finish:
                on_finish()
            try:
                if audio_file.exists():
                    audio_file.unlink()
            except Exception:
                pass

    def speak(
        self,
        text: str,
        on_start: Optional[Callable[[], None]] = None,
        on_finish: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Public non-blocking method to speak text in J.A.R.V.I.S. voice.
        Safely interrupts any ongoing speech first.
        """
        if not config.ORION_VOICE_ENABLED:
            if on_finish:
                on_finish()
            return

        cleaned_text = clean_for_speech(text)
        if not cleaned_text:
            if on_finish:
                on_finish()
            return

        # Interrupt ongoing speech
        self.stop()
        self._stop_event.clear()

        def _worker():
            with self._lock:
                timestamp = int(time.time() * 1000)
                audio_file = self._temp_dir / f"jarvis_{timestamp}.mp3"
                offline_wav = self._temp_dir / f"jarvis_{timestamp}.wav"

                # 1. Attempt edge-tts neural voice
                success = False
                try:
                    success = asyncio.run(self._synthesize_edge_tts(cleaned_text, audio_file))
                except Exception:
                    success = False

                # 2. Fall back to pyttsx3 if edge-tts failed or offline
                if not success:
                    success = self._synthesize_offline_pyttsx3(cleaned_text, offline_wav)
                    if success:
                        audio_file = offline_wav

                if not success or not audio_file.exists():
                    if on_finish:
                        on_finish()
                    return

                # 3. Play generated speech
                self._play_audio_file(audio_file, on_start, on_finish)

        self._current_thread = threading.Thread(target=_worker, daemon=True)
        self._current_thread.start()


# Global Singleton Voice Engine
_global_voice_engine: Optional[JarvisVoiceEngine] = None


def get_voice_engine() -> JarvisVoiceEngine:
    global _global_voice_engine
    if _global_voice_engine is None:
        _global_voice_engine = JarvisVoiceEngine()
    return _global_voice_engine
