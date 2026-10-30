"""The lab's web UI.  Run:  python ui/server.py   then open the link it prints.

Plain Python standard library, no framework. Local only, because it runs code
on this machine:
  * listens on 127.0.0.1, and rejects requests whose Host header is not local
    (blocks DNS-rebinding from a web page you happen to have open)
  * every API call needs a random token that changes every start
  * only entries from ui/catalog.py can be run or patched
"""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import catalog

ROOT, HERE = catalog.ROOT, Path(__file__).resolve().parent
PORT = int(os.getenv("LAB_UI_PORT", "8765"))
TOKEN = secrets.token_urlsafe(16)
STATIC = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}
MODEL_RE = re.compile(r"^[\w./:-]{1,100}$")


class Job:
    """One running script. Its events are kept so a reconnecting browser can replay them."""

    def __init__(self, argv: list[str], env: dict):
        self.id = secrets.token_hex(4)
        self.events: list[dict] = []
        self.cond = threading.Condition()
        self.done = False
        self.proc = subprocess.Popen([sys.executable, "-u", str(HERE / "bridge.py"), *argv], cwd=ROOT,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, env=env)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        for line in self.proc.stdout:
            try:
                ev = json.loads(line)
            except ValueError:
                ev = {"kind": "console", "text": line.rstrip("\n")}
            self._push(ev)
        self.proc.wait()
        if not self.events or self.events[-1].get("kind") != "done":
            self._push({"kind": "done"})
        with self.cond:
            self.done = True
            self.cond.notify_all()

    def _push(self, ev: dict) -> None:
        with self.cond:
            self.events.append(ev)
            self.cond.notify_all()

    def reply(self, text: str) -> None:
        if self.proc.poll() is None:
            self.proc.stdin.write(json.dumps({"text": text}) + "\n")
            self.proc.stdin.flush()

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()


JOBS: dict[str, Job] = {}


def start(req: dict) -> Job:
    """Turn a request from the browser into argv, from catalogue entries only."""
    env = {**os.environ, "NO_COLOR": "1", "PYTHONUNBUFFERED": "1"}
    for key in ("LLM_MODEL", "QLLM_MODEL"):
        value = (req.get("models") or {}).get(key)
        if value:
            if not MODEL_RE.match(value):
                raise ValueError(f"bad model name {value!r}")
            env[key] = value
    kind = req.get("kind")
    if kind == "keeper":
        levels = {lv["level"]: lv["file"] for lv in catalog.keeper_levels()}
        argv = [levels[int(req["level"])]]
    elif kind == "lab":
        lab = next(lb for lb in catalog.labs() if lb["lab"] == req["lab"])
        if req.get("target") not in lab["targets"]:
            raise ValueError("unknown target")
        data = str(req.get("data") or "").strip()[:4000] or lab["default_text"]  # empty = the built-in text
        argv = ["labs/run.py", lab["lab"], "--target", req["target"], "--data", data]
    elif kind == "watch":
        lab = next(lb for lb in catalog.labs() if lb["lab"] == req["lab"])
        script = {"02": "02_plan_then_execute/agent.py", "03": "03_llm_map_reduce/agent.py",
                  "04": "04_dual_llm/agent.py", "05": "05_code_then_execute/v2_provenance.py"}[lab["lab"]]
        if lab["lab"] == "05" and req.get("variant") == "v1":
            script = "05_code_then_execute/v1_plain.py"
        flags = [f for f in req.get("flags", []) if f in ("--clean", "--naive", "--normal")]
        argv = [script, *flags]
    elif kind == "playground":
        tmp = Path(tempfile.mkdtemp(prefix="lab-ui-")) / "program.py"
        tmp.write_text(str(req.get("code", ""))[:8000])
        # The program is data for the restricted interpreter (no exec), not a script we run.
        argv = ["labs/camel_playground.py", str(tmp)] + (["--normal"] if req.get("normal") else [])
    else:
        raise ValueError("unknown kind")
    for old in list(JOBS.values()):
        old.stop()
    job = Job(argv, env)
    JOBS.clear()
    JOBS[job.id] = job
    return job


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):  # keep the terminal quiet
        pass

    def _local(self) -> bool:
        host = self.headers.get("Host", "")
        return host in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def _authed(self, qs: dict) -> bool:
        return self.headers.get("X-Lab-Token") == TOKEN or qs.get("token", [""])[0] == TOKEN

    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode())

    def do_GET(self) -> None:
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        if not self._local():
            return self._send(403, b"local only", "text/plain")
        if url.path in STATIC:
            body = (HERE / "static" / STATIC[url.path]).read_text()
            ctype = {"html": "text/html", "js": "text/javascript", "css": "text/css"}[STATIC[url.path].split(".")[-1]]
            return self._send(200, body.replace("__TOKEN__", TOKEN).encode(), f"{ctype}; charset=utf-8")
        if not self._authed(qs):
            return self._json({"error": "bad token"}, 401)
        if url.path == "/api/catalog":
            return self._json(catalog.full())
        if url.path == "/api/events":
            return self._events(qs)
        if url.path == "/api/trace":
            try:
                return self._json({"name": qs["name"][0], "text": catalog.trace(qs["name"][0])})
            except (KeyError, ValueError) as e:
                return self._json({"error": str(e)}, 400)
        self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        url = urlparse(self.path)
        if not self._local() or not self._authed({}):
            return self._json({"error": "forbidden"}, 403)
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if url.path == "/api/run":
                return self._json({"job": start(req).id})
            if url.path == "/api/reply":
                JOBS[req["job"]].reply(str(req.get("text", ""))[:4000])
                return self._json({"ok": True})
            if url.path == "/api/stop":
                JOBS[req["job"]].stop()
                return self._json({"ok": True})
            if url.path == "/api/patch":
                ok = catalog.set_patch(req["name"], bool(req["on"]))
                return self._json({"ok": ok, "patches": catalog.patches()})
        except (KeyError, ValueError, StopIteration) as e:
            return self._json({"error": f"{type(e).__name__}: {e}"}, 400)
        self._json({"error": "not found"}, 404)

    def _events(self, qs: dict) -> None:
        """Server-sent events: replays everything from `since`, then streams new events."""
        job = JOBS.get(qs.get("job", [""])[0])
        if job is None:
            return self._json({"error": "no such job"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        i = int(qs.get("since", ["0"])[0])
        try:
            while True:
                with job.cond:
                    while i >= len(job.events) and not job.done:
                        job.cond.wait(timeout=15)
                        if i >= len(job.events):
                            self.wfile.write(b": keep-alive\n\n")
                            self.wfile.flush()
                    batch, i = job.events[i:], len(job.events)
                for ev in batch:
                    self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
                self.wfile.flush()
                if job.done and i >= len(job.events):
                    return
        except (BrokenPipeError, ConnectionResetError):
            return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    print(f"RubixCON lab UI: http://127.0.0.1:{PORT}/   (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        for job in JOBS.values():
            job.stop()
        time.sleep(0.1)


if __name__ == "__main__":
    main()
