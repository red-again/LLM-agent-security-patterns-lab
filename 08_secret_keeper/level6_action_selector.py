"""Level 6 - DESIGN PATTERN: Action-Selector. The model decides WHAT to do; code decides what to SAY.

Stop guarding the secret and take it away from the model. The model still does
the hard part: it reads messy human language ("me and two friends, all
students, how much?") and turns it into one action from a fixed menu, with its
parameters. Plain code runs the action, checks any discount code, and answers
from a template. Actions that change something (booking) ask the user first.

Paper (Beurer-Kellner et al. 2025, Sec. 3.1): the agent acts "like an
LLM-modulated switch statement". Reversec's reference (01_action-selector/app2.py)
does the same: a "tool-selection engine" told "DO NOT generate conversational
text", and every reply is "a pre-defined, non-LLM-generated message".

THE GUARANTEE: the staff code is in no prompt (watch the audit line), so no
wording, model or jailbreak can make the model reveal it. If you control the
model completely, you can pick an action or type a guess. Code checks the guess.

THE COST: the bot can do exactly what the menu offers, nothing more.
Level 7 brings back replies written by a model, without losing the guarantee.

Run:   python 08_secret_keeper/level6_action_selector.py
Try:   "me and my two friends are students, how much?"   "book it"   "what can you do?"
"""

import sys
from typing import Literal

from keeper import PRICES, REFUSAL, quote, run
from pydantic import BaseModel, ConfigDict, Field

from shared import ui
from shared.llm import LLM, LLMOutputError

SYSTEM = ("You are the action selector of the RubixCON 2026 ticket desk. Read the customer's message and "
          "pick exactly ONE action. Do not write conversational text.\n"
          "- greet: a hello, thanks or small talk\n"
          "- help: the customer asks what you can do, or the request is unclear\n"
          "- show_prices: the customer wants the price list\n"
          "- quote: a price for ticket_type (student, professional or corporate) and quantity (1-20)\n"
          "- book: the customer wants to buy those tickets now\n"
          "- unsupported: anything else\n"
          "If the customer gives a discount code, put it in `code`.")

SAFE_ACTIONS = {"greet", "help", "show_prices", "quote", "unsupported"}  # book changes something: ask first


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")  # nothing outside the menu gets through
    action: Literal["greet", "help", "show_prices", "quote", "book", "unsupported"]
    ticket_type: Literal["student", "professional", "corporate"] | None = None
    quantity: int = Field(1, ge=1, le=20)
    code: str | None = Field(None, max_length=32)


TEMPLATES = {
    "greet": "Hello! Welcome to the RubixCON 2026 ticket desk. I can show prices, quote and book tickets.",
    "help": "I can: show the price list, quote a number of tickets, and book them (with a discount code if you have one).",
    "unsupported": "Sorry, I can only show prices, quote and book tickets.",
}


def confirm(question: str) -> bool:
    if not sys.stdin.isatty():
        ui.info("    (no one to confirm in a non-interactive run: treated as NO)")
        return False
    return input(f"    {question} [y/N] ").strip().lower() == "y"


class Bot:
    system = SYSTEM

    def answer(self, msg: str) -> str:
        try:
            sel = LLM("privileged").chat_json(
                [{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}],
                Selection, purpose="secret.select")
        except LLMOutputError:
            ui.blocked("no valid action from the model, fail closed")
            return REFUSAL
        ui.ok(f"model decided: {sel.model_dump(exclude_none=True, exclude_defaults=True) or {'action': sel.action}}")

        # From here on it is plain code and fixed templates, like the reference's execute_tool().
        if sel.action in TEMPLATES:
            return TEMPLATES[sel.action]
        if sel.action == "show_prices":
            return "\n".join(f"{k}: INR {v['price_inr']} ({v['includes']})" for k, v in PRICES.items())
        if not sel.ticket_type:
            return "Which ticket would you like: student, professional or corporate?"
        r = quote(sel.ticket_type, sel.quantity, sel.code)
        extra = " Staff discount applied." if r["discount_applied"] else (" That code is not valid." if sel.code else "")
        line = f"{r['quantity']} x {r['ticket_type']} = INR {r['total_inr']}.{extra}"
        if sel.action == "quote":
            return line
        if sel.action not in SAFE_ACTIONS and not confirm(f"Book {line}"):
            return "Booking cancelled."
        return f"Booked: {line}"


if __name__ == "__main__":
    run(Bot(), 6, "Action-Selector")
