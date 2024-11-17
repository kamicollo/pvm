"""Field classes for PVM."""

from __future__ import annotations

import dataclasses
from abc import ABC
from collections.abc import Sequence
from typing import Literal

from ibis import Deferred

# Define the literal type for field types
FieldType = Literal["simple", "rate", "quantity", "reconciliation"]


@dataclasses.dataclass(frozen=True, eq=True)
class BaseField(ABC):
    """
    Base class for fields.

    Raises:
        ValueError: Errors raised when field configuration is invalid

    Returns:
        BaseField: _description_

    """

    name: str
    type: FieldType
    components: list[Field | RateField | QuantityField] = dataclasses.field(default_factory=list, compare=False)
    definition: Deferred | None = None

    @property
    def _rate_components(self) -> list[RateField]:
        return [c for c in self.components if isinstance(c, RateField)]

    @property
    def _quantity_components(self) -> list[QuantityField]:
        return [c for c in self.components if isinstance(c, QuantityField)]

    @property
    def other_components(self) -> list[Field]:
        """
        Retrieves all components that are not rate or quantity fields.

        Returns:
            list[Field]: List of components that are not rate or quantity fields

        """
        return [c for c in self.components if isinstance(c, Field)]

    @property
    def rate(self) -> RateField | None:
        """
        Retrieves the rate component of the field.

        Returns:
            RateField | None: Rate component of the field

        """
        return next(iter(self._rate_components), None)

    @property
    def quantity(self) -> QuantityField | None:
        """
        Retrieves the quantity component of the field.

        Returns:
            QuantityField | None: Quantity component of the field

        """
        return next(iter(self._quantity_components), None)

    @property
    def reconciliation_field(self) -> ReconciliationField | None:
        """
        Retrieves the reconciliation field of the field.

        Returns:
            Field | None: Reconciliation field of the field

        """
        return next(
            (c for c in self.components if isinstance(c, ReconciliationField)),
            None,
        )

    @property
    def calculated_definition(self) -> Deferred | None:
        """
        Returns the calculated definition derived from the components.

        Returns:
            Deferred | None: Ibis expression representing the calculated definition

        """
        if self.rate and self.quantity:
            return (self.rate.formula * self.quantity.formula) + sum(
                [c.formula for c in self.other_components],
            )
        return None

    @property
    def formula(self) -> Deferred:
        """
        Returns the formula for the field.

        Returns:
            Deferred: Formula for the field is either the definition or the calculated definition.

        """
        if self.definition is not None:
            return self.definition
        if self.calculated_definition is not None:
            return self.calculated_definition
        raise ValueError(f"Field {self.name} has no definition or components")  # pragma: no cover

    def _validate_components(self) -> None:
        if not self.components and self.definition is None:
            raise ValueError(
                f"Field '{self.name}' must have either components or a definition",
            )
        if len(self._rate_components) > 1:
            raise ValueError(
                f"Field {self.name} has multiple rate components which is not supported",
            )
        if len(self._quantity_components) > 1:
            raise ValueError(
                f"Field {self.name} has multiple quantity components which is not supported",
            )
        if len(self._rate_components) == 1 and len(self._quantity_components) == 0:
            raise ValueError(f"Field {self.name} is missing a quantity component")
        if len(self._rate_components) == 0 and len(self._quantity_components) == 1:
            raise ValueError(f"Field {self.name} is missing a rate component")

    def __post_init__(self) -> None:
        """Validate the field configuration and adds reconciliation field if necessary."""
        self._validate_components()
        self._add_reconciliation_field()

    def _add_reconciliation_field(self) -> None:
        """Add a reconciliation field to the field if it has components and a definition."""
        if self.rate and self.quantity and self.definition is not None:
            self.components.append(
                ReconciliationField(
                    name=self.name + "_rec",
                    definition=((self.definition) - self.calculated_definition),
                ),
            )

    def get_flattened_graph(self) -> Sequence[RateField | Field | QuantityField]:
        """
        Get a flattened graph of the field and its components.

        Returns:
            list[BaseField]: List of fields in the graph

        """
        flat_graph: Sequence = [self]
        for component in self.components:
            flat_graph.extend(component.get_flattened_graph())
        return flat_graph


@dataclasses.dataclass(frozen=True, eq=True)
class Field(BaseField):
    """Field class for simple fields."""

    type: FieldType = "simple"


@dataclasses.dataclass(frozen=True, eq=True)
class ReconciliationField(Field):
    """Field class for reconciliation fields."""

    type: FieldType = "reconciliation"


@dataclasses.dataclass(frozen=True, eq=True)
class RateField(BaseField):
    """Field class for rate fields."""

    type: FieldType = "rate"


@dataclasses.dataclass(frozen=True, eq=True)
class QuantityField(BaseField):
    """Field class for quantity fields."""

    type: FieldType = "quantity"


@dataclasses.dataclass(frozen=True, eq=True)
class CompositeRateField(RateField):
    """A field that combines multiple rate components."""

    @property
    def rate(self) -> None:
        """CompositeRateField does not have a single rate component."""
        return None

    @property
    def rates(self) -> list[RateField]:
        """List of rate components."""
        return self.components  # type: ignore

    def _validate_components(self) -> None:
        if not self.components:
            raise ValueError(f"CompositeRateField '{self.name}' must have at least one rate component")

        if self.definition is not None:
            raise ValueError(f"CompositeRateField '{self.name}' cannot have a direct definition")

        if not all(isinstance(c, RateField) for c in self.components):
            raise ValueError(f"CompositeRateField '{self.name}' can only have RateField components")

    @property
    def calculated_definition(self) -> Deferred:
        """Sum of all rate components."""
        return sum(c.formula for c in self.components)  # type: ignore
