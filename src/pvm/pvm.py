from enum import Enum
import ibis
from .fields import Field, BaseField
from typing import Self


class CalculationMethod(Enum):
    CLASSIC = 0
    INVERSE = 1
    THREE_WAY = 2
    SYMMETRIC = 3


class PVM:
    method: CalculationMethod
    hierarchy: list[ibis.Expr]
    aggregated: ibis.Table | None

    def __init__(
        self,
        method_to_use: CalculationMethod = CalculationMethod.CLASSIC,
    ):
        self.method = method_to_use
        self.hierarchy = []
        self.aggregated = None

    def set_data(self, table: ibis.Table) -> Self:
        self.data = table
        return self

    def set_graph(self, graph: Field) -> Self:
        self.graph = graph
        return self

    def set_periods(self, definition: ibis.Expr, order=list[str]) -> Self:
        self.period_expression = definition
        self.period_order = order
        return self

    def set_hierarchy(self, hierarchy: list[ibis.Expr]) -> Self:
        self.hierarchy = hierarchy
        return self

    def get_graph_components(self) -> list[BaseField]:
        return self.flattened_list

    def aggregate(self) -> ibis.Table:
        """Foo bar"""
        if self.aggregated is None:
            self.aggregated = (
                self.data.filter(self.period_expression.isin(list(self.period_order)))
                .group_by(self.hierarchy + [self.period_expression.name("period")])
                .aggregate(
                    [
                        f.definition.name(f.name)
                        for f in self.graph.get_flattened_graph()
                    ]
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
        t = self.aggregate()
        for period_start, period_end in zip(
            self.period_order[:-1], self.period_order[1:]
        ):
            t = t.mutate(self.graph.effect_fields(period_start, period_end))
        return t
