"""
Tests FastAPI endpoints for Project ORION.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from backend.server import app

client = TestClient(app)


def test_api():
    print("=== Testing FastAPI Endpoints ===")

    # 1. /api/v1/health
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    print("✓ Health check status:", data["status"])
    print("✓ Configured model:", data["model"])

    # 2. /api/v1/act with sandbox mock
    payload = {
        "user_query": "Please open buggy_calc.py",
        "active_window": "VSCode",
        "clipboard_text": "",
        "screenshot_b64": None,
        "workspace_context": {},
        "history": [],
    }
    resp = client.post("/api/v1/act", json=payload)
    assert resp.status_code == 200
    act_data = resp.json()
    print("✓ Act endpoint response status: 200")
    print("✓ Act action executed:", act_data["action"])
    print("✓ Summary for user:", act_data["summary_for_user"])
    print("✓ Spoken response:", act_data["spoken_response"])

    print("\n🎉 ALL API ENDPOINTS VERIFIED SUCCESSFULLY!")


if __name__ == "__main__":
    test_api()
