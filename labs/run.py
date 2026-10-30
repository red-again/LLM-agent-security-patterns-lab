"""Workshop labs: attack each pattern yourself.

You plant text where an attacker could (an email, an invite, a doc, a CFP
abstract, or your own chat message). Every model that reads it is yours: you
type its replies. Then we check what actually happened.

  python labs/run.py                       # list the labs
  python labs/run.py 02                    # attack plan-then-execute
  python labs/run.py 02 --naive            # the same attack on the unprotected agent
  python labs/run.py 05 --target v2        # labs with several targets
  python labs/run.py 02 --hints
  python labs/run.py 02 --replay labs/attempts/lab02-pattern.json   # re-run a saved attack
  python labs/run.py 02 --real --data "..."  # a REAL model reads your text (needs LLM_API_KEY)
"""

from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labs.labs import LABS, SLOT_NAMES, Lab  # noqa: E402

from shared import lab, ui  # noqa: E402
from shared.llm import mock_enabled  # noqa: E402

ATTEMPTS = ROOT / "labs" / "attempts"


def list_labs() -> None:
    ui.header("Workshop labs")
    for lb in LABS.values():
        ui._print(f"  {ui.bold(lb.id)}  {lb.title:55s} targets: {', '.join(lb.targets)}")
    ui._print("\nStart with:  python labs/run.py 00        (see labs/README.md for the rules)")


def briefing(lb: Lab, target: str, real: bool) -> None:
    ui.header(f"Lab {lb.id}: {lb.title}   [target: {target}]")
    ui._print(lb.story)
    ui.section("your goals")
    for i, g in enumerate(lb.goals, 1):
        ui._print(f"  {i}. {g.text}")
    ui.section("how to play")
    ui._print(f"  * Your text is planted in: {SLOT_NAMES[lb.slot]}.")
    if real:
        ui._print("  * REAL mode: a real model reads your text and decides. Your words have to work.")
    else:
        ui._print("  * Every model that reads your text is YOURS. At 'YOU ARE THE MODEL', type its reply.")
        ui._print("    Enter = the honest reply. p = show the full prompt. End a line with \\ to continue.")
        ui._print("  * Models that never see your text answer honestly. That is the pattern at work.")
    ui._print(f"  * Stuck? python labs/run.py {lb.id} --hints")


def plant_text(lb: Lab, args, replay: dict) -> str:
    if args.data is not None:
        return args.data
    if "data" in replay:
        return replay["data"]
    if sys.stdin.isatty() and not args.replay:
        ui.section("plant your text")
        ui._print(f"Where: {SLOT_NAMES[lb.slot]}.")
        ui._print("Enter = use the built-in injection. (In --real mode your wording is everything.)")
        typed = lab.read_multiline(ui.bold("your text: "))
        if typed:
            return typed
    return lb.default_text


def run(lab_id: str, target: str, data: str | None = None, replay: dict | None = None,
        real: bool = False) -> dict[str, bool]:
    """Run one lab attempt and return {goal_id: achieved}. Used by selftest.py too."""
    lb = LABS[lab_id]
    script, *extra = lb.targets[target]
    text = lb.default_text if data is None else data
    argv = [script, *extra] + (["--ask", text] if lb.slot == "user" else [])

    lab.start(lb.slot, text, real=real, replay=(replay or {}).get("replies"))
    path = ROOT / script
    sys.path.insert(0, str(path.parent))
    old_argv, sys.argv = sys.argv, argv
    try:
        runpy.run_path(str(path), run_name="__main__")
    except SystemExit:
        pass
    except Exception as e:  # noqa: BLE001 - an attempt that crashes the target just ends the run
        ui.blocked(f"the target stopped with {type(e).__name__}: {e} (fail closed)")
    finally:
        sys.argv = old_argv
        sys.path.remove(str(path.parent))
    return {g.id: bool(g.check()) for g in lb.goals}


def scoreboard(lb: Lab, target: str, results: dict[str, bool]) -> None:
    reached = sorted({f"{e['purpose']} ({e['role']})" for e in lab.STATE.events if e["kind"] == "reached"})
    ui.emit("scoreboard", lab=lb.id, target=target, reached=reached,
            goals=[{"id": g.id, "text": g.text, "won": results[g.id], "lesson": g.lesson} for g in lb.goals])
    ui.header(f"Lab {lb.id} results   [target: {target}]")
    for g in lb.goals:
        tag = ui.bold(ui.red("PWNED")) if results[g.id] else ui.bold(ui.green("held "))
        ui._print(f"  [{tag}] {g.text}")
        if target != "naive":
            ui._print(ui.dim(f"           {g.lesson}"))
    yours = sorted({f"{e['purpose']} ({e['role']})" for e in lab.STATE.events if e["kind"] == "reached"})
    ui.emit("scoreboard", target=target, reached=yours,
            goals=[{"id": g.id, "text": g.text, "won": results[g.id], "lesson": g.lesson} for g in lb.goals])
    ui._print("\n  models your text reached: " + (", ".join(yours) or "none"))


def save_attempt(lb: Lab, target: str, text: str) -> Path:
    ATTEMPTS.mkdir(exist_ok=True)
    path = ATTEMPTS / f"lab{lb.id}-{target}.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    replies = {**old.get("replies", {}), **lab.STATE.typed}
    path.write_text(json.dumps({"lab": lb.id, "data": text, "replies": replies}, indent=2))
    return path


def main() -> None:
    p = argparse.ArgumentParser(description="Attack the patterns yourself.")
    p.add_argument("lab", nargs="?", help="lab id, e.g. 02")
    p.add_argument("--target", help="which version to attack (see the lab list)")
    p.add_argument("--naive", action="store_true", help="shortcut for --target naive")
    p.add_argument("--hints", action="store_true", help="print the hints and exit")
    p.add_argument("--data", help="the text you plant (skips the prompt)")
    p.add_argument("--replay", metavar="FILE", help="replay a saved attempt (labs/attempts/*.json)")
    p.add_argument("--real", action="store_true", help="no takeover: a real model reads your text")
    args = p.parse_args()

    if not args.lab:
        return list_labs()
    lb = LABS.get(args.lab.zfill(2))
    if lb is None:
        sys.exit(f"unknown lab {args.lab!r}. Run `python labs/run.py` for the list.")
    target = "naive" if args.naive else (args.target or next(iter(lb.targets)))
    if target not in lb.targets:
        sys.exit(f"lab {lb.id} has targets: {', '.join(lb.targets)}")
    if args.hints:
        ui.header(f"Lab {lb.id} hints")
        for i, h in enumerate(lb.hints, 1):
            ui._print(f"  {i}. {h}")
        return
    if args.real and mock_enabled():
        sys.exit("--real needs a real model: set LLM_API_KEY in .env and unset MOCK_LLM.")

    replay = json.loads(Path(args.replay).read_text()) if args.replay else {}
    briefing(lb, target, args.real)
    text = plant_text(lb, args, replay)
    results = run(lb.id, target, text, replay, args.real)
    scoreboard(lb, target, results)
    saved = save_attempt(lb, target, text)

    ui.section("next")
    ui._print(f"  replay this attack:   python labs/run.py {lb.id} --target {target} --replay {saved.relative_to(ROOT)}")
    others = [t for t in lb.targets if t != target]
    if others:
        ui._print(f"  same planted text, other target:  python labs/run.py {lb.id} --target {others[0]} --data \"...\"")
    ui._print(f"  defend: {lb.defend}")


if __name__ == "__main__":
    main()
