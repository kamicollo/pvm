"""Base measure class for PVM."""

from __future__ import annotations

import dataclasses
from abc import ABC
from collections.abc import Callable, MutableSequence
from functools import wraps
from typing import TypeVar

from ibis import Deferred

from pvm import CHANGE_COLUMN, EFFECT_COLUMN
from pvm.common import ObservableList

T = TypeVar("T")


def requires_validation(method: Callable[..., T]) -> Callable[..., T]:
    """Ensure measure is validated before method execution."""

    @wraps(method)
    def wrapper(self: BaseMeasure, *args, **kwargs) -> T:  # noqa: ANN002, ANN003
        self._ensure_validated()
        return method(self, *args, **kwargs)

    return wrapper


# Fields that should trigger invalidation when changed
_INVALIDATING_FIELDS = frozenset({"name", "reconcile", "components", "definition"})


@dataclasses.dataclass(eq=True)
class BaseMeasure(ABC):
    """
    Base class for measures.s.

    Raises:
        ValueError: Errors raised when measure configuration is invalid

    Returns:
        BaseMeasure: _description_

    """

    name: str
    reconcile: bool
    components: list[Measure | RateMeasure | QuantityMeasure | ReconciliationMeasure] = dataclasses.field(
        default_factory=list,
        compare=False,
    )
    definition: Deferred | None = None
    _validated: bool = dataclasses.field(default=False, compare=False, repr=False)

    @property
    def _rate_components(self) -> list[RateMeasure]:
        return [c for c in self.components if isinstance(c, RateMeasure)]

    @property
    def _quantity_components(self) -> list[QuantityMeasure]:
        return [c for c in self.components if isinstance(c, QuantityMeasure)]

    @property
    def other_components(self) -> list[Measure]:
        """
        Retrieves all components that are not rate or quantity measures.

        Returns:
            list[Measure]: List of components that are not rate or quantity measures

        """
        return [c for c in self.components if isinstance(c, Measure)]

    @property
    def rate(self) -> RateMeasure | None:
        """
        Retrieves the rate component of the measure.

        Returns:
            RateMeasure | None: Rate component of the measure

        """
        return next(iter(self._rate_components), None)

    @property
    def quantity(self) -> QuantityMeasure | None:
        """
        Retrieves the quantity component of the measure.

        Returns:
            QuantityMeasure | None: Quantity component of the measure

        """
        return next(iter(self._quantity_components), None)

    @property
    def reconciliation_field(self) -> ReconciliationMeasure | None:
        """
        Retrieves the reconciliation measure of the measure.

        Returns:
            ReconciliationMeasure | None: Reconciliation measure of the measure

        """
        return next(
            (c for c in self.components if isinstance(c, ReconciliationMeasure)),
            None,
        )

    @property
    def calculated_definition(self) -> Deferred | None:
        """
        Returns the calculated definition derived from the components.

        Returns:
            Deferred | None: Ibis expression representing the calculated definition

        """
        if self.components:
            if self.rate and self.quantity:
                return (self.rate.formula * self.quantity.formula) + sum(
                    [c.formula for c in self.other_components],
                )
            return sum([c.formula for c in self.other_components])  # type: ignore
        return None

    @property
    def formula(self) -> Deferred:
        """
        Returns the formula for the measure.

        Returns:
            Deferred: Formula for the measure is either the definition or the calculated definition.

        """
        self._ensure_validated()
        if self.definition is not None:
            return self.definition
        if self.calculated_definition is not None:
            return self.calculated_definition
        raise ValueError(f"Measure {self.name} has no definition or components")  # pragma: no cover

    def _validate_components(self) -> None:
        if not self.components and self.definition is None:
            raise ValueError(
                f"Measure '{self.name}' must have either components or a definition",
            )
        if len(self._rate_components) > 1:
            raise ValueError(
                f"Measure {self.name} has multiple rate components which is not supported",
            )
        if len(self._quantity_components) > 1:
            raise ValueError(
                f"Measure {self.name} has multiple quantity components which is not supported",
            )
        if len(self._rate_components) == 1 and len(self._quantity_components) == 0:
            raise ValueError(f"Measure {self.name} is missing a quantity component")
        if len(self._rate_components) == 0 and len(self._quantity_components) == 1:
            raise ValueError(f"Measure {self.name} is missing a rate component")

    def __post_init__(self) -> None:
        """Initialize the measure with observable components list."""
        # Wrap the components list to auto-invalidate on mutations
        object.__setattr__(
            self,
            "components",
            ObservableList(self.components, on_mutate=self._invalidate),
        )

    def _invalidate(self) -> None:
        """Mark the measure as needing re-validation (called automatically on mutations)."""
        object.__setattr__(self, "_validated", False)

    def __setattr__(self, name: str, value: object) -> None:
        """Override setattr to auto-invalidate when data fields change."""
        # Always allow setting during initialization or for non-invalidating fields
        if name in _INVALIDATING_FIELDS and hasattr(self, "_validated") and self._validated:
            object.__setattr__(self, "_validated", False)

        # Special handling for components: wrap in ObservableList
        if name == "components" and not isinstance(value, ObservableList):
            value = ObservableList(value, on_mutate=self._invalidate)  # type: ignore

        object.__setattr__(self, name, value)

    def _ensure_validated(self) -> None:
        """Ensure the measure is validated, performing validation if not already done."""
        if not self._validated:
            self._validate_components()
            self._add_reconciliation_field()
            object.__setattr__(self, "_validated", True)

    def _add_reconciliation_field(self) -> None:
        """Add a reconciliation measure to the measure if it has components and a definition."""
        if self.rate and self.quantity and self.definition is not None and self.reconcile:
            # Check if reconciliation field already exists to avoid duplicates
            rec_name = self.name + "_rec"
            if not any(c.name == rec_name for c in self.components):
                self.components.append(
                    ReconciliationMeasure(
                        name=rec_name,
                        definition=((self.definition) - self.calculated_definition),
                    ),
                )

    @requires_validation
    def get_flattened_graph(self) -> MutableSequence[RateMeasure | Measure | QuantityMeasure]:
        """
        Get a flattened graph of the measure and its components.

        Returns:
            list[BaseMeasure]: List of measures in the graph

        """
        flat_graph: MutableSequence = [self]
        for component in self.components:
            flat_graph.extend(component.get_flattened_graph())
        return flat_graph  # ty: ignore

    def period_column(self, period: str) -> str:
        """
        Get string reference to a wide column representing the field value for a given period.

        Args:
            period (str): period of interest

        Returns:
            str: string reference to a column of form "fieldname_period"

        """
        return self.name + "_" + period

    def change_column(self, period: str) -> str:
        """
        Get string reference to a wide column representing the field change value for a given period.

        Args:
            period (str): period of interest

        Returns:
            str: string reference to a column of form "fieldname__change__period"

        """
        return self.name + CHANGE_COLUMN + period

    def effect_column(self, period: str) -> str:
        """
        Get string reference to a wide column representing the field value for a given period.

        Args:
            period (str): period of interest

        Returns:
            str: string reference to a column of form "fieldname__effect__period"

        """
        return self.name + EFFECT_COLUMN + period

    @requires_validation
    def display(
        self, *, dpi: int = 96, size: tuple[int, int] | None = None, show_implied_formulas: bool = False
    ) -> None:
        """
        Display a graphviz representation of the measure and its components.

        Args:
            dpi: Dots per inch for rendering (default: 96)
            size: Graph size as (width, height) in inches
            show_implied_formulas: Whether to show implied formulas in the graph (default: False)

        Returns:
            None

        """
        from pvm.measures.visualization.dot_graph import display_dot_graph  # noqa: PLC0415

        return display_dot_graph(self, dpi=dpi, size=size, show_implied_formulas=show_implied_formulas)


@dataclasses.dataclass(eq=True)
class Measure(BaseMeasure):
    """Measure class for simple measures."""

    reconcile: bool = True


@dataclasses.dataclass(eq=True)
class ReconciliationMeasure(BaseMeasure):
    """Measure class for reconciliation measures."""

    reconcile: bool = False


@dataclasses.dataclass(eq=True)
class RateMeasure(BaseMeasure):
    """Measure class for rate measures."""

    reconcile: bool = False

    def _validate_components(self) -> None:
        super()._validate_components()
        # we do not allow measures that are of Rate type to have simple components
        if any(isinstance(c, Measure) for c in self.components):
            raise ValueError(f"Measure {self.name} of type {self.__class__.__name__} cannot have simple components")


@dataclasses.dataclass(eq=True)
class QuantityMeasure(BaseMeasure):
    """Measure class for quantity measures."""

    reconcile: bool = False

    def _validate_components(self) -> None:
        super()._validate_components()
        # we do not allow measures that are of Quantity type to have simple components
        if any(isinstance(c, Measure) for c in self.components):
            raise ValueError(f"Measure {self.name} of type {self.__class__.__name__} cannot have simple components")


@dataclasses.dataclass(eq=True)
class CompositeRateMeasure(RateMeasure):
    """A measure that combines multiple rate components."""

    @property
    def rate(self) -> None:
        """CompositeRateMeasure does not have a single rate component."""
        return None

    @property
    def rates(self) -> list[RateMeasure]:
        """List of rate components."""
        return self.components  # type: ignore

    def _validate_components(self) -> None:
        if not self.components:
            raise ValueError(f"CompositeRateMeasure '{self.name}' must have at least one rate component")

        if self.definition is not None:
            raise ValueError(f"CompositeRateMeasure '{self.name}' cannot have a direct definition")

        if not all(isinstance(c, RateMeasure) for c in self.components):
            raise ValueError(f"CompositeRateMeasure '{self.name}' can only have RateMeasure components")

    @property
    def calculated_definition(self) -> Deferred:
        """Sum of all rate components."""
        return sum(c.formula for c in self.components)  # type: ignore
