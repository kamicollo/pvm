from __future__ import annotations
import dataclasses
from abc import ABC
from typing import List, Literal
from ibis import Deferred
from ibis import deferred as col
import ibis

# Define the literal type for field types
FieldType = Literal["simple", "rate", "quantity"]


@dataclasses.dataclass(frozen=True, eq=True)
class BaseField(ABC):
    name: str
    type: FieldType
    components: List[BaseField] = dataclasses.field(default_factory=list, compare=False)
    definition: Deferred | None = None

    @property
    def _rate_components(self) -> List[RateField]:
        return [c for c in self.components if isinstance(c, RateField)]

    @property
    def _quantity_components(self) -> list[QuantityField]:
        return [c for c in self.components if isinstance(c, QuantityField)]

    @property
    def other_components(self) -> List[Field]:
        return [c for c in self.components if isinstance(c, Field)]

    @property
    def rate(self) -> RateField | None:
        return next(iter(self._rate_components), None)

    @property
    def quantity(self) -> QuantityField | None:
        return next(iter(self._quantity_components), None)

    def _validate_components(self):
        if self.components and self.definition is None:
            raise ValueError(
                f"Field '{self.name}' must have either components or a definition"
            )
        elif len(self._rate_components) > 1:
            raise ValueError(
                f"Field {self.name} has multiple rate components which is not supported"
            )
        elif len(self._quantity_components) > 1:
            raise ValueError(
                f"Field {self.name} has multiple quantity components which is not supported"
            )
        elif len(self._rate_components) == 1 and len(self._quantity_components) == 0:
            raise ValueError(f"Field {self.name} is missing a quantity component")
        elif len(self._rate_components) == 0 and len(self._quantity_components) == 1:
            raise ValueError(f"Field {self.name} is missing a rate component")

    def __post_init__(self):
        self._validate_components()
        if self.components and self.definition is not None:
            self._add_reconciliation_field()

    def _add_reconciliation_field(self):
        self.components.append(
            Field(
                name=self.name + "_rec",
                definition=(
                    (self.definition)
                    - (
                        (self.rate.definition * self.quantity.definition)
                        if self.rate
                        else 0
                    )
                    - sum([c.definition for c in self.other_components])
                ),
            )
        )

    def get_flattened_graph(self) -> list[BaseField]:
        flat_graph = [self]
        for component in self.components:
            flat_graph.extend(component.get_flattened_graph())
        return flat_graph

    def effect_fields(self, start: str, end: str, expr_prefix=1) -> list[Deferred]:
        fields = []
        if self.rate and self.quantity:
            quantity_change = (
                col[self.quantity.name + "_" + end]
                - col[self.quantity.name + "_" + start]
            )
            rate_change = (
                col[self.rate.name + "_" + end] - col[self.rate.name + "_" + start]
            )
            fields.append(rate_change.name(self.rate.name + "_change_" + start))
            fields.append(quantity_change.name(self.quantity.name + "_change_" + start))
            fields.append(
                ibis.case()
                .when(
                    (col[self.quantity.name + "_" + end] != 0)
                    & (col[self.quantity.name + "_" + start] != 0),
                    quantity_change * col[self.rate.name + "_" + end] * expr_prefix,
                )
                .else_(quantity_change * expr_prefix)
                .end()
                .name(self.quantity.name + "_effect_" + start)
            )

            if self.quantity.components:
                fields.extend(
                    self.quantity.effect_fields(
                        start, end, expr_prefix * (col[self.rate.name + "_" + end])
                    )
                )

            fields.append(
                ibis.case()
                .when(
                    (col[self.quantity.name + "_" + end] != 0)
                    & (col[self.quantity.name + "_" + start] != 0),
                    rate_change * col[self.quantity.name + "_" + start] * expr_prefix,
                )
                .else_(0)
                .end()
                .name(self.rate.name + "_effect_" + start)
            )

            if self.rate.components:
                fields.extend(
                    self.rate.effect_fields(
                        start,
                        end,
                        expr_prefix * (col[self.quantity.name + "_" + start]),
                    )
                )

        for f in self.other_components:
            fields.append(
                (
                    (col[f.name + "_" + end] - col[f.name + "_" + start]) * expr_prefix
                ).name(f.name + "_effect_" + start)
            )
        return fields


@dataclasses.dataclass(frozen=True, eq=True)
class Field(BaseField):
    type: FieldType = "simple"


@dataclasses.dataclass(frozen=True, eq=True)
class RateField(BaseField):
    type: FieldType = "rate"


@dataclasses.dataclass(frozen=True, eq=True)
class QuantityField(BaseField):
    type: FieldType = "quantity"
