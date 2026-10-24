"""
Comprehensive verification test for Project ORION MVP.
Tests:
1. Config validation
2. Flake8 guardrail & auto-revert
3. ACI tools (open_file, edit_lines, search_workspace, type_or_paste_text)
4. Context capture (window title, screen capture, clipboard)
5. J.A.R.V.I.S. voice sanitization & offline/online TTS
6. Dual Action Parser on multiple response formats
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import config
from aci.verifier import run_flake8_guardrail
from aci.tools import open_file, edit_lines, search_workspace, type_or_paste_text
from voice.jarvis_tts import clean_for_speech, get_voice_engine
from trigger.context_capture import get_active_window_title, capture_screen_base64, capture_os_context
from backend.openrouter_client import parse_agent_response


def test_all():
    print("=== 1. Testing Configuration ===")
    assert config.config.OPENROUTER_MODEL == "nvidia/nemotron-3.5-super-vl:free"
    print("✓ Model:", config.config.OPENROUTER_MODEL)
    print("✓ Backend Port:", config.config.BACKEND_PORT)

    print("\n=== 2. Testing Flake8 Guardrail on buggy_calc.py ===")
    passed, error = run_flake8_guardrail("demo_workspace/buggy_calc.py")
    assert not passed, "Flake8 should have caught the deliberate indentation error!"
    print("✓ Deliberate error caught successfully:")
    print("  ", error.strip().split("\n")[0])

    print("\n=== 3. Testing ACI Tools ===")
    # Test open_file
    open_res = open_file("buggy_calc.py", line_start=1, window_size=20)
    assert open_res["status"] == "success"
    assert "calculate_discount" in open_res["content"]
    print("✓ open_file succeeded, read lines 1-20")

    # Test search_workspace
    search_res = search_workspace("calculate_discount")
    assert search_res["status"] == "success"
    assert search_res["match_count"] > 0
    print("✓ search_workspace succeeded, matches:", search_res["match_count"])

    # Test type_or_paste_text
    paste_res = type_or_paste_text("Testing Project ORION clipboard integration.")
    assert paste_res["status"] == "success"
    print("✓ type_or_paste_text succeeded")

    # Test edit_lines with invalid syntax (should auto-revert)
    bad_edit_res = edit_lines(
        "buggy_calc.py",
        start_line=1,
        end_line=2,
        replacement_text="def broken_syntax(:\n    pass\n",
    )
    assert bad_edit_res["status"] == "syntax_error"
    assert bad_edit_res["reverted"] is True
    print("✓ edit_lines auto-revert on syntax error verified!")

    print("\n=== 4. Testing Context Capture ===")
    active_win = get_active_window_title()
    print("✓ Active window title:", active_win)

    sct_b64 = capture_screen_base64()
    if sct_b64:
        print(f"✓ Screenshot captured & compressed: {len(sct_b64)} b64 chars")
    else:
        print("ℹ Running headless/virtual display, screenshot skipped gracefully")

    full_ctx = capture_os_context(include_screenshot=False)
    assert "active_window" in full_ctx
    print("✓ Full OS context compiled successfully")

    print("\n=== 5. Testing J.A.R.V.I.S. Voice Sanitization ===")
    raw_markdown = "**Right away**, `Sir`. I have patched `buggy_calc.py` (L12-14) and verified with #Flake8! Check http://localhost:8765"
    cleaned = clean_for_speech(raw_markdown)
    print("✓ Raw:", raw_markdown)
    print("✓ Cleaned for speech:", cleaned)
    assert "**" not in cleaned
    assert "`" not in cleaned
    assert "#" not in cleaned
    assert "dot py" in cleaned

    print("\n=== 6. Testing Dual Action Parser ===")
    # Case A: Markdown code fence
    markdown_payload = {
        "choices": [
            {
                "message": {
                    "content": '```json\n{\n  "thought": "Screen shows broken calculator indentation.",\n  "action": "edit_lines",\n  "args": {"path": "buggy_calc.py", "start_line": 13, "end_line": 13, "replacement_text": "    final_price = price - discount_amount\\n"},\n  "summary_for_user": "Fixing indentation on line 13",\n  "spoken_response": "Right away, Sir. Correcting indentation in buggy calc."\n}\n```'
                }
            }
        ]
    }
    action_a = parse_agent_response(markdown_payload)
    assert action_a.action == "edit_lines"
    assert action_a.args.get("start_line") == 13
    print("✓ Case A (Markdown ```json): Successfully parsed action", action_a.action)

    # Case B: Native OpenAI tool_calls
    tool_calls_payload = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "name": "open_file",
                                "arguments": '{"path": "buggy_calc.py", "line_start": 1}',
                            }
                        }
                    ]
                }
            }
        ]
    }
    action_b = parse_agent_response(tool_calls_payload)
    assert action_b.action == "open_file"
    print("✓ Case B (Native tool_calls): Successfully parsed action", action_b.action)

    print("\n==========================================")
    print("🎉 ALL 6 COMPONENT INTEGRATION TESTS PASSED!")
    print("==========================================")


if __name__ == "__main__":
    test_all()
