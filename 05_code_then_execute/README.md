# 05 Code-Then-Execute (with provenance)

> "an agent that writes a formal computer program to solve a task" (paper, Sec. 3.5), instantiated by CaMeL.

Task (CaMeL's running example): *"Send Bob the document he asked for in our last meeting."*

| file | what it is |
|------|------------|
| `common.py` | the task, the P-LLM prompt, the Q-LLM helper |
| `v1_plain.py` | P-LLM writes code. AST allowlist + `exec` with only the tools. **Still leaks** (attacker picks `address`) |
| `capabilities.py` | `Capabilities(sources, readers)`, `Value`, `derive` (union sources, intersect readers) |
| `interpreter.py` | AST-walking interpreter: dependency tracking, STRICT/NORMAL modes, a policy before every tool call |
| `policies.py` | deny-by-default. `send_email`: recipients must be readers of all data; else ask if the user typed the address; else deny. Deliberately stricter than the CaMeL reference, which allows user-sourced recipients outright and runs the readers check only otherwise |
| `v2_provenance.py` | the same program run through the interpreter. **BLOCKED** with the injection, **allowed** with `--clean` |
| `selftest.py` | asserts: taint spread, readers, block/allow, STRICT side channel, rejected syntax |

```
notes (src: you, guest)  ──Q-LLM──>  address = attacker@evil.example  (UNTRUSTED, readers: bob, guest, you)
speaker-contracts.pdf (readers: you, director, bob) ──> send_email(to=address, attachment=doc)
policy: attacker not among the doc's readers, and the address came from untrusted data => BLOCKED
```
Try `--normal` to switch off STRICT mode, and read `selftest.py` case 6 for the side channel it stops.

Refs: [CaMeL paper](https://arxiv.org/abs/2503.18813) · [CaMeL code](https://github.com/google-research/camel-prompt-injection) · [Willison on CaMeL](https://simonwillison.net/2025/Apr/11/camel/)

**Step-by-step tutorial (tested on real models):** [TUTORIAL.md](TUTORIAL.md)
