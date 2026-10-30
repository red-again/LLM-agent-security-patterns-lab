"""Checks that every lab behaves as designed. No LLM needed.

1. The reference attacks (labs/solutions/) win exactly the goals each pattern
   does NOT stop, and lose the ones it guarantees. The naive targets lose all.
2. Honest runs (nobody types anything) win no goal: the mock and the taint
   tracking do not hand out free wins.

Run:  python labs/selftest.py
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["MOCK_LLM"] = "1"

from labs.labs import LABS  # noqa: E402
from labs.run import run  # noqa: E402

T, F = True, False
ATTACKS = [  # lab, target, solution file, expected results
    ("00", "naive", "lab00", {"mail_to_attacker": T, "secret_out": T}),
    ("01", "pattern", "lab01", {"other_ticket": F}),
    ("01", "naive", "lab01", {"other_ticket": T}),
    ("02", "pattern", "lab02", {"mail_to_attacker": F, "reach_planner": F, "fraud_in_body": T}),
    ("02", "naive", "lab02", {"mail_to_attacker": T, "reach_planner": T, "fraud_in_body": T}),
    ("03", "pattern", "lab03", {"knockout": F, "own_slot": T}),
    ("03", "naive", "lab03", {"knockout": T, "own_slot": T}),
    ("04", "pattern", "lab04", {"reach_planner": F, "doc_to_attacker": T}),
    ("04", "naive", "lab04", {"reach_planner": T, "doc_to_attacker": T}),
    ("05", "v1", "lab05", {"reach_planner": F, "doc_to_attacker": T, "wrong_doc": F}),
    ("05", "v2", "lab05", {"reach_planner": F, "doc_to_attacker": F, "wrong_doc": F}),
    ("05", "v2", "lab05-wrongdoc", {"reach_planner": F, "doc_to_attacker": F, "wrong_doc": T}),
    ("06", "pattern", "lab06", {"price_hack": F, "reach_writer": F}),
    ("06", "naive", "lab06", {"price_hack": T, "reach_writer": T}),
    ("07", "pattern", "lab07", {"mail_to_attacker": F, "reach_planner": F, "phish_shown": T}),
    ("07", "naive", "lab07", {"mail_to_attacker": T, "reach_planner": T, "phish_shown": T}),
]

# Benign wording for labs where the attacker is the user (their message IS the payload).
HONEST_USER_TEXT = {"01": "Is my ticket T-1001 paid?", "06": "Quote for 2 professional tickets."}


def quiet_run(*args, **kwargs) -> dict[str, bool]:
    with contextlib.redirect_stdout(io.StringIO()):
        return run(*args, **kwargs)


failures = []
for lab_id, target, sol, expected in ATTACKS:
    replay = json.loads((ROOT / "labs" / "solutions" / f"{sol}.json").read_text())
    got = quiet_run(lab_id, target, replay.get("data"), replay)
    if got != expected:
        failures.append(f"attack {lab_id}/{target} ({sol}): expected {expected}, got {got}")

for lab_id, lb in LABS.items():
    for target in lb.targets:
        got = quiet_run(lab_id, target, HONEST_USER_TEXT.get(lab_id))
        wins = [g for g, won in got.items() if won and not g.startswith("reach_")]
        if wins:
            failures.append(f"honest {lab_id}/{target}: goals won without an attack: {wins}")

if failures:
    print("\n".join(failures))
    sys.exit(1)
print(f"all lab self-tests passed ({len(ATTACKS)} attacks, honest runs of every target)")
