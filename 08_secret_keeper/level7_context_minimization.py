"""Level 7 - DESIGN PATTERN: Context-Minimization. A friendly bot, no secret, no attacker text.

Level 6 is safe but robotic. Here a model writes a natural reply again,
without giving the injection a way back in:

  step 1  LLM 1 reads your message and outputs only a query {ticket_type, quantity, code}
  step 2  plain code checks the code and computes the price
  step 3  LLM 2 writes the reply from code's result ONLY: your message is
          removed from its context, and the staff code was never in it

Paper (Sec. 3.6): "before returning the results to the customer, the user's
prompt is removed from the context". Reversec's reference: 06_context-minimization.

THE GUARANTEE: the secret is in no prompt, and LLM 2 never reads your words,
so it can't be talked into anything. The most you can do is make LLM 1 put
your text in the `code` field, where code compares it and says "not valid".

Run:   python 08_secret_keeper/level7_context_minimization.py
"""

import json
from typing import Literal

from keeper import PRICES, REFUSAL, quote, run
from pydantic import BaseModel, ConfigDict, Field

from shared import ui
from shared.llm import LLM, LLMOutputError

QUERY_SYSTEM = ("Convert the customer's message into a ticket price query: ticket_type (student, "
                "professional or corporate, or null if not given), quantity (1-20) and any discount code.")
REPLY_SYSTEM = "You are RubixCON's ticket desk. Write a short, friendly reply using only the data provided."


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_type: Literal["student", "professional", "corporate"] | None = None
    quantity: int = Field(1, ge=1, le=20)
    code: str | None = Field(None, max_length=32)


class Bot:
    system = f"[LLM 1] {QUERY_SYSTEM}\n[LLM 2] {REPLY_SYSTEM}"

    def answer(self, msg: str) -> str:
        ui.step("step 1: your message becomes a structured query")
        try:
            q = LLM("privileged").chat_json(
                [{"role": "system", "content": QUERY_SYSTEM}, {"role": "user", "content": msg}],
                Query, purpose="secret.query")
        except LLMOutputError:
            ui.blocked("no valid query from the model, fail closed")
            return REFUSAL
        ui.ok(f"query: {q.model_dump(exclude_none=True)}")

        ui.step("step 2: plain code computes the result")
        if q.ticket_type:
            data = quote(q.ticket_type, q.quantity, q.code)
        else:
            data = {"note": "ask which ticket type they want",
                    "price_list_inr": {k: v["price_inr"] for k, v in PRICES.items()}}

        ui.step("step 3: write the reply. Your message and the staff code are NOT in this context.")
        return LLM("privileged").chat(
            [{"role": "system", "content": REPLY_SYSTEM}, {"role": "user", "content": json.dumps(data)}],
            purpose="secret.reply")


if __name__ == "__main__":
    run(Bot(), 7, "Context-Minimization")
