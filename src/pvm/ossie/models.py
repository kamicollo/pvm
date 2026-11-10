"""Pydantic models for the PVM vendor extension payloads."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class NodeRole(StrEnum):
    """The role a node plays within a PVM graph."""

    measure = "measure"
    rate = "rate"
    quantity = "quantity"


class MetricExtension(BaseModel):
    """Metric-level PVM extension: the metric's default role."""

    model_config = ConfigDict(extra="forbid")

    version: int
    role: NodeRole = NodeRole.measure


class Graph(BaseModel):
    """A single PVM graph: its root, role overrides and components."""

    model_config = ConfigDict(extra="forbid")

    root: str
    roles: dict[str, NodeRole] = {}
    components: dict[str, str] = {}


class GraphsExtension(BaseModel):
    """Document-level PVM extension: the named graphs it declares."""

    model_config = ConfigDict(extra="forbid")

    version: int
    graphs: dict[str, Graph]
