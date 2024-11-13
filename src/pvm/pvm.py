"""PVM class module."""

from __future__ import annotations

from enum import Enum
from typing import Self

import ibis

from pvm.fields import Field
from pvm.formulas import derive_effect_fields


class CalculationMethod(Enum):
    """Calculation methods for PVM."""

    CLASSIC = 0
    INVERSE = 1
    THREE_WAY = 2
    SYMMETRIC = 3


class PVM:
    """PVM class."""

    method: CalculationMethod
    hierarchy: list[ibis.Expr]
    aggregated: ibis.Table | None

    def __init__(
        self,
        method_to_use: CalculationMethod = CalculationMethod.CLASSIC,
    ) -> None:
        """
        Initialize the PVM class.

        Args:
            method_to_use (CalculationMethod, optional): The calculation method to use.
            Defaults to CalculationMethod.CLASSIC.

        """
        self.method = method_to_use
        self.hierarchy = []
        self.aggregated = None
        self.data = None

    def set_data(self, table: ibis.Table) -> Self:
        """
        Set the reference to the underlying data source.

        Args:
            table (ibis.Table): The data source.

        Returns:
            Self: The PVM instance.

        """
        self.data = table
        return self

    def set_graph(self, graph: Field) -> Self:
        """
        Set the calculation graph for the instance.

        Args:
            graph (Field): The graph to be set.

        Returns:
            Self: The instance with the updated graph attribute.

        """
        self.graph = graph
        return self

    def set_periods(self, definition: ibis.Expr, order: list[str]) -> Self:
        """
        Set the period field definition and period order for the instance.

        Args:
            definition (ibis.Expr): An Ibis expression defining the period.
            order (list[str]): A list of strings representing the order of periods.

        Returns:
            Self: The instance with updated period definition and order.

        """
        self.period_expression = definition
        self.period_order = order
        return self

    def set_hierarchy(self, hierarchy: list[ibis.Expr]) -> Self:
        """
        Set the dimension hierarchy for the current instance.

        Args:
            hierarchy (list[ibis.Expr]): A list of ibis expressions representing the dimension hierarchy.

        Returns:
            Self: The instance with the updated hierarchy.

        """
        self.hierarchy = hierarchy
        return self

    def aggregate(self) -> ibis.Table:
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
        if self.aggregated is None:
            self.aggregated = (
                self.data.filter(self.period_expression.isin(list(self.period_order)))
                .group_by(self.hierarchy + [self.period_expression.name("period")])
                .aggregate(
                    [f.formula.name(f.name) for f in self.graph.get_flattened_graph()],
                )
                .pivot_wider(
                    names=self.period_order,
                    names_from=["period"],
                    values_from=[f.name for f in self.graph.get_flattened_graph()],
                    values_agg="sum",
                    values_fill=0,
                )
            )
        return self.aggregated

    def calculate_effects(self) -> ibis.Table:
        """
        Calculate the effects over the specified periods.

        This method aggregates data and then iteratively mutates the table by deriving
        effect fields for each consecutive period defined in `self.period_order`.

        Returns:
            ibis.Table: The table with the calculated effects.

        """
        t = self.aggregate()
        for period_start, period_end in zip(
            self.period_order[:-1],
            self.period_order[1:],
            strict=False,
        ):
            t = t.mutate(derive_effect_fields(self.graph, period_start, period_end))
        return t
