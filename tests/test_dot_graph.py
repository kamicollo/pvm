"""Tests for dot graph formatting functions."""

import pytest
from pvm.measures.visualization.formatting import format_recursive


class TestFormatFormulaWithLinebreaks:
    """Tests for the format_formula_with_linebreaks function."""

    @pytest.mark.parametrize(
        ("formula", "max_line_length", "expected"),
        [
            # Empty and None strings
            ("", 50, ""),
            # Short formulas without breaks
            (
                "a + b",
                50,
                """
                a + b
                """,
            ),
            (
                "(a + b) * c",
                50,
                """
                (a + b) * c
                """,
            ),
            # Long formula with single paren group
            (
                "(this_is_a_very_long_variable_name + another_long_name) + more",
                50,
                """
                (
                    this_is_a_very_long_variable_name +
                    another_long_name
                ) + more
                """,
            ),
            # Nested parentheses
            (
                "((inner + expression) * factor + other_term_here) + next_item",
                50,
                """
                (
                    (inner + expression) * factor + other_term_here
                ) + next_item
                """,
            ),
            # Multiple paren groups
            (
                "(first_very_long_expression + second_term_here_too * 10) + (another_long_expression + more_terms_x) + end",
                50,
                """
                (
                    first_very_long_expression +
                    second_term_here_too * 10
                ) + (another_long_expression + more_terms_x) + end
                """,
            ),
            # No break at end of formula
            (
                "(very_long_expression_that_exceeds_the_limit)",
                30,
                """
                (very_long_expression_that_exceeds_the_limit)
                """,
            ),
            # Deeply nested parentheses
            (
                "(((a + b) * c) + ((d + e) * f) + more_terms_here_now) + next_item",
                30,
                """
                (
                    ((a + b) * c) +
                    ((d + e) * f) +
                    more_terms_here_now
                ) + next_item
                """,
            ),
            # Formula without parentheses - break, too
            (
                "a + b + c + d + e + f + g + h + i + j + k + l + m + n",
                20,
                """
                a + b + c + d + e +
                f + g + h + i + j +
                k + l + m + n
                """,
            ),
            # Deeply nested - both outer and inner need expansion
            (
                "((very_long_inner_name + another_long) * factor) + y",
                30,
                """
                (
                    (
                        very_long_inner_name +
                        another_long
                    ) * factor
                ) + y
                """,
            ),
            # Failing test case from real usage
            (
                "(_.revenue.sum() - ((((_.volume * _.unit_price).sum() / _.volume.sum()) * _.volume.sum()) + (0 + _.flat_fee.sum())))",
                50,
                """
(
    _.revenue.sum() -
    (
        (
            (
                (_.volume * _.unit_price).sum() / _.volume.sum()
            ) * _.volume.sum()
        ) + (0 + _.flat_fee.sum())
    )
)
                """,
            ),
            # Negation prefix
            (
                "-a + b + c",
                50,
                """
                -a + b + c
                """,
            ),
            # Method call on parenthesized expression
            (
                "(a + b).sum() + c",
                50,
                """
                (a + b).sum() + c
                """,
            ),
            # Property access chain
            (
                "_.foo.bar + _.baz.qux",
                50,
                """
                _.foo.bar + _.baz.qux
                """,
            ),
            # Invalid/unparseable input - returns as-is
            (
                "((( incomplete",
                50,
                """
                ((( incomplete
                """,
            ),
            # Exactly at max_len boundary (9 chars fits, 8 would break)
            (
                "a + b + c",
                9,
                """
                a + b + c
                """,
            ),
            # Just under max_len forces a break
            (
                "a + b + c",
                8,
                """
                a + b +
                c
                """,
            ),
            # Only multiplicative operators (long chain)
            (
                "a * b * c * d * e * f * g * h",
                20,
                """
                a * b * c * d * e *
                f * g * h
                """,
            ),
            # Negated parenthesized expression
            (
                "-(a + b) + c",
                50,
                """
                -(a + b) + c
                """,
            ),
        ],
    )
    def test_format_formula_with_linebreaks(
        self, formula: str, max_line_length: int, expected: str
    ) -> None:
        """Test formula formatting with various inputs and line length limits."""
        import textwrap

        result = format_recursive(formula, max_len=max_line_length)
        assert result == textwrap.dedent(expected).strip()
