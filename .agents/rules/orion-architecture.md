---
trigger: always_on
---

# Project ORION (S.T.A.R.K. MVP) — Single-Feature WhatsApp Report Compiler Rules

## 1. MVP Scope (Critical Function Prototype)
- Build a single, rock-solid vertical slice: **Voice-Activated WhatsApp Chat Inspector & Report Compiler** with a Wispr Flow-style floating desktop overlay and J.A.R.V.I.S. British butler TTS voice.
- Do NOT build code-linters or multi-tool IDE editors in this MVP. Focus 100% on the WhatsApp automation, VLM report synthesis, floating HUD, and Jarvis voice playback.

## 2. WhatsApp Web Automation Guardrails (`Playwright`)
- Always use `playwright.async_api` with `launch_persistent_context(user_data_dir="./whatsapp_session", headless=False)` so the user's WhatsApp Web login persists across runs without re-scanning the QR code during a live presentation.
- Never rely on brittle, obfuscated WhatsApp CSS class names (like `._ak8l`). Use resilient selectors:
  - Search box: `div[contenteditable="true"][data-tab="3"]`, `div[role="textbox"]`, or keyboard shortcut `Ctrl+Alt+/` followed by typing the contact name and pressing `Enter`.
  - Message extraction: Extract `inner_text()` from `#main` (the active chat container) AND always capture a JPEG screenshot (`quality=80`) of the open WhatsApp chat viewport.
- Include a `DEMO_FALLBACK_MODE` in `.env`: if WhatsApp Web has no internet or the contact isn't found within 12 seconds, smoothly fall back to a realistic pre-loaded WhatsApp chat log in `./demo_data/sample_whatsapp_chat.txt` so a live classroom demo can NEVER fail on stage.

## 3. VLM & OpenRouter Conventions
- Default model: `OPENROUTER_MODEL="nvidia/nemotron-3.5-super-vl:free"` via `https://openrouter.ai/api/v1/chat/completions`.
- Pass BOTH the scraped `#main` chat text and the base64 viewport screenshot to the VLM.
- Enforce a structured JSON output from the VLM containing:
  1. `contact_name`: The person/group inspected.
  2. `spoken_response`: A 1–2 sentence J.A.R.V.I.S. British butler spoken briefing (max 30 words, no markdown/symbols).
  3. `report_markdown`: A clean Markdown report with sections: `### Executive Summary`, `### Key Points & Updates`, and `### Action Items / Deadlines`.

## 4. UI & Voice Conventions
- UI (`PyQt6`): Frameless, always-on-top, translucent Wispr-style floating pill at the bottom-center of the screen (`480x58` collapsed; expands to `520x380` to display the compiled WhatsApp report card).
- Voice TTS (`edge-tts` + `pygame`): Use `en-GB-RyanNeural` (`rate="+6%"`, `pitch="-4Hz"`) with offline `pyttsx3` fallback and instant barge-in stop when recording starts.