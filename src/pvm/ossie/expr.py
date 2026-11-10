"""Parser for PVM operand expressions.

Grammar (see docs/ossie-pvm-extension.md):

    expression := term (("+" | "-") term)*
    term       := ["-"] name ["*" name]
    name       := [A-Za-z_][A-Za-z0-9_]*

This module is standalone: it has no dependency on the rest of
``pvm.ossie``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(
    r"""
    (?P<name>[A-Za-z_][A-Za-z0-9_]*)
    | (?P<op>[+*-])
    | (?P<ws>\s+)
    | (?P<other>[\s\S])
    """,
    re.VERBOSE,
)

_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

_PRODUCT_NAME_COUNT = 2


class ExprError(ValueError):
    """Raised when an operand expression does not match the grammar."""


@dataclass(frozen=True)
class Term:
    """A single term of an operand expression.

    ``names`` holds one name for a single term, or two names (in source
    order) for a product term. ``negated`` is ``True`` when the term is
    preceded by a unary ``-`` or follows a binary ``-``.
    """

    names: tuple[str, ...]
    negated: bool

    @property
    def is_product(self) -> bool:
        """Whether this term is a product of two names."""
        return len(self.names) == _PRODUCT_NAME_COUNT


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for match in _TOKEN_RE.finditer(text):
        if match.lastgroup == "ws":
            continue
        if match.lastgroup == "other":
            raise ExprError(f"unexpected character {match.group()!r} in expression {text!r}")
        tokens.append(match.group())
    return tokens


class _Parser:
    """Recursive-descent parser over a flat token list."""

    def __init__(self, tokens: list[str], text: str) -> None:
        self._tokens = tokens
        self._pos = 0
        self._text = text

    def _peek(self) -> str | None:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _advance(self) -> str:
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _error(self, message: str) -> ExprError:
        return ExprError(f"{message} in expression {self._text!r}")

    def _expect_name(self) -> str:
        token = self._peek()
        if token is None or not _NAME_RE.fullmatch(token):
            raise self._error("expected a name")
        return self._advance()

    def parse_expression(self) -> list[Term]:
        terms = [self._parse_term()]
        while self._peek() in ("+", "-"):
            op = self._advance()
            term = self._parse_term()
            if op == "-":
                term = Term(term.names, not term.negated)
            terms.append(term)
        if self._peek() is not None:
            raise self._error(f"unexpected token {self._peek()!r}")
        return terms

    def _parse_term(self) -> Term:
        negated = False
        if self._peek() == "-":
            self._advance()
            negated = True
        first = self._expect_name()
        names: tuple[str, ...] = (first,)
        if self._peek() == "*":
            self._advance()
            second = self._expect_name()
            names = (first, second)
        return Term(names, negated)


def parse_expression(text: str) -> list[Term]:
    """Parse an operand expression into a list of :class:`Term`.

    Raises :class:`ExprError` if ``text`` does not match the grammar.
    """
    tokens = _tokenize(text)
    if not tokens:
        raise ExprError(f"empty expression {text!r}")
    parser = _Parser(tokens, text)
    return parser.parse_expression()
