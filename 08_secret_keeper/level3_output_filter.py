"""Level 3 - PATCH: plain code blocks any reply that contains the code.

Finally a check in CODE, not in the prompt. If the exact code appears in the
reply, the user gets a refusal instead.

WHY IT IS NOT ENOUGH: the filter knows one spelling of the secret. The model
can write it spaced out, letter by letter, backwards, in another language or
inside a story, and the filter has to guess every one of them. The secret is
still in the prompt, so the model can still hand it over in some form.

Run:   python 08_secret_keeper/level3_output_filter.py
Next:  level4_input_filter.py
"""

from keeper import REFUSAL, SECRET, run
from level2_prompt_rules import Bot as Level2Bot

from shared import ui


class Bot(Level2Bot):
    def answer(self, msg: str) -> str:
        reply = super().answer(msg)
        if SECRET.lower() in reply.lower():  # <- the patch
            ui.blocked("output filter: the reply contained the staff code, so it was replaced")
            return REFUSAL
        return reply


if __name__ == "__main__":
    run(Bot(), 3, "+ output filter in code")
