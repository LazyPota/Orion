"""
Project ORION - SWE-Agent Style Agent-Computer Interface (ACI) Tools
Provides deterministic, verified interaction with files, workspace, browser, and OS clipboard.
"""

import difflib
import os
import re
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any, Dict

import pyperclip

from .verifier import run_flake8_guardrail
from config import config


def resolve_path(path_str: str) -> Path:
    """Safely resolves path relative to workspace or cwd."""
    p = Path(path_str)
    if p.is_absolute():
        return p
    # If path directly exists relative to cwd (e.g. ./demo_workspace or demo_workspace/buggy_calc.py)
    if p.exists():
        return p.resolve()
    # Otherwise resolve relative to configured workspace
    ws_path = (config.ORION_WORKSPACE_DIR / p).resolve()
    if ws_path.exists():
        return ws_path
    return ws_path


def open_file(path: str, line_start: int = 1, window_size: int = 100) -> Dict[str, Any]:
    """
    Opens a file and returns up to 100 lines with 1-indexed line numbers.
    Includes metadata on total lines and omitted lines above/below.
    """
    try:
        file_path = resolve_path(path)
        if not file_path.exists():
            return {
                "status": "error",
                "message": f"File not found: {path} (resolved: {file_path})",
            }
        if not file_path.is_file():
            return {
                "status": "error",
                "message": f"Path is not a regular file: {path}",
            }

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)
        if line_start < 1:
            line_start = 1

        start_idx = line_start - 1
        end_idx = min(start_idx + window_size, total_lines)

        slice_lines = lines[start_idx:end_idx]
        formatted_content = "".join(
            f"{i + start_idx + 1:4d}: {line}" for i, line in enumerate(slice_lines)
        )

        lines_above = start_idx
        lines_below = max(0, total_lines - end_idx)

        return {
            "status": "success",
            "file_path": str(file_path),
            "line_start": line_start,
            "line_end": end_idx,
            "total_lines": total_lines,
            "lines_omitted_above": lines_above,
            "lines_omitted_below": lines_below,
            "content": formatted_content,
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to open file {path}: {str(e)}"}


def edit_lines(
    path: str, start_line: int, end_line: int, replacement_text: str
) -> Dict[str, Any]:
    """
    Replaces lines start_line to end_line (1-indexed, inclusive) with replacement_text.
    Immediately verifies Python files with flake8. If syntax/indentation errors occur,
    reverts the change automatically and returns detailed error feedback.
    """
    try:
        file_path = resolve_path(path)
        if not file_path.exists():
            return {"status": "error", "message": f"File does not exist: {path}"}

        with open(file_path, "r", encoding="utf-8") as f:
            original_lines = f.readlines()

        total_original = len(original_lines)
        if start_line < 1:
            start_line = 1
        if end_line > total_original:
            end_line = total_original
        if start_line > end_line and total_original > 0:
            return {
                "status": "error",
                "message": f"Invalid line range: {start_line} to {end_line}",
            }

        # Format replacement text into lines
        if replacement_text and not replacement_text.endswith("\n"):
            replacement_text += "\n"
        replacement_lines = (
            replacement_text.splitlines(keepends=True) if replacement_text else []
        )

        # Original snippet for diff/feedback
        orig_slice = original_lines[start_line - 1 : end_line]
        original_snippet = "".join(
            f"{start_line + i}: {line}" for i, line in enumerate(orig_slice)
        )
        attempted_snippet = replacement_text

        # Construct modified file content
        new_lines = (
            original_lines[: start_line - 1]
            + replacement_lines
            + original_lines[end_line:]
        )

        # Write attempted edit to file
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        # Run Verification Loop if Python file
        if file_path.suffix.lower() == ".py":
            passed, linter_output = run_flake8_guardrail(file_path)
            if not passed:
                # REVERT IMMEDIATELY
                with open(file_path, "w", encoding="utf-8") as f:
                    f.writelines(original_lines)

                return {
                    "status": "syntax_error",
                    "reverted": True,
                    "file_path": str(file_path),
                    "linter_errors": linter_output,
                    "original_snippet": original_snippet,
                    "attempted_snippet": attempted_snippet,
                    "message": (
                        f"Linter detected syntax/indentation error. Edit was reverted automatically. "
                        f"Flake8 output: {linter_output}"
                    ),
                }

        # Diff preview
        diff = list(
            difflib.unified_diff(
                orig_slice,
                replacement_lines,
                fromfile=f"a/{file_path.name} (L{start_line}-L{end_line})",
                tofile=f"b/{file_path.name}",
                lineterm="",
            )
        )
        diff_preview = "\n".join(diff) if diff else "No textual difference"

        # Read updated surrounding window
        window_start = max(1, start_line - 5)
        window = open_file(str(file_path), line_start=window_start, window_size=30)

        return {
            "status": "success",
            "file_path": str(file_path),
            "diff_preview": diff_preview,
            "start_line": start_line,
            "end_line": end_line,
            "updated_window": window.get("content", ""),
            "message": f"Successfully edited lines {start_line}-{end_line} in {file_path.name}. Flake8 verified.",
        }

    except Exception as e:
        return {"status": "error", "message": f"Failed to edit {path}: {str(e)}"}


def search_workspace(
    query: str, directory: str = "./demo_workspace", max_results: int = 25
) -> Dict[str, Any]:
    """
    Fast regex workspace search returning file paths, line numbers, and matching line content.
    """
    try:
        base_dir = resolve_path(directory)
        if not base_dir.exists():
            return {
                "status": "error",
                "message": f"Directory not found: {directory}",
            }

        pattern = re.compile(re.escape(query), re.IGNORECASE)
        results = []

        for root, _, files in os.walk(base_dir):
            if any(
                part.startswith(".") or part == "__pycache__"
                for part in Path(root).parts
            ):
                continue
            for file in files:
                file_path = Path(root) / file
                try:
                    with open(
                        file_path, "r", encoding="utf-8", errors="ignore"
                    ) as f:
                        for lineno, line in enumerate(f, 1):
                            if pattern.search(line):
                                results.append(
                                    {
                                        "file": str(
                                            file_path.relative_to(base_dir)
                                        ),
                                        "line_number": lineno,
                                        "line": line.strip(),
                                    }
                                )
                                if len(results) >= max_results:
                                    break
                except Exception:
                    continue
                if len(results) >= max_results:
                    break

        return {
            "status": "success",
            "query": query,
            "match_count": len(results),
            "matches": results,
        }
    except Exception as e:
        return {"status": "error", "message": f"Workspace search failed: {str(e)}"}


def type_or_paste_text(text: str) -> Dict[str, Any]:
    """
    Copies synthesized output to OS clipboard so user can dictate or paste
    into any active application (browser, editor, Notion, Discord).
    """
    try:
        pyperclip.copy(text)
        preview = text[:80] + "..." if len(text) > 80 else text
        return {
            "status": "success",
            "action": "copied_to_clipboard",
            "preview": preview,
            "char_count": len(text),
            "message": f"Copied {len(text)} characters to clipboard for instant pasting.",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to copy to clipboard: {str(e)}",
        }


def open_web_url(url_or_query: str) -> Dict[str, Any]:
    """
    Opens documentation or search query in default web browser.
    """
    try:
        target = url_or_query.strip()
        if not (target.startswith("http://") or target.startswith("https://")):
            encoded = urllib.parse.quote_plus(target)
            target = f"https://www.google.com/search?q={encoded}"

        webbrowser.open(target)
        return {
            "status": "success",
            "url": target,
            "message": f"Opened {target} in OS browser.",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to open URL: {str(e)}"}


def write_markdown_note(filename: str, content: str) -> Dict[str, Any]:
    """
    Writes structured research/study markdown notes into notes directory.
    """
    try:
        notes_dir = (config.ORION_WORKSPACE_DIR / "notes").resolve()
        notes_dir.mkdir(parents=True, exist_ok=True)

        if not filename.endswith(".md"):
            filename += ".md"

        target_file = notes_dir / Path(filename).name
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "status": "success",
            "file_path": str(target_file),
            "message": f"Saved research note to {target_file.name}",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to write note: {str(e)}"}


def execute_aci_tool(action: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatch function executing requested ACI tool safely.
    """
    action = action.strip().lower()

    if action == "open_file":
        return open_file(
            path=args.get("path", ""),
            line_start=int(args.get("line_start", 1)),
        )
    elif action == "edit_lines":
        return edit_lines(
            path=args.get("path", ""),
            start_line=int(args.get("start_line", 1)),
            end_line=int(args.get("end_line", 1)),
            replacement_text=args.get(
                "replacement_text", args.get("replacement", "")
            ),
        )
    elif action == "search_workspace":
        return search_workspace(
            query=args.get("query", ""),
            directory=args.get("directory", str(config.ORION_WORKSPACE_DIR)),
        )
    elif action == "type_or_paste_text":
        return type_or_paste_text(text=args.get("text", ""))
    elif action == "open_web_url":
        return open_web_url(
            url_or_query=args.get(
                "url_or_query", args.get("url", args.get("query", ""))
            )
        )
    elif action == "write_markdown_note":
        return write_markdown_note(
            filename=args.get("filename", "note.md"),
            content=args.get("content", ""),
        )
    elif action in ("answer_only", "none", "noop"):
        return {
            "status": "success",
            "action": "answer_only",
            "message": args.get(
                "message", "Direct response provided without modifying files."
            ),
        }
    else:
        return {
            "status": "error",
            "message": f"Unknown ACI tool: '{action}'. Allowed: open_file, edit_lines, search_workspace, type_or_paste_text, open_web_url, write_markdown_note, answer_only",
        }
