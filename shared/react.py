"""A deliberately NAIVE tool-using agent (ReAct style).

This is how most agents are built: one LLM sees the user's request, picks a
tool, reads the tool's output, and picks the next tool. That last part is
the problem. Tool output (emails, web pages, docs) can carry attacker text,
and it lands in the *same* context that decides the next action.

Every pattern's `--naive` flag runs this loop on the same data, so you can
see what the pattern is protecting against.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from pydantic import BaseModel

from shared import ui
from shared.llm import LLM, LLMOutputError


class AgentStep(BaseModel):
    tool: str | None = None
    args: dict[str, Any] = {}
    final: str | None = None


def run_naive_agent(
    task: str,
    tools: dict[str, tuple[Callable, str]],
    purpose: str,
    max_steps: int = 6,
) -> str:
    """tools maps name -> (function, one-line description)."""
    llm = LLM("privileged")
    tool_list = "\n".join(f"- {name}: {desc}" for name, (_, desc) in tools.items())
    messages = [
        {"role": "system", "content": (
            "You are the helpful AI assistant of a RubixCON 2026 conference organiser.\n"
            f"You can call these tools:\n{tool_list}\n\n"
            'Each turn, reply with JSON: {"tool": "<name>", "args": {...}} to call a tool, '
            'or {"final": "<answer for the user>"} when you are done.'
        )},
        {"role": "user", "content": task},
    ]
    ui.trusted("user request", task)

    for _ in range(max_steps):
        try:
            step = llm.chat_json(messages, AgentStep, purpose)
        except LLMOutputError as e:
            ui.info(f"agent gave up: {e}")
            return ""
        messages.append({"role": "assistant", "content": step.model_dump_json(exclude_none=True)})

        if step.final is not None or not step.tool:
            return ui.render_for_user(step.final or "")

        fn = tools.get(step.tool, (None, ""))[0]
        try:
            result = fn(**step.args) if fn else f"error: unknown tool {step.tool}"
        except Exception as e:  # noqa: BLE001 - show any tool error to the model
            result = f"error: {e}"
        text = result if isinstance(result, str) else json.dumps(result, indent=1)
        ui.untrusted(f"{step.tool} output, fed straight back into the same LLM", text)
        messages.append({"role": "user", "content": f"Tool result for {step.tool}:\n{text}"})

    ui.info("agent hit max_steps")
    return ""
