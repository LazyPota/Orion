"""
Project ORION - Pydantic v2 Data Schemas
Defines request and response structures for VLM routing, ACI execution, and J.A.R.V.I.S. voice feedback.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TriggerPayload(BaseModel):
    """Payload received from OS trigger (voice transcript or typed prompt + context)."""
    user_query: str = Field(..., description="User voice transcript or typed command")
    active_window: str = Field(default="Desktop", description="Title of the active OS window")
    clipboard_text: Optional[str] = Field(default="", description="Current clipboard text")
    screenshot_b64: Optional[str] = Field(default=None, description="Base64 JPEG screenshot of active screen")
    workspace_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Recent file preview & logs")
    history: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Prior conversation history")


class AgentAction(BaseModel):
    """Structured decision parsed from OpenRouter VLM."""
    thought: str = Field(
        ...,
        description="Technical reasoning about the user's screen/code context and intent.",
    )
    action: str = Field(
        ...,
        description="ACI tool name: edit_lines, open_file, search_workspace, type_or_paste_text, open_web_url, write_markdown_note, or answer_only",
    )
    args: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments passed to the chosen ACI tool",
    )
    summary_for_user: str = Field(
        ...,
        description="Concise technical summary for the visual HUD pill.",
    )
    spoken_response: str = Field(
        default="",
        description="Concise, composed British Butler reply spoken by J.A.R.V.I.S. (1-2 sentences, max 25 words).",
    )


class VerificationResult(BaseModel):
    """Status of Flake8 linter guardrail execution."""
    status: str = Field(..., description="'success', 'syntax_error', or 'skipped'")
    reverted: bool = Field(default=False, description="True if edit was reverted due to linter error")
    linter_errors: Optional[str] = Field(default=None, description="Exact output from flake8")
    original_snippet: Optional[str] = Field(default=None)
    attempted_snippet: Optional[str] = Field(default=None)
    retries_used: int = Field(default=0, description="Number of self-correction attempts made")


class AgentResponse(BaseModel):
    """Final unified response returned by FastAPI to Wispr HUD overlay."""
    thought: str
    action: str
    args: Dict[str, Any]
    tool_result: Dict[str, Any]
    verification: Optional[VerificationResult] = None
    summary_for_user: str
    spoken_response: str
    retries_used: int = 0
