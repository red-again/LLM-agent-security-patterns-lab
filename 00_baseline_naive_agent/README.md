# 00 Baseline: the naive agent

```
user ──> LLM ──> tool ──> output (UNTRUSTED) ──┐
          ^                                    │
          └──────── same context ──────────────┘   <- the attacker's text picks the next tool
```
The agent has private data (a reset code), untrusted input (a stranger's email) and a way out
(send_email, markdown images): Willison's *lethal trifecta*.

- `python agent.py`: the email's hidden instructions forward your reset code and leak it in an image URL
- `python agent.py --clean`: a benign inbox

Refs: [Prompt injection: what's the worst that can happen?](https://simonwillison.net/2023/Apr/14/worst-that-can-happen/)
