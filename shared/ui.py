"""Console helpers so attendees can *see* trusted vs untrusted data on screen.

Colour code used across every demo:
  green  = trusted (the user, our own code)
  red    = UNTRUSTED (anything an attacker could have written)
  yellow = tool calls / actions with side effects
  cyan   = LLM calls
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import textwrap

from shared import lab

_COLOR = sys.stdout.isatty() and not os.getenv("NO_COLOR")
VERBOSE = os.getenv("VERBOSE", "0").lower() in ("1", "true", "yes")


# --------------------------------------------------------------------------
# Event stream for the web UI (ui/). Off unless ui/bridge.py installs a sink,
# so the terminal output is exactly the same with or without it.
# --------------------------------------------------------------------------
SINK = None  # a function(dict) -> None, set by ui/bridge.py


def _plain(v):
    """Make a value JSON-friendly for the UI."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (list, tuple, set)):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    return str(v)


def emit(kind: str, **data) -> None:
    if SINK is not None:
        SINK({"kind": kind, **{k: _plain(v) for k, v in data.items()}})


def _print(*args, **kwargs) -> None:
    """Terminal output. With the web UI attached, the event above replaces it (no duplicates)."""
    if SINK is None:
        print(*args, **kwargs)


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def green(t: str) -> str: return _c("32", t)
def red(t: str) -> str: return _c("31", t)
def yellow(t: str) -> str: return _c("33", t)
def cyan(t: str) -> str: return _c("36", t)
def bold(t: str) -> str: return _c("1", t)
def dim(t: str) -> str: return _c("2", t)


def _indent(text: str, width: int = 96) -> str:
    lines = []
    for line in str(text).splitlines() or [""]:
        lines.extend(textwrap.wrap(line, width) or [""])
    return "\n".join("    " + line for line in lines)


def header(title: str) -> None:
    emit("header", title=title)
    bar = "=" * 78
    _print("\n" + bold(bar) + "\n" + bold(f"  {title}") + "\n" + bold(bar))


def section(title: str) -> None:
    emit("section", title=title)
    _print("\n" + bold(f"--- {title} ---"))


def step(msg: str) -> None:
    emit("step", text=msg)
    _print(f"\n{bold('>>')} {msg}")


def trusted(label: str, text: str) -> None:
    lab.record("trusted", label=label, text=str(text))
    emit("trusted", label=label, text=str(text))
    _print(green(f"[trusted] {label}:"))
    _print(green(_indent(text)))


def untrusted(label: str, text: str) -> None:
    emit("untrusted", label=label, text=str(text))
    _print(red(f"[UNTRUSTED] {label}:"))
    _print(red(_indent(text)))


def tool(tool_name: str, /, **args) -> None:
    emit("tool", name=tool_name, args=args)
    shown = ", ".join(f"{k}={_short(repr(v))}" for k, v in args.items())
    _print(yellow(f"[tool] {tool_name}({shown})"))


def email(to: list[str], subject: str, body: str, attachment=None) -> None:
    """Show a sent email in full, the way the recipient reads it."""
    emit("email", to=to, subject=subject, body=body, attachment=attachment)
    _print(yellow(f"[email sent] to {', '.join(to)}"))
    text = f"Subject: {subject}\n\n{body}"
    if attachment:
        text += f"\n\n[attachment] {_short(attachment, 80)}"
    _print(_indent(text))


def llm(role: str, purpose: str, model: str) -> None:
    emit("llm", role=role, purpose=purpose, model=model)
    _print(cyan(f"[llm:{role}] {purpose}  ({model})"))


def llm_io(messages: list[dict], reply: str) -> None:
    """Only printed with VERBOSE=1: exactly what the model was given, and what it answered."""
    emit("llm_io", messages=messages, reply=reply)  # the web UI always shows prompts
    if not VERBOSE:
        return
    _print(cyan("    ┌─ prompt sent to the model"))
    for m in messages:
        _print(cyan(f"    │ [{m['role']}]"))
        for line in str(m["content"]).splitlines() or [""]:
            _print(dim(f"    │   {line}"))
    _print(cyan("    ├─ model's reply"))
    for line in str(reply).splitlines() or [""]:
        _print(dim(f"    │   {line}"))
    _print(cyan("    └─"))


def blocked(reason: str) -> None:
    emit("blocked", text=reason)
    _print(bold(green(f"[BLOCKED] {reason}")))


def danger(msg: str) -> None:
    emit("danger", text=msg)
    _print(bold(red(f"[COMPROMISED] {msg}")))


def ok(msg: str) -> None:
    emit("ok", text=msg)
    _print(green(f"[ok] {msg}"))


def info(msg: str) -> None:
    emit("info", text=msg)
    _print(dim(msg))


def _short(v, n: int = 80) -> str:
    s = str(v).replace("\n", " ")
    return s if len(s) <= n else s[: n - 3] + "..."


# --------------------------------------------------------------------------
# Rendering output to the user. Markdown images/links are an exfiltration
# channel: the browser fetches the URL and the query string carries data.
# See "Prompt injection: What's the worst that can happen?" (Willison, 2023).
# --------------------------------------------------------------------------
ALLOWED_LINK_DOMAINS = {"rubixcon.example"}
_MD_URL = re.compile(r"(!?)\[([^\]]*)\]\((https?://([^/\s)]+)[^\s)]*)\)")


def render_for_user(text: str, enforce_allowlist: bool = False) -> str:
    """Print assistant output. Flags (or strips) links to unknown domains."""
    leaks = []

    def check(m: re.Match) -> str:
        is_img, label, url, domain = m.groups()
        if domain in ALLOWED_LINK_DOMAINS:
            return m.group(0)
        leaks.append((("image" if is_img else "link"), url))
        return f"[{label} - link removed]" if enforce_allowlist else m.group(0)

    cleaned = _MD_URL.sub(check, text)
    lab.record("rendered", text=cleaned, links=[(k, u, not enforce_allowlist) for k, u in leaks])
    emit("render", text=cleaned, links=leaks, enforced=enforce_allowlist)
    _print(bold("[assistant -> user]"))
    _print(_indent(cleaned))
    for kind, url in leaks:
        if enforce_allowlist:
            blocked(f"removed {kind} to non-allowlisted domain: {url}")
        else:
            danger(f"{kind} to attacker domain rendered: {url}  (the browser would fetch it -> data exfiltrated)")
    return cleaned


# --------------------------------------------------------------------------
# Shared command-line flags for every demo script.
# --------------------------------------------------------------------------
def parse_args(description: str, naive: bool = True, clean: bool = True, ask: bool = True) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=description)
    if naive:
        p.add_argument("--naive", action="store_true", help="run the UNPROTECTED agent on the same data for comparison")
    if clean:
        p.add_argument("--clean", action="store_true", help="remove the planted prompt injections from the fake world")
    if ask:
        p.add_argument("--ask", metavar="TEXT", help="your own request instead of the built-in demo requests")
    return p.parse_args()
