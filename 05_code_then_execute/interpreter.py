"""A tiny CaMeL-style interpreter for a restricted subset of Python.

CaMeL paper, Sec. 5.4: "We build a custom Python interpreter that operates
over a restricted version of Python ... We use Python's built-in ast library
to parse the abstract syntax tree, and interpret each tree node in a
recursive fashion."

We never call exec(). We walk the AST ourselves, which lets us:
  1. wrap every value in a `Value` that carries capabilities (capabilities.py)
  2. record dependencies: in `c = a + b`, c depends on a and b
  3. run a security POLICY before every tool call (policies.py)

STRICT mode (CaMeL Sec. 5.4 and Sec. 7, side channels):
  * Inside an `if`/`for` block, everything assigned or called also depends on
    the test/iterable. Otherwise `if secret == "x": send_email(...)` would leak
    `secret` without any direct data flow.
  * After a quarantined-LLM call, every later tool call also depends on that
    call's inputs (the Q-LLM's answer could steer what happens next).

Supported: assignments, calls to registered tools, constants, f-strings, +,
comparisons, and/or/not, lists, dicts, subscripts, if/else, for, pass.
Everything else (imports, attributes, def, while, lambda, ...) is rejected,
so `().__class__.__bases__` style escapes are not even parseable here.

This is a teaching implementation (about 200 lines). The real one lives at
https://github.com/google-research/camel-prompt-injection
"""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass, field
from typing import Callable

from capabilities import Capabilities, Value, derive

_CMP = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.Gt: operator.gt,
    ast.LtE: operator.le, ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
}


class InterpreterError(Exception):
    pass


# Every node type the restricted language may contain (checked BEFORE anything runs).
_ALLOWED = (
    ast.Module, ast.Assign, ast.Expr, ast.If, ast.For, ast.Pass, ast.Name, ast.Load, ast.Store,
    ast.Constant, ast.JoinedStr, ast.FormattedValue, ast.BinOp, ast.Add, ast.Compare, ast.BoolOp,
    ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.List, ast.Dict, ast.Subscript, ast.Call, ast.keyword,
    *_CMP,
)


class PolicyViolation(Exception):
    pass


@dataclass
class Decision:
    allowed: bool
    reason: str


# A policy gets (tool_name, kwargs as Values, control-flow context Values) -> Decision
Policy = Callable[[str, dict[str, Value], tuple[Value, ...]], Decision]


@dataclass
class Interpreter:
    tools: dict[str, Callable[..., Value]]
    policy: Policy
    strict: bool = True
    qllm_tool: str = "query_quarantined_llm"
    env: dict[str, Value] = field(default_factory=dict)
    calls: list[tuple[str, dict[str, Value]]] = field(default_factory=list)
    _ctrl: list[Value] = field(default_factory=list)    # if/for tests we are inside
    _sticky: list[Value] = field(default_factory=list)  # inputs of earlier Q-LLM calls

    # ------------------------------------------------------------- statements
    def check(self, code: str) -> ast.Module:
        """Check the WHOLE program before any line runs, so a refused program has no side effects."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise InterpreterError(f"syntax error: {e}") from e
        for n in ast.walk(tree):
            if not isinstance(n, _ALLOWED):
                raise InterpreterError(f"not allowed: {type(n).__name__} (line {getattr(n, 'lineno', '?')})")
            if isinstance(n, ast.Assign) and (len(n.targets) != 1 or not isinstance(n.targets[0], ast.Name)):
                raise InterpreterError("only `name = expr` assignments are allowed")
            if isinstance(n, ast.For) and (not isinstance(n.target, ast.Name) or n.orelse):
                raise InterpreterError("only `for name in expr:` loops are allowed")
            if isinstance(n, ast.Compare) and len(n.ops) != 1:
                raise InterpreterError("only one comparison at a time")
            if isinstance(n, ast.Call) and not (isinstance(n.func, ast.Name) and n.func.id in self.tools):
                raise InterpreterError(f"only these functions may be called: {sorted(self.tools)}")
        return tree

    def run(self, code: str) -> None:
        for stmt in self.check(code).body:
            self._exec(stmt)

    def _exec(self, s: ast.stmt) -> None:
        if isinstance(s, ast.Assign):
            if len(s.targets) != 1 or not isinstance(s.targets[0], ast.Name):
                raise InterpreterError("only `name = expr` assignments are allowed")
            name = s.targets[0].id
            v = self._eval(s.value)
            ctrl = self._ctrl if self.strict else []
            self.env[name] = derive(v.raw, v, *ctrl, label=name)
        elif isinstance(s, ast.Expr):
            self._eval(s.value)
        elif isinstance(s, ast.If):
            test = self._eval(s.test)
            self._ctrl.append(test)
            for b in s.body if test.raw else s.orelse:
                self._exec(b)
            self._ctrl.pop()
        elif isinstance(s, ast.For):
            if not isinstance(s.target, ast.Name) or s.orelse:
                raise InterpreterError("only `for name in expr:` loops are allowed")
            it = self._eval(s.iter)
            self._ctrl.append(it)
            for item in list(it.raw)[:100]:  # bounded loops
                self.env[s.target.id] = derive(item, it, label=s.target.id)
                for b in s.body:
                    self._exec(b)
            self._ctrl.pop()
        elif isinstance(s, ast.Pass):
            pass
        else:
            raise InterpreterError(f"statement not allowed: {type(s).__name__}")

    # ------------------------------------------------------------ expressions
    def _eval(self, n: ast.expr) -> Value:
        if isinstance(n, ast.Constant):
            # Literals were written by the P-LLM, which only saw the user's request.
            return Value(n.value, Capabilities.user_literal(), label="")
        if isinstance(n, ast.Name):
            if n.id not in self.env:
                raise InterpreterError(f"unknown variable {n.id!r}")
            return self.env[n.id]
        if isinstance(n, ast.JoinedStr):
            parts = [self._eval(p.value if isinstance(p, ast.FormattedValue) else p) for p in n.values]
            return derive("".join(str(p.raw) for p in parts), *parts)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
            a, b = self._eval(n.left), self._eval(n.right)
            return derive(a.raw + b.raw, a, b)
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in _CMP:
            a, b = self._eval(n.left), self._eval(n.comparators[0])
            return derive(_CMP[type(n.ops[0])](a.raw, b.raw), a, b)
        if isinstance(n, ast.BoolOp):
            vals = [self._eval(v) for v in n.values]
            fn = all if isinstance(n.op, ast.And) else any
            return derive(fn(v.raw for v in vals), *vals)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            v = self._eval(n.operand)
            return derive(not v.raw, v)
        if isinstance(n, ast.List):
            elts = [self._eval(e) for e in n.elts]
            return derive([e.raw for e in elts], *elts)
        if isinstance(n, ast.Dict):
            keys = [self._eval(k) for k in n.keys]
            vals = [self._eval(v) for v in n.values]
            return derive({k.raw: v.raw for k, v in zip(keys, vals)}, *keys, *vals)
        if isinstance(n, ast.Subscript):
            base, idx = self._eval(n.value), self._eval(n.slice)
            return derive(base.raw[idx.raw], base, idx)
        if isinstance(n, ast.Call):
            return self._call(n)
        raise InterpreterError(f"expression not allowed: {type(n).__name__}")

    def _call(self, n: ast.Call) -> Value:
        if not isinstance(n.func, ast.Name) or n.func.id not in self.tools:
            raise InterpreterError(f"only these functions may be called: {sorted(self.tools)}")
        name = n.func.id
        fn = self.tools[name]
        # Bind positional args to parameter names so policies can look them up by name.
        params = list(fn.__code__.co_varnames[: fn.__code__.co_argcount])
        kwargs = {params[i]: self._eval(a) for i, a in enumerate(n.args)}
        kwargs.update({k.arg: self._eval(k.value) for k in n.keywords})

        context = tuple(self._ctrl) + tuple(self._sticky) if self.strict else ()
        decision = self.policy(name, kwargs, context)
        if not decision.allowed:
            raise PolicyViolation(f"{name}: {decision.reason}")
        self.calls.append((name, kwargs))
        result = fn(**kwargs)
        if self.strict and name == self.qllm_tool:
            self._sticky.extend(kwargs.values())
        return result
