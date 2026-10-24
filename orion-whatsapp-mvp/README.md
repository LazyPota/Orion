# Project ORION (S.T.A.R.K. MVP)
### Voice-Activated WhatsApp Intelligence Report Compiler with Wispr Flow Ambient HUD & J.A.R.V.I.S. Neural Voice

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium%20Persistent-green.svg)](https://playwright.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![PyQt6](https://img.shields.io/badge/PyQt6-Wispr%20HUD-41CD52.svg)](https://riverbankcomputing.com/software/pyqt/)
[![OpenRouter VLM](https://img.shields.io/badge/VLM-nvidia%2Fnemotron--3.5--super--vl%3Afree-76B900.svg)](https://openrouter.ai/)
[![J.A.R.V.I.S. Voice](https://img.shields.io/badge/TTS-edge--tts%20RyanNeural-yellow.svg)](https://github.com/rany2/edge-tts)

---

## 1. Executive Summary & Value Proposition

Project ORION is an OS-wide, voice-activated Agent-Computer Interface (ACI) designed by **Group S.T.A.R.K.**. It provides a zero-friction, ambient assistant experience without locking developers into an IDE or forcing context switches into a web-browser chatbot.

### Core Critical Function Prototype:
1. **Push-to-Talk HUD (The Wispr Layer):** A frameless, translucent, always-on-top desktop pill overlay (`PyQt6`) anchored at the bottom-center of the screen. Holds `Alt + Space` to record natural voice commands without stealing window focus.
2. **Automated WhatsApp Web Inspection:** Uses `playwright.async_api` with a persistent Chromium context (`./whatsapp_session`, `headless=False`). The audience watches ORION navigate WhatsApp Web, search for the requested contact, select the chat, scrape visible `#main` message history, and take an automated viewport screenshot.
3. **Multimodal VLM Intelligence Synthesis:** Transmits both the scraped chat text and base64 viewport screenshot to OpenRouter's `nvidia/nemotron-3.5-super-vl:free` at `temperature: 0.0`.
4. **Structured Intelligence Report:** Compiles a structured Markdown report (`Executive Summary`, `Key Points & Updates`, `Action Items & Deadlines`) and auto-saves it to `./reports/`.
5. **Interactive Report Viewer:** Expands the HUD pill into a 540x380 dark card with a scrollable report viewer, `[📂 Open Report File]`, and `[📋 Copy Markdown]` buttons.
6. **J.A.R.V.I.S. British Butler Voice:** Synthesizes a natural, concise spoken briefing (strictly under 30 words, addressing the user as "Sir") via Microsoft `edge-tts` (`en-GB-RyanNeural`) with instant push-to-talk barge-in interruption.
7. **Stage-Safe Demo Fallback Mode:** If venue Wi-Fi is unstable or WhatsApp Web is unreachable, ORION automatically loads realistic chat data (`./demo_data/sample_whatsapp_chat.txt`), captures the screen, and synthesizes the report seamlessly—ensuring a live presentation can **never fail on stage**.

---

## 2. Directory Structure

```text
orion-whatsapp-mvp/
├── .env.example                    # Environment template
├── .env                            # Active configuration & OpenRouter API key
├── requirements.txt                # Python dependencies
├── README.md                       # Full documentation & Slide 9 content
├── run_orion.py                    # Unified launcher (FastAPI backend + PyQt6 HUD)
├── setup_whatsapp_login.py         # One-time helper to scan WhatsApp QR code before presentation
├── config.py                       # Configuration & path management
├── demo_data/
│   └── sample_whatsapp_chat.txt    # Fallback chat log for stage-safe demo mode
├── reports/                        # Auto-saved Markdown reports
├── voice/
│   ├── __init__.py
│   ├── audio_recorder.py           # Sounddevice mic capture & multi-tier STT (Google / Whisper)
│   └── jarvis_tts.py               # J.A.R.V.I.S. British butler TTS with barge-in stop
├── automation/
│   ├── __init__.py
│   └── whatsapp_agent.py           # Playwright persistent WhatsApp automation & dual capture
├── backend/
│   ├── __init__.py
│   ├── schemas.py                  # Pydantic v2 request/response models
│   ├── prompts.py                  # Regex contact extraction & VLM persona prompt
│   ├── openrouter_client.py        # Async httpx client for Nemotron-VL & JSON parser
│   └── server.py                   # FastAPI service (/api/v1/whatsapp-report, /api/v1/health)
├── ui/
│   ├── __init__.py
│   ├── hotkey_listener.py          # Global OS Push-to-Talk hotkey listener (Alt+Space)
│   └── wispr_overlay.py            # PyQt6 floating pill HUD & Report Viewer
└── tests/
    └── test_whatsapp_report.py     # End-to-end integration test suite
```

---

## 3. Quick Start & Setup

### Step 1: Install Dependencies & Chromium
```powershell
pip install -r requirements.txt
playwright install chromium
```

### Step 2: One-Time WhatsApp Login Setup (Before Presentation)
Run the one-time login script so you don't have to scan the QR code live in front of the audience:
```powershell
python setup_whatsapp_login.py
```
- Chromium opens to `https://web.whatsapp.com`.
- Open WhatsApp on your phone -> **Linked Devices** -> **Link a Device**.
- Scan the QR code.
- Once the chat list loads, ORION detects `#pane-side`, saves the session to `./whatsapp_session`, and exits automatically.

### Step 3: Launch Project ORION
```powershell
python run_orion.py
```
- The FastAPI backend starts on `127.0.0.1:8765`.
- The Wispr Flow floating pill anchors at the bottom-center of your screen.
- J.A.R.V.I.S. greets you: *"Project ORION WhatsApp Intelligence is online, Sir. Awaiting your instruction."*

---

## 4. Live Presentation Demo Flow

### Trigger Option A: Voice Command (Push-to-Talk)
1. Hold **`[Alt + Space]`** anywhere in Windows (or click the 🎙️ mic button in the HUD).
2. Say: *"Open WhatsApp and check messages from Derrian"* (or *"What did Derrian say on WhatsApp?"*).
3. Release **`[Alt + Space]`**.

### Trigger Option B: Silent Text Input
Click the ⌨️ keyboard icon on the pill HUD, type `Check messages from Derrian`, and press `Enter`.

### What Happens Live:
1. **HUD Status:** Glows emerald (`Opening WhatsApp & inspecting chat...`).
2. **Browser Execution:** Chromium opens WhatsApp Web, searches for the contact, opens the conversation, and captures messages and a viewport screenshot.
3. **VLM Synthesis:** HUD glows amber (`Compiling report via Nemotron-VL...`).
4. **Report Card Expansion:** The HUD smoothly expands upward to `540x380` displaying:
   - Spoken subtitle in glowing gold: *"Sir, Derrian confirms the backend is live on port 8765. He requests your Slide 9 review before 8 PM ahead of the 3 PM dry run."*
   - Scrollable rendered Markdown report with **Executive Summary**, **Key Points & Updates**, and **Action Items**.
   - `[📂 Open Report File]` button to open the auto-saved `.md` in your text editor.
   - `[📋 Copy Markdown]` button for instant sharing.
5. **J.A.R.V.I.S. Voice:** Speaks the 1–2 sentence briefing aloud in natural British butler tone. Pressing `Alt + Space` or clicking `🔊` instantly stops speech (barge-in).

---

## 5. Slide 9 Presentation Content

```markdown
### SLIDE 9: Critical Function Prototype — WhatsApp Intelligence Report Compiler

#### Title:
**Project ORION: Voice-Activated WhatsApp Intelligence Agent**
*Group S.T.A.R.K. | Autonomous Multimodal ACI*

#### Key Value Proposition:
Transitioning from passive code chatbots to an autonomous ambient interface that connects daily human communication (WhatsApp) to vision-language synthesis.

#### Core Technical Architecture:
1. **Wispr Flow Floating HUD (PyQt6):**
   - Translucent, non-focus-stealing pill overlay anchored at bottom-center.
   - Global push-to-talk (`Alt + Space`) via OS hooks with cross-thread signal safety.
   - Dynamic states: Cyan (Listening), Emerald (Inspecting), Amber (Reasoning), Gold (Speaking).

2. **Persistent WhatsApp Playwright Automation:**
   - Headless-optional Chromium context (`./whatsapp_session`) retains QR authentication.
   - Resilient DOM selection (`#pane-side`, `div[contenteditable="true"]`, `#main`).
   - Dual multimodal capture: Scraped chat text + high-definition viewport screenshot.

3. **NVIDIA Nemotron-3.5-Super-VL via OpenRouter:**
   - Free-tier high-capacity Vision-Language Model operating at `temperature: 0.0`.
   - Synthesizes unstructured multi-message conversations into structured Markdown reports.
   - Enforces 3-part schema: Executive Summary, Key Points & Updates, Action Items.

4. **J.A.R.V.I.S. British Butler Voice Engine:**
   - Neural TTS (`edge-tts` `en-GB-RyanNeural`, `rate="+6%"`, `pitch="-4Hz"`).
   - Concise verbal briefing (under 30 words) with instant Push-to-Talk barge-in interruption.

5. **Stage-Safe Demo Reliability:**
   - Deterministic regex contact extraction + automatic fallback mode (`DEMO_FALLBACK_MODE=true`).
   - Guarantees zero failures on stage even in venues with disconnected or throttled Wi-Fi.
```
