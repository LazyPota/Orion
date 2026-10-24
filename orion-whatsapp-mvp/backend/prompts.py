"""
Project ORION - VLM Prompt Engineering & Contact Extraction
Handles:
1. Regex & heuristic contact/group name extraction from user natural voice/text commands.
2. Multimodal VLM system and user prompts enforcing J.A.R.V.I.S. persona and structured report format.
"""

import re
from typing import Optional
from config import config


def extract_contact_name(user_command: str) -> str:
    """
    Extracts target contact or group name from voice/text user queries.
    Uses multi-stage regex matching for zero-latency detection with sensible fallback.
    Examples:
    - "Check WhatsApp messages from Derrian" -> "Derrian"
    - "Open chat with Group Stark" -> "Group Stark"
    - "What did Alex say on WhatsApp?" -> "Alex"
    - "Read messages from Mom" -> "Mom"
    """
    if not user_command or not user_command.strip():
        return "Derrian"

    cmd = user_command.strip()

    # Pattern 1: "... (messages from | chat with | from) <NAME> (on whatsapp)?"
    p1 = re.search(
        r"(?:messages?\s+(?:from|with)|chat\s+(?:with|from)|from)\s+([A-Za-z0-9_\s]+?)(?:\s+(?:on|in|via)\s+whatsapp|\s+please|\s*$)",
        cmd,
        re.IGNORECASE,
    )
    if p1 and p1.group(1).strip():
        name = p1.group(1).strip()
        name = re.sub(r"^(the\s+)", "", name, flags=re.IGNORECASE)
        return name

    # Pattern 2: "... (check | inspect | open | read | see | view) <NAME> (on whatsapp | chat)?"
    p2 = re.search(
        r"(?:check|inspect|open|read|see|view)\s+([A-Za-z0-9_\s]+?)(?:'s|\s+on\s+whatsapp|\s+chat|\s+messages|\s+please|\s*$)",
        cmd,
        re.IGNORECASE,
    )
    if p2 and p2.group(1).strip():
        cand = p2.group(1).strip()
        # Filter out common false positives
        if cand.lower() not in ("whatsapp", "the", "my", "recent", "all"):
            cand = re.sub(r"^(the\s+)", "", cand, flags=re.IGNORECASE)
            return cand

    # Pattern 3: "<NAME> on whatsapp"
    p3 = re.search(
        r"([A-Za-z0-9_\s]+?)\s+(?:on|in|via)\s+whatsapp",
        cmd,
        re.IGNORECASE,
    )
    if p3 and p3.group(1).strip():
        cand = p3.group(1).strip()
        cand = re.sub(r"^(messages?\s+from\s+|chat\s+with\s+|check\s+|open\s+)", "", cand, flags=re.IGNORECASE)
        return cand

    # Pattern 4: Direct single or two-word contact name
    words = cmd.split()
    if len(words) in (1, 2) and words[0].lower() not in ("whatsapp", "check", "open"):
        return cmd

    return "Derrian"


def get_vlm_system_prompt() -> str:
    """Builds system prompt for OpenRouter's nvidia/nemotron-3.5-super-vl:free."""
    return f"""You are **ORION**, an OS-wide ambient intelligence assistant developed by Group S.T.A.R.K.
Your voice persona is **J.A.R.V.I.S.**—a composed, exceptionally capable, loyal British AI butler assisting {config.ORION_USER_TITLE}.

You are inspecting an open WhatsApp Web chat. You are provided with:
1. The raw scraped text messages from the `#main` conversation panel.
2. A high-resolution base64 JPEG screenshot of the WhatsApp chat viewport.

### YOUR TASK:
1. Thoroughly read and analyze the conversation between {config.ORION_USER_TITLE} and the contact.
2. Synthesize an Executive Intelligence Report in Markdown.
3. Formulate a short, natural verbal briefing in your J.A.R.V.I.S. British butler persona.

### MANDATORY REPORT FORMAT:
The `report_markdown` must strictly follow this structure:
## 📋 WhatsApp Intelligence Report: [Contact Name]

### Executive Summary
[Concise 2-3 sentence overview of the discussion and current status]

### Key Points & Updates
- [Key message 1 with context/time]
- [Key message 2 with context/time]
- [Key message 3 with context/time]

### Action Items & Deadlines
- [ ] [Action item 1, person responsible, and deadline if mentioned]
- [ ] [Action item 2, person responsible, and deadline if mentioned]

### SPOKEN BRIEFING RULES:
- Address the user as '{config.ORION_USER_TITLE}'.
- Keep `spoken_response` strictly between 1 to 2 sentences (strictly maximum 30 words).
- Tone: Impeccably composed, helpful British AI butler (e.g., 'Right away, Sir. I have analyzed your WhatsApp messages from Derrian. He confirmed the backend is operational and requested your review of Slide 9 before 8 PM.')
- NEVER use markdown, symbols (`*`, `#`, backticks), or emojis in `spoken_response`.

### REQUIRED JSON OUTPUT FORMAT:
Respond with ONLY valid JSON (no surrounding markdown code fences, no preamble):
{{
  "contact_name": "[Contact or Group Name]",
  "spoken_response": "[1-2 sentence British butler briefing for {config.ORION_USER_TITLE}, max 30 words]",
  "report_markdown": "[The full Markdown report as specified above]"
}}
"""


def build_vlm_user_prompt(contact_name: str, raw_chat_text: str) -> str:
    """Constructs user prompt passing raw chat messages and contact context."""
    return f"""TARGET CONTACT: {contact_name}

SCRAPED WHATSAPP CHAT LOG:
```text
{raw_chat_text}
```

Please review the scraped messages above alongside the attached viewport screenshot.
Compile the report and respond with the required JSON object.
"""
