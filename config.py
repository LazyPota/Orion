"""
Project ORION (S.T.A.R.K. MVP) - Central Configuration Module
Loads settings from environment variables and .env with strict validation.
"""

from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OrionConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenRouter VLM Settings
    OPENROUTER_API_KEY: str = Field(default="", description="OpenRouter API Key")
    OPENROUTER_MODEL: str = Field(
        default="nvidia/nemotron-3.5-super-vl:free",
        description="Default vision-language model",
    )
    OPENROUTER_TEMPERATURE: float = Field(
        default=0.0,
        description="Temperature for deterministic report compilation (0.0)",
    )
    OPENROUTER_BASE_URL: str = Field(
        default="https://openrouter.ai/api/v1/chat/completions",
        description="OpenRouter API endpoint",
    )

    # Backend Server Settings
    BACKEND_HOST: str = Field(default="127.0.0.1")
    BACKEND_PORT: int = Field(default=8765)

    # WhatsApp Automation & Stage-Safe Demo Mode
    WHATSAPP_SESSION_DIR: Path = Field(
        default=Path("./whatsapp_session"),
        description="Directory for persistent Chromium WhatsApp profile",
    )
    WHATSAPP_TIMEOUT_SECONDS: int = Field(
        default=15,
        description="Max seconds to wait for WhatsApp Web elements before fallback",
    )
    DEMO_FALLBACK_MODE: bool = Field(
        default=True,
        description="Whether to fall back gracefully to sample chat log if WhatsApp is unreachable",
    )
    DEMO_DATA_FILE: Path = Field(
        default=Path("./demo_data/sample_whatsapp_chat.txt"),
        description="Fallback chat data for stage demos",
    )
    REPORTS_DIR: Path = Field(
        default=Path("./reports"),
        description="Directory where compiled Markdown reports are saved",
    )

    # Visual State Context (mss + Pillow compression)
    SCREENSHOT_MAX_DIMENSION: int = 1280
    SCREENSHOT_JPEG_QUALITY: int = 80

    # J.A.R.V.I.S. Butler Neural Voice Engine Settings
    ORION_VOICE_ENABLED: bool = Field(default=True)
    ORION_TTS_VOICE: str = Field(default="en-GB-RyanNeural")
    ORION_TTS_RATE: str = Field(default="+6%")
    ORION_TTS_PITCH: str = Field(default="-4Hz")
    ORION_USER_TITLE: str = Field(default="Sir")

    # Global Hotkey Settings
    ORION_HOTKEY: str = Field(default="alt+space")

    @property
    def backend_url(self) -> str:
        return f"http://{self.BACKEND_HOST}:{self.BACKEND_PORT}"


# Global singleton configuration
config = OrionConfig()

# Ensure directories exist
config.WHATSAPP_SESSION_DIR.mkdir(parents=True, exist_ok=True)
config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
Path("./demo_data").mkdir(parents=True, exist_ok=True)
