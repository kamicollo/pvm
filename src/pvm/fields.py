from __future__ import annotations
import dataclasses
from typing import List, Optional


@dataclasses.dataclass(frozen=True, eq=True)
class Field:
    name: str
    type: str
    components: List[Field] = dataclasses.field(default_factory=list, compare=False)


@dataclasses.dataclass(frozen=True, eq=True)
class TotalField(Field):
    type: str = "total"


@dataclasses.dataclass(frozen=True, eq=True)
class RateField(Field):
    type: str = "rate"


@dataclasses.dataclass(frozen=True, eq=True)
class QuantityField(Field):
    type: str = "quantity"


@dataclasses.dataclass(frozen=True, eq=True)
class OtherField(Field):
    type: str = "other"


@dataclasses.dataclass(frozen=True, eq=True)
class RecField(Field):
    type: str = "reconciliation"
