# Live patches for patterns 2-5

Each pattern guarantees something, and leaves one gap. Each patch closes that
gap in plain code (never in a prompt), and is small enough to read on screen.

| Patch | Pattern | The gap it closes | Lines |
|-------|---------|-------------------|-------|
| `02_calendar_fields_only.patch` | Plan-Then-Execute | the plan is frozen, but the outsider's invite text still flows into the email body | 5 |
| `03_human_review.patch` | LLM Map-Reduce | one submission can still lie about itself and win a slot | 19 |
| `04_contact_book_recipients.patch` | Dual LLM | the P-LLM never saw the attack, but the Q-LLM picked the recipient | 3 |
| `05_domain_allowlist.patch` | Code-Then-Execute (CaMeL) | the policy ASKS before sending outside, and a tired user clicks yes | 4 |

```bash
patch -p1 < patches/02_calendar_fields_only.patch      # apply
patch -p1 -R < patches/02_calendar_fields_only.patch   # undo
```

Undo every patch when you are done: `python labs/selftest.py` expects the
unpatched code (the patched code makes some lab goals unwinnable, on purpose).
The step-by-step demo for each patch is in WORKSHOP_GUIDE.md, "Live patching".
