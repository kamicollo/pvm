"""Metric index and name resolution for the PVM vendor extension.

Collects the document-level ``metrics`` and each ``datasets[i].metrics``
into an index keyed by metric name, validating each metric's PVM extension
(if any) along the way, and resolves graph/reference names against that
index.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from pvm.ossie.extract import find_pvm_extension
from pvm.ossie.models import SUPPORTED_VERSIONS, MetricExtension, NodeRole
from pvm.ossie.report import Issue


@dataclass(frozen=True)
class MetricInfo:
    """A single metric found in the document, with its PVM default role."""

    name: str
    datatype: str | None
    location: str
    default_role: NodeRole | None


def _is_role_error(error: ValidationError) -> bool:
    """Whether error is specifically an invalid `role` enum value."""
    errors = error.errors()
    return len(errors) == 1 and errors[0]["type"] == "enum" and errors[0]["loc"] == ("role",)


def _metric_default_role(metric: Mapping[str, Any], path: str, issues: list[Issue]) -> NodeRole | None:
    """Validate metric's PVM extension (if any) and return its default role."""
    ext_path = f"{path}.custom_extensions[PVM]"
    payload = find_pvm_extension(metric, ext_path, issues)
    if payload is None:
        return None

    try:
        extension = MetricExtension.model_validate(payload)
    except ValidationError as exc:
        code = "PVM_UNKNOWN_ROLE" if _is_role_error(exc) else "PVM_BAD_EXTENSION"
        issues.append(
            Issue(
                code=code,
                severity="error",
                path=ext_path,
                message=f"invalid PVM metric extension: {exc}",
            ),
        )
        return None

    if extension.version not in SUPPORTED_VERSIONS:
        issues.append(
            Issue(
                code="PVM_UNKNOWN_VERSION",
                severity="error",
                path=ext_path,
                message=f"unsupported PVM extension version {extension.version!r}",
            ),
        )
        return None

    return extension.role


def _collect_metrics(metrics: Any, prefix: str, issues: list[Issue], index: dict[str, list[MetricInfo]]) -> None:  # noqa: ANN401
    """Append MetricInfo entries for each valid metric mapping in metrics."""
    if not isinstance(metrics, list):
        return
    for i, metric in enumerate(metrics):
        if not isinstance(metric, Mapping):
            continue
        name = metric.get("name")
        if not isinstance(name, str):
            continue
        location = f"{prefix}[{i}]"
        datatype = metric.get("datatype")
        default_role = _metric_default_role(metric, location, issues)
        index.setdefault(name, []).append(
            MetricInfo(
                name=name,
                datatype=datatype if isinstance(datatype, str) else None,
                location=location,
                default_role=default_role,
            ),
        )


def build_metric_index(doc: Mapping[str, Any], issues: list[Issue]) -> dict[str, list[MetricInfo]]:
    """Build an index of metric name -> list of MetricInfo found in doc.

    Collects document-level ``metrics`` and each ``datasets[i].metrics``,
    validating each metric's PVM extension against `MetricExtension` and
    appending any `PVM_BAD_EXTENSION` / `PVM_UNKNOWN_VERSION` /
    `PVM_UNKNOWN_ROLE` issues. Malformed entries (non-mapping metrics or
    datasets, missing/non-string names, `None` collections) are skipped.
    """
    index: dict[str, list[MetricInfo]] = {}

    _collect_metrics(doc.get("metrics"), "metrics", issues, index)

    datasets = doc.get("datasets")
    if isinstance(datasets, list):
        for i, dataset in enumerate(datasets):
            if not isinstance(dataset, Mapping):
                continue
            _collect_metrics(dataset.get("metrics"), f"datasets[{i}].metrics", issues, index)

    return index


def resolve(
    index: Mapping[str, list[MetricInfo]],
    name: str,
    path: str,
    issues: list[Issue],
) -> MetricInfo | None:
    """Resolve name against index, returning the unique MetricInfo, if any.

    Appends `PVM_UNRESOLVED_NAME` when name is absent from index, and
    `PVM_AMBIGUOUS_REF` when it matches more than one metric. Either way,
    returns None.
    """
    candidates = index.get(name)
    if not candidates:
        issues.append(
            Issue(
                code="PVM_UNRESOLVED_NAME",
                severity="error",
                path=path,
                message=f"name {name!r} does not resolve to any metric",
            ),
        )
        return None

    if len(candidates) > 1:
        locations = ", ".join(c.location for c in candidates)
        issues.append(
            Issue(
                code="PVM_AMBIGUOUS_REF",
                severity="error",
                path=path,
                message=f"name {name!r} resolves to more than one metric: {locations}",
            ),
        )
        return None

    return candidates[0]
