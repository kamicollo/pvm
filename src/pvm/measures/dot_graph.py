"""Dot graph generation for measure graphs using singledispatch."""

from __future__ import annotations

from functools import singledispatch

from .measures import BaseMeasure, CompositeRateMeasure, Measure, QuantityMeasure, RateMeasure, ReconciliationMeasure


@singledispatch
def get_dot_shape(_field: BaseMeasure) -> str:
    """Get the shape for the measure in dot graph."""
    return "box"


@get_dot_shape.register
def _(_field: Measure) -> str:
    return "box"


@get_dot_shape.register
def _(_field: ReconciliationMeasure) -> str:
    return "note"


@get_dot_shape.register
def _(_field: RateMeasure) -> str:
    return "box"


@get_dot_shape.register
def _(_field: QuantityMeasure) -> str:
    return "box"


@singledispatch
def get_dot_color(_field: BaseMeasure) -> str:
    """Get the fill color for the measure in dot graph."""
    return "lightblue"


@get_dot_color.register
def _(_field: Measure) -> str:
    return "#E8F4F8"  # Light blue-gray


@get_dot_color.register
def _(_field: ReconciliationMeasure) -> str:
    return "#FFF9E6"  # Light yellow


@get_dot_color.register
def _(_field: RateMeasure) -> str:
    return "#E8F5E9"  # Light green


@get_dot_color.register
def _(_field: QuantityMeasure) -> str:
    return "#F3E5F5"  # Light purple


@singledispatch
def get_dot_formula(field: BaseMeasure) -> str:
    """Get the formula string for the measure in dot graph."""
    if field.definition is None:
        return "None"
    return str(field.definition)


@get_dot_formula.register
def _(_field: ReconciliationMeasure) -> str:
    return "None"


@singledispatch
def get_calculated_definition_as_string(field: BaseMeasure) -> str:
    """Get the calculated definition as a string for dot graph."""
    if field.components:
        comps = ""
        if field.other_components:
            comps = " + ".join([c.name for c in field.other_components])
        if field.rate and field.quantity:
            return f"{field.rate.name} * {field.quantity.name}" + (f" + ({comps})" if comps else "")
        return comps
    return "None"


@get_calculated_definition_as_string.register
def _(_field: ReconciliationMeasure) -> str:
    return "calculated as difference"


@get_calculated_definition_as_string.register
def _(field: CompositeRateMeasure) -> str:
    return " + ".join([c.name for c in field.rates])


def get_dot_label(field: BaseMeasure) -> str:
    """Get the label for the measure in dot graph."""
    return f"""
        <table border="0" cellborder="1" cellspacing="0" cellpadding="6" style="rounded">
			<tr> <td bgcolor="{get_dot_color(field)}" align="center"> <font point-size="13" color="#2C3E50">
                <b>{field.name}</b>
            </font> </td> </tr>
			<tr> <td align="center"> <font point-size="9" color="#7F8C8D">
                <i>{field.__class__.__name__}</i>
            </font></td> </tr>
            <tr> <td align="left" balign="left"> <font point-size="9" color="#34495E">
                <b>Formula:</b> <i>{get_dot_formula(field)}</i>
            </font></td> </tr>
            <tr> <td align="left" balign="left"> <font point-size="9" color="#34495E">
                <b>Implied formula:</b> <i>{get_calculated_definition_as_string(field)}</i>
            </font></td> </tr>
		</table>
        """


def get_dot_representation(field: BaseMeasure) -> str:
    """Generate a representation of the measure as a node in the graphviz dot graph."""
    return f"""{field.name} [
            label=<{get_dot_label(field)}>
            shape={get_dot_shape(field)}
            style="filled,rounded"
            fillcolor="{get_dot_color(field)}"
            color="#95A5A6"
            penwidth=1.5
        ]
        """


def to_dot_graph(
    field: BaseMeasure, *, initialize: bool = True, dpi: int = 96, size: tuple[int, int] | None = None
) -> str:
    """
    Generate a dot graph (graphviz) representation of the measure and its components.

    Args:
        field: The measure to generate the graph for
        initialize: Whether to add the digraph wrapper
        dpi: Dots per inch for rendering (default: 150)
        size: Graph size as "width,height" in inches (e.g., "10,8")

    Returns:
        str: a Dot graph representation of the measure and its components

    """
    if initialize:
        graph = f"digraph {field.name} {{\n"
        graph += '    bgcolor="white"\n'
        graph += "    rankdir=TB\n"
        graph += f"    dpi={dpi}\n"
        if size:
            graph += f'    size="{size[0]},{size[1]}"\n'
        graph += '    node [fontname="Helvetica", fontsize=10, margin=0.2]\n'
        graph += '    edge [color="#7F8C8D", penwidth=1.5, arrowsize=0.8]\n'
    else:
        graph = ""
    graph += get_dot_representation(field)
    for component in field.components:
        graph += f'"{field.name}" -> "{component.name}"\n'
        graph += to_dot_graph(component, initialize=False, dpi=dpi, size=size)
    if initialize:
        graph += "}\n"
    return graph


def display_dot_graph(field: BaseMeasure, dpi: int = 96, size: tuple[int, int] | None = None) -> None:
    """Display the dot graph in a Jupyter notebook."""
    from graphviz import Source  # noqa: PLC0415
    from IPython.display import display  # noqa: PLC0415

    dot_graph = to_dot_graph(field, dpi=dpi, size=size)
    display(Source(dot_graph, format="svg", engine="dot"))
