"""
Project ORION - One-Time WhatsApp Web Session Setup
Launches persistent Chromium context so the user can scan the QR code once before the presentation.
The login session is stored in ./whatsapp_session and persists across runs.
"""

import asyncio
import os
import sys
from pathlib import Path

from config import config


async def setup_whatsapp_login():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[Error] Playwright is not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    session_path = config.WHATSAPP_SESSION_DIR.resolve()
    session_path.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("  PROJECT ORION — ONE-TIME WHATSAPP QR CODE SETUP")
    print("  Group S.T.A.R.K. | Persistent Session Initializer")
    print("=" * 65)
    print(f"  • Session Directory: {session_path}")
    print("  • Instructions:")
    print("    1. Chromium is opening to https://web.whatsapp.com.")
    print("    2. On your phone: Open WhatsApp -> Linked Devices -> Link a Device.")
    print("    3. Point your phone camera at the QR code on the screen.")
    print("    4. Once scanned, ORION will detect the chat list and save your session!")
    print("=" * 65)

    async with async_playwright() as p:
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

        print("\nNavigating to https://web.whatsapp.com...")
        await page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")

        print("Waiting for QR code scan and chat list (#pane-side)...")
        print("(You have 120 seconds to scan the QR code)")

        try:
            # Wait for the main WhatsApp chat panel to load after QR scan
            await page.wait_for_selector("#pane-side", timeout=120000)
            print("\n" + "=" * 65)
            print("  ✓ WhatsApp Session Saved Successfully!")
            print("  You are now ready for the live presentation.")
            print("  Your login will automatically persist when ORION runs.")
            print("=" * 65)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"\n[Warning] Timed out waiting for login: {e}")
            print("If you already scanned, you can verify by re-running this script.")
        finally:
            await browser_context.close()


def main():
    asyncio.run(setup_whatsapp_login())


if __name__ == "__main__":
    main()
