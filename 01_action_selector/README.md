# 01 Action-Selector

> "The agent acts merely as an action selector ... like an LLM-modulated 'switch' statement." (paper, Sec. 3.1)

```
user ──> LLM ──> {one of N actions}  ──> code runs it ──> result to user (never back to an LLM)
```
| file | idea |
|------|------|
| `v1_switch.py` | Enum of 4 actions. An off-list choice fails validation, so it fails closed |
| `v2_templated.py` | Actions with params (`ticket_id`, `track`). Code checks format and **ownership** from the session |

**Guarantee:** untrusted data never reaches an LLM that chooses actions.
**Not stopped:** untrusted text displayed to the user (see the talk abstract). Utility is tiny.
**Case studies:** Customer Service Chatbot.
