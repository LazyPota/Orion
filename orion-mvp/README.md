# Project ORION (S.T.A.R.K. MVP)
### OS-Wide Voice-Activated Agent-Computer Interface (ACI) with Wispr Flow-Style Ambient HUD & J.A.R.V.I.S. Neural Voice

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![PyQt6](https://img.shields.io/badge/PyQt6-HUD%20Overlay-41CD52.svg)](https://riverbankcomputing.com/software/pyqt/)
[![OpenRouter VLM](https://img.shields.io/badge/VLM-nvidia%2Fnemotron--3.5--super--vl%3Afree-76B900.svg)](https://openrouter.ai/)
[![Flake8 Guardrail](https://img.shields.io/badge/ACI%20Verification-Flake8%20Isolated-blueviolet.svg)](https://flake8.pycqa.org/)

---

## 1. Architectural Overview

Project ORION breaks out of traditional IDE-locked panels and chat browser windows, transforming into an **OS-wide ambient assistant**. Built on empirical HCI research (ProAIDE, FlowLight, and Princeton SWE-agent), ORION unites:

1. **The Wispr Layer (`ui/`):** A frameless, translucent, always-on-top desktop pill overlay (`PyQt6`) anchored at the bottom-center of the screen. Holds `Alt + Space` for global Push-to-Talk without stealing window focus.
2. **The Ears (`trigger/audio_recorder.py`):** Low-latency 16kHz mono audio buffering (`sounddevice` + `numpy`) with local / API speech-to-text and silent text input fallback.
3. **The Eyes (`trigger/context_capture.py`):** Active window title detection, clipboard capture (`pyperclip`), recent workspace edits, terminal error logs, and ultra-fast primary display screenshots (`mss` + `Pillow`) compressed to 1280px JPEG Base64.
4. **The Brain (`backend/`):** Local `FastAPI` server routing to OpenRouter's `nvidia/nemotron-3.5-super-vl:free` at `temperature: 0.0`. Features 5-turn history compression and a resilient Dual Action Parser handling native `tool_calls` and markdown JSON.
5. **The Hands (`aci/`):** SWE-agent style deterministic ACI commands (`open_file`, `edit_lines`, `search_workspace`, `type_or_paste_text`, `open_web_url`, `write_markdown_note`).
6. **The Linter Guardrail (`aci/verifier.py`):** Whenever `edit_lines` touches Python code, `flake8 --isolated --select=F821,F822,F831,E111,E112,E113,E999,E902` runs immediately. If an error is detected, the change is reverted instantly and fed back for up to 2 self-correction retries.
7. **J.A.R.V.I.S. Butler Voice Engine (`voice/jarvis_tts.py`):** Neural British speech synthesis (`edge-tts` `en-GB-RyanNeural`) with non-blocking `pygame.mixer` playback, visual golden waveform synchronization, offline `pyttsx3` fallback, and instant barge-in cancellation.

---

## 2. Directory Structure

```text
orion/
├── .antigravityrules        # Antigravity IDE workspace guardrails
├── .env.example             # Template environment variables
├── .env                     # Local configuration
├── requirements.txt         # Project dependencies
├── README.md                # Documentation and Slide 9 content
├── run_orion.py             # Unified launcher (FastAPI + PyQt6 HUD + J.A.R.V.I.S. Voice)
├── config.py                # Pydantic v2 settings & path resolution
├── trigger/
│   ├── __init__.py
│   ├── audio_recorder.py   # Push-to-talk mic capture & STT transcription
│   └── context_capture.py  # Screen capture (mss/Pillow), clipboard, window title, CWD
├── aci/
│   ├── __init__.py
│   ├── tools.py            # SWE-agent ACI tools (edit_lines, open_file, search, paste, etc.)
│   └── verifier.py         # Flake8 isolated guardrail & syntax verification
├── backend/
│   ├── __init__.py
│   ├── schemas.py          # Pydantic v2 models (TriggerPayload, AgentAction, AgentResponse)
│   ├── prompts.py          # J.A.R.V.I.S. persona prompt & self-correction loop builder
│   ├── openrouter_client.py# Async httpx client for Nemotron-VL + Dual Action Parser
│   └── server.py           # FastAPI server (/api/v1/act, /api/v1/health, /api/v1/speak)
├── ui/
│   ├── __init__.py
│   ├── hotkey_listener.py  # Global OS hotkey listener (pynput: Alt+Space)
│   └── wispr_overlay.py    # PyQt6 floating pill HUD with animated waveforms & diff cards
├── voice/
│   ├── __init__.py
│   └── jarvis_tts.py       # Non-blocking edge-tts/pyttsx3 British Butler engine with barge-in
└── demo_workspace/
    ├── buggy_calc.py       # Sample Python script with deliberate indentation error
    └── notes/              # Directory for AI research and study notes
```

---

## 3. Quick Start & Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and set your OpenRouter API key:
```ini
OPENROUTER_API_KEY="sk-or-v1-..."
OPENROUTER_MODEL="nvidia/nemotron-3.5-super-vl:free"
ORION_VOICE_ENABLED=true
ORION_TTS_VOICE="en-GB-RyanNeural"
ORION_USER_TITLE="Sir"
```
*(Note: If `OPENROUTER_API_KEY` is omitted, ORION will automatically run in local sandbox test mode).*

### 3. Launch ORION
```bash
python run_orion.py
```
- The local FastAPI backend starts on `127.0.0.1:8765`.
- The Wispr Flow floating pill appears anchored at the bottom-center of your screen.
- J.A.R.V.I.S. speaks: *"Project ORION is online and at your service, Sir."*

---

## 4. Live Demo Walkthrough

### Test Case: Autonomous Linter Verification & Code Repair
1. Open `demo_workspace/buggy_calc.py` in your code editor or on screen. Notice line 13 has a deliberate indentation error (`E999`).
2. Hold **`[Alt + Space]`** (or click the 🎙️ mic button in the HUD).
3. Say: *"Fix the indentation error in buggy_calc.py"* (or click the ⌨️ keyboard icon and type it silently).
4. Release `Alt + Space`.
5. **Watch the Execution Loop in Real Time:**
   - **HUD State:** Turns Amber (`Analyzing screen & workspace context via Nemotron-VL...`).
   - **ACI Action:** Model issues `edit_lines` on `buggy_calc.py`.
   - **Guardrail:** Flake8 automatically runs. If an error is detected, ORION reverts and self-corrects.
   - **Verification:** The HUD card expands with a green **`✓ Flake8 Verified`** badge and unified diff preview.
   - **J.A.R.V.I.S. Persona:** Speaks aloud in a composed British Butler tone: *"Right away, Sir. I have rectified the indentation error in buggy calc and verified it with Flake8."*

---

## 5. Slide 9 Presentation Content

```markdown
### SLIDE 9: System Architecture & Verification Loop (Group S.T.A.R.K.)

#### Title:
**Project ORION: Multimodal OS-Wide Agent-Computer Interface**

#### Key Value Proposition:
Transitioning from an IDE-locked sidebar chatbot to a zero-friction, ambient OS HUD powered by NVIDIA Nemotron-3.5-Super-VL and SWE-agent ACI.

#### Architecture Pillars:
1. **Wispr Flow Ambient HUD:** Frameless, non-focus-stealing PyQt6 pill overlay; global push-to-talk (`Alt+Space`) via low-overhead OS hooks.
2. **Multimodal Grounding:** Transmits synchronized 1280px JPEG display snapshots, active window metadata, and clipboard state directly to the VLM.
3. **SWE-Agent ACI Layer:** Deterministic tools (`open_file`, `edit_lines`, `search_workspace`, `type_or_paste_text`) replace vulnerable bash execution.
4. **Flake8 Linter Guardrail:** Automatic pre-commit verification (`F821, E111-113, E999`) with instant rollback and autonomous 2-step self-correction.
5. **J.A.R.V.I.S. Neural Voice:** Low-latency British Butler TTS (`edge-tts` / `pyttsx3`) with instant push-to-talk barge-in interruption.
```
