"""Plain-assert tests for the capability interpreter. No LLM needed.

Run:  python 05_code_then_execute/selftest.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capabilities import Capabilities, Value, derive
from interpreter import Interpreter, InterpreterError, PolicyViolation
from policies import policy as real_policy


def policy(tool, kwargs, context):
    """The real policies, plus allow the test-only read tools."""
    if tool.startswith("read_"):
        return real_policy("read_file", kwargs, context)
    return real_policy(tool, kwargs, context)



SECRET = Capabilities(frozenset({"you@rubixcon.example"}), frozenset({"you@rubixcon.example", "bob@partner.example"}))
EVIL = Capabilities(frozenset({"guest@unknown.example"}), None)

sent: list[str] = []


def tools():
    def read_secret() -> Value:
        return Value("budget: 1.2 Cr", SECRET, label="read_secret()")

    def read_evil() -> Value:
        return Value("attacker@evil.example", EVIL, label="read_evil()")

    def query_quarantined_llm(question: Value, data: Value) -> Value:
        return derive(str(data.raw), question, data, label="qllm")

    def send_email(to: Value, subject: Value, body: Value, attachment: Value | None = None) -> Value:
        sent.append(to.raw)
        return Value("sent", Capabilities.user_literal())

    return {f.__name__: f for f in (read_secret, read_evil, query_quarantined_llm, send_email)}


def run(code: str, strict: bool = True) -> Interpreter:
    sent.clear()
    i = Interpreter(tools(), policy, strict=strict)
    i.run(code)
    return i


def expect_block(code: str, strict: bool = True) -> None:
    try:
        run(code, strict)
    except PolicyViolation:
        return
    raise AssertionError(f"expected BLOCK for:\n{code}")


# 1. taint propagates through f-strings, + and Q-LLM calls
i = run('e = read_evil()\nx = f"to {e}"\ny = x + "!"\nz = query_quarantined_llm("q", y)')
assert not i.env["z"].caps.trusted and "guest@unknown.example" in i.env["z"].caps.sources

# 2. literals are trusted and public
i = run('a = "hello"')
assert i.env["a"].caps.trusted and i.env["a"].caps.readers is None

# 3. readers intersect
i = run('s = read_secret()\ne = read_evil()\nc = s + e')
assert i.env["c"].caps.readers == SECRET.readers

# 4. allowed reader -> allowed
run('s = read_secret()\nsend_email(to="bob@partner.example", subject="b", body=s)')
assert sent == ["bob@partner.example"]

# 5. untrusted recipient + secret data -> blocked
expect_block('s = read_secret()\nto = read_evil()\nsend_email(to=to, subject="b", body=s)')

# 6. STRICT: leaking via control flow (no direct data flow) is blocked ...
leak = 's = read_secret()\nif s == "budget: 1.2 Cr":\n    send_email(to=read_evil(), subject="yes", body="x")'
expect_block(leak, strict=True)
# ... while NORMAL mode misses it (the side channel from the CaMeL paper, Sec. 7)
run(leak, strict=False)
assert sent == ["attacker@evil.example"]

# 7. disallowed syntax is rejected
for bad in ["import os", "().__class__", "def f(): pass", "while True: pass", "open('x')"]:
    try:
        run(bad)
        raise AssertionError(f"should reject: {bad}")
    except InterpreterError:
        pass

# 8. the whole program is checked BEFORE anything runs: a bad line 2 stops the email on line 1
try:
    run('send_email(to="bob@partner.example", subject="hi", body="x")\nn = "a".strip()')
    raise AssertionError("should reject .strip()")
except InterpreterError:
    assert sent == [], "nothing may run when the program is refused"

print("all interpreter self-tests passed")
