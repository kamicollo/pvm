"""Dot graph generation for measure graphs using singledispatch."""

from __future__ import annotations

from functools import singledispatch

from .measures import BaseMeasure, CompositeRateMeasure, Measure, QuantityMeasure, RateMeasure, ReconciliationMeasure


def format_formula_with_linebreaks(formula: str, max_line_length: int = 50) -> str:
    """
    Format a formula string with line breaks for readability.

    Breaks long formulas at operators, respecting parentheses and nested structures.
    Parenthesized groups that exceed max_line_length are expanded with proper indentation.

    Args:
        formula: The formula string to format
        max_line_length: Maximum length of each line (default: 50)

    Returns:
        Formatted formula string with line breaks and indentation

    """
    if not formula:
        return ""

    def find_matching_paren(s: str, start: int) -> int:
        """Find the position of the closing paren matching the opening paren at start."""
        depth = 1
        i = start + 1
        while i < len(s) and depth > 0:
            if s[i] == "(":
                depth += 1
            elif s[i] == ")":
                depth -= 1
            i += 1
        return i - 1

    def find_top_level_operator_positions(s: str, op: str) -> list[int]:
        """Find all positions of operator at top level (outside parens)."""
        positions = []
        depth = 0
        for i, c in enumerate(s):
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            elif depth == 0 and s[i : i + len(op)] == op:
                positions.append(i)
        return positions

    def break_at_operators(s: str, max_len: int) -> str:
        """Break an expression at operators to fit lines within max_len."""
        s = s.strip()
        if len(s) <= max_len:
            return s

        lines: list[str] = []
        current_line = ""

        i = 0
        while i < len(s):
            if s[i] == "(":
                # Handle paren groups as single units
                match_pos = find_matching_paren(s, i)
                token = s[i : match_pos + 1]
                current_line += token
                i = match_pos + 1
            elif s[i : i + 3] in (" + ", " - ", " * ", " / "):
                op = s[i : i + 3]
                current_line += op
                i += 3
            else:
                current_line += s[i]
                i += 1

            # Check if we need to break after adding content
            if len(current_line.rstrip()) > max_len:
                # Find the best TOP-LEVEL operator position to break at
                best_break_pos = -1

                # Prefer + and - operators
                for break_op in [" + ", " - "]:
                    for pos in find_top_level_operator_positions(current_line, break_op):
                        candidate = pos + len(break_op)
                        if len(current_line[:candidate].rstrip()) <= max_len:
                            best_break_pos = candidate  # Keep finding later valid positions

                # Fall back to * and / if no + or - found
                if best_break_pos <= 0:
                    for break_op in [" * ", " / "]:
                        for pos in find_top_level_operator_positions(current_line, break_op):
                            candidate = pos + len(break_op)
                            if len(current_line[:candidate].rstrip()) <= max_len:
                                best_break_pos = candidate

                if best_break_pos > 0:
                    lines.append(current_line[:best_break_pos].rstrip())
                    current_line = current_line[best_break_pos:]

        if current_line.strip():
            lines.append(current_line.rstrip())

        return "\n".join(lines)

    def format_recursive(s: str, max_len: int) -> str:
        """Recursively format a formula string. Returns non-indented output."""
        s = s.strip()
        if not s:
            return ""

        # If it fits, return as-is
        if len(s) <= max_len:
            return s

        # Try to find an outer paren group that starts the expression and can be expanded
        if s.startswith("("):
            match_pos = find_matching_paren(s, 0)
            paren_group = s[: match_pos + 1]  # Including both parens
            paren_content = s[1:match_pos]
            after = s[match_pos + 1 :].strip()

            # Check if the paren content has top-level operators we can break on
            # (not operators inside nested parens)
            top_level_has_operators = False
            depth = 0
            for i, c in enumerate(paren_content):
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                elif depth == 0 and paren_content[i : i + 3] in [" + ", " - ", " * ", " / "]:
                    top_level_has_operators = True
                    break

            # Expand paren if it has top-level operators AND either:
            # 1. The paren group itself exceeds max_len, OR
            # 2. The paren group + after together exceed max_len (need to split to make room)
            should_expand = top_level_has_operators and (
                len(paren_group) > max_len or (after and len(paren_group) + 1 + len(after.split()[0]) > max_len)
            )
            if should_expand:
                # Format the inner content recursively with same max_len
                inner_formatted = format_recursive(paren_content, max_len)

                # Build the expanded result - add one level of indent to inner content
                lines = ["("]
                for line in inner_formatted.split("\n"):
                    lines.append("    " + line)

                if after:
                    # Format after part recursively
                    after_formatted = format_recursive(after, max_len)
                    after_lines = after_formatted.split("\n")
                    lines.append(") " + after_lines[0])
                    lines.extend(after_lines[1:])
                else:
                    lines.append(")")

                return "\n".join(lines)

        # No paren expansion possible/needed - just break at operators
        return break_at_operators(s, max_len)

    return format_recursive(formula, max_line_length)


@singledispatch
def get_dot_shape(_measure: BaseMeasure) -> str:
    """Get the shape for the measure in dot graph."""
    return "box"


@get_dot_shape.register
def _(_measure: Measure) -> str:
    return "box"


@get_dot_shape.register
def _(_measure: ReconciliationMeasure) -> str:
    return "note"


@get_dot_shape.register
def _(_measure: RateMeasure) -> str:
    return "box"


@get_dot_shape.register
def _(_measure: QuantityMeasure) -> str:
    return "box"


@singledispatch
def get_dot_color(_measure: BaseMeasure) -> str:
    """Get the fill color for the measure in dot graph."""
    return "lightblue"


@get_dot_color.register
def _(_measure: Measure) -> str:
    return "#E8F4F8"  # Light blue-gray


@get_dot_color.register
def _(_measure: ReconciliationMeasure) -> str:
    return "#FFF9E6"  # Light yellow


@get_dot_color.register
def _(_measure: RateMeasure) -> str:
    return "#E8F5E9"  # Light green


@get_dot_color.register
def _(_measure: QuantityMeasure) -> str:
    return "#F3E5F5"  # Light purple


@singledispatch
def get_dot_formula(measure: BaseMeasure) -> str:
    """Get the formula string for the measure in dot graph."""
    if measure.definition is None:
        return "None"
    return format_formula_with_linebreaks(str(measure.definition))


@get_dot_formula.register
def _(_measure: ReconciliationMeasure) -> str:
    return "None"


@singledispatch
def get_calculated_definition_as_string(measure: BaseMeasure) -> str:
    """Get the calculated definition as a string for dot graph."""
    if measure.components:
        comps = ""
        if measure.other_components:
            comps = " + ".join([c.name for c in measure.other_components])
        if measure.rate and measure.quantity:
            return format_formula_with_linebreaks(
                f"{measure.rate.name} * {measure.quantity.name}" + (f" + ({comps})" if comps else "")
            )
        return comps
    return "None"


@get_calculated_definition_as_string.register
def _(measure: ReconciliationMeasure) -> str:
    if measure.definition is None:
        return "None"
    return format_formula_with_linebreaks(str(measure.definition))


@get_calculated_definition_as_string.register
def _(measure: CompositeRateMeasure) -> str:
    return " + ".join([c.name for c in measure.rates])


def get_dot_label(measure: BaseMeasure) -> str:
    """Get the label for the measure in dot graph."""
    return f"""
        <table border="0" cellborder="1" cellspacing="0" cellpadding="6" style="rounded">
			<tr> <td bgcolor="{get_dot_color(measure)}" align="center"> <font point-size="13" color="#2C3E50">
                <b>{measure.name}</b>
            </font> </td> </tr>
			<tr> <td align="center"> <font point-size="9" color="#7F8C8D">
                <i>{measure.__class__.__name__}</i>
            </font></td> </tr>
            <tr> <td align="left" balign="left"> <font point-size="9" color="#34495E">
                <b>Formula:</b> <i>{get_dot_formula(measure)}</i>
            </font></td> </tr>
            <tr> <td align="left" balign="left"> <font point-size="9" color="#34495E">
                <b>Implied formula:</b> <i>{get_calculated_definition_as_string(measure)}</i>
            </font></td> </tr>
		</table>
        """


def get_dot_representation(measure: BaseMeasure) -> str:
    """Generate a representation of the measure as a node in the graphviz dot graph."""
    return f"""{measure.name} [
            label=<{get_dot_label(measure)}>
            shape={get_dot_shape(measure)}
            style="filled,rounded"
            fillcolor="{get_dot_color(measure)}"
            color="#95A5A6"
            penwidth=1.5
        ]
        """


def to_dot_graph(
    measure: BaseMeasure, *, initialize: bool = True, dpi: int = 96, size: tuple[int, int] | None = None
) -> str:
    """
    Generate a dot graph (graphviz) representation of the measure and its components.

    Args:
        measure: The measure to generate the graph for
        initialize: Whether to add the digraph wrapper
        dpi: Dots per inch for rendering (default: 150)
        size: Graph size as "width,height" in inches (e.g., "10,8")

    Returns:
        str: a Dot graph representation of the measure and its components

    """
    if initialize:
        graph = f"digraph {measure.name} {{\n"
        graph += '    bgcolor="white"\n'
        graph += "    rankdir=TB\n"
        graph += f"    dpi={dpi}\n"
        if size:
            graph += f'    size="{size[0]},{size[1]}"\n'
        graph += '    node [fontname="Helvetica", fontsize=10, margin=0.2]\n'
        graph += '    edge [color="#7F8C8D", penwidth=1.5, arrowsize=0.8]\n'
    else:
        graph = ""
    graph += get_dot_representation(measure)
    for component in measure.components:
        graph += f'"{measure.name}" -> "{component.name}"\n'
        graph += to_dot_graph(component, initialize=False, dpi=dpi, size=size)
    if initialize:
        graph += "}\n"
    return graph


def display_dot_graph(measure: BaseMeasure, dpi: int = 96, size: tuple[int, int] | None = None) -> None:
    """Display the dot graph in a Jupyter notebook."""
    from graphviz import Source  # noqa: PLC0415
    from IPython.display import display  # noqa: PLC0415

    dot_graph = to_dot_graph(measure, dpi=dpi, size=size)
    print(dot_graph)
    display(Source(dot_graph, format="svg", engine="dot"))
