"""
Project ORION - Wispr Flow-Style Desktop Overlay & WhatsApp Report Viewer (PyQt6)
Frameless, translucent, always-on-top floating pill HUD anchored at bottom-center.
Expands into a rich WhatsApp Intelligence Report Card with J.A.R.V.I.S. voice feedback.
"""

import math
import os
import sys
from pathlib import Path
from typing import Optional

import httpx
import pyperclip
from PyQt6.QtCore import (
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
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from config import config
from trigger.audio_recorder import AudioRecorder, transcribe_audio
from voice.jarvis_tts import get_voice_engine


class TranscriptionWorker(QThread):
    """Background worker transcribing audio so the UI main thread never stutters."""
    transcription_ready = pyqtSignal(str)

    def __init__(self, wav_path: Path):
        super().__init__()
        self.wav_path = wav_path

    def run(self):
        text = transcribe_audio(self.wav_path)
        self.transcription_ready.emit(text)


class WhatsAppReportWorker(QThread):
    """Background worker calling FastAPI /api/v1/whatsapp-report."""
    status_update = pyqtSignal(str, str)  # status_text, color_hex
    report_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, command: str, contact_override: Optional[str] = None):
        super().__init__()
        self.command = command
        self.contact_override = contact_override

    def run(self):
        try:
            self.status_update.emit("Opening WhatsApp & inspecting chat...", "#10B981")

            payload = {
                "user_command": self.command,
                "contact_override": self.contact_override,
            }

            with httpx.Client(timeout=90.0) as client:
                self.status_update.emit("Compiling report via Nemotron-VL...", "#F59E0B")
                resp = client.post(
                    f"{config.backend_url}/api/v1/whatsapp-report",
                    json=payload,
                )

                if resp.status_code == 200:
                    self.report_ready.emit(resp.json())
                else:
                    self.error_occurred.emit(f"Server error ({resp.status_code}): {resp.text}")
        except Exception as e:
            self.error_occurred.emit(f"Report request failed: {str(e)}")


class WaveformWidget(QWidget):
    """Animated pulsing waveform bars for Listening, Inspecting, and Speaking states."""

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
            # Static 3 dots in idle state
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#64748B"))
            for i in range(3):
                painter.drawEllipse(12 + i * 10, 10, 4, 4)
            return

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
    Collapsed: 480x60 px (minimal floating pill)
    Expanded:  540x380 px (rich WhatsApp Intelligence Report Viewer)
    """
    hotkey_down_signal = pyqtSignal()
    hotkey_up_signal = pyqtSignal()
    trigger_voice_start = pyqtSignal()
    trigger_voice_stop = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.audio_recorder = AudioRecorder()
        self.voice_engine = get_voice_engine()
        self.report_worker: Optional[WhatsAppReportWorker] = None
        self.transcribe_thread: Optional[TranscriptionWorker] = None
        self.current_report_file: Optional[str] = None
        self.current_report_text: str = ""
        self.is_recording = False
        self.is_expanded = False

        self._init_window_flags()
        self._build_ui()
        self._reposition_bottom_center(width=480, height=60)

        # Thread-safe signal connections
        self.hotkey_down_signal.connect(self._handle_hotkey_down, Qt.ConnectionType.QueuedConnection)
        self.hotkey_up_signal.connect(self._handle_hotkey_up, Qt.ConnectionType.QueuedConnection)
        self.trigger_voice_start.connect(self._on_voice_start, Qt.ConnectionType.QueuedConnection)
        self.trigger_voice_stop.connect(self._on_voice_stop, Qt.ConnectionType.QueuedConnection)

    def _init_window_flags(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _build_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        self.main_layout.setSpacing(0)

        # Container Frame
        self.pill_frame = QFrame(self)
        self.pill_frame.setObjectName("pillFrame")
        self.pill_frame.setStyleSheet("""
            QFrame#pillFrame {
                background-color: rgba(15, 23, 42, 0.95);
                border: 1px solid rgba(56, 189, 248, 0.4);
                border-radius: 24px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 6)
        self.pill_frame.setGraphicsEffect(shadow)

        self.pill_layout = QVBoxLayout(self.pill_frame)
        self.pill_layout.setContentsMargins(12, 8, 12, 8)
        self.pill_layout.setSpacing(8)

        # ==========================================
        # 1. TOP BAR (Always Visible Minimal Pill)
        # ==========================================
        self.top_bar = QHBoxLayout()
        self.top_bar.setContentsMargins(0, 0, 0, 0)
        self.top_bar.setSpacing(8)

        # Animated Waveform
        self.waveform = WaveformWidget(self)
        self.top_bar.addWidget(self.waveform)

        # Status Label
        self.status_label = QLabel("ORION • Hold [Alt+Space] to Inspect WhatsApp", self)
        self.status_label.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 500;")
        self.top_bar.addWidget(self.status_label, 1)

        # Push-to-Talk Mic Button
        self.mic_btn = QPushButton("🎙️", self)
        self.mic_btn.setFixedSize(32, 32)
        self.mic_btn.setToolTip("Click to toggle Push-to-Talk recording")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(30, 41, 59, 0.85);
                color: #38BDF8;
                border: 1px solid rgba(56, 189, 248, 0.35);
                border-radius: 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(56, 189, 248, 0.25);
            }
        """)
        self.mic_btn.clicked.connect(self._toggle_mic_click)
        self.top_bar.addWidget(self.mic_btn)

        # Silent Text Command Input Toggle
        self.text_toggle_btn = QPushButton("⌨️", self)
        self.text_toggle_btn.setFixedSize(32, 32)
        self.text_toggle_btn.setToolTip("Type WhatsApp command silently")
        self.text_toggle_btn.setStyleSheet("""
            QPushButton {
                background: rgba(30, 41, 59, 0.85);
                color: #94A3B8;
                border: 1px solid rgba(148, 163, 184, 0.25);
                border-radius: 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(148, 163, 184, 0.25);
                color: #F8FAFC;
            }
        """)
        self.text_toggle_btn.clicked.connect(self._toggle_text_input)
        self.top_bar.addWidget(self.text_toggle_btn)

        # Mute / Barge-In Stop Button
        self.mute_btn = QPushButton("🔊", self)
        self.mute_btn.setFixedSize(32, 32)
        self.mute_btn.setToolTip("Stop speech / Mute")
        self.mute_btn.setStyleSheet("""
            QPushButton {
                background: rgba(30, 41, 59, 0.85);
                color: #FCD34D;
                border: 1px solid rgba(252, 211, 77, 0.3);
                border-radius: 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(252, 211, 77, 0.2);
            }
        """)
        self.mute_btn.clicked.connect(self._on_mute_clicked)
        self.top_bar.addWidget(self.mute_btn)

        self.pill_layout.addLayout(self.top_bar)

        # ==========================================
        # 2. SILENT TEXT INPUT BAR (Toggleable)
        # ==========================================
        self.text_input = QLineEdit(self)
        self.text_input.setPlaceholderText("e.g. 'Open WhatsApp and see messages from Derrian' (Press Enter)")
        self.text_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(15, 23, 42, 0.9);
                border: 1px solid rgba(56, 189, 248, 0.5);
                border-radius: 12px;
                color: #F8FAFC;
                padding: 6px 12px;
                font-size: 12px;
            }
        """)
        self.text_input.returnPressed.connect(self._on_text_submitted)
        self.text_input.hide()
        self.pill_layout.addWidget(self.text_input)

        # ==========================================
        # 3. EXPANDABLE WHATSAPP REPORT CARD (540x380)
        # ==========================================
        self.report_card = QFrame(self)
        self.report_card.setObjectName("reportCard")
        self.report_card.setStyleSheet("""
            QFrame#reportCard {
                background-color: rgba(15, 23, 42, 0.9);
                border: 1px solid rgba(56, 189, 248, 0.25);
                border-radius: 16px;
            }
        """)
        self.report_layout = QVBoxLayout(self.report_card)
        self.report_layout.setContentsMargins(12, 10, 12, 10)
        self.report_layout.setSpacing(8)

        # Top Header Row: Badges & Controls
        self.header_row = QHBoxLayout()
        self.report_badge = QLabel("📋 WHATSAPP INTELLIGENCE", self)
        self.report_badge.setStyleSheet("""
            background-color: #0284C7;
            color: #FFFFFF;
            font-size: 11px;
            font-weight: bold;
            padding: 3px 8px;
            border-radius: 6px;
        """)
        self.header_row.addWidget(self.report_badge)

        self.save_badge = QLabel("✓ Saved to ./reports/", self)
        self.save_badge.setStyleSheet("""
            background-color: #059669;
            color: #FFFFFF;
            font-size: 11px;
            font-weight: bold;
            padding: 3px 8px;
            border-radius: 6px;
        """)
        self.header_row.addWidget(self.save_badge)

        self.header_row.addStretch()

        self.collapse_btn = QPushButton("✕", self)
        self.collapse_btn.setFixedSize(22, 22)
        self.collapse_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94A3B8;
                border: none;
                font-size: 13px;
            }
            QPushButton:hover { color: #F8FAFC; }
        """)
        self.collapse_btn.clicked.connect(self._collapse_card)
        self.header_row.addWidget(self.collapse_btn)

        self.report_layout.addLayout(self.header_row)

        # Spoken Response Subtitle (Golden text with Jarvis voice)
        self.spoken_subtitle = QLabel(self)
        self.spoken_subtitle.setWordWrap(True)
        self.spoken_subtitle.setStyleSheet("""
            color: #FCD34D;
            font-size: 13px;
            font-weight: 500;
            background: rgba(30, 41, 59, 0.6);
            border-left: 3px solid #FCD34D;
            padding: 6px 10px;
            border-radius: 4px;
        """)
        self.report_layout.addWidget(self.spoken_subtitle)

        # Markdown Report Viewer (Scrollable)
        self.report_viewer = QTextBrowser(self)
        self.report_viewer.setOpenExternalLinks(True)
        self.report_viewer.setStyleSheet("""
            QTextBrowser {
                background-color: rgba(15, 23, 42, 0.8);
                color: #E2E8F0;
                border: 1px solid rgba(148, 163, 184, 0.2);
                border-radius: 8px;
                padding: 10px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 12px;
                line-height: 1.5;
            }
        """)
        self.report_layout.addWidget(self.report_viewer, 1)

        # Bottom Action Bar
        self.action_bar = QHBoxLayout()
        self.action_bar.setSpacing(8)

        self.open_file_btn = QPushButton("📂 Open Report File", self)
        self.open_file_btn.setStyleSheet("""
            QPushButton {
                background: rgba(30, 41, 59, 0.9);
                color: #38BDF8;
                border: 1px solid rgba(56, 189, 248, 0.4);
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(56, 189, 248, 0.2);
            }
        """)
        self.open_file_btn.clicked.connect(self._open_report_file)
        self.action_bar.addWidget(self.open_file_btn)

        self.copy_btn = QPushButton("📋 Copy Markdown", self)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background: rgba(30, 41, 59, 0.9);
                color: #94A3B8;
                border: 1px solid rgba(148, 163, 184, 0.3);
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(148, 163, 184, 0.2);
                color: #F8FAFC;
            }
        """)
        self.copy_btn.clicked.connect(self._copy_report_markdown)
        self.action_bar.addWidget(self.copy_btn)

        self.action_bar.addStretch()

        self.close_btn = QPushButton("Collapse", self)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748B;
                border: none;
                font-size: 11px;
            }
            QPushButton:hover { color: #CBD5E1; }
        """)
        self.close_btn.clicked.connect(self._collapse_card)
        self.action_bar.addWidget(self.close_btn)

        self.report_layout.addLayout(self.action_bar)

        self.report_card.hide()
        self.pill_layout.addWidget(self.report_card)

        self.main_layout.addWidget(self.pill_frame)
        self.resize(480, 60)

    def _reposition_bottom_center(self, width: int = 480, height: int = 60):
        """Anchors HUD at the bottom-center of the screen."""
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - width) // 2
        y = geo.y() + geo.height() - height - 28
        self.setGeometry(x, y, width, height)

    def _toggle_text_input(self):
        """Toggles the silent text input bar."""
        if self.text_input.isVisible():
            self.text_input.hide()
            self._reposition_bottom_center(width=self.width(), height=60 if not self.is_expanded else 380)
        else:
            self.text_input.show()
            self.text_input.setFocus()
            self._reposition_bottom_center(width=self.width(), height=100 if not self.is_expanded else 380)

    def _toggle_mic_click(self):
        """Simulates hold/release from UI mic button click."""
        if not self.is_recording:
            self.on_hotkey_down()
        else:
            self.on_hotkey_up()

    # Public callback invoked by pynput background thread
    def on_hotkey_down(self):
        self.hotkey_down_signal.emit()

    # Public callback invoked by pynput background thread
    def on_hotkey_up(self):
        self.hotkey_up_signal.emit()

    def _handle_hotkey_down(self):
        """Runs safely on Qt GUI main thread."""
        self.voice_engine.stop()
        self.is_recording = True
        self.audio_recorder.start()
        self.waveform.start_animation("#38BDF8")  # Cyan pulsing
        self.status_label.setText("Listening... [Release Alt+Space to send]")
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
                background: rgba(30, 41, 59, 0.85);
                color: #38BDF8;
                border: 1px solid rgba(56, 189, 248, 0.35);
                border-radius: 16px;
            }
        """)

        wav_path = self.audio_recorder.stop()
        if not wav_path:
            self.waveform.stop_animation()
            self.status_label.setText("Audio was too short. Hold [Alt+Space] while speaking.")
            self.status_label.setStyleSheet("color: #94A3B8;")
            return

        self.transcribe_thread = TranscriptionWorker(wav_path)
        self.transcribe_thread.transcription_ready.connect(self._on_transcription_ready)
        self.transcribe_thread.start()

    def _on_transcription_ready(self, transcription: str):
        """Called on main GUI thread when transcription finishes."""
        if not transcription:
            self.waveform.stop_animation()
            self.status_label.setText("No speech recognized. Type command below:")
            self.status_label.setStyleSheet("color: #FCD34D;")
            self.text_input.show()
            self.text_input.setFocus()
            self._reposition_bottom_center(width=480, height=100)
            return

        self.status_label.setText(f'Heard: "{transcription}"')
        self._dispatch_report_command(transcription)

    def _on_text_submitted(self):
        """User pressed enter in silent text bar."""
        query = self.text_input.text().strip()
        if not query:
            return
        self.text_input.clear()
        self.text_input.hide()
        self._dispatch_report_command(query)

    def _dispatch_report_command(self, command: str):
        """Launches background WhatsApp inspection & VLM synthesis."""
        self.waveform.start_animation("#10B981")  # Emerald inspecting
        self.status_label.setText("Connecting to WhatsApp...")
        self.status_label.setStyleSheet("color: #10B981;")

        self.report_worker = WhatsAppReportWorker(command)
        self.report_worker.status_update.connect(self._handle_status_update)
        self.report_worker.report_ready.connect(self._handle_report_response)
        self.report_worker.error_occurred.connect(self._handle_report_error)
        self.report_worker.start()

    def _handle_status_update(self, status_text: str, color_hex: str):
        """Updates status text and waveform color while agent runs."""
        self.waveform.start_animation(color_hex)
        self.status_label.setText(status_text)
        self.status_label.setStyleSheet(f"color: {color_hex}; font-weight: 500;")

    def _handle_report_response(self, response: dict):
        """Displays completed report in expanded HUD card and triggers J.A.R.V.I.S. voice."""
        self.waveform.stop_animation()

        contact_name = response.get("contact_name", "Contact")
        spoken_response = response.get("spoken_response", "")
        report_markdown = response.get("report_markdown", "")
        file_path = response.get("report_file_path")
        is_fallback = response.get("is_fallback", False)

        self.current_report_file = file_path
        self.current_report_text = report_markdown

        # Update top status
        self.status_label.setText(f"Report Ready: {contact_name}")
        self.status_label.setStyleSheet("color: #38BDF8; font-weight: bold;")

        # Badges
        self.report_badge.setText(f"📋 WHATSAPP: {contact_name.upper()}")
        if is_fallback:
            self.save_badge.setText("✓ Stage-Safe Mode")
            self.save_badge.setStyleSheet("background-color: #D97706; color: #FFFFFF; font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 6px;")
        else:
            self.save_badge.setText("✓ Live Scraped")
            self.save_badge.setStyleSheet("background-color: #059669; color: #FFFFFF; font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 6px;")

        # Subtitle
        if spoken_response:
            self.spoken_subtitle.setText(f'J.A.R.V.I.S.: "{spoken_response}"')
            self.spoken_subtitle.show()
        else:
            self.spoken_subtitle.hide()

        # Render Markdown in QTextBrowser
        self.report_viewer.setMarkdown(report_markdown)

        # Expand card upwards to 540x380
        self.report_card.show()
        self.is_expanded = True
        self._reposition_bottom_center(width=540, height=380)

        # Trigger J.A.R.V.I.S. Voice briefing
        if spoken_response and config.ORION_VOICE_ENABLED:
            self.voice_engine.speak(
                spoken_response,
                on_start=lambda: self.trigger_voice_start.emit(),
                on_finish=lambda: self.trigger_voice_stop.emit(),
            )

    def _handle_report_error(self, err_msg: str):
        """Displays error in status bar."""
        self.waveform.stop_animation()
        self.status_label.setText(f"Error: {err_msg[:60]}")
        self.status_label.setStyleSheet("color: #F43F5E;")

    def _collapse_card(self):
        """Collapses expanded report card back to minimal pill."""
        self.report_card.hide()
        self.is_expanded = False
        self._reposition_bottom_center(width=480, height=60)

    def _open_report_file(self):
        """Opens the saved Markdown report in user's default OS viewer."""
        if self.current_report_file and os.path.exists(self.current_report_file):
            try:
                os.startfile(self.current_report_file)
            except Exception as e:
                print(f"[Warning] Failed to open report file: {e}")

    def _copy_report_markdown(self):
        """Copies report Markdown to OS clipboard."""
        if self.current_report_text:
            pyperclip.copy(self.current_report_text)
            self.copy_btn.setText("✓ Copied!")
            QTimer.singleShot(2000, lambda: self.copy_btn.setText("📋 Copy Markdown"))

    def _on_mute_clicked(self):
        """Interrupts voice playback."""
        self.voice_engine.stop()
        self.waveform.stop_animation()

    def _on_voice_start(self):
        """Golden waveform while J.A.R.V.I.S. talks."""
        self.waveform.start_animation("#FCD34D")

    def _on_voice_stop(self):
        self.waveform.stop_animation()
