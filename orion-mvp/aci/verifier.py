"""
Project ORION - Flake8 Linter Guardrail & Verification Loop
Enforces syntax and indentation integrity on Python files before accepting edits.
"""

import ast
import subprocess
import sys
from pathlib import Path
from typing import Tuple


FLAKE8_SELECT_CODES = "F821,F822,F831,E111,E112,E113,E999,E902"


def run_flake8_guardrail(file_path: str | Path) -> Tuple[bool, str]:
    """
    Executes flake8 with strict isolated selection:
    F821: undefined name
    F822: undefined name in __all__
    F831: duplicate argument name in function definition
    E111: indentation is not a multiple of four
    E112: expected an indented block
    E113: unexpected indentation
    E999: SyntaxError
    E902: IOError/TokenError

    Returns:
        (is_valid: bool, error_message: str)
    """
    path = Path(file_path)
    if not path.exists():
        return False, f"File does not exist: {path}"

    if not path.suffix.lower() == ".py":
        return True, ""

    # Attempt running flake8 via sys.executable -m flake8 or direct flake8 executable
    cmd = [
        sys.executable,
        "-m",
        "flake8",
        "--isolated",
        f"--select={FLAKE8_SELECT_CODES}",
        str(path.resolve()),
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        if proc.returncode == 0 and not stdout:
            return True, ""

        error_output = "\n".join(filter(None, [stdout, stderr]))
        return False, error_output

    except FileNotFoundError:
        # Fallback to direct AST validation if flake8 is not in environment
        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()
            ast.parse(source, filename=str(path))
            return True, ""
        except SyntaxError as e:
            return False, f"SyntaxError: {e.msg} at line {e.lineno}:{e.offset} ({path.name})"
        except Exception as e:
            return False, f"Verification failed with error: {str(e)}"
    except subprocess.TimeoutExpired:
        return False, "Verification timed out after 10 seconds."
    except Exception as e:
        return False, f"Unexpected error during verification: {str(e)}"
