"""
Project ORION - FastAPI Server for WhatsApp Intelligence Reporting
Exposes /api/v1/whatsapp-report and /api/v1/health endpoints.
"""

from typing import Any, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import config
from automation.whatsapp_agent import fetch_whatsapp_chat
from .prompts import extract_contact_name
from .openrouter_client import compile_whatsapp_report
from .schemas import CommandRequest, WhatsAppReportResponse
from voice.jarvis_tts import get_voice_engine

app = FastAPI(
    title="Project ORION - WhatsApp Intelligence Service",
    version="1.0.0",
    description="Voice-activated WhatsApp Chat Inspector & Multimodal VLM Report Compiler by Group S.T.A.R.K.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
async def health_check():
    """Returns service health and operational parameters."""
    return {
        "status": "online",
        "service": "Project ORION WhatsApp Intelligence",
        "model": config.OPENROUTER_MODEL,
        "temperature": config.OPENROUTER_TEMPERATURE,
        "demo_fallback_mode": config.DEMO_FALLBACK_MODE,
        "voice": config.ORION_TTS_VOICE,
        "honorific": config.ORION_USER_TITLE,
    }


@app.post("/api/v1/whatsapp-report", response_model=WhatsAppReportResponse)
async def whatsapp_report_endpoint(request: CommandRequest):
    """
    Main pipeline:
    1. Extracts contact or group name from voice/text command.
    2. Opens WhatsApp Web in persistent Chromium & scrapes chat + screenshot.
    3. Multimodal VLM synthesizes structured Markdown report & J.A.R.V.I.S. briefing.
    4. Auto-saves report to disk and returns payload to floating HUD overlay.
    """
    # 1. Determine contact name
    contact_name = request.contact_override or extract_contact_name(request.user_command)
    print(f"\n[Backend] Request received: '{request.user_command}' -> Target: '{contact_name}'")

    # 2. Inspect WhatsApp via Playwright
    try:
        chat_data = await fetch_whatsapp_chat(contact_name)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"WhatsApp automation failed: {str(e)}",
        )

    raw_chat = chat_data.get("raw_chat_text", "")
    screenshot_b64 = chat_data.get("screenshot_b64")
    is_fallback = chat_data.get("is_fallback", False)

    # 3. Multimodal VLM Report Compilation
    report_response = await compile_whatsapp_report(
        contact_name=contact_name,
        raw_chat_text=raw_chat,
        screenshot_b64=screenshot_b64,
    )

    report_response.is_fallback = is_fallback
    report_response.message = (
        f"Compiled report from {'demo fallback data' if is_fallback else 'live WhatsApp messages'}."
    )

    return report_response


@app.post("/api/v1/speak")
async def speak_endpoint(payload: Dict[str, str]):
    """Speaks text via J.A.R.V.I.S. British butler voice."""
    text = payload.get("text", "")
    if text:
        voice = get_voice_engine()
        voice.speak(text)
    return {"status": "ok"}


@app.post("/api/v1/stop_speech")
async def stop_speech_endpoint():
    """Interrupts active J.A.R.V.I.S. speech playback (barge-in)."""
    voice = get_voice_engine()
    voice.stop()
    return {"status": "stopped"}
