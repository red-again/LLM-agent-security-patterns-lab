# 02 Plan-Then-Execute

> "prevent the tool outputs from influencing the choice of actions taken by the agent" (paper, Sec. 3.2)

```
user ──> planner LLM ──> frozen plan [read_calendar, summarise($1), send_email(boss, $2)]
                                   └──> executor runs it; data flows via $1, $2 ...
```
**Guarantee:** control-flow integrity. The poisoned invite can't add `send_email(attacker)` or change the recipient.
**Not stopped:** poisoned *content*. The run shows the IBAN fraud line landing in the boss's email body.
**Case studies:** Email & Calendar Assistant, SQL Agent.

**Step-by-step tutorial (tested on real models):** [TUTORIAL.md](TUTORIAL.md)
