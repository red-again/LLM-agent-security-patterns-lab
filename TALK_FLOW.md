# Session flow (90 minutes), for the instructor

What happens in each block, what you run, and what to point at on screen.
Exact attack messages for the Secret keeper are in WORKSHOP_GUIDE.md, Module 0.

Before the session: `.env` has your NVIDIA key, then run
`python 08_secret_keeper/try_attacks.py` and check the table still matches Module 0.

Status: every block (1-6) is tested on real models (NVIDIA API, 2026-10-29). Each module folder
has a TUTORIAL.md with the commands, the line-by-line code walkthrough and the results.
Model split: Blocks 1-3 and 6 use the .env defaults; Blocks 4-5 use a big planner and a small
reader (the export line in each block).

---

## Block 1: Intro (0-5)

**Say:** the model will be fooled. Don't ask "will it resist?", ask "what can it do
once it is fooled?". Private data + untrusted input + a way out = the lethal trifecta.

**Show:** nothing yet. One slide with the six patterns.

## Block 2: Secret keeper, levels 1-7 (5-27)

**Story:** a ticket desk bot knows a staff discount code. You are the customer.

| Level | File | Point at |
|---|---|---|
| 1 | `08_secret_keeper/level1_naive.py` | the code sits in `SYSTEM`; one polite ask leaks it |
| 2 | `level2_prompt_rules.py` | the whole patch is one line of prompt; translation gets past it |
| 3 | `level3_output_filter.py` | first check in CODE; it knows one spelling only |
| 4 | `level4_input_filter.py` | blocklist of words; the model reads meaning, not words |
| 5 | `level5_llm_guard.py` | a big model checks each reply; it judges one reply at a time |
| 6 | `level6_action_selector.py` | **pattern**: the model picks from a menu; code holds the secret |
| 7 | `level7_context_minimization.py` | **pattern**: the reply model never sees the user's words |

**Watch on screen:** the `audit:` line. Levels 1-5: "inside 1 of 1 prompts". Levels 6-7:
"inside 0 prompts. There is nothing for the model to leak."

**Takeaway:** a system prompt is not a vault. Detectors stack around a leak; patterns remove it.

## Block 3: Plan-Then-Execute (27-39)

**Story:** the assistant emails today's schedule to the director. You sent one calendar invite.

```bash
python 02_plan_then_execute/agent.py --clean   # real planner, normal day: plan frozen, director gets the schedule
python 02_plan_then_execute/agent.py           # outsider's invite: no extra email, but its text reaches the director
patch -p1 < patches/02_calendar_fields_only.patch
python 02_plan_then_execute/agent.py           # only time + title flow on: clean schedule
python labs/run.py 02                          # attendees plant their own invite text
```

**Point at:** the plan's sha256 line (frozen before any data is read), then the director's email body.
Tested on real models: no model has to be fooled for the outsider's text to reach the director.
**Takeaway:** a frozen plan protects the control flow, not the data inside it.

## Block 4: Dual LLM (39-51)

**Story:** "send Bob the document from our meeting notes". You can edit the notes.

```bash
export LLM_MODEL=nvidia/nemotron-3-ultra-550b-a55b QLLM_MODEL=nvidia/nemotron-3.5-bolt-e4b  # big planner, small reader
VERBOSE=1 python 04_dual_llm/agent.py --clean  # the P-LLM only ever sees $VAR names
python labs/run.py 04                          # you answer as the quarantined model: attacker@evil.example
patch -p1 < patches/04_contact_book_recipients.patch
python labs/run.py 04 --replay labs/attempts/lab04-pattern.json   # [BLOCKED] tool send_email refused
python 04_dual_llm/agent.py --clean            # Bob still gets it
```

**Point at:** `send_email(to=$VAR2)`. The planner was never fooled, the DATA was.
Tested on real models. Use the lab for the "before" shot: live, the small reader poisons `$VAR2`
every time but sometimes misreads the file name, so the send only completes about 1 run in 3.
Full walkthrough: `04_dual_llm/TUTORIAL.md`.
**Takeaway:** hiding data from the planner protects control flow, not data flow.

## Block 5: Code-Then-Execute and CaMeL (51-77)

```bash
export LLM_MODEL=nvidia/nemotron-3-ultra-550b-a55b QLLM_MODEL=nvidia/nemotron-3.5-bolt-e4b  # big planner, small reader
python 05_code_then_execute/v1_plain.py                                 # live: contracts go to attacker@evil.example
python 05_code_then_execute/v2_provenance.py                            # live: same program, blocked by policy
python labs/run.py 05 --target v1                                       # you answer as the Q-LLM: you win
python labs/run.py 05 --target v2 --replay labs/attempts/lab05-v1.json  # same answers, CaMeL blocks
python labs/run.py 05 --target v2 --replay labs/solutions/lab05-wrongdoc.json  # intent gap: Bob gets the wrong file
python labs/camel_playground.py labs/playground/m1_exfiltrate_budget.py # policy ASKS: type y
patch -p1 < patches/05_domain_allowlist.patch
python labs/camel_playground.py labs/playground/m1_exfiltrate_budget.py # denied without asking
python labs/camel_playground.py labs/playground/m3_side_channel.py       # STRICT: blocked
python labs/camel_playground.py labs/playground/m3_side_channel.py --normal  # NORMAL: sent
```

**Point at:** the data-flow graph at the end of v2 (sources and readers of `address`), and
that m3 leaks one bit through an `if`, with no data in any argument.
**Takeaway:** track where every value came from and who may read it; enforce at every tool call.
Tested on real models: v1 leaked live, v2 blocked the same answer twice. Full walkthrough:
`05_code_then_execute/TUTORIAL.md`.

## Block 6: Map-Reduce and the gaps after CaMeL (77-83)

```bash
export LLM_MODEL=nvidia/nemotron-3.5-bolt-e4b QLLM_MODEL=nvidia/nemotron-3.5-bolt-e4b   # same model, fair comparison
python labs/run.py 03 --replay labs/solutions/lab03.json --naive   # one fooled model: CFP-06 alone, good talks gone
python labs/run.py 03 --replay labs/solutions/lab03.json           # fooled reviewer: CFP-06 takes ONE slot, good talks stay
patch -p1 < patches/03_human_review.patch
python labs/run.py 03 --replay labs/solutions/lab03.json           # human says n to CFP-06: CFP-05 moves up
```

**Say:** real models ignored this "SYSTEM OVERRIDE" in both designs when we tested. The lab shows
the day one doesn't: naive loses the whole decision, map-reduce loses one record.
Full walkthrough: `03_llm_map_reduce/TUTORIAL.md`.

Then the "gaps CaMeL leaves in auto mode" table in WORKSHOP_CONTEXT.md.

## Block 7: Checklist and Q&A (83-90)

The architect's checklist at the end of WORKSHOP_GUIDE.md.

## After the session

Undo the patches (`patch -p1 -R < patches/<name>.patch`), then `python labs/selftest.py`.
