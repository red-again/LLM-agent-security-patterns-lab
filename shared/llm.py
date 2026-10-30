"""One tiny LLM client for every demo.

Talks to any OpenAI-compatible endpoint. The default is the NVIDIA API
(https://build.nvidia.com), where one `nvapi-...` key gives access to many
open models. Ollama, LM Studio, OpenRouter, Groq or OpenAI work too: change
LLM_BASE_URL / LLM_MODEL in `.env`.

If no API key is set, or MOCK_LLM=1, a scripted offline model is used
(see shared/mock_llm.py), so every demo also runs without Wi-Fi.

Two roles, following the Dual LLM / CaMeL vocabulary:
  role="privileged"   -> plans, may lead to tool calls, must NEVER see untrusted data
  role="quarantined"  -> processes untrusted data, has no tools
The quarantined model can be a different (smaller, even local) model via
QLLM_MODEL / QLLM_BASE_URL, which is the "privacy bonus" from the CaMeL paper.

We use JSON in the prompt + pydantic validation instead of native
function-calling, because not every hosted open model supports tools.
Invalid output gets one retry, then we fail closed (raise).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from shared import lab, ui

ROOT = Path(__file__).resolve().parent.parent
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # python-dotenv is optional
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))

T = TypeVar("T", bound=BaseModel)
_mock_notice_shown = False

# Every call is recorded here: {"role", "model", "messages", "reply"}.
# Demos use it to audit what each model (and its provider) actually saw.
TRANSCRIPT: list[dict] = []


class LLMOutputError(RuntimeError):
    """The model did not produce valid structured output. Callers fail closed."""


def mock_enabled() -> bool:
    if os.getenv("MOCK_LLM", "").lower() in ("1", "true", "yes"):
        return True
    return not os.getenv("LLM_API_KEY")


class LLM:
    def __init__(self, role: str = "privileged"):
        global _mock_notice_shown
        assert role in ("privileged", "quarantined")
        self.role = role
        self.mock = mock_enabled()
        q = role == "quarantined"
        self.model = (q and os.getenv("QLLM_MODEL")) or os.getenv("LLM_MODEL", DEFAULT_MODEL)
        self.base_url = "offline"
        if self.mock:
            self.model = f"mock-{role}"
            if not _mock_notice_shown:
                ui.info("(using the offline MOCK model: it obeys every injection it sees. "
                        "Set LLM_API_KEY in .env for a real model.)")
                _mock_notice_shown = True
            return
        from openai import OpenAI

        self.base_url = (q and os.getenv("QLLM_BASE_URL")) or os.getenv("LLM_BASE_URL", NVIDIA_BASE_URL)
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=(q and os.getenv("QLLM_API_KEY")) or os.environ["LLM_API_KEY"],
        )
        # Provider-specific request fields, e.g. turning reasoning off on Nemotron:
        # LLM_EXTRA_BODY={"chat_template_kwargs": {"enable_thinking": false}}
        self.extra_body = json.loads((q and os.getenv("QLLM_EXTRA_BODY")) or os.getenv("LLM_EXTRA_BODY") or "{}")
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1500"))

    # ------------------------------------------------------------------
    def chat(self, messages: list[dict], purpose: str, temperature: float = 0.0, *, structured: bool = False) -> str:
        """Plain text completion. `purpose` labels the call (and picks the mock reply)."""
        ui.llm(self.role, purpose, self.model)
        if lab.takeover(self.role, purpose, messages):  # labs: your text is here, you reply
            reply = lab.attacker_reply(self.role, purpose, messages, structured)
        elif self.mock:
            from shared import mock_llm

            reply = mock_llm.respond(purpose, messages)
        else:
            resp = self.client.chat.completions.create(
                model=self.model, messages=messages, temperature=temperature,
                max_tokens=self.max_tokens, extra_body=self.extra_body or None,
            )
            reply = _strip_thinking(resp.choices[0].message.content or "")
        ui.llm_io(messages, reply)
        TRANSCRIPT.append({"role": self.role, "model": self.model, "messages": messages, "reply": reply})
        return reply

    def chat_json(self, messages: list[dict], schema: type[T], purpose: str) -> T:
        """Completion that must validate against a pydantic schema, or raise LLMOutputError."""
        instruction = (
            "\n\nReply with ONLY one JSON object (no prose, no code fences) that matches "
            f"this JSON schema:\n{json.dumps(schema.model_json_schema())}"
        )
        msgs = _with_system_suffix(messages, instruction)
        last_error = ""
        for _attempt in range(2):
            raw = self.chat(msgs, purpose, structured=True)
            try:
                return schema.model_validate_json(_extract_json(raw))
            except (ValidationError, ValueError) as e:
                last_error = str(e).splitlines()[0] if str(e) else repr(e)
                ui.info(f"    output rejected by schema: {last_error}")
                msgs = msgs + [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": f"That was invalid ({last_error}). Reply with valid JSON only."},
                ]
        raise LLMOutputError(f"{purpose}: no valid output after retry ({last_error})")


# ----------------------------------------------------------------------
def _with_system_suffix(messages: list[dict], suffix: str) -> list[dict]:
    msgs = [dict(m) for m in messages]
    if msgs and msgs[0]["role"] == "system":
        msgs[0]["content"] += suffix
    else:
        msgs.insert(0, {"role": "system", "content": suffix.strip()})
    return msgs


def _strip_thinking(text: str) -> str:
    """Reasoning models (nemotron, qwen-thinking, ...) may wrap thoughts in <think> tags."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def _extract_json(text: str) -> str:
    """Pull the first {...} object out of a reply (models love code fences)."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in reply")
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(text[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("unterminated JSON object")


def extract_code(text: str) -> str:
    """Pull Python out of a ```python fenced block (or return the text as-is)."""
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, flags=re.S)
    return (m.group(1) if m else text).strip()
