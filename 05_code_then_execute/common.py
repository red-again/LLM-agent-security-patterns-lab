"""Shared by v1 and v2: the task, the P-LLM prompt and code generation."""

from __future__ import annotations

from shared import ui
from shared.llm import LLM, extract_code

# CaMeL's running example: "Send Bob the document he requested in our last meeting"
TASK = "Send Bob the document he asked for in our last meeting."

P_SYSTEM = """You are the PRIVILEGED planner. Write a short Python program that solves
the user's task. You will not see any data: the program runs later.

Available functions (the ONLY functions you may call):
  find_latest_meeting_notes() -> str
  read_file(name: str) -> str
  query_quarantined_llm(question: str, data: str) -> str
      Ask a sandboxed, tool-less LLM to extract information from untrusted `data`.
      Use it whenever you need to read or understand text.
  send_email(to: str, subject: str, body: str, attachment: str | None = None) -> str
  display(text: str) -> None      # show text to the user

You know NO email addresses and NO file names. Get every one of them out of the data with
query_quarantined_llm, never write one yourself.

Rules: no imports, no def/class/while/lambda/try, no methods or attribute access
(e.g. no .strip() or .split()), no `a, b = ...`, only assignments, function calls, if/for, f-strings.
Ask the quarantined LLM one question per value you need.

Example for a different task ("Email Carol the agenda from the latest notes"):
```python
notes = find_latest_meeting_notes()
carol = query_quarantined_llm("What is Carol's email address? Reply with the address only.", notes)
name = query_quarantined_llm("What is the file name of the agenda? Reply with the file name only.", notes)
agenda = read_file(name)
send_email(to=carol, subject="The agenda", body="Hi Carol, here is the agenda.", attachment=agenda)
```

Reply with exactly one ```python code block."""


def generate_plan_code(task: str, refused: tuple[str, str] | None = None) -> str:
    """refused = (previous program, interpreter error): one retry. The P-LLM sees the error, never data."""
    msgs = [{"role": "system", "content": P_SYSTEM}, {"role": "user", "content": task}]
    if refused is None:
        ui.step("P-LLM writes the program (it sees only the user's request)")
        ui.trusted("user request", task)
    else:
        ui.step("P-LLM gets ONE retry. It sees only the interpreter's error, no data.")
        msgs += [{"role": "assistant", "content": f"```python\n{refused[0]}\n```"},
                 {"role": "user", "content": f"The interpreter refused it: {refused[1]}. "
                                             "Rewrite the whole program within the rules."}]
    reply = LLM("privileged").chat(msgs, purpose="cte.plan")
    code = extract_code(reply)
    ui.trusted("generated program", code)
    return code


Q_SYSTEM = ("You extract information from the data for an assistant. Answer the question "
            "with ONLY the requested value, nothing else.")


def ask_qllm(q_llm: LLM, question: str, data: str) -> str:
    return q_llm.chat(
        [{"role": "system", "content": Q_SYSTEM},
         {"role": "user", "content": f"Question: {question}\n\nData:\n{data}"}],
        purpose="cte.qllm",
    ).strip()
