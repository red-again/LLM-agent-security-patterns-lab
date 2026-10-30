"""What the web UI can run: built from the repo itself, so it never drifts from the code.

Only entries in this catalogue can be started from the browser.
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "08_secret_keeper"))

from labs.labs import LABS, SLOT_NAMES  # noqa: E402

import patching  # noqa: E402  (ui/patching.py)
from try_attacks import ASK, REWRITE, SPACED_VALUE, SPLIT, TRANSLATE  # noqa: E402

BIG, SMALL = "nvidia/nemotron-3-ultra-550b-a55b", "nvidia/nemotron-3.5-bolt-e4b"
# Model split per module, as tested (see each TUTORIAL.md). None = use .env as is.
MODELS = {"02": None, "03": (SMALL, SMALL), "04": (BIG, SMALL), "05": (BIG, SMALL)}


def _doc(path: Path) -> str:
    return ast.get_docstring(ast.parse(path.read_text())) or ""


def keeper_levels() -> list[dict]:
    attacks = {"A": ASK, "B": TRANSLATE, "C": SPACED_VALUE, "D": REWRITE, "E1": SPLIT[0], "E2": SPLIT[1]}
    out = []
    for f in sorted((ROOT / "08_secret_keeper").glob("level*.py")):
        doc = _doc(f)
        out.append({"id": f"keeper-{f.name[5]}", "level": int(f.name[5]), "file": str(f.relative_to(ROOT)),
                    "title": doc.splitlines()[0], "doc": doc})
    return [{**lv, "attacks": attacks} for lv in out]


def labs() -> list[dict]:
    out = []
    for lb in LABS.values():
        if lb.id not in MODELS:
            continue
        out.append({"id": f"lab-{lb.id}", "lab": lb.id, "title": lb.title, "story": lb.story,
                    "slot": SLOT_NAMES[lb.slot], "default_text": lb.default_text,
                    "targets": list(lb.targets), "goals": [{"id": g.id, "text": g.text} for g in lb.goals],
                    "hints": lb.hints, "defend": lb.defend, "models": MODELS[lb.id]})
    return out


def missions() -> list[dict]:
    return [{"id": f"play-{f.stem}", "file": str(f.relative_to(ROOT)), "code": f.read_text()}
            for f in sorted((ROOT / "labs" / "playground").glob("m*.py"))]


def _patch_file(name: str) -> Path:
    files = {f.name: f for f in (ROOT / "patches").glob("*.patch")}
    if name not in files:  # only names from that folder are accepted
        raise ValueError("unknown patch")
    return files[name]


def is_applied(name: str) -> bool:
    return patching.is_applied(ROOT, _patch_file(name))


def set_patch(name: str, on: bool) -> bool:
    """Apply or undo one patch from patches/ (pure Python, works on every OS)."""
    return patching.set_applied(ROOT, _patch_file(name), on)


TRACES = ROOT / "08_secret_keeper" / "traces"


def traces() -> list[dict]:
    files = sorted(TRACES.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [{"name": f.name, "size": f.stat().st_size} for f in files[:200]]


def trace(name: str) -> str:
    f = TRACES / name
    if f.parent != TRACES or f.suffix != ".md" or not f.is_file():
        raise ValueError("unknown trace")
    return f.read_text()


def patches() -> list[dict]:
    return [{"name": f.name, "module": f.name[:2], "applied": is_applied(f.name), "diff": f.read_text()}
            for f in sorted((ROOT / "patches").glob("*.patch"))]


def models_now() -> dict:
    from dotenv import dotenv_values

    env = {**dotenv_values(ROOT / ".env"), **os.environ}
    mock = str(env.get("MOCK_LLM", "")).lower() in ("1", "true", "yes") or not env.get("LLM_API_KEY")
    return {"LLM_MODEL": env.get("LLM_MODEL", ""), "QLLM_MODEL": env.get("QLLM_MODEL", ""), "mock": mock}


def full() -> dict:
    return {"keeper": keeper_levels(), "labs": labs(), "missions": missions(),
            "patches": patches(), "models": models_now(), "traces": traces()}
