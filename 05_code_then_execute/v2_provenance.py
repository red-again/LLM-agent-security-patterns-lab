"""05 Code-Then-Execute, v2: CaMeL-style capabilities, provenance and policies.

CaMeL ("Defeating Prompt Injections by Design", Debenedetti et al. 2025):
"CaMeL explicitly extracts the control and data flows from the (trusted)
query; therefore, the untrusted data retrieved by the LLM can never impact the
program flow. To further improve security, CaMeL uses a notion of a capability
to prevent the exfiltration of private data over unauthorized data flows by
enforcing security policies when tools are called."

Same task and same generated program as v1. The difference is HOW it runs:
  * interpreter.py walks the AST itself (no exec) and wraps every value in a
    Value with capabilities: sources (who could have written it) and readers
    (who may see it).
  * Tool results get capabilities from the data, e.g. the meeting notes are
    edited by an outside guest, so they are UNTRUSTED.
  * The Q-LLM's answer inherits the capabilities of its input. So `address`
    is untrusted, because it came from the notes.
  * Before send_email, policies.py checks: may every recipient read
    everything in this email? attacker@evil.example may not -> BLOCKED.

Run with --clean: the same program sends to bob@partner.example and the
policy ALLOWS it. Security without losing utility, with no extra AI involved.

What it does NOT stop (CaMeL Sec. 7-8): side channels (partly handled by
STRICT mode), phishing text shown to the user, and the burden of writing and
maintaining policies.

Refs:
  - https://arxiv.org/abs/2503.18813
  - https://github.com/google-research/camel-prompt-injection
  - https://simonwillison.net/2025/Apr/11/camel/

Run:
  python 05_code_then_execute/v2_provenance.py
  python 05_code_then_execute/v2_provenance.py --clean
  python 05_code_then_execute/v2_provenance.py --normal   # turn off STRICT mode
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capabilities import Capabilities, Value, dependency_tree, derive
from common import TASK, ask_qllm, generate_plan_code
from interpreter import Interpreter, InterpreterError, PolicyViolation
from policies import policy

from shared import ui
from shared.llm import LLM
from shared.world import World


def make_tools(world: World, q_llm: LLM) -> dict:
    """Each tool takes Values and returns a Value with the right capabilities."""

    def file_caps(name: str) -> Capabilities:
        f = world.drive[name]
        # sources = the file's editors (CaMeL's "inner source"); readers = who it is shared with
        return Capabilities(frozenset(f["editors"]), frozenset(f["readers"]))

    def find_latest_meeting_notes() -> Value:
        raw = world.find_latest_meeting_notes()
        return Value(raw, file_caps("meeting-notes-2026-10-20.txt"), label="find_latest_meeting_notes()")

    def read_file(name: Value) -> Value:
        fname = str(name.raw).strip()
        raw = world.read_file(fname)
        # depends on the file AND on the name (an attacker may have chosen which file)
        return derive(raw, name, label=f"read_file({fname!r})", extra=file_caps(fname))

    def query_quarantined_llm(question: Value, data: Value) -> Value:
        out = ask_qllm(q_llm, str(question.raw), str(data.raw))
        v = derive(out, question, data, label="query_quarantined_llm(...)")
        ui.untrusted("quarantined LLM answer", f"{out}\n  capabilities: {v.caps}")
        return v

    def send_email(to: Value, subject: Value, body: Value, attachment: Value | None = None) -> Value:
        res = world.send_email(str(to.raw).strip(), str(subject.raw), str(body.raw),
                               None if attachment is None else str(attachment.raw))
        return Value(res, Capabilities.user_literal(), label="send_email(...)")

    def display(text: Value) -> Value:
        if not text.caps.trusted:
            # CaMeL bonus: provenance lets the UI say where shown text came from.
            ui.info(f"    (shown text comes from: {sorted(text.caps.sources)})")
        ui.render_for_user(str(text.raw), enforce_allowlist=True)
        return Value(None, Capabilities.user_literal())

    return {f.__name__: f for f in (find_latest_meeting_notes, read_file, query_quarantined_llm, send_email, display)}


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--clean", action="store_true", help="remove the planted injections")
    p.add_argument("--normal", action="store_true", help="NORMAL mode instead of STRICT (no control-flow deps)")
    p.add_argument("--ask", metavar="TEXT")
    args = p.parse_args()

    world = World(clean=args.clean)
    ui.header("05 Code-Then-Execute v2 - CaMeL-style capabilities + policies")
    code = generate_plan_code(args.ask or TASK)

    interp = Interpreter(make_tools(world, LLM("quarantined")), policy, strict=not args.normal)
    try:
        interp.check(code)  # nothing has run yet, so a retry has no side effects
    except InterpreterError as e:
        ui.blocked(f"interpreter refused the program: {e}")
        code = generate_plan_code(args.ask or TASK, refused=(code, str(e)))
    ui.step(f"EXECUTE in the capability-tracking interpreter ({'NORMAL' if args.normal else 'STRICT'} mode)")
    try:
        interp.run(code)
    except PolicyViolation as e:
        ui.blocked(f"policy: {e}")
    except InterpreterError as e:
        ui.blocked(f"interpreter refused the program: {e}")
    except (TypeError, KeyError, ValueError, FileNotFoundError) as e:
        ui.blocked(f"program failed ({type(e).__name__}: {e}), so we stop here (fail closed)")

    ui.section("data-flow graph of the variables")
    seen: set[int] = set()
    for v in interp.env.values():
        print(dependency_tree(v, seen=seen))

    ui.section("result")
    if world.attacker_got_mail():
        ui.danger("document reached the attacker")
    elif world.outbox:
        ui.ok(f"email sent to {world.outbox[-1]['to']}, and the policy allowed it because they are an allowed reader")
    else:
        ui.ok("nothing was sent to someone who may not read the data")


if __name__ == "__main__":
    main()
