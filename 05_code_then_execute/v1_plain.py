"""05 Code-Then-Execute, v1: the plan is a program.

Paper (Sec. 3.5): "we can envision an agent that writes a formal computer
program to solve a task. This program may call tools available to the agent,
and spawn unprivileged LLMs to process untrusted text." It generalises
plan-then-execute: loops and conditionals are allowed, but they are all fixed
before any data is seen.

v1 is the basic version. The program is AST-checked (allowed syntax and
function names only), then run with only the tool functions in scope.

The guarantee:
  * Control flow is fixed by the P-LLM, which only saw the user request.

What it does NOT stop (run it and see):
  * Exactly the Dual LLM flaw from 04. `address` comes from
    query_quarantined_llm over the poisoned notes, so the attacker picks the
    recipient. Nothing tracks where `address` came from. v2 does.

!!! exec() with an AST allowlist is NOT a real sandbox. It is fine for a demo
!!! with only these tools. In production, run generated code in an isolated
!!! sandbox (the paper's "action sandboxing" best practice), or interpret it
!!! yourself as v2 does.

Refs:
  - https://arxiv.org/abs/2506.08837 Sec. 3.5
  - https://simonwillison.net/2025/Apr/11/camel/

Run:
  python 05_code_then_execute/v1_plain.py
  python 05_code_then_execute/v1_plain.py --clean
"""

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import TASK, ask_qllm, generate_plan_code

from shared import ui
from shared.llm import LLM
from shared.world import BOB, World

ALLOWED_NODES = (
    ast.Module, ast.Expr, ast.Assign, ast.Name, ast.Load, ast.Store, ast.Call, ast.keyword,
    ast.Constant, ast.JoinedStr, ast.FormattedValue, ast.If, ast.For, ast.Compare, ast.Eq,
    ast.NotEq, ast.In, ast.NotIn, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
    ast.List, ast.Dict, ast.Subscript, ast.BinOp, ast.Add, ast.Pass,
)


def check_code(code: str, tool_names: set[str]) -> ast.Module:
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError(f"disallowed syntax: {type(node).__name__}")
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id in tool_names):
            raise ValueError(f"call to a non-tool: {ast.unparse(node.func)}")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("dunder names are not allowed")
    return tree


def main() -> None:
    args = ui.parse_args(__doc__.splitlines()[0], naive=False)
    world = World(clean=args.clean)
    q_llm = LLM("quarantined")
    ui.header("05 Code-Then-Execute v1 - plan as code, no provenance")

    def query_quarantined_llm(question, data):
        out = ask_qllm(q_llm, question, data)
        ui.untrusted("quarantined LLM answer", out)
        return out

    tools = {
        "find_latest_meeting_notes": world.find_latest_meeting_notes,
        "read_file": lambda name: world.read_file(name.strip()),
        "query_quarantined_llm": query_quarantined_llm,
        "send_email": lambda to, subject, body, attachment=None: world.send_email(to.strip(), subject, body, attachment),
        "display": lambda text: ui.render_for_user(str(text), enforce_allowlist=True),
    }

    code = generate_plan_code(args.ask or TASK)
    try:
        tree = check_code(code, set(tools))
    except (SyntaxError, ValueError) as e:
        ui.blocked(f"program rejected: {e}")
        code = generate_plan_code(args.ask or TASK, refused=(code, str(e)))  # one retry, error only
        try:
            tree = check_code(code, set(tools))
        except (SyntaxError, ValueError) as e2:
            ui.blocked(f"program rejected again: {e2}, so we stop here (fail closed)")
            return
    ui.step("EXECUTE the program")
    try:
        exec(compile(tree, "<plan>", "exec"), {"__builtins__": {}, **tools})  # noqa: S102 - see docstring
    except Exception as e:  # noqa: BLE001
        ui.blocked(f"program failed ({type(e).__name__}: {e}), so we stop here")

    ui.section("result")
    if world.attacker_got_mail():
        ui.danger("the program's control flow was fixed, but `address` came from poisoned data. "
                  "Nobody tracked that. -> v2_provenance.py")
    elif world.outbox and BOB in world.outbox[-1]["to"]:
        ui.ok("document sent to Bob")
    elif world.outbox:
        ui.info(f"sent to {world.outbox[-1]['to']}, which is not Bob's address from the notes")
    else:
        ui.ok("nothing was sent")


if __name__ == "__main__":
    main()
