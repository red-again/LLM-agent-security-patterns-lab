"""Lab mode: you play the compromised model.

Workshop rule: assume the model is always fooled. Lab mode makes that literal.
labs/run.py plants YOUR text in one place an attacker can write to (an email,
an invite, a shared doc, a CFP abstract, or the user's own message). Then:

  * Any LLM call whose prompt contains your text is yours: you type its reply.
    The injection "worked" perfectly. That is the worst case for the defender.
  * Any LLM call your text never reached answers honestly (the offline mock,
    or a real model if one is configured). That is the pattern at work.
  * Free text you type as a model counts as your text too. If it flows into
    another model's prompt, you control that model as well. Replies that had
    to pass a schema (enums, numbers, booleans) do not carry your text on.

Real mode (`--real`) skips the takeover: a real model reads your planted text
and decides for itself, so you must write an injection that actually works.

Nothing here decides who wins. labs/labs.py looks at what HAPPENED (emails
sent, text shown to the user, which models your text reached) after the run.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field


@dataclass
class _State:
    active: bool = False
    real: bool = False
    slot: str = ""                                   # where the text was planted
    taint: list[str] = field(default_factory=list)   # text the attacker wrote
    replay: dict[str, list] = field(default_factory=dict)  # purpose -> queued replies
    typed: dict[str, list[str]] = field(default_factory=dict)  # what you replied, for replay
    events: list[dict] = field(default_factory=list)


STATE = _State()


def start(slot: str, text: str, real: bool = False, replay: dict | None = None) -> None:
    global STATE
    STATE = _State(active=True, real=real, slot=slot, taint=[text],
                   replay={k: list(v) for k, v in (replay or {}).items()})


def record(kind: str, **data) -> None:
    """Called by the world and the UI. Does nothing outside a lab."""
    if STATE.active:
        STATE.events.append({"kind": kind, **data})


# ------------------------------------------------------------------ taint
def _fragments(text: str) -> set[str]:
    """Lines of attacker text, raw and JSON-escaped (tool output is often JSON)."""
    out = set()
    for line in [text, *text.splitlines()]:
        line = line.strip()
        if len(line) >= 8:
            out |= {line, json.dumps(line)[1:-1]}
    return out


def _all_fragments() -> list[str]:
    return sorted({f for t in STATE.taint for f in _fragments(t)}, key=len, reverse=True)


def reached(messages: list[dict]) -> bool:
    blob = "\n".join(m["content"] for m in messages)
    return any(f in blob for f in _all_fragments())


def takeover(role: str, purpose: str, messages: list[dict]) -> bool:
    """True if the attacker writes this reply. Records every model the text reached."""
    if not STATE.active or not reached(messages):
        return False
    record("reached", role=role, purpose=purpose)
    return not STATE.real


# ------------------------------------------------------------- the reply
def _honest(purpose: str, messages: list[dict]) -> str:
    """What the offline mock says when it does NOT see the planted text."""
    from shared import mock_llm

    if STATE.slot == "user":  # the user is the attacker: an honest model still reads the request
        return mock_llm.respond(purpose, messages)
    frags = _all_fragments()
    scrubbed = []
    for m in messages:
        c = m["content"]
        for f in frags:
            c = c.replace(f, "")
        scrubbed.append({**m, "content": c})
    return mock_llm.respond(purpose, scrubbed)


def attacker_reply(role: str, purpose: str, messages: list[dict], structured: bool) -> str:
    honest = _honest(purpose, messages)
    queue = STATE.replay.get(purpose)
    if queue:
        r = queue.pop(0)
        reply = r if isinstance(r, str) else json.dumps(r)
    elif sys.stdin.isatty():
        reply = _ask(role, purpose, messages, honest)
    else:
        reply = honest
    STATE.typed.setdefault(purpose, []).append(reply)
    if not structured and reply.strip() != honest.strip():
        STATE.taint.append(reply)
    return reply


def read_multiline(prompt: str) -> str:
    """One line; end a line with a backslash to continue on the next."""
    lines = []
    while True:
        try:
            line = input(prompt if not lines else "    ... ")
        except EOFError:
            return "\n".join(lines)
        if line.endswith("\\"):
            lines.append(line[:-1])
            continue
        lines.append(line)
        return "\n".join(lines).strip()


def _clip(s: str, n: int) -> str:
    s = s.replace("\n", "\n            ")
    return s if len(s) <= n else s[: n - 3] + "..."


def _ask(role: str, purpose: str, messages: list[dict], honest: str) -> str:
    from shared import ui

    ui.emit("model_turn", role=role, purpose=purpose, messages=messages, honest=honest)
    ui._print(ui.bold(ui.red(f"\n>>> YOU ARE THE MODEL  ({role} LLM, purpose '{purpose}')")))
    ui._print(ui.red("    Your text is in this prompt, so the injection worked. You write the reply."))
    for m in [messages[0], messages[-1]] if len(messages) > 1 else messages:
        ui._print(ui.dim(f"    {m['role']:>9}> {_clip(m['content'], 700)}"))
    ui._print(ui.dim("     honest> ") + _clip(honest, 400))
    while True:
        line = read_multiline(ui.bold("    your reply as this model (Enter or 'honest' = honest reply, p = full prompt): "))
        if line.lower() == "p":
            for m in messages:
                ui._print(ui.dim(f"    {m['role']:>9}> {m['content']}"))
            continue
        return honest if line.lower() in ("", "honest", "h") else line
