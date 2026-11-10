"""Top-level entry point: validate a whole Ossie document through all layers.

Implements the "Validator" section of docs/ossie-pvm-extension.md: parse the
document, run it through the Ossie SDK (or a minimal structural fallback),
then the PVM-specific payload and graph layers. Each layer runs only if the
previous one reported no errors (warnings do not block later layers).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from pvm.ossie.refs import build_metric_index
from pvm.ossie.report import Issue, ValidationReport
from pvm.ossie.validate import validate_graphs

_ROOT_PATH = "$"
_STRUCTURAL_LIST_FIELDS = ("datasets", "metrics", "custom_extensions")


def _error(code: str, path: str, message: str) -> Issue:
    return Issue(code=code, severity="error", path=path, message=message)


def _warning(code: str, path: str, message: str) -> Issue:
    return Issue(code=code, severity="warning", path=path, message=message)


def _has_errors(issues: list[Issue]) -> bool:
    return any(issue.severity == "error" for issue in issues)


def _read_text(source: str | Path) -> str:
    if isinstance(source, Path):
        return source.read_text()
    try:
        is_file = Path(source).is_file()
    except OSError:
        # A long or otherwise filesystem-illegal string is YAML text, not a path.
        is_file = False
    return Path(source).read_text() if is_file else source


def _parse_source(source: str | Path | Mapping[str, Any], issues: list[Issue]) -> Mapping[str, Any] | None:
    """Layer 1: parse source into a document mapping, or report PVM_BAD_YAML."""
    if not isinstance(source, str | Path):
        return source

    text = _read_text(source)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        issues.append(_error("PVM_BAD_YAML", _ROOT_PATH, f"could not parse document as YAML: {exc}"))
        return None

    if not isinstance(data, Mapping):
        issues.append(_error("PVM_BAD_YAML", _ROOT_PATH, "document must parse to a mapping"))
        return None

    return data


def _check_minimal_structure(doc: Mapping[str, Any], issues: list[Issue]) -> None:
    """Fallback structural check used when the Ossie SDK is not installed."""
    for name in _STRUCTURAL_LIST_FIELDS:
        value = doc.get(name)
        if value is not None and not isinstance(value, list):
            msg = f"{name!r} must be a list, got {type(value).__name__}"
            issues.append(_error("PVM_BAD_STRUCTURE", f"{_ROOT_PATH}.{name}", msg))


def _validate_with_ossie(doc: Mapping[str, Any], issues: list[Issue]) -> None:
    """Layer 2: validate doc with the Ossie SDK, or fall back to a minimal check."""
    try:
        from ossie import OssieDocument  # noqa: PLC0415
    except ImportError:
        issues.append(
            _warning("OSSIE_SDK_SKIPPED", _ROOT_PATH, "apache-ossie is not installed; skipping full Ossie validation")
        )
        _check_minimal_structure(doc, issues)
        return

    try:
        # `_from_document` applies the schema checks `model_validate` alone would
        # miss (a missing `version`, a null-valued property, ...); see its
        # docstring on `OssieDocument.from_ossie_yaml`, its public, text-taking
        # counterpart. `doc` is already a parsed mapping, so call the shared
        # private entry point directly rather than re-serializing to YAML text.
        OssieDocument._from_document(doc)  # noqa: SLF001
    except (ValidationError, ValueError) as exc:
        issues.append(_error("OSSIE_INVALID", _ROOT_PATH, f"document failed Ossie SDK validation: {exc}"))


def validate_document(source: str | Path | Mapping[str, Any]) -> ValidationReport:
    """Validate an Ossie document carrying the PVM vendor extension.

    `source` is a parsed document (a mapping), a `Path` (read as a file), or a
    `str`: a `str` naming an existing file is read, any other `str` is treated
    as YAML text directly (JSON is valid YAML, so JSON text works too).

    Runs four layers in order, skipping later layers once an earlier one
    reports an error (warnings do not block later layers):

    1. Parse YAML/JSON into a document mapping (`PVM_BAD_YAML`).
    2. Validate the document with the `apache-ossie` SDK's `OssieDocument`
       model (`OSSIE_INVALID`). If the SDK is not importable, emit a
       `OSSIE_SDK_SKIPPED` warning and run a minimal structural check of
       `datasets`/`metrics`/`custom_extensions` instead (`PVM_BAD_STRUCTURE`).
    3. Build the metric index, validating each metric's PVM extension
       (`build_metric_index`): this is the per-metric half of "payload
       syntax".
    4. Validate the document-level PVM graphs extension (`validate_graphs`).
       `validate_graphs` parses and validates that extension's own payload
       syntax as part of resolving references and checking graph structure
       and types, so document-level payload syntax is folded into this layer
       rather than split out: `validate_graphs` treats the payload as a
       single unit, and re-implementing a syntax-only subset of it would
       duplicate that logic for no added signal.
    """
    issues: list[Issue] = []

    doc = _parse_source(source, issues)
    if doc is None or _has_errors(issues):
        return ValidationReport(issues=issues)

    _validate_with_ossie(doc, issues)
    if _has_errors(issues):
        return ValidationReport(issues=issues)

    index = build_metric_index(doc, issues)
    if _has_errors(issues):
        return ValidationReport(issues=issues)

    validate_graphs(doc, index, issues)
    return ValidationReport(issues=issues)
