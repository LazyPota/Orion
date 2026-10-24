"""
Unit and Integration Tests for Project ORION WhatsApp Report Intelligence MVP.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient

from config import config
from backend.prompts import extract_contact_name
from backend.openrouter_client import parse_vlm_report_response, save_report_to_disk
from automation.whatsapp_agent import load_fallback_chat
from backend.server import app

client = TestClient(app)


def test_contact_name_extraction():
    print("=== 1. Testing Contact Name Extraction ===")
    test_cases = [
        ("Check WhatsApp messages from Derrian", "Derrian"),
        ("Open chat with Group Stark", "Group Stark"),
        ("See messages from Mom on whatsapp", "Mom"),
        ("Read chat from Alex", "Alex"),
        ("What did Professor Davis say on WhatsApp?", "Professor Davis"),
        ("Derrian on WhatsApp", "Derrian"),
        ("Derrian", "Derrian"),
    ]

    for query, expected in test_cases:
        extracted = extract_contact_name(query)
        print(f"  Query: '{query}' -> Extracted: '{extracted}'")
        assert expected.lower() in extracted.lower(), f"Failed for '{query}': got '{extracted}'"
    print("✓ All contact name extraction tests passed!\n")


def test_stage_fallback_chat():
    print("=== 2. Testing Stage-Safe Fallback Chat ===")
    fallback = load_fallback_chat("Derrian")
    assert fallback["status"] == "fallback"
    assert fallback["contact_name"] == "Derrian"
    assert "Derrian" in fallback["raw_chat_text"]
    assert "Slide 9" in fallback["raw_chat_text"]
    assert fallback["is_fallback"] is True
    print("✓ Fallback chat log generated with customized sender name!\n")


def test_dual_vlm_parser():
    print("=== 3. Testing Dual VLM Parser ===")
    sample_json = {
        "choices": [
            {
                "message": {
                    "content": """```json
{
  "contact_name": "Derrian",
  "spoken_response": "Right away, Sir. Derrian confirmed the backend is operational and asked for your review of Slide 9.",
  "report_markdown": "## 📋 WhatsApp Intelligence Report: Derrian\\n\\n### Executive Summary\\nDerrian verified the system.\\n\\n### Key Points & Updates\\n- FastAPI routes active.\\n\\n### Action Items & Deadlines\\n- [ ] Review Slide 9 before 8 PM."
}
```"""
                }
            }
        ]
    }

    parsed = parse_vlm_report_response(sample_json, fallback_contact="Derrian")
    assert parsed.contact_name == "Derrian"
    assert "Slide 9" in parsed.spoken_response
    assert "### Executive Summary" in parsed.report_markdown
    print("✓ Dual VLM response parser successfully extracted JSON payload!\n")


def test_report_disk_saving():
    print("=== 4. Testing Report Disk Saving ===")
    md_content = "## Test Report\n\nSample intelligence content."
    saved_path = save_report_to_disk("TestContact", md_content)
    assert saved_path.exists()
    with open(saved_path, "r", encoding="utf-8") as f:
        read_content = f.read()
    assert read_content == md_content
    print(f"✓ Report successfully written to disk: {saved_path.name}\n")


def test_fastapi_endpoints():
    print("=== 5. Testing FastAPI WhatsApp Report Endpoints ===")
    # 1. Health check
    h_resp = client.get("/api/v1/health")
    assert h_resp.status_code == 200
    h_data = h_resp.json()
    assert h_data["status"] == "online"
    assert "WhatsApp" in h_data["service"]
    print("✓ Health check online:", h_data["service"])

    # 2. WhatsApp report endpoint (stage fallback / live test)
    cmd_payload = {
        "user_command": "Check WhatsApp messages from Derrian",
    }
    r_resp = client.post("/api/v1/whatsapp-report", json=cmd_payload)
    assert r_resp.status_code == 200
    report_data = r_resp.json()
    assert report_data["contact_name"] == "Derrian"
    assert report_data["spoken_response"]
    assert "Executive Summary" in report_data["report_markdown"]
    print("✓ WhatsApp report endpoint generated complete briefing!")
    print(f"  Spoken response: \"{report_data['spoken_response']}\"")
    print(f"  Saved file: {report_data.get('report_file_path')}\n")

    print("==================================================")
    print("🎉 ALL WHATSAPP REPORT INTELLIGENCE TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    test_contact_name_extraction()
    test_stage_fallback_chat()
    test_dual_vlm_parser()
    test_report_disk_saving()
    test_fastapi_endpoints()
