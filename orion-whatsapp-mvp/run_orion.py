"""
Project ORION (by Group S.T.A.R.K.) - Unified System Launcher
Starts the local FastAPI backend, connects the global OS Push-to-Talk hotkey listener,
initializes the J.A.R.V.I.S. neural voice engine, and displays the Wispr Flow WhatsApp HUD.
"""

import os
import sys
import threading
import time
import uvicorn
from PyQt6.QtWidgets import QApplication

from config import config
from backend.server import app
from ui.wispr_overlay import OrionWisprHUD
from ui.hotkey_listener import GlobalHotkeyListener
from voice.jarvis_tts import get_voice_engine


class ServerThread(threading.Thread):
    """Runs Uvicorn FastAPI server on background daemon thread."""

    def __init__(self, host: str, port: int):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.server: uvicorn.Server | None = None

    def run(self):
        cfg = uvicorn.Config(
            app=app,
            host=self.host,
            port=self.port,
            log_level="warning",
            loop="asyncio",
        )
        self.server = uvicorn.Server(cfg)
        self.server.run()

    def stop(self):
        if self.server:
            self.server.should_exit = True


def print_banner():
    """Prints launch information to console."""
    print("=" * 68)
    print("  PROJECT ORION — VOICE-ACTIVATED WHATSAPP REPORT COMPILER")
    print("  Group S.T.A.R.K. | Wispr Flow Ambient HUD + Nemotron-3.5-VL")
    print("=" * 68)
    print(f"  • VLM Model:         {config.OPENROUTER_MODEL}")
    print(f"  • Backend Server:    {config.backend_url}")
    print(f"  • Voice Persona:     J.A.R.V.I.S. ({config.ORION_TTS_VOICE})")
    print(f"  • Honorific:         {config.ORION_USER_TITLE}")
    print(f"  • Push-to-Talk:      Hold [Alt + Space]")
    print(f"  • Session Dir:       {config.WHATSAPP_SESSION_DIR.resolve()}")
    print(f"  • Reports Dir:       {config.REPORTS_DIR.resolve()}")
    print(f"  • Demo Fallback:     {'ENABLED' if config.DEMO_FALLBACK_MODE else 'DISABLED'}")
    print("=" * 68)
    print("  Ready. Press [Alt + Space] or click 🎙️ to inspect WhatsApp chats.\n")


def main():
    print_banner()

    # 1. Start FastAPI Backend Server
    server_thread = ServerThread(host=config.BACKEND_HOST, port=config.BACKEND_PORT)
    server_thread.start()
    time.sleep(0.5)

    # 2. Initialize PyQt6 GUI Application
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("Project ORION")
    qt_app.setQuitOnLastWindowClosed(False)

    hud = OrionWisprHUD()
    hud.show()

    # 3. Start Global OS Push-to-Talk Hotkey Listener (pynput)
    hotkey_listener = GlobalHotkeyListener(
        on_press_callback=hud.on_hotkey_down,
        on_release_callback=hud.on_hotkey_up,
    )
    hotkey_listener.start()

    # 4. J.A.R.V.I.S. Startup Greeting
    if config.ORION_VOICE_ENABLED:
        voice = get_voice_engine()
        greeting = f"Project ORION WhatsApp Intelligence is online, {config.ORION_USER_TITLE}. Awaiting your instruction."
        voice.speak(greeting)

    # 5. Enter Qt Event Loop
    try:
        sys.exit(qt_app.exec())
    except KeyboardInterrupt:
        pass
    finally:
        print("\nShutting down Project ORION...")
        hotkey_listener.stop()
        server_thread.stop()


if __name__ == "__main__":
    main()
