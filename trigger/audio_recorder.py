"""
Project ORION - Push-to-Talk Audio Recorder & Multi-Tier Speech-to-Text Engine
Captures 16000Hz mono PCM audio using sounddevice + numpy while hotkey is held.
Transcribes using SpeechRecognition (Google API) and faster-whisper neural models.
"""

import os
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import sounddevice as sd
    _sounddevice_available = True
except Exception:
    _sounddevice_available = False

# Lazy-loaded faster-whisper singleton
_cached_whisper_model = None
_whisper_lock = threading.Lock()


def get_whisper_model():
    """Lazy loader for local faster-whisper model."""
    global _cached_whisper_model
    with _whisper_lock:
        if _cached_whisper_model is None:
            try:
                from faster_whisper import WhisperModel
                # Use tiny.en on CPU with int8 compute for sub-second local STT
                _cached_whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
            except Exception as e:
                print(f"[Warning] Could not initialize faster-whisper model: {e}")
        return _cached_whisper_model


class AudioRecorder:
    """
    Non-blocking push-to-talk audio recorder.
    Buffers 16kHz mono audio frames in memory and flushes to WAV upon release.
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.channels = 1
        self.is_recording = False
        self._frames: list[np.ndarray] = []
        self._stream: Optional[object] = None
        self._lock = threading.Lock()
        self._temp_dir = Path(tempfile.gettempdir()) / "orion_audio"
        self._temp_dir.mkdir(parents=True, exist_ok=True)

    def _audio_callback(self, indata, frames, time_info, status):
        """Internal callback invoked by sounddevice for each audio chunk."""
        if self.is_recording:
            with self._lock:
                self._frames.append(indata.copy())

    def start(self) -> bool:
        """Starts recording audio from the system default input device."""
        if not _sounddevice_available:
            print("[Warning] sounddevice is not available.")
            return False

        with self._lock:
            self._frames.clear()
            self.is_recording = True

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=self._audio_callback,
            )
            self._stream.start()
            return True
        except Exception as e:
            print(f"[Warning] Failed to start microphone recording: {e}")
            self.is_recording = False
            self._stream = None
            return False

    def stop(self) -> Optional[Path]:
        """
        Stops recording and saves accumulated frames to a 16-bit PCM WAV file.
        Returns the path to the saved WAV file or None if no audio recorded.
        """
        if not self.is_recording:
            return None

        self.is_recording = False

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._lock:
            if not self._frames:
                return None
            audio_data = np.concatenate(self._frames, axis=0)
            self._frames.clear()

        # Minimum duration: at least 0.25 seconds of audio
        if len(audio_data) < int(self.sample_rate * 0.25):
            print(f"[Info] Audio snippet too short ({len(audio_data)} samples), ignored.")
            return None

        # Check peak amplitude
        peak = int(np.max(np.abs(audio_data)))
        if peak < 80:
            print(f"[Info] Microphone signal near zero (peak={peak}). Check microphone privacy/mute settings in Windows.")

        wav_path = self._temp_dir / f"capture_{os.getpid()}_{int(time.time()*1000)}.wav"
        try:
            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # 16-bit PCM
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data.tobytes())
            return wav_path
        except Exception as e:
            print(f"[Error] Failed to write audio file: {e}")
            return None


def transcribe_audio(wav_path: str | Path) -> str:
    """
    Multi-tier resilient transcription engine:
    1. SpeechRecognition (Google Web Speech API): instant (~300ms), zero model download.
    2. faster-whisper (tiny.en): local offline neural transcription.
    """
    path = Path(wav_path)
    if not path.exists():
        return ""

    transcript = ""

    # 1. Attempt SpeechRecognition (Google Web Speech - fast & accurate)
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        with sr.AudioFile(str(path)) as source:
            audio_record = recognizer.record(source)
        transcript = recognizer.recognize_google(audio_record)
        if transcript and transcript.strip():
            transcript = transcript.strip()
            print(f"[STT: Google Speech] Transcribed: \"{transcript}\"")
            _cleanup_file(path)
            return transcript
    except Exception as e:
        # Fall back to faster-whisper
        pass

    # 2. Attempt faster-whisper (local offline neural model)
    try:
        model = get_whisper_model()
        if model is not None:
            segments, _ = model.transcribe(str(path), beam_size=1)
            seg_texts = [seg.text for seg in segments]
            transcript = " ".join(seg_texts).strip()
            if transcript:
                print(f"[STT: faster-whisper] Transcribed: \"{transcript}\"")
                _cleanup_file(path)
                return transcript
    except Exception as e:
        print(f"[Warning] faster-whisper transcription error: {e}")

    _cleanup_file(path)
    return transcript


def _cleanup_file(path: Path):
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass
