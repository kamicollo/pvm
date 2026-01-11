"""Dot graph generation for measure graphs using singledispatch."""

from __future__ import annotations

from functools import singledispatch

from ..measures import BaseMeasure, CompositeRateMeasure, Measure, QuantityMeasure, RateMeasure, ReconciliationMeasure
from .formatting import format_recursive


def format_formula_with_linebreaks(formula: str, max_line_length: int = 70) -> str:
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

    return "<br/>" + format_recursive(formula, max_line_length).replace("\n", "<br/>\n")


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
        return format_formula_with_linebreaks("None")
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
        return format_formula_with_linebreaks("None")
    return format_formula_with_linebreaks(str(measure.definition))


@get_calculated_definition_as_string.register
def _(measure: CompositeRateMeasure) -> str:
    return " + ".join([c.name for c in measure.rates])


def get_dot_label(measure: BaseMeasure, *, show_implied_formulas: bool = False) -> str:
    """Get the label for the measure in dot graph."""
    implied_formula_section = ""
    if show_implied_formulas:
        implied_formula_section = f"""
            <tr>
                <td align="center" balign="center">
                    <font point-size="9" color="#34495E">
                    <b>Implied formula</b>
                    </font>
                </td>
            </tr>
            <tr>
                <td align="text" balign="left">
                    <font point-size="9" color="#34495E">
                        <i>{get_calculated_definition_as_string(measure)}</i>
                    </font>
                </td>
            </tr>"""

    label = f"""
        <table
            border="0"
            cellborder="1"
            cellspacing="0"
            cellpadding="6"
            style="rounded"
            align="center"
        >
			<tr>
            <td bgcolor="{get_dot_color(measure)}" align="center">
            <font point-size="13" color="#2C3E50">
            <b>{measure.name}</b>
            </font>
            </td>
            </tr>

            <tr>
                <td align="center">
                    <font point-size="9" color="#7F8C8D">
                        <i>{measure.__class__.__name__}</i>
                    </font>
                </td>
            </tr>
            <tr>
                <td align="center">
                    <font point-size="9" color="#34495E">
                        <b>Formula</b>
                    </font>
                </td>
            </tr>
            <tr>
                <td align="text" balign="left">
                    <font point-size="9" color="#34495E">
                        <i>{get_dot_formula(measure)}</i>
                    </font>
                </td>
            </tr>{implied_formula_section}
		</table>
        """

    return "\n".join([line.strip() for line in label.split("\n")])


def get_dot_representation(measure: BaseMeasure, *, show_implied_formulas: bool = False) -> str:
    """Generate a representation of the measure as a node in the graphviz dot graph."""
    return f"""{measure.name} [
            label=<{get_dot_label(measure, show_implied_formulas=show_implied_formulas)}>
            shape={get_dot_shape(measure)}
            style="filled,rounded"
            fillcolor="{get_dot_color(measure)}"
            color="#95A5A6"
            penwidth=1
        ]
        """


def to_dot_graph(
    measure: BaseMeasure,
    *,
    initialize: bool = True,
    dpi: int = 96,
    size: tuple[int, int] | None = None,
    show_implied_formulas: bool = False,
) -> str:
    """
    Generate a dot graph (graphviz) representation of the measure and its components.

    Args:
        measure: The measure to generate the graph for
        initialize: Whether to add the digraph wrapper
        dpi: Dots per inch for rendering (default: 150)
        size: Graph size as "width,height" in inches (e.g., "10,8")
        show_implied_formulas: Whether to show implied formulas in the graph (default: False)

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
        graph += '    node [fontname="Helvetica", margin=0, fontsize=10]\n'
        graph += '    edge [color="#7F8C8D", penwidth=1.5, arrowsize=0.8]\n'
    else:
        graph = ""
    graph += get_dot_representation(measure, show_implied_formulas=show_implied_formulas)
    for component in measure.components:
        graph += f'"{measure.name}" -> "{component.name}"\n'
        graph += to_dot_graph(
            component, initialize=False, dpi=dpi, size=size, show_implied_formulas=show_implied_formulas
        )
    if initialize:
        graph += "}\n"
    return graph


def display_dot_graph(
    measure: BaseMeasure,
    dpi: int = 96,
    size: tuple[int, int] | None = None,
    show_implied_formulas: bool = False,  # noqa: FBT001, FBT002
) -> None:
    """Display the dot graph in a Jupyter notebook."""
    from graphviz import Source  # noqa: PLC0415
    from IPython.display import display  # noqa: PLC0415

    dot_graph = to_dot_graph(measure, dpi=dpi, size=size, show_implied_formulas=show_implied_formulas)
    display(Source(dot_graph, format="svg", engine="dot"))
