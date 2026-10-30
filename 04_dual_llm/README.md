# 04 Dual LLM

> "it is absolutely crucial that unfiltered content output by the Quarantined LLM is never forwarded on to the Privileged LLM" (Willison, 2023)

```
user ──> P-LLM (tools, sees only $VAR names) ──actions──> Controller (plain code, holds $VAR values)
                                                              │
                                              Q-LLM (no tools, reads untrusted data)
```
- **Demo A** (`--ask "Summarise my latest email for me."`, not run by default): the injection reaches only the Q-LLM. The P-LLM can't be steered, and the exfil image is stripped.
- **Demo B** (send Bob the doc): the CaMeL critique. The Q-LLM extracts the *attacker's* address, `$VAR2` flows into `send_email`, and the doc leaks.
  The control flow was safe. The **data flow** was not. Pattern 05 v2 fixes this.

Refs: [Dual LLM pattern](https://simonwillison.net/2023/Apr/25/dual-llm-pattern/) · [CaMeL post](https://simonwillison.net/2025/Apr/11/camel/)

**Step-by-step tutorial (tested on real models):** [TUTORIAL.md](TUTORIAL.md)
