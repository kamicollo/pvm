"""PVM class module."""

from __future__ import annotations

from enum import Enum
from functools import cached_property
from typing import Self

import ibis

from pvm import PERIOD_COLUMN
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
    hierarchy: list[ibis.Deferred]
    data: ibis.Table | None
    period_expression: ibis.Deferred | None
    period_order: list[str] | None
    graph: Field | None

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

    def set_graph(self, graph: Field) -> Self:
        """
        Set the calculation graph for the instance.

        Args:
            graph (Field): The graph to be set.

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
            effect_fields = derive_effect_fields(self.graph, period_start, period_end)
            t = t.mutate(effect_fields)  # type: ignore
        return t
