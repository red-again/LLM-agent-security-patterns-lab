# CLAUDE.md

Nullcon workshop code: the six prompt-injection design patterns (Beurer-Kellner et al. 2025) + a CaMeL-style interpreter.

**Read `WORKSHOP_CONTEXT.md` first.** It has every source, the pattern summaries, CaMeL details and the conventions.

Key rules when changing code:
- Plain Python + pydantic only (no LangChain/Chainlit). Keep files short enough to present live.
- Security checks belong in code (validators, policies, allowlists), never in prompts. Fail closed.
- Every LLM call has a `purpose` label. Add a matching responder in `shared/mock_llm.py` (the mock is deliberately gullible).
- Planted injections live in `shared/world.py` (`INJECTION_*`). Use only `*.example` domains.
- Each script supports `--naive`, `--clean`, `--ask` where it makes sense (`shared/ui.parse_args`).
- Verify with `MOCK_LLM=1 python <script>` for every script, plus `python 05_code_then_execute/selftest.py`, `python 08_secret_keeper/selftest.py` and `python labs/selftest.py`.
- Labs (`labs/`, `shared/lab.py`): goal checks look only at recorded outcomes, never at payloads. If you change a demo's flow, update `labs/labs.py`, `labs/solutions/*.json` and the expectations in `labs/selftest.py`.
- `WORKSHOP_GUIDE.md` is the attendee step-by-step; keep commands in it runnable.
