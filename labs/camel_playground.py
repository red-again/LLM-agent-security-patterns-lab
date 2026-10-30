"""CaMeL playground: write the plan program yourself and see what the policy says.

You play the P-LLM. Write restricted Python (rules and tools are in
05_code_then_execute/common.py) and run it through the SAME interpreter,
tools and policies as 05 v2. Missions are in labs/playground/ and labs/README.md.

  python labs/camel_playground.py labs/playground/m1_exfiltrate_budget.py
  python labs/camel_playground.py labs/playground/m3_side_channel.py --normal
  python labs/camel_playground.py -c 'display(read_file("budget-2026.xlsx"))'

In a terminal, "ask the user" policies really ask you (y/N). Piped, they say no.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "05_code_then_execute"))

from interpreter import Interpreter, InterpreterError, PolicyViolation  # noqa: E402
from policies import policy  # noqa: E402
from v2_provenance import make_tools  # noqa: E402

from capabilities import dependency_tree  # noqa: E402
from shared import ui  # noqa: E402
from shared.llm import LLM  # noqa: E402
from shared.world import World  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("file", nargs="?", help="a .py file with your plan program")
    p.add_argument("-c", dest="code", help="the program as a string")
    p.add_argument("--normal", action="store_true", help="NORMAL mode: no control-flow dependencies")
    p.add_argument("--clean", action="store_true", help="remove the planted injection from the notes")
    args = p.parse_args()
    if not (args.file or args.code):
        p.error("give a program file or -c CODE")
    code = args.code or Path(args.file).read_text()

    world = World(clean=args.clean)
    mode = "NORMAL" if args.normal else "STRICT"
    ui.header(f"CaMeL playground ({mode} mode)")
    ui.trusted("your program", code.strip())
    for name, f in world.drive.items():
        ui.info(f"    {name:32s} editors={f['editors']}  readers={f['readers']}")

    interp = Interpreter(make_tools(world, LLM("quarantined")), policy, strict=not args.normal)
    verdict = None
    try:
        interp.run(code)
    except PolicyViolation as e:
        verdict = f"BLOCKED by policy: {e}"
    except InterpreterError as e:
        verdict = f"REFUSED by the interpreter: {e}"
    except (TypeError, KeyError, ValueError, FileNotFoundError, IndexError) as e:
        verdict = f"program failed ({type(e).__name__}: {e}), fail closed"

    ui.section("data-flow graph")
    seen: set[int] = set()
    for v in interp.env.values():
        print(dependency_tree(v, seen=seen))

    ui.section("verdict")
    for m in world.outbox:
        att = f" + attachment from {m['attachment'][:30]!r}" if m["attachment"] else ""
        ui.ok(f"SENT to {m['to']}: subject {m['subject']!r}{att}")
    if verdict:
        ui.blocked(verdict)
    elif not world.outbox:
        ui.ok("program finished, nothing was sent")


if __name__ == "__main__":
    main()
