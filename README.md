# Design Patterns for Securing LLM Agents: workshop code

Runnable, framework-free Python for the six prompt-injection design patterns from
[Beurer-Kellner et al. (2025)](https://arxiv.org/abs/2506.08837), including a small
CaMeL-style interpreter with capabilities and policies
([Debenedetti et al. 2025](https://arxiv.org/abs/2503.18813)).

Every demo runs in a fictional world: the AI assistant of a "RubixCON 2026" conference
organiser, with planted prompt injections in emails, calendar invites, shared docs and
CFP abstracts. Each script can run an **unprotected** agent (`--naive`) and the
**pattern** on the same data, so you see the attack land and then see it fail.

> Workshop rule: **assume the model is always fooled.** A pattern only counts if the
> *system* still holds, however well the attacker steers the model.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your NVIDIA key (nvapi-...) from https://build.nvidia.com
```

```bash
python labs/check_models.py  # which models YOUR key can actually use (the provider's list shows more)
```

Any OpenAI-compatible endpoint works (NVIDIA, OpenRouter, a local Ollama, OpenAI): set
`LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` in `.env`. Use one key per person; free tiers are
rate limited per key. The self-tests (`*/selftest.py`) run offline on a scripted model, so they
need no key.

## Follow the workshop

[`WORKSHOP_GUIDE.md`](WORKSHOP_GUIDE.md) walks you through every module step by step:
**watch** the demo, **hack** it in a lab (you play the compromised model), **defend** it in
code, and replay your attack.

```bash
python labs/selftest.py      # setup check: "all lab self-tests passed"
python labs/run.py           # list the labs
python labs/run.py 00        # start here
```

## Run the patterns

| # | Pattern | Command | What you'll see |
|---|---------|---------|-----------------|
| 00 | Naive baseline | `python 00_baseline_naive_agent/agent.py` | An email makes the agent forward your reset code and leak it via a markdown image |
| 01 | Action-Selector v1 | `python 01_action_selector/v1_switch.py` | The LLM can only pick from an Enum. "Admin mode" requests fail closed |
| 01 | Action-Selector v2 | `python 01_action_selector/v2_templated.py` | LLM-filled params validated by code. Another user's ticket is rejected |
| 02 | Plan-Then-Execute | `python 02_plan_then_execute/agent.py` | The poisoned invite can't add an email to the attacker, but it does poison the body |
| 03 | LLM Map-Reduce | `python 03_llm_map_reduce/agent.py` | One malicious CFP abstract can only game its own score |
| 04 | Dual LLM | `python 04_dual_llm/agent.py` | The P-LLM sees only `$VAR`s. Demo B shows the data-flow flaw |
| 05 | Code-Then-Execute v1 | `python 05_code_then_execute/v1_plain.py` | Plan as code. The attacker still picks the recipient |
| 05 | Code-Then-Execute v2 | `python 05_code_then_execute/v2_provenance.py` | Capabilities + policy BLOCK the exfiltration. `--clean` still sends to Bob |
| 06 | Context-Minimization | `python 06_context_minimization/agent.py` | The user's "100% discount" injection never reaches the reply writer |
| 07 | Quarantined LLM in depth | `python 07_quarantined_llm/agent.py` | Two separate models; only schema-verified records reach the planner; an audit proves it never saw your data |
| 08 | Secret keeper (the user is the attacker) | `python 08_secret_keeper/level1_naive.py` ... `level7_context_minimization.py` | One file per defence: prompt rules, output filter, input filter and an AI guard all leak; Action-Selector and Context-Minimization never put the code in a prompt |

Common flags:
- `--naive` runs the unprotected agent for comparison
- `--clean` removes the injections, to check the pattern still does its job
- `--ask "..."` lets you try your own input
- `VERBOSE=1` prints full prompts and replies

`python 05_code_then_execute/selftest.py` tests the capability interpreter and `python 08_secret_keeper/selftest.py` the secret keeper levels (no LLM needed).

## Labs

In the labs you plant text where an attacker could (an email, an invite, a doc, a CFP
abstract, your own message). **Every model that reads your text is yours: you type its
replies.** Models your text never reaches answer honestly, and that is the pattern working.
A scoreboard then checks what actually happened. Details: [`labs/README.md`](labs/README.md).

| Command | What it does |
|---------|--------------|
| `python labs/run.py 02` | attack plan-then-execute (`--naive` for the unprotected agent, `--hints` if stuck) |
| `python labs/run.py 05 --target v2 --replay labs/attempts/lab05-v1.json` | replay your v1 attack against CaMeL |
| `python labs/camel_playground.py labs/playground/m3_side_channel.py` | write the plan yourself, test the policy |
| `python labs/run.py 02 --real --data "..."` | a real model reads your injection (needs a key) |

The full hands-on session takes about 3 hours; `WORKSHOP_GUIDE.md` also has a 90-minute path. `WORKSHOP_CONTEXT.md` has the run of
show, the gaps CaMeL leaves in auto mode, a containment note and an architect's checklist (sections 10 to 13).

## Layout

```
shared/        llm client, offline mock (tests), fake world, console UI, naive agent, lab mode
00_ ... 07_    one folder per pattern; each has a README.md and runnable scripts
08_secret_keeper/  7 levels of one chatbot: prompt rules, filters, AI guard, then two patterns
labs/          lab runner, lab catalogue, CaMeL playground, model checker, selftest, reference solutions
patches/       live patches that close each pattern's gap (patterns 2-5)
WORKSHOP_GUIDE.md     attendee step-by-step: watch, hack, defend per module
WORKSHOP_CONTEXT.md   full background: sources, pattern summaries, CaMeL details, conventions
```

## References

- Beurer-Kellner et al., *Design Patterns for Securing LLM Agents against Prompt Injections*, 2025. https://arxiv.org/abs/2506.08837
- Debenedetti et al., *Defeating Prompt Injections by Design* (CaMeL), 2025. https://arxiv.org/abs/2503.18813, code at https://github.com/google-research/camel-prompt-injection
- Simon Willison:
  [Design patterns post (2025)](https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/) ·
  [CaMeL (2025)](https://simonwillison.net/2025/Apr/11/camel/) ·
  [The Dual LLM pattern (2023)](https://simonwillison.net/2023/Apr/25/dual-llm-pattern/) ·
  [Prompt injection: what's the worst that can happen? (2023)](https://simonwillison.net/2023/Apr/14/worst-that-can-happen/) ·
  [Living dangerously with Claude (2025)](https://simonwillison.net/2025/Oct/22/living-dangerously-with-claude/)
- Meta, *Agents Rule of Two*, 2025. https://ai.meta.com/blog/practical-ai-agent-security/
- Nasr, Carlini et al., *The Attacker Moves Second*, 2025. https://arxiv.org/abs/2510.09023
- Costa et al., *FIDES* (Microsoft), 2025. https://arxiv.org/abs/2505.23643, code at https://github.com/microsoft/fides
- Prior art: ReversecLabs code samples for the same patterns. https://github.com/ReversecLabs/design-patterns-for-securing-llm-agents-code-samples

The interpreter in `05_code_then_execute/` is a teaching implementation. It is not a security product.

## License

MIT, see [LICENSE](LICENSE).
