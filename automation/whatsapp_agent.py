"""
Project ORION - WhatsApp Web Playwright Automation
Automates WhatsApp Web in persistent Chromium context:
1. Opens WhatsApp Web with persistent profile (./whatsapp_session).
2. Searches contact or group via resilient selectors.
3. Scrapes visible messages from #main.
4. Captures base64 JPEG screenshot of chat viewport.
5. Smoothly falls back to realistic demo data if offline or timeout.
"""

import asyncio
import base64
import io
import re
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image

from config import config
from trigger.context_capture import capture_screen_base64


def load_fallback_chat(contact_name: str) -> Dict[str, Any]:
    """
    Stage-Safe Demo Fallback:
    Loads realistic chat log from demo_data/sample_whatsapp_chat.txt,
    replaces default sender 'Derrian' with requested contact_name,
    and captures primary monitor screenshot so the presentation never stalls.
    """
    print(f"[Stage-Safe Fallback] Activating demo fallback for contact: '{contact_name}'")

    chat_text = (
        f"[10:14 AM, 10/24/2026] {contact_name}: Hey team, just pushed the latest FastAPI endpoints for Project ORION.\n"
        f"[10:16 AM, 10/24/2026] Muhammad Rafli Putra: Great work! How are the VLM routing and Nemotron integration looking?\n"
        f"[10:18 AM, 10/24/2026] {contact_name}: Multi-modal prompt router is working smoothly. Scraped text and screenshot are processed with zero latency spikes.\n"
        f"[10:21 AM, 10/24/2026] {contact_name}: Verified J.A.R.V.I.S. voice synthesis using edge-tts. Very crisp and natural British accent.\n"
        f"[10:25 AM, 10/24/2026] {contact_name}: Action item for you Rafli: please review Slide 9 for the presentation before 8:00 PM tonight.\n"
        f"[10:28 AM, 10/24/2026] {contact_name}: Also make sure WhatsApp persistent session is scanned so we don't have to scan the QR code live in front of the audience.\n"
        f"[10:30 AM, 10/24/2026] Muhammad Rafli Putra: Understood. I'll test the Wispr HUD pill now.\n"
        f"[10:32 AM, 10/24/2026] {contact_name}: Perfect. Let's do a dry run at 3:00 PM. See you then!"
    )

    if config.DEMO_DATA_FILE.exists():
        try:
            with open(config.DEMO_DATA_FILE, "r", encoding="utf-8") as f:
                raw_template = f.read()
            if raw_template.strip():
                # Replace Derrian with contact_name if different
                chat_text = re.sub(r"\bDerrian\b", contact_name, raw_template)
        except Exception as e:
            print(f"[Warning] Error reading demo data file: {e}")

    screenshot_b64 = capture_screen_base64() or ""

    return {
        "status": "fallback",
        "contact_name": contact_name,
        "raw_chat_text": chat_text,
        "screenshot_b64": screenshot_b64,
        "is_fallback": True,
        "message": f"Stage-Safe Demo Fallback: compiled realistic messages from {contact_name}",
    }


async def fetch_whatsapp_chat(contact_name: str) -> Dict[str, Any]:
    """
    Automates WhatsApp Web in persistent Chromium browser:
    - Opens https://web.whatsapp.com
    - Searches for contact_name
    - Extracts visible message text from #main
    - Captures high-res JPEG viewport screenshot
    - If WhatsApp is unreachable or timeout occurs, smoothly falls back to demo data.
    """
    clean_contact = contact_name.strip()
    if not clean_contact:
        clean_contact = "Derrian"

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[Warning] Playwright not installed. Falling back to demo data.")
        return load_fallback_chat(clean_contact)

    session_path = config.WHATSAPP_SESSION_DIR.resolve()
    session_path.mkdir(parents=True, exist_ok=True)

    try:
        async with async_playwright() as p:
            # Launch persistent browser so user stays logged in
            browser_context = await p.chromium.launch_persistent_context(
                user_data_dir=str(session_path),
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                ],
                viewport=None,
            )

            page = browser_context.pages[0] if browser_context.pages else await browser_context.new_page()

            # 1. Navigate to WhatsApp Web
            print(f"[WhatsApp Agent] Opening WhatsApp Web for contact: '{clean_contact}'...")
            try:
                await page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=12000)
            except Exception as e:
                print(f"[Warning] Navigation timeout/error: {e}")
                if config.DEMO_FALLBACK_MODE:
                    await browser_context.close()
                    return load_fallback_chat(clean_contact)
                raise e

            # 2. Check for chat sidebar (#pane-side)
            try:
                await page.wait_for_selector("#pane-side", timeout=config.WHATSAPP_TIMEOUT_SECONDS * 1000)
            except Exception:
                print("[WhatsApp Agent] '#pane-side' not detected (not logged in or slow connection).")
                if config.DEMO_FALLBACK_MODE:
                    await browser_context.close()
                    return load_fallback_chat(clean_contact)
                raise TimeoutError("WhatsApp Web was not logged in. Please run 'python setup_whatsapp_login.py' first.")

            # 3. Locate search box using resilient selectors
            search_input = None
            selectors = [
                'div[contenteditable="true"][data-tab="3"]',
                'div[role="textbox"]',
                'div[contenteditable="true"]',
            ]

            for sel in selectors:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        search_input = el
                        break
                except Exception:
                    continue

            if not search_input:
                # Try keyboard shortcut Ctrl+Alt+/ (WhatsApp shortcut to focus search)
                try:
                    await page.keyboard.press("Control+Alt+/")
                    await asyncio.sleep(0.5)
                except Exception:
                    pass

            if search_input:
                await search_input.click()
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                await search_input.fill(clean_contact)
                await asyncio.sleep(1.2)
                await page.keyboard.press("Enter")
            else:
                # Type directly into focused element
                await page.keyboard.type(clean_contact, delay=50)
                await asyncio.sleep(1.2)
                await page.keyboard.press("Enter")

            # Click matching contact card if enter did not immediately select
            await asyncio.sleep(1.5)
            try:
                contact_card = page.locator(f'span[title*="{clean_contact}" i]').first
                if await contact_card.is_visible(timeout=2000):
                    await contact_card.click()
            except Exception:
                pass

            # 4. Wait for main conversation container (#main)
            has_main = False
            try:
                await page.wait_for_selector("#main", timeout=6000)
                has_main = True
            except Exception:
                print(f"[WhatsApp Agent] '#main' chat container not found for '{clean_contact}'.")

            if not has_main:
                if config.DEMO_FALLBACK_MODE:
                    await browser_context.close()
                    return load_fallback_chat(clean_contact)
                raise RuntimeError(f"Could not open chat with '{clean_contact}' on WhatsApp Web.")

            # 5. Extract chat text from #main
            raw_chat_text = ""
            try:
                main_element = page.locator("#main")
                raw_chat_text = await main_element.inner_text()
            except Exception as e:
                print(f"[Warning] Could not extract text from #main: {e}")

            # 6. Capture browser screenshot
            screenshot_b64 = ""
            try:
                raw_bytes = await page.screenshot(type="jpeg", quality=config.SCREENSHOT_JPEG_QUALITY)
                img = Image.open(io.BytesIO(raw_bytes))
                img.thumbnail((config.SCREENSHOT_MAX_DIMENSION, 720), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=config.SCREENSHOT_JPEG_QUALITY)
                screenshot_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            except Exception as e:
                print(f"[Warning] Screenshot capture failed: {e}")
                screenshot_b64 = capture_screen_base64() or ""

            # Leave browser open for a moment so audience sees the chat, then close context
            await asyncio.sleep(1.5)
            await browser_context.close()

            return {
                "status": "success",
                "contact_name": clean_contact,
                "raw_chat_text": raw_chat_text,
                "screenshot_b64": screenshot_b64,
                "is_fallback": False,
                "message": f"Successfully scraped live messages and screenshot from '{clean_contact}'",
            }

    except Exception as e:
        print(f"[WhatsApp Agent] Automation error: {e}")
        if config.DEMO_FALLBACK_MODE:
            return load_fallback_chat(clean_contact)
        raise e
