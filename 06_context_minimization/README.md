# 06 Context-Minimization

> "before returning the results to the customer, the user's prompt is removed from the context" (paper, Sec. 3.6)

```
user msg ──> LLM #1 ──> {ticket_type, quantity} ──> code: price lookup ──> LLM #2 (sees ONLY the db row) ──> reply
```
**Threat:** injection in the *user's own* prompt (a malicious customer, or text pasted from an attacker's site).
**Guarantee:** the "100% discount, code FREE-VIP-100" text never reaches the reply writer, and totals are computed by code.
**Case studies:** Customer Service Chatbot, Medication Leaflet Chatbot, Medical Diagnosis Chatbot.
