"""Capabilities: metadata attached to every value, as in CaMeL.

CaMeL paper, Sec. 5.3: "The current implementation of CaMeL tags data with
information on data provenance and a set of allowed readers. Readers are
expressed as either the Public singleton ... or as a set of users."

  sources  who could have written (influenced) this value.
           "user" = a literal in the plan code (the P-LLM only saw the user's
           request), otherwise the principals behind the data, e.g. the editors
           of a drive file or the sender of an email (CaMeL's "inner source").
  readers  who is allowed to see this value. None means Public.

When values are combined, sources are UNIONED (more people could have
influenced the result) and readers are INTERSECTED (only people allowed to
read every input may read the output).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from typing import Any

PUBLIC = None  # readers=None means anyone may read it
TRUSTED_PRINCIPALS = frozenset({"user", "you@rubixcon.example"})

_ids = count(1)


@dataclass(frozen=True)
class Capabilities:
    sources: frozenset[str]
    readers: frozenset[str] | None = PUBLIC

    @staticmethod
    def user_literal() -> Capabilities:
        return Capabilities(frozenset({"user"}), PUBLIC)

    def merge(self, other: Capabilities) -> Capabilities:
        if self.readers is None:
            readers = other.readers
        elif other.readers is None:
            readers = self.readers
        else:
            readers = self.readers & other.readers
        return Capabilities(self.sources | other.sources, readers)

    @property
    def trusted(self) -> bool:
        return self.sources <= TRUSTED_PRINCIPALS

    def can_read(self, who: str) -> bool:
        return self.readers is None or who in self.readers

    def __str__(self) -> str:
        readers = "Public" if self.readers is None else "{" + ", ".join(sorted(self.readers)) + "}"
        flag = "trusted" if self.trusted else "UNTRUSTED"
        return f"{flag} sources={{{', '.join(sorted(self.sources))}}} readers={readers}"

    def short(self) -> str:
        """Compact form for the graph: e-mail local parts only (bob, guest, you)."""
        def names(xs):
            return ",".join(sorted(x.split("@")[0] for x in xs))
        readers = "Public" if self.readers is None else names(self.readers)
        return f"{'trusted' if self.trusted else 'UNTRUSTED'} src={names(self.sources)} readers={readers}"


@dataclass(eq=False)
class Value:
    """A value plus its capabilities and the values it was derived from."""

    raw: Any
    caps: Capabilities
    deps: tuple[Value, ...] = ()
    label: str = ""
    id: int = field(default_factory=lambda: next(_ids))

    def __repr__(self) -> str:
        return f"Value({self.raw!r}, {self.caps})"


def derive(raw: Any, *parents: Value, label: str = "", extra: Capabilities | None = None) -> Value:
    """A new value computed from `parents`: it inherits all their capabilities."""
    caps = extra or Capabilities(frozenset(), PUBLIC)
    for p in parents:
        caps = caps.merge(p.caps)
    return Value(raw, caps, tuple(parents), label)


def merged_caps(values) -> Capabilities:
    caps = Capabilities(frozenset(), PUBLIC)
    for v in values:
        caps = caps.merge(v.caps)
    return caps


def dependency_tree(v: Value, indent: str = "", seen: set[int] | None = None) -> str:
    """Pretty-print where a value came from (the data-flow graph)."""
    seen = set() if seen is None else seen
    raw = repr(v.raw)
    raw = raw if len(raw) < 40 else raw[:37] + "..."
    line = f"{indent}{v.label or '<expr>'} = {raw}   [{v.caps.short()}]"
    if v.id in seen:
        return line + "  (see above)"
    seen.add(v.id)
    children = [dependency_tree(d, indent + "    ", seen) for d in v.deps if d.label]
    return "\n".join([line, *children])
