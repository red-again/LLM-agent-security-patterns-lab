# 03 LLM Map-Reduce

> "dispatch an isolated LLM-agent to process individual pieces of 3rd party data (a map operation)" (paper, Sec. 3.3)

```
CFP-01 ──> Q-LLM ──> {on_topic, score}  ┐
CFP-02 ──> Q-LLM ──> {on_topic, score}  ├──> plain Python reduce ──> top 3
  ...       (fresh, isolated, no tools)  ┘
```
**Guarantee:** a malicious abstract affects only its own record, within the schema (score 10 is rejected; 5 is the max).
**Not stopped:** that record can still be gamed. Keep a human on the final decision.
**Case studies:** Resume Screening Assistant; the paper's invoice-filtering example.

**Step-by-step tutorial (tested on real models):** [TUTORIAL.md](TUTORIAL.md)
