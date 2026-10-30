"""Apply and undo the unified diffs in patches/ in pure Python (no `patch` program, works on Windows).

Exact matching only: every hunk's lines must be found as written, or nothing is changed.
"""

from __future__ import annotations

import re
from pathlib import Path

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")


def _parse(text: str) -> dict[str, list[tuple[list[str], list[str]]]]:
    """{file: [(old_lines, new_lines), ...]} from a unified diff."""
    files: dict[str, list] = {}
    current = hunk = None
    for line in text.splitlines():
        if line.startswith("+++ "):
            current = line[4:].split("\t")[0].removeprefix("b/")
            files[current] = []
        elif line.startswith("--- "):
            continue
        elif _HUNK.match(line) and current:
            hunk = ([], [])
            files[current].append(hunk)
        elif hunk is not None and line[:1] in (" ", "-", "+"):
            body = line[1:]
            if line[0] != "+":
                hunk[0].append(body)
            if line[0] != "-":
                hunk[1].append(body)
        elif hunk is not None and line == "":
            hunk[0].append("")
            hunk[1].append("")
    return files


def _find(lines: list[str], block: list[str]) -> int:
    for i in range(len(lines) - len(block) + 1):
        if lines[i:i + len(block)] == block:
            return i
    return -1


def _rewrite(root: Path, text: str, reverse: bool, dry: bool) -> bool:
    changed = {}
    for name, hunks in _parse(text).items():
        lines = (root / name).read_text().split("\n")
        for old, new in hunks:
            src, dst = (new, old) if reverse else (old, new)
            i = _find(lines, src)
            if i < 0:
                return False
            lines[i:i + len(src)] = dst
        changed[name] = "\n".join(lines)
    if not dry:
        for name, content in changed.items():
            (root / name).write_text(content)
    return True


def is_applied(root: Path, patch_file: Path) -> bool:
    """Every hunk's new text is present, and its old text is gone (unless the hunk only adds lines)."""
    for name, hunks in _parse(patch_file.read_text()).items():
        lines = (root / name).read_text().split("\n")
        for old, new in hunks:
            if _find(lines, new) < 0 or (_find(lines, old) >= 0 and not set(old) <= set(new)):
                return False
    return True


def set_applied(root: Path, patch_file: Path, on: bool) -> bool:
    if is_applied(root, patch_file) == on:
        return True
    return _rewrite(root, patch_file.read_text(), reverse=not on, dry=False)
