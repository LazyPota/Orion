"""
Project ORION - Global OS Hotkey Listener
Uses pynput to listen for Push-to-Talk key combinations (Alt+Space) across the entire OS.
"""

import threading
from typing import Callable, Optional, Set
from pynput import keyboard


class GlobalHotkeyListener:
    """
    Global Push-to-Talk hotkey listener running on background thread.
    Emits on_press when combination is held, and on_release when released.
    """

    def __init__(
        self,
        on_press_callback: Optional[Callable[[], None]] = None,
        on_release_callback: Optional[Callable[[], None]] = None,
    ):
        self.on_press_callback = on_press_callback
        self.on_release_callback = on_release_callback
        self._current_keys: Set[keyboard.Key | keyboard.KeyCode] = set()
        self._is_active = False
        self._listener: Optional[keyboard.Listener] = None
        self._lock = threading.Lock()

    def _is_alt_pressed(self) -> bool:
        return any(
            k in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr)
            for k in self._current_keys
        )

    def _is_space_pressed(self) -> bool:
        return keyboard.Key.space in self._current_keys

    def _on_key_press(self, key):
        with self._lock:
            self._current_keys.add(key)
            if self._is_alt_pressed() and self._is_space_pressed():
                if not self._is_active:
                    self._is_active = True
                    if self.on_press_callback:
                        self.on_press_callback()

    def _on_key_release(self, key):
        with self._lock:
            # If active and either Alt or Space is released
            is_relevant = (
                key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.space)
            )
            if key in self._current_keys:
                self._current_keys.remove(key)

            if self._is_active and is_relevant:
                self._is_active = False
                if self.on_release_callback:
                    self.on_release_callback()

    def start(self):
        """Starts global keyboard hook."""
        self._listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        """Stops global keyboard hook."""
        if self._listener:
            self._listener.stop()
            self._listener = None
