"""Formatting utilities for formula strings using PEG parsing."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from pest import Parser
from pest.pairs import Pair

# Operator rule names from grammar
_OPERATORS = frozenset(("add", "sub", "mul", "div"))

# PEG grammar for parsing mathematical expressions
_GRAMMAR = """\
WHITESPACE   =  _{ " " | "\\t" | NEWLINE }

program      =   { SOI ~ expr ~ EOI }
  expr       =   { prefix* ~ primary ~ postfix* ~ (infix ~ prefix* ~ primary ~ postfix* )* }
    infix    =  _{ add | sub | mul | div }
      add    =   { "+" }
      sub    =   { "-" }
      mul    =   { "*" }
      div    =   { "/" }
    prefix   =  _{ neg }
      neg    =   { "-" }
    postfix  =  _{ method_call }
      method_call = @{ "." ~ (ASCII_ALPHA | "_")+ ~ "(" ~ ")" }
    primary  =  _{ int | "(" ~ expr ~ ")" | ident }
      int    =  @{ (ASCII_NONZERO_DIGIT ~ ASCII_DIGIT+ | ASCII_DIGIT) }
      ident  =  @{ (ASCII_ALPHA | "_")+ ~ (prop_access)* }
      prop_access = @{ "." ~ (ASCII_ALPHA | "_")+ ~ !("(") }
"""


@cache
def get_parser() -> Parser:
    """Get or create the parser instance."""
    return Parser.from_grammar(_GRAMMAR)


def format_recursive(s: str, max_len: int) -> str:
    """Format a formula string, breaking long lines at operators."""
    s = s.strip()
    if not s or len(s) <= max_len:
        return s

    try:
        tree = get_parser().parse("program", text=s)
        program = tree.first()
        for child in program.inner():
            if child.name == "expr":
                return _format_expr(child, max_len)
    except Exception:  # noqa: S110 - gracefully fall back to unformatted string
        pass
    return s


@dataclass(frozen=True)
class _Part:
    """A part of an expression with its preceding operator."""

    text: str
    op: str | None = None  # operator BEFORE this part
    inner_expr: Pair | None = None  # for parenthesized groups


def _format_expr(node: Pair, max_len: int) -> str:
    """Format an expression, recursively expanding parentheses if needed."""
    parts = _collect_parts(node)

    if not parts:
        return node.text

    # Try to fit on one line
    line = _parts_to_string(parts)
    if len(line) <= max_len:
        return line

    # If single paren group with inner operators, expand it
    if len(parts) == 1 and parts[0].inner_expr and _has_operators(parts[0].inner_expr):
        return _expand_paren(parts[0].inner_expr, max_len)

    # If first part is an expandable paren group that's too long, expand it first
    # This handles cases like "(very_long_expr + ...) + rest" where the paren group
    # itself exceeds max_len and needs to be expanded before we can proceed
    first = parts[0]
    if first.inner_expr and _has_operators(first.inner_expr) and len(first.text) + 3 > max_len:
        inner = _format_expr(first.inner_expr, max_len)
        lines = ["(", *("    " + ln for ln in inner.split("\n"))]
        # Build remaining parts after the closing paren
        current = ")"
        for part in parts[1:]:
            addition = f" {part.op} {part.text}"
            if len(current) + len(addition) <= max_len:
                current += addition
            else:
                lines.append(f"{current} {part.op}")
                current = part.text
        lines.append(current)
        return "\n".join(lines)

    # Break at operators (handles expansion of any too-long paren groups)
    return _break_at_operators(parts, max_len)


def _collect_parts(node: Pair) -> list[_Part]:
    """Collect expression parts as a flat list."""
    parts: list[_Part] = []
    pending_op: str | None = None
    pending_neg = ""
    pending_method_calls = ""

    for child in node.inner():
        name = child.name
        if name in _OPERATORS:
            pending_op = child.text
        elif name == "neg":
            pending_neg += "-"
        elif name == "expr":
            parts.append(_Part(f"{pending_neg}({child.text}){pending_method_calls}", pending_op, child))
            pending_op, pending_neg, pending_method_calls = None, "", ""
        elif name in ("ident", "int"):
            parts.append(_Part(f"{pending_neg}{child.text}{pending_method_calls}", pending_op))
            pending_op, pending_neg, pending_method_calls = None, "", ""
        elif name == "method_call":
            if parts:
                # Append to previous part by creating new immutable instance
                prev = parts[-1]
                parts[-1] = _Part(prev.text + child.text, prev.op, prev.inner_expr)
            else:
                pending_method_calls += child.text

    return parts


def _parts_to_string(parts: list[_Part]) -> str:
    """Join parts into a single string."""
    if not parts:
        return ""
    return parts[0].text + "".join(f" {p.op} {p.text}" for p in parts[1:])


def _has_operators(node: Pair) -> bool:
    """Check if a node has top-level operators."""
    return any(c.name in _OPERATORS for c in node.inner())


def _expand_paren(inner_expr: Pair, max_len: int) -> str:
    """Expand a parenthesized expression into multiple lines."""
    inner = _format_expr(inner_expr, max_len)
    inner_lines = ["    " + ln for ln in inner.split("\n")]
    return "\n".join(["(", *inner_lines, ")"])


def _break_at_operators(parts: list[_Part], max_len: int) -> str:
    """Break parts into lines at operator boundaries, recursively expanding long paren groups."""
    lines: list[str] = []
    current = ""

    for i, part in enumerate(parts):
        # Check if this part needs recursive expansion
        if part.inner_expr and len(part.text) > max_len and _has_operators(part.inner_expr):
            # Flush current line with the operator
            if current and part.op:
                lines.append(f"{current} {part.op}")
            elif current:
                lines.append(current)

            # Expand this paren group
            expanded_lines = _expand_paren(part.inner_expr, max_len).split("\n")
            lines.extend(expanded_lines[:-1])
            current = expanded_lines[-1]
        elif i == 0:
            current = part.text
        else:
            addition = f" {part.op} {part.text}"
            if len(current) + len(addition) + 2 <= max_len:
                current += addition
            else:
                lines.append(f"{current} {part.op}")
                current = part.text

    if current:
        lines.append(current)

    return "\n".join(lines)
