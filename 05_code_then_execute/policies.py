"""Security policies: plain Python functions that run before every tool call.

CaMeL paper, Sec. 5.2: "security policies: functions that define what is and
what is not allowed when calling tools". Simon Willison's summary:
  get_last_email : always allowed
  send_email     : only if `recipient` is trusted

Our send_email policy, in order:
  1. Every recipient must be an allowed READER of all the data in the email
     (args and control-flow context). If so, allow: the email reveals nothing
     new to them.
  2. Otherwise, if the recipient address itself came only from the user (a
     literal in the plan), the user clearly meant it, so ASK for confirmation.
  3. Otherwise, DENY. An address that came out of untrusted data must not
     receive data it is not allowed to read. This is what stops 04's Demo B.

Policies see Values (capabilities included), never just raw strings.
"""

from __future__ import annotations

import sys

from capabilities import Value, merged_caps
from interpreter import Decision

from shared import ui

ALWAYS_ALLOWED = {"find_latest_meeting_notes", "read_file", "query_quarantined_llm", "display"}


def _ask_user(question: str) -> bool:
    if not sys.stdin.isatty():
        ui.info("    (non-interactive run: treating 'ask user' as NO)")
        return False
    return input(f"    {question} [y/N] ").strip().lower() == "y"


def send_email_policy(kwargs: dict[str, Value], context: tuple[Value, ...]) -> Decision:
    to = kwargs["to"]
    recipients = [to.raw] if isinstance(to.raw, str) else list(to.raw)
    data_caps = merged_caps([*kwargs.values(), *context])
    not_allowed = [r for r in recipients if not data_caps.can_read(r)]

    if not not_allowed:
        return Decision(True, "every recipient may read all data in this email")
    if to.caps.trusted:
        ok = _ask_user(f"Send data readable only by {sorted(data_caps.readers)} to {not_allowed}?")
        return Decision(ok, "user confirmed" if ok else "user declined")
    return Decision(False, f"recipient {not_allowed} came from UNTRUSTED data ({to.caps}) "
                           f"and is not an allowed reader of the email's content")


def policy(tool: str, kwargs: dict[str, Value], context: tuple[Value, ...]) -> Decision:
    if tool in ALWAYS_ALLOWED:
        return Decision(True, "always allowed")
    if tool == "send_email":
        return send_email_policy(kwargs, context)
    return Decision(False, f"no policy for {tool}: deny by default")
