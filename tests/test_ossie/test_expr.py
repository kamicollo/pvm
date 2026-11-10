"""Tests for pvm.ossie.expr.parse_expression."""

from __future__ import annotations

import pytest

from pvm.ossie.expr import ExprError, Term, parse_expression


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a", [Term(("a",), False)]),
        ("a * b", [Term(("a", "b"), False)]),
        ("a - b", [Term(("a",), False), Term(("b",), True)]),
        ("-a + b", [Term(("a",), True), Term(("b",), False)]),
        ("a + -b", [Term(("a",), False), Term(("b",), True)]),
        ("a - -b", [Term(("a",), False), Term(("b",), False)]),
        (
            "a*b + c - d*e",
            [
                Term(("a", "b"), False),
                Term(("c",), False),
                Term(("d", "e"), True),
            ],
        ),
    ],
)
def test_parse_expression_valid(text: str, expected: list[Term]) -> None:
    assert parse_expression(text) == expected


def test_parse_expression_product_term_has_two_names() -> None:
    [term] = parse_expression("a * b")
    assert term.is_product is True


def test_parse_expression_single_term_is_not_product() -> None:
    [term] = parse_expression("a")
    assert term.is_product is False


def test_three_terms_two_products() -> None:
    terms = parse_expression("a*b + c - d*e")
    assert len(terms) == 3
    assert sum(1 for term in terms if term.is_product) == 2


@pytest.mark.parametrize(
    "text",
    [
        "",
        "a +",
        "(a)",
        "a / b",
        "a * b * c",
        "2 * a",
        "a b",
        "a-b.c",
    ],
)
def test_parse_expression_errors(text: str) -> None:
    with pytest.raises(ExprError):
        parse_expression(text)


def test_parse_expression_invalid_char_after_newline_raises() -> None:
    with pytest.raises(ExprError):
        parse_expression("a +\n$")
