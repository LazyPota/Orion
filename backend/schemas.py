"""
Project ORION - Pydantic v2 Schemas for WhatsApp Report Intelligence
"""

from typing import Optional
from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    """User voice or text command requesting WhatsApp inspection."""
    user_command: str = Field(
        ...,
        description="Spoken or typed command (e.g., 'Check WhatsApp messages from Derrian')",
    )
    contact_override: Optional[str] = Field(
        default=None,
        description="Explicit contact or group name if already extracted by client",
    )


class WhatsAppReportResponse(BaseModel):
    """Structured report and J.A.R.V.I.S. briefing returned to the floating HUD."""
    contact_name: str = Field(..., description="Target contact or group inspected")
    spoken_response: str = Field(
        ...,
        description="1-2 sentence composed British butler briefing (max 30 words, no markdown)",
    )
    report_markdown: str = Field(
        ...,
        description="Executive Markdown report synthesizing chat history and action items",
    )
    report_file_path: Optional[str] = Field(
        default=None,
        description="Path to auto-saved report file on disk",
    )
    is_fallback: bool = Field(
        default=False,
        description="True if compiled using stage-safe demo fallback mode",
    )
    message: str = Field(default="Report successfully generated.")
