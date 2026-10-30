# 07 The quarantined LLM in depth

> "if the Quarantined LLM is running a prompt that does something verifiable like classifying text into a fixed set
> of categories we can validate that one of those categories was output cleanly before safely passing that on"
> (Willison, 2023)

```
inbox (UNTRUSTED) ──> Q-LLM (QLLM_MODEL, no tools, one email at a time)
                        ├─ verified record {category: Enum, needs_reply, urgency 1..3} ──> P-LLM (LLM_MODEL)
                        └─ free-text summary ──> $SUMMARY_<id>, held by the controller ──┐
P-LLM reply template "... $SUMMARY_3 ..." ──> controller fills it, strips bad links ──> user
```
- **Two models.** Point `QLLM_MODEL` / `QLLM_BASE_URL` at a small local model (e.g. Ollama). The cloud P-LLM never sees your data (CaMeL's privacy bonus).
- **Verified vs unverified output.** Only schema-checked fields (enums, bools, bounded ints, extra fields forbidden) reach the P-LLM. Free text never does.
- **Audit.** At the end the script scans every recorded prompt and proves that no email text, and not the reset code, was sent to the P-LLM.

**What the injection still can do:** lie about its own record (it claims to be an urgent security alert) and put phishing text in its own summary, which the user sees. Willison's warning about social engineering still applies.
**What it can't do:** call tools, add fields, reach the P-LLM, or affect other emails.

Run: `python agent.py` · `python agent.py --naive` · `python agent.py --clean`
