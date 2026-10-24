"""
Project ORION - Multimodal OS Context Capture
Captures primary screen (compressed Base64 JPEG), active window title,
clipboard text, recent workspace edits, and terminal logs.
"""

import base64
import ctypes
import io
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import mss
from PIL import Image
import pyperclip

from config import config


def get_active_window_title() -> str:
    """
    Retrieves the title of the currently focused OS window.
    Supports Windows natively via user32.dll with Linux/macOS fallbacks.
    """
    try:
        if sys.platform == "win32":
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                return "Desktop"
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return "Active Window (No Title)"
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value or "Active Window"
        elif sys.platform.startswith("linux"):
            import subprocess
            try:
                out = subprocess.check_output(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                return out.strip()
            except Exception:
                return "Linux Desktop Window"
        elif sys.platform == "darwin":
            return "macOS Active Window"
    except Exception:
        pass
    return "Unknown Active Window"


def capture_screen_base64() -> Optional[str]:
    """
    Captures primary screen using mss, resizes to max dimension 1280px (maintaining aspect ratio),
    and compresses to JPEG Base64 with quality 75 to minimize VLM transmission latency.
    """
    try:
        with mss.mss() as sct:
            # monitors[1] is the primary display; fallback to monitors[0] (all monitors) if needed
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            sct_img = sct.grab(monitor)

            # Convert BGRA raw bytes to PIL Image RGB
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

            # Downscale proportionally to fit within 1280x720 max
            img.thumbnail((config.SCREENSHOT_MAX_DIMENSION, 720), Image.Resampling.LANCZOS)

            # Compress to JPEG
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=config.SCREENSHOT_JPEG_QUALITY, optimize=True)
            b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return b64_str
    except Exception as e:
        print(f"[Warning] Screenshot capture failed: {e}")
        return None


def get_recent_workspace_context(workspace_dir: str | Path) -> Dict[str, Any]:
    """
    Scans workspace for the most recently modified file and reads
    the last 30 lines of .orion_terminal.log if available.
    """
    ws = Path(workspace_dir).resolve()
    recent_file_info = None
    terminal_log = ""

    if ws.exists() and ws.is_dir():
        # 1. Find recently modified code file
        candidates = []
        for root, _, files in os.walk(ws):
            if any(p.startswith(".") or p == "__pycache__" for p in Path(root).parts):
                continue
            for f in files:
                fpath = Path(root) / f
                if fpath.name == ".orion_terminal.log":
                    continue
                try:
                    candidates.append((fpath.stat().st_mtime, fpath))
                except Exception:
                    pass

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            most_recent_path = candidates[0][1]
            try:
                with open(most_recent_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                snippet = "".join(f"{i+1:3d}: {line}" for i, line in enumerate(lines[:60]))
                recent_file_info = {
                    "path": str(most_recent_path.relative_to(ws)),
                    "total_lines": len(lines),
                    "preview": snippet,
                }
            except Exception:
                pass

        # 2. Check for terminal error log
        term_log_path = ws / ".orion_terminal.log"
        if term_log_path.exists():
            try:
                with open(term_log_path, "r", encoding="utf-8", errors="replace") as f:
                    log_lines = f.readlines()
                terminal_log = "".join(log_lines[-30:])
            except Exception:
                pass

    return {
        "workspace_path": str(ws),
        "recent_file": recent_file_info,
        "terminal_log": terminal_log.strip(),
    }


def capture_os_context(
    include_screenshot: bool = True,
    workspace_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compiles complete OS context snapshot:
    - Base64 compressed screenshot
    - Active window title
    - Clipboard contents
    - Recent workspace edits & terminal logs
    """
    target_ws = workspace_dir or str(config.ORION_WORKSPACE_DIR)

    # 1. Screenshot
    screenshot_b64 = capture_screen_base64() if include_screenshot else None

    # 2. Active Window
    active_window = get_active_window_title()

    # 3. Clipboard safely
    clipboard_text = ""
    try:
        raw_clip = pyperclip.paste()
        if raw_clip and isinstance(raw_clip, str):
            clipboard_text = raw_clip[:2000].strip()
    except Exception:
        pass

    # 4. Workspace & Terminal context
    ws_context = get_recent_workspace_context(target_ws)

    return {
        "screenshot_b64": screenshot_b64,
        "active_window": active_window,
        "clipboard_text": clipboard_text,
        "workspace_context": ws_context,
    }
