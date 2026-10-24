"""
Project ORION - Wispr Flow-Style OS-Wide Ambient Overlay (PyQt6)
Frameless, translucent, always-on-top desktop pill HUD anchored at bottom-center.
Features visual waveform animations, quick silent text input, ACI tool diff cards,
Flake8 verification badges, and J.A.R.V.I.S. voice feedback.
"""

import math
import sys
from pathlib import Path
from typing import Optional

import httpx
from PyQt6.QtCore import (
    QPoint,
    QRect,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config import config
from trigger.audio_recorder import AudioRecorder, transcribe_audio
from trigger.context_capture import capture_os_context
from voice.jarvis_tts import get_voice_engine


class TranscriptionWorker(QThread):
    """Background worker transcribing audio file so UI thread never freezes."""
    transcription_ready = pyqtSignal(str)

    def __init__(self, wav_path: Path):
        super().__init__()
        self.wav_path = wav_path

    def run(self):
        text = transcribe_audio(self.wav_path)
        self.transcription_ready.emit(text)


class WorkerActThread(QThread):
    """Background worker querying FastAPI /api/v1/act to keep PyQt UI responsive."""
    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, query: str):
        super().__init__()
        self.query = query

    def run(self):
        try:
            # 1. Capture OS visual & workspace context
            context = capture_os_context(include_screenshot=True)

            # 2. Package request
            payload = {
                "user_query": self.query,
                "active_window": context.get("active_window", "Desktop"),
                "clipboard_text": context.get("clipboard_text", ""),
                "screenshot_b64": context.get("screenshot_b64"),
                "workspace_context": context.get("workspace_context", {}),
                "history": [],
            }

            # 3. Call local FastAPI server
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(f"{config.backend_url}/api/v1/act", json=payload)
                if resp.status_code == 200:
                    self.result_ready.emit(resp.json())
                else:
                    self.error_occurred.emit(f"Server error ({resp.status_code}): {resp.text}")
        except Exception as e:
            self.error_occurred.emit(f"Request failed: {str(e)}")


class WaveformWidget(QWidget):
    """Pulsing animated waveform indicator for Listening / Speaking states."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 24)
        self._phase = 0
        self._color = QColor("#38BDF8")  # Cyan default
        self._is_active = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start_animation(self, color_hex: str = "#38BDF8"):
        self._color = QColor(color_hex)
        self._is_active = True
        if not self._timer.isActive():
            self._timer.start(40)

    def stop_animation(self):
        self._is_active = False
        if self._timer.isActive():
            self._timer.stop()
        self.update()

    def _tick(self):
        self._phase = (self._phase + 1) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._is_active:
            # Idle static 3 dots
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#64748B"))
            for i in range(3):
                painter.drawEllipse(12 + i * 10, 10, 4, 4)
            return

        # Animated waveform bars
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)

        num_bars = 4
        bar_w = 4
        spacing = 4
        start_x = 8

        for i in range(num_bars):
            factor = math.sin(math.radians(self._phase * 3 + i * 60))
            h = int(6 + abs(factor) * 14)
            y = (24 - h) // 2
            x = start_x + i * (bar_w + spacing)
            painter.drawRoundedRect(x, y, bar_w, h, 2, 2)


class OrionWisprHUD(QWidget):
    """
    Wispr Flow-style floating desktop pill overlay.
    Collapsed: 480x56 px (sleek minimal floating pill)
    Expanded:  500x230 px (action thought, tool diff, and linter badge)
    """
    # Thread-safe signals to marshal calls from pynput OS thread into Qt GUI thread
    hotkey_down_signal = pyqtSignal()
    hotkey_up_signal = pyqtSignal()
    trigger_voice_start = pyqtSignal()
    trigger_voice_stop = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.audio_recorder = AudioRecorder()
        self.voice_engine = get_voice_engine()
        self.act_thread: Optional[WorkerActThread] = None
        self.transcribe_thread: Optional[TranscriptionWorker] = None
        self.is_recording = False
        self.is_expanded = False

        self._init_window_flags()
        self._build_ui()
        self._reposition_bottom_center()

        # Connect thread-safe signals using QueuedConnection
        self.hotkey_down_signal.connect(self._handle_hotkey_down, Qt.ConnectionType.QueuedConnection)
        self.hotkey_up_signal.connect(self._handle_hotkey_up, Qt.ConnectionType.QueuedConnection)
        self.trigger_voice_start.connect(self._on_voice_start, Qt.ConnectionType.QueuedConnection)
        self.trigger_voice_stop.connect(self._on_voice_stop, Qt.ConnectionType.QueuedConnection)

    def _init_window_flags(self):
        """Configure non-intrusive floating overlay window properties."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _build_ui(self):
        """Constructs modern dark-mode glassmorphic HUD pill layout."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(0)

        # Container Frame
        self.pill_frame = QFrame(self)
        self.pill_frame.setObjectName("pillFrame")
        self.pill_frame.setStyleSheet("""
            QFrame#pillFrame {
                background-color: rgba(15, 23, 42, 0.94);
                border: 1px solid rgba(56, 189, 248, 0.35);
                border-radius: 26px;
            }
        """)

        # Drop Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 6)
        self.pill_frame.setGraphicsEffect(shadow)

        self.pill_layout = QVBoxLayout(self.pill_frame)
        self.pill_layout.setContentsMargins(14, 8, 14, 8)
        self.pill_layout.setSpacing(8)

        # 1. TOP BAR (Always Visible Pill Header)
        self.top_bar = QHBoxLayout()
        self.top_bar.setContentsMargins(0, 0, 0, 0)
        self.top_bar.setSpacing(10)

        # Animated Waveform / Status Orb
        self.waveform = WaveformWidget(self)
        self.top_bar.addWidget(self.waveform)

        # Status Label
        self.status_label = QLabel("ORION Ready • Hold [Alt+Space] or Click Mic", self)
        self.status_label.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 500;")
        self.top_bar.addWidget(self.status_label, 1)

        # Push-to-Talk Mic Button
        self.mic_btn = QPushButton("🎙️", self)
        self.mic_btn.setFixedSize(32, 32)
        self.mic_btn.setToolTip("Click to toggle Push-to-Talk")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(30, 41, 59, 0.8);
                color: #38BDF8;
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(56, 189, 248, 0.2);
            }
        """)
        self.mic_btn.clicked.connect(self._toggle_mic_click)
        self.top_bar.addWidget(self.mic_btn)

        # Silent Text Input Toggle Button
        self.text_toggle_btn = QPushButton("⌨️", self)
        self.text_toggle_btn.setFixedSize(32, 32)
        self.text_toggle_btn.setToolTip("Type command silently")
        self.text_toggle_btn.setStyleSheet("""
            QPushButton {
                background: rgba(30, 41, 59, 0.8);
                color: #94A3B8;
                border: 1px solid rgba(148, 163, 184, 0.2);
                border-radius: 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(148, 163, 184, 0.2);
                color: #F8FAFC;
            }
        """)
        self.text_toggle_btn.clicked.connect(self._toggle_text_input)
        self.top_bar.addWidget(self.text_toggle_btn)

        # Mute / Barge-in Stop Button
        self.mute_btn = QPushButton("⏹", self)
        self.mute_btn.setFixedSize(32, 32)
        self.mute_btn.setToolTip("Stop speech / Barge-in")
        self.mute_btn.setStyleSheet("""
            QPushButton {
                background: rgba(30, 41, 59, 0.8);
                color: #F43F5E;
                border: 1px solid rgba(244, 63, 94, 0.3);
                border-radius: 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(244, 63, 94, 0.25);
            }
        """)
        self.mute_btn.clicked.connect(self._on_stop_speech_clicked)
        self.top_bar.addWidget(self.mute_btn)

        self.pill_layout.addLayout(self.top_bar)

        # 2. SILENT TEXT INPUT BAR (Toggleable)
        self.text_input = QLineEdit(self)
        self.text_input.setPlaceholderText("Type command (e.g. 'Fix error in buggy_calc.py') & press Enter...")
        self.text_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(15, 23, 42, 0.8);
                border: 1px solid rgba(56, 189, 248, 0.4);
                border-radius: 12px;
                color: #F8FAFC;
                padding: 6px 12px;
                font-size: 12px;
            }
        """)
        self.text_input.returnPressed.connect(self._on_text_submitted)
        self.text_input.hide()
        self.pill_layout.addWidget(self.text_input)

        # 3. EXPANDABLE ACTION & VERIFICATION CARD
        self.detail_card = QFrame(self)
        self.detail_card.setObjectName("detailCard")
        self.detail_card.setStyleSheet("""
            QFrame#detailCard {
                background-color: rgba(30, 41, 59, 0.7);
                border: 1px solid rgba(148, 163, 184, 0.15);
                border-radius: 14px;
                padding: 6px;
            }
        """)
        self.detail_layout = QVBoxLayout(self.detail_card)
        self.detail_layout.setContentsMargins(10, 8, 10, 8)
        self.detail_layout.setSpacing(6)

        # Action Header (Tool Badge + Flake8 Status)
        self.badge_row = QHBoxLayout()
        self.action_badge = QLabel("ACI: edit_lines", self)
        self.action_badge.setStyleSheet("""
            background-color: #0284C7;
            color: #FFFFFF;
            font-size: 11px;
            font-weight: bold;
            padding: 3px 8px;
            border-radius: 6px;
        """)
        self.badge_row.addWidget(self.action_badge)

        self.verify_badge = QLabel("✓ Flake8 Verified", self)
        self.verify_badge.setStyleSheet("""
            background-color: #059669;
            color: #FFFFFF;
            font-size: 11px;
            font-weight: bold;
            padding: 3px 8px;
            border-radius: 6px;
        """)
        self.badge_row.addWidget(self.verify_badge)
        self.badge_row.addStretch()

        self.dismiss_btn = QPushButton("✕", self)
        self.dismiss_btn.setFixedSize(22, 22)
        self.dismiss_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94A3B8;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover { color: #F8FAFC; }
        """)
        self.dismiss_btn.clicked.connect(self._collapse_card)
        self.badge_row.addWidget(self.dismiss_btn)

        self.detail_layout.addLayout(self.badge_row)

        # Thought Text
        self.thought_label = QLabel(self)
        self.thought_label.setWordWrap(True)
        self.thought_label.setStyleSheet("color: #CBD5E1; font-size: 12px; font-style: italic;")
        self.detail_layout.addWidget(self.thought_label)

        # Diff / Result Scroll Area
        self.diff_label = QLabel(self)
        self.diff_label.setWordWrap(True)
        self.diff_label.setStyleSheet("""
            color: #38BDF8;
            font-family: Consolas, monospace;
            font-size: 11px;
            background: rgba(15, 23, 42, 0.6);
            border-radius: 6px;
            padding: 6px;
        """)
        self.detail_layout.addWidget(self.diff_label)

        # Spoken Response Subtitle
        self.spoken_subtitle = QLabel(self)
        self.spoken_subtitle.setWordWrap(True)
        self.spoken_subtitle.setStyleSheet("color: #FCD34D; font-size: 12px; font-weight: 500;")
        self.detail_layout.addWidget(self.spoken_subtitle)

        self.detail_card.hide()
        self.pill_layout.addWidget(self.detail_card)

        self.main_layout.addWidget(self.pill_frame)
        self.resize(500, 76)

    def _reposition_bottom_center(self):
        """Anchors HUD at bottom center of the active screen."""
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        w = max(480, self.width())
        h = max(60, self.height())
        x = geo.x() + (geo.width() - w) // 2
        y = geo.y() + geo.height() - h - 30
        self.setGeometry(x, y, w, h)

    def _toggle_text_input(self):
        """Toggles the silent text input bar."""
        if self.text_input.isVisible():
            self.text_input.hide()
            self.adjustSize()
            self._reposition_bottom_center()
        else:
            self.text_input.show()
            self.text_input.setFocus()
            self.adjustSize()
            self._reposition_bottom_center()

    def _toggle_mic_click(self):
        """Simulates hold/release from UI button click."""
        if not self.is_recording:
            self.on_hotkey_down()
        else:
            self.on_hotkey_up()

    # Public callback invoked by pynput background thread
    def on_hotkey_down(self):
        """Dispatches press signal to Qt main thread."""
        self.hotkey_down_signal.emit()

    # Public callback invoked by pynput background thread
    def on_hotkey_up(self):
        """Dispatches release signal to Qt main thread."""
        self.hotkey_up_signal.emit()

    def _handle_hotkey_down(self):
        """Runs safely on Qt GUI main thread."""
        # Barge-in: interrupt speech immediately
        self.voice_engine.stop()

        self.is_recording = True
        started = self.audio_recorder.start()
        self.waveform.start_animation("#38BDF8")  # Cyan pulsing
        if started:
            self.status_label.setText("Listening... [Release Alt+Space to send]")
        else:
            self.status_label.setText("Recording started... [Release to send]")
        self.status_label.setStyleSheet("color: #38BDF8; font-weight: bold;")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: #0284C7;
                color: #FFFFFF;
                border: 1px solid #38BDF8;
                border-radius: 16px;
            }
        """)

    def _handle_hotkey_up(self):
        """Runs safely on Qt GUI main thread."""
        if not self.is_recording:
            return
        self.is_recording = False
        self.waveform.start_animation("#F59E0B")  # Amber pulsing
        self.status_label.setText("Transcribing speech...")
        self.status_label.setStyleSheet("color: #FCD34D;")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(30, 41, 59, 0.8);
                color: #38BDF8;
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 16px;
            }
        """)

        wav_path = self.audio_recorder.stop()
        if not wav_path:
            self.waveform.stop_animation()
            self.status_label.setText("Audio was too short. Hold [Alt+Space] while speaking.")
            self.status_label.setStyleSheet("color: #94A3B8;")
            return

        # Run transcription on background thread to keep GUI responsive
        self.transcribe_thread = TranscriptionWorker(wav_path)
        self.transcribe_thread.transcription_ready.connect(self._on_transcription_ready)
        self.transcribe_thread.start()

    def _on_transcription_ready(self, transcription: str):
        """Called on main GUI thread when transcription finishes."""
        if not transcription:
            self.waveform.stop_animation()
            self.status_label.setText("No speech recognized. Speak clearly or type below:")
            self.status_label.setStyleSheet("color: #FCD34D;")
            self.text_input.show()
            self.text_input.setFocus()
            self.adjustSize()
            self._reposition_bottom_center()
            return

        self.status_label.setText(f'Heard: "{transcription}"')
        self._dispatch_agent_query(transcription)

    def _on_text_submitted(self):
        """User pressed enter in silent text bar."""
        query = self.text_input.text().strip()
        if not query:
            return
        self.text_input.clear()
        self.text_input.hide()
        self._dispatch_agent_query(query)

    def _dispatch_agent_query(self, query: str):
        """Launches background agent execution worker thread."""
        self.waveform.start_animation("#F59E0B")  # Amber reasoning
        self.status_label.setText("Nemotron-VL Reasoning & ACI Execution...")
        self.status_label.setStyleSheet("color: #F59E0B;")

        self.act_thread = WorkerActThread(query)
        self.act_thread.result_ready.connect(self._handle_act_response)
        self.act_thread.error_occurred.connect(self._handle_act_error)
        self.act_thread.start()

    def _handle_act_response(self, response: dict):
        """Receives execution result from backend and updates HUD overlay."""
        self.waveform.stop_animation()

        thought = response.get("thought", "")
        action = response.get("action", "answer_only")
        summary = response.get("summary_for_user", "Done.")
        tool_result = response.get("tool_result", {})
        verification = response.get("verification")
        spoken_response = response.get("spoken_response", "")

        # Update top status
        self.status_label.setText(summary)
        self.status_label.setStyleSheet("color: #38BDF8; font-weight: 500;")

        # Populate expanded card
        self.action_badge.setText(f"ACI: {action}")
        self.thought_label.setText(f'Thought: "{thought}"')

        # Verification badge
        if verification and verification.get("status") == "success":
            retries = verification.get("retries_used", 0)
            if retries > 0:
                self.verify_badge.setText(f"✓ Flake8 Verified (Self-Corrected x{retries})")
                self.verify_badge.setStyleSheet("background-color: #D97706; color: #FFF; font-weight: bold; padding: 3px 8px; border-radius: 6px;")
            else:
                self.verify_badge.setText("✓ Flake8 Verified")
                self.verify_badge.setStyleSheet("background-color: #059669; color: #FFF; font-weight: bold; padding: 3px 8px; border-radius: 6px;")
            self.verify_badge.show()
        elif verification and verification.get("status") == "syntax_error":
            self.verify_badge.setText("⚠ Flake8 Error (Reverted)")
            self.verify_badge.setStyleSheet("background-color: #DC2626; color: #FFF; font-weight: bold; padding: 3px 8px; border-radius: 6px;")
            self.verify_badge.show()
        else:
            self.verify_badge.hide()

        # Tool result preview
        diff_text = tool_result.get("diff_preview") or tool_result.get("message") or ""
        self.diff_label.setText(diff_text[:300])

        # Spoken response subtitle
        if spoken_response:
            self.spoken_subtitle.setText(f'J.A.R.V.I.S.: "{spoken_response}"')
            self.spoken_subtitle.show()
        else:
            self.spoken_subtitle.hide()

        # Expand card
        self.detail_card.show()
        self.is_expanded = True
        self.adjustSize()
        self._reposition_bottom_center()

        # Speak via J.A.R.V.I.S. voice engine
        if spoken_response and config.ORION_VOICE_ENABLED:
            self.voice_engine.speak(
                spoken_response,
                on_start=lambda: self.trigger_voice_start.emit(),
                on_finish=lambda: self.trigger_voice_stop.emit(),
            )

    def _handle_act_error(self, err_msg: str):
        """Displays error in status bar."""
        self.waveform.stop_animation()
        self.status_label.setText(f"Error: {err_msg[:60]}")
        self.status_label.setStyleSheet("color: #F43F5E;")

    def _collapse_card(self):
        """Collapses expanded detail card back to minimal pill."""
        self.detail_card.hide()
        self.is_expanded = False
        self.adjustSize()
        self._reposition_bottom_center()

    def _on_stop_speech_clicked(self):
        """Mute / Barge-in button clicked."""
        self.voice_engine.stop()
        self.waveform.stop_animation()

    def _on_voice_start(self):
        """Triggered when J.A.R.V.I.S. begins speaking."""
        self.waveform.start_animation("#FCD34D")  # Golden waveform for Butler voice

    def _on_voice_stop(self):
        """Triggered when J.A.R.V.I.S. finishes speaking."""
        self.waveform.stop_animation()
