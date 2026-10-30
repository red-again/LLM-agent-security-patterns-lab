"""Runs ONE lab script for the web UI, in its own process.

The server starts `python ui/bridge.py <script> [args...]`. Then:
  stdout  one JSON event per line (the shared/ui.py event stream, console text, input requests)
  stdin   one JSON line per answer the script asked for ({"text": "..."})

Each run is a fresh process, so runs never share state (secrets, transcripts, lab state).
"""

from __future__ import annotations

import builtins
import io
import json
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_OUT = sys.stdout  # the real stdout carries events only


def send(event: dict) -> None:
    _OUT.write(json.dumps(event, default=str) + "\n")
    _OUT.flush()


class _Console(io.TextIOBase):
    """Everything the script prints becomes a 'console' event, one line at a time."""

    def __init__(self):
        self._buf = ""

    def write(self, s: str) -> int:
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            send({"kind": "console", "text": line})
        return len(s)

    def flush(self) -> None:
        if self._buf:
            send({"kind": "console", "text": self._buf})
            self._buf = ""

    def isatty(self) -> bool:
        return False


class _Stdin(io.TextIOBase):
    """Scripts check isatty() before asking a human. In the UI, a human is there."""

    def isatty(self) -> bool:
        return True

    def readline(self, *_) -> str:
        return _ask("") + "\n"


def _ask(prompt: str = "") -> str:
    sys.stdout.flush()
    send({"kind": "input", "prompt": str(prompt)})
    line = sys.__stdin__.readline()
    if not line:
        raise EOFError
    return str(json.loads(line).get("text", ""))


def main() -> None:
    script = (ROOT / sys.argv[1]).resolve()
    if ROOT not in script.parents or script.suffix != ".py":
        sys.exit("refusing to run a file outside the project")
    sys.path[:0] = [str(ROOT), str(script.parent)]

    from shared import ui  # imported after sys.path is set

    ui.SINK = send
    builtins.input = _ask
    sys.stdout, sys.stdin = _Console(), _Stdin()
    sys.argv = [str(script), *sys.argv[2:]]
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit:
        pass
    except EOFError:
        send({"kind": "info", "text": "run stopped"})
    except Exception as e:  # noqa: BLE001 - show any crash in the UI
        send({"kind": "error", "text": f"{type(e).__name__}: {e}"})
    finally:
        sys.stdout.flush()
        send({"kind": "done"})


if __name__ == "__main__":
    main()
