"""
Project ORION - FastAPI Backend Server
Hosts /api/v1/act and /api/v1/health endpoints with 5-turn history truncation
and autonomous 2-step Flake8 self-correction verification loop.
"""

import json
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .openrouter_client import parse_agent_response, query_openrouter_vlm
from .prompts import build_self_correction_prompt, get_system_prompt
from .schemas import AgentAction, AgentResponse, TriggerPayload, VerificationResult
from aci.tools import execute_aci_tool
from config import config
from voice.jarvis_tts import get_voice_engine

app = FastAPI(
    title="Project ORION ACI Backend",
    version="1.0.0",
    description="Agent-Computer Interface & Multimodal VLM Router by Group S.T.A.R.K.",
)

# Enable CORS for desktop UI and local clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def compress_conversation_history(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Truncates and compresses conversation history:
    Retains the last 5 turns in full detail, collapsing any earlier turns
    into single-line summary messages to prevent context window bloat.
    """
    if not history or len(history) <= 5:
        return history

    older_turns = history[:-5]
    recent_turns = history[-5:]

    compressed_summaries = []
    for turn in older_turns:
        role = turn.get("role", "assistant")
        content = str(turn.get("content", ""))
        first_line = content.split("\n")[0][:100]
        compressed_summaries.append(f"[{role}]: {first_line}")

    summary_message = {
        "role": "system",
        "content": "Prior conversation summary:\n" + "\n".join(compressed_summaries),
    }

    return [summary_message] + recent_turns


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint providing runtime diagnostics."""
    return {
        "status": "online",
        "service": "Project ORION",
        "model": config.OPENROUTER_MODEL,
        "temperature": config.OPENROUTER_TEMPERATURE,
        "workspace_dir": str(config.ORION_WORKSPACE_DIR.resolve()),
        "voice_enabled": config.ORION_VOICE_ENABLED,
        "voice": config.ORION_TTS_VOICE,
    }


@app.post("/api/v1/act", response_model=AgentResponse)
async def act_endpoint(payload: TriggerPayload):
    """
    Core multimodal reasoning and execution endpoint:
    1. Formats multimodal messages with visual screen state and text context.
    2. Queries OpenRouter VLM (nvidia/nemotron-3.5-super-vl:free).
    3. Runs Dual Action Parser to extract ACI tool call.
    4. Executes ACI tool with Flake8 verification.
    5. Autonomous Self-Correction: Automatically retries if syntax error is detected.
    """
    # 1. Prepare user context block
    user_context_text = f"USER QUERY: {payload.user_query}\n\n"
    user_context_text += f"ACTIVE OS WINDOW: {payload.active_window}\n"

    if payload.clipboard_text:
        user_context_text += f"CLIPBOARD CONTENT:\n```\n{payload.clipboard_text}\n```\n\n"

    ws_ctx = payload.workspace_context or {}
    if ws_ctx.get("recent_file"):
        rf = ws_ctx["recent_file"]
        user_context_text += (
            f"RECENTLY MODIFIED WORKSPACE FILE: {rf.get('path')} ({rf.get('total_lines')} lines)\n"
            f"FILE PREVIEW:\n```python\n{rf.get('preview', '')}\n```\n\n"
        )
    if ws_ctx.get("terminal_log"):
        user_context_text += f"RECENT TERMINAL LOG:\n```\n{ws_ctx['terminal_log']}\n```\n\n"

    user_context_text += "Determine the best ACI action and respond with exactly one JSON object."

    # 2. Build multimodal user content
    user_content_parts: List[Dict[str, Any]] = [
        {"type": "text", "text": user_context_text}
    ]

    # Include base64 screenshot if available
    if payload.screenshot_b64:
        user_content_parts.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{payload.screenshot_b64}"
                },
            }
        )

    # 3. Assemble full message list
    system_msg = {"role": "system", "content": get_system_prompt()}
    truncated_history = compress_conversation_history(payload.history or [])
    user_msg = {"role": "user", "content": user_content_parts}

    messages = [system_msg] + truncated_history + [user_msg]

    # 4. Query VLM
    try:
        raw_response = await query_openrouter_vlm(
            messages=messages,
            temperature=config.OPENROUTER_TEMPERATURE,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"OpenRouter VLM request failed: {str(e)}",
        )

    # 5. Parse agent action via Dual Action Parser
    action_decision: AgentAction = parse_agent_response(raw_response)

    # 6. Execute ACI Tool
    tool_result = execute_aci_tool(
        action=action_decision.action,
        args=action_decision.args,
    )

    retries_used = 0
    verification = None

    # 7. Autonomous Verification & Self-Correction Loop for edit_lines
    if action_decision.action == "edit_lines":
        if tool_result.get("status") == "syntax_error":
            verification = VerificationResult(
                status="syntax_error",
                reverted=True,
                linter_errors=tool_result.get("linter_errors"),
                original_snippet=tool_result.get("original_snippet"),
                attempted_snippet=tool_result.get("attempted_snippet"),
                retries_used=0,
            )

            # Attempt self-correction up to MAX_VERIFICATION_RETRIES
            for attempt in range(1, config.MAX_VERIFICATION_RETRIES + 1):
                retries_used = attempt
                correction_prompt = build_self_correction_prompt(
                    original_action=action_decision.model_dump(),
                    linter_error=tool_result.get("linter_errors", ""),
                    original_snippet=tool_result.get("original_snippet", ""),
                    attempted_snippet=tool_result.get("attempted_snippet", ""),
                    retry_count=attempt,
                )

                messages.append(
                    {"role": "assistant", "content": json.dumps(action_decision.model_dump())}
                )
                messages.append(
                    {"role": "user", "content": [{"type": "text", "text": correction_prompt}]}
                )

                try:
                    retry_resp = await query_openrouter_vlm(
                        messages=messages,
                        temperature=config.OPENROUTER_TEMPERATURE,
                    )
                    action_decision = parse_agent_response(retry_resp)
                    tool_result = execute_aci_tool(
                        action=action_decision.action,
                        args=action_decision.args,
                    )

                    if tool_result.get("status") == "success":
                        verification = VerificationResult(
                            status="success",
                            reverted=False,
                            linter_errors=None,
                            retries_used=attempt,
                        )
                        break
                    else:
                        verification.retries_used = attempt
                except Exception:
                    break

        elif tool_result.get("status") == "success":
            verification = VerificationResult(
                status="success",
                reverted=False,
                retries_used=0,
            )

    return AgentResponse(
        thought=action_decision.thought,
        action=action_decision.action,
        args=action_decision.args,
        tool_result=tool_result,
        verification=verification,
        summary_for_user=action_decision.summary_for_user,
        spoken_response=action_decision.spoken_response,
        retries_used=retries_used,
    )


@app.post("/api/v1/speak")
async def speak_endpoint(data: Dict[str, str]):
    """Triggers J.A.R.V.I.S. neural speech synthesis and playback."""
    text = data.get("text", "")
    if text:
        engine = get_voice_engine()
        engine.speak(text)
    return {"status": "ok"}


@app.post("/api/v1/stop_speech")
async def stop_speech_endpoint():
    """Interrupts active speech playback (barge-in)."""
    engine = get_voice_engine()
    engine.stop()
    return {"status": "stopped"}
