"""PVM class module."""

from __future__ import annotations

from enum import Enum
from functools import cached_property
from typing import Self

import ibis
from ibis import Deferred

from pvm import CHANGE_COLUMN, EFFECT_COLUMN, PERIOD_COLUMN
from pvm.formulas import change_field, derive_effect_fields
from pvm.measures import Measure, QuantityMeasure, RateMeasure, ReconciliationMeasure

_AnyMeasure = Measure | RateMeasure | QuantityMeasure | ReconciliationMeasure


def _get_ancestor_paths(measure: _AnyMeasure, path: list[str] | None = None) -> dict[str, list[str]]:
    """Return {measure_name: [root, ..., self]} for every node in the graph."""
    if path is None:
        path = []
    current_path = path + [measure.name]
    result = {measure.name: current_path}
    for component in measure.components:
        result.update(_get_ancestor_paths(component, current_path))
    return result


def _get_leaf_measures(measure: _AnyMeasure) -> set[str]:
    """Return names of measures with no components (leaf nodes)."""
    if not measure.components:
        return {measure.name}
    leaves: set[str] = set()
    for component in measure.components:
        leaves.update(_get_leaf_measures(component))
    return leaves


class CalculationMethod(Enum):
    """Calculation methods for PVM."""

    CLASSIC = 0
    INVERSE = 1
    THREE_WAY = 2
    SYMMETRIC = 3


class PVM:
    """PVM class."""

    method: CalculationMethod
    hierarchy: list[ibis.Deferred]
    data: ibis.Table | None
    period_expression: ibis.Deferred | None
    period_order: list[str] | None
    graph: Measure | None

    def __init__(
        self,
        method_to_use: CalculationMethod = CalculationMethod.CLASSIC,
        data: ibis.Table | None = None,
    ) -> None:
        """
        Initialize the PVM class.

        Args:
            method_to_use (CalculationMethod, optional): The calculation method to use.
                Defaults to CalculationMethod.CLASSIC.
            data (ibis.Table | None, optional): The data source. Defaults to None.

        """
        self.method = method_to_use
        self.hierarchy = []
        self.data = data
        self.period_expression = None
        self.period_order = None
        self.graph = None

    def set_data(self, table: ibis.Table) -> Self:
        """
        Set the reference to the underlying data source.

        Args:
            table (ibis.Table): The data source.

        Returns:
            Self: The PVM instance.

        """
        self.data = table
        self.reset_aggregated()
        return self

    def set_graph(self, graph: Measure) -> Self:
        """
        Set the calculation graph for the instance.

        Args:
            graph (Measure): The graph to be set.

        Returns:
            Self: The instance with the updated graph attribute.

        """
        self.graph = graph
        self.reset_aggregated()
        return self

    def set_periods(self, definition: ibis.Deferred, order: list[str]) -> Self:
        """
        Set the period field definition and period order for the instance.

        Args:
            definition (ibis.Expr): An Ibis expression defining the period.
            order (list[str]): A list of strings representing the order of periods.

        Returns:
            Self: The instance with updated period definition and order.

        """
        self.period_expression = definition.cast(str)
        self.period_order = order
        self.reset_aggregated()
        return self

    def set_hierarchy(self, hierarchy: list[ibis.Deferred]) -> Self:
        """
        Set the dimension hierarchy for the current instance.

        Args:
            hierarchy (list[ibis.Expr]): A list of ibis expressions representing the dimension hierarchy.

        Returns:
            Self: The instance with the updated hierarchy.

        """
        self.hierarchy = hierarchy
        self.reset_aggregated()
        return self

    @cached_property
    def aggregated(self) -> ibis.Table:
        """
        Aggregate the data based on the specified period and hierarchy.

        This method filters the data based on the period expression, groups it by the hierarchy and period,
        and then aggregates it using the formulas defined in the graph. The result is then pivoted to a wider format
        with periods as columns, aggregated values as cell values, and missing values filled with zero.

        Returns:
            ibis.Table: The aggregated and pivoted table.

        """
        if self.data is None:
            raise ValueError("Data source is not set")
        if self.period_expression is None:
            raise ValueError("Period expression is not set")
        if self.period_order is None:
            raise ValueError("Period order is not set")
        if self.graph is None:
            raise ValueError("Calculation graph is not set")

        period_filter = self.period_expression.isin(list(self.period_order))
        group_by_fields = self.hierarchy + [self.period_expression.name(PERIOD_COLUMN)]
        return (
            self.data.filter(period_filter)  # type: ignore
            .group_by(group_by_fields)  # type: ignore
            .aggregate(
                [f.formula.name(f.name) for f in self.graph.get_flattened_graph()],
            )
        )

    def reset_aggregated(self) -> None:
        """Reset the aggregated table."""
        if self.__dict__.get("aggregated") is not None:
            del self.aggregated

    def get_wide_table(self) -> ibis.Table:
        """
        Get the wide table with the aggregated data.

        Returns:
            ibis.Table: The wide table.

        """
        if self.graph is None:
            raise ValueError("Calculation graph is not set")
        return self.aggregated.pivot_wider(
            names=self.period_order,
            names_from=[PERIOD_COLUMN],
            values_from=[f.name for f in self.graph.get_flattened_graph()],
            values_agg="sum",
            values_fill=0,
        )

    def calculate_effects(self) -> ibis.Table:
        """
        Calculate the effects over the specified periods.

        This method aggregates data and then iteratively mutates the table by deriving
        effect fields for each consecutive period defined in `self.period_order`.

        Returns:
            ibis.Table: The table with the calculated effects.

        """
        if not self.period_order or len(self.period_order) < 2:  # noqa: PLR2004
            raise ValueError("Calculation requires at least two periods")
        if self.graph is None:
            raise ValueError("Calculation graph is not set")
        t = self.get_wide_table()
        for period_start, period_end in zip(
            self.period_order[:-1],
            self.period_order[1:],
            strict=False,
        ):
            effect_fields: list[Deferred] = derive_effect_fields(self.graph, period_start, period_end)
            change_fields = [change_field(f, period_start, period_end) for f in self.graph.get_flattened_graph()]
            t = t.mutate(change_fields).mutate(effect_fields)  # type: ignore
        return t

    def get_effects(self) -> ibis.Table:
        """
        Get the PVM effects in unpivoted (long) format.

        Calls `calculate_effects()` and returns only the effect columns,
        unpivoted into a long table with one row per (hierarchy, measure, period).

        Returns:
            ibis.Table: Long-format table with hierarchy columns plus
                ``measure`` (effect name), ``period`` (transition start period),
                and ``value`` (effect value).

        """
        if self.graph is None:
            raise ValueError("Calculation graph is not set")
        t = self.calculate_effects()

        ancestor_paths = _get_ancestor_paths(self.graph)
        leaf_measures = _get_leaf_measures(self.graph)
        max_depth = max(len(p) for p in ancestor_paths.values()) - 1

        effect_cols = [
            col for col in t.columns
            if EFFECT_COLUMN in col and col.split(EFFECT_COLUMN)[0] in leaf_measures
        ]
        measure_names = {f.name for f in self.graph.get_flattened_graph()}
        base_period_cols = {f"{m}_{p}" for m in measure_names for p in (self.period_order or [])}
        non_hierarchy = base_period_cols | {c for c in t.columns if CHANGE_COLUMN in c or EFFECT_COLUMN in c}
        hierarchy_col_names = [col for col in t.columns if col not in non_hierarchy]

        long = t.select(hierarchy_col_names + effect_cols).pivot_longer(
            effect_cols,
            names_to=["measure", "period"],
            names_pattern=f"^(.+?){EFFECT_COLUMN}(.+)$",
            values_to="value",
        )

        level_cols = []
        for depth in range(max_depth + 1):
            expr = ibis.case()
            for m_name in leaf_measures:
                path = ancestor_paths.get(m_name, [m_name])
                ancestor = path[depth] if depth < len(path) else path[-1]
                expr = expr.when(ibis._["measure"] == m_name, ancestor)
            level_cols.append(expr.else_(None).end().name(f"L{depth + 1}"))

        result = long.mutate(level_cols)
        level_col_names = [f"L{d + 1}" for d in range(max_depth + 1)]
        other_cols = [c for c in result.columns if c not in level_col_names]
        return result.select(level_col_names + other_cols)
