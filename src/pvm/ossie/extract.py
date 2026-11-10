"""Locate and parse the PVM vendor extension within an Ossie document object."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import yaml

from pvm.ossie.report import Issue

_VENDOR_NAME = "PVM"


def _parse_payload(data: str, path: str, issues: list[Issue]) -> Any | None:  # noqa: ANN401
    """Parse a single PVM extension's "data" value as YAML/JSON."""
    try:
        payload = yaml.safe_load(data)
    except yaml.YAMLError as exc:
        issues.append(
            Issue(
                code="PVM_BAD_YAML",
                severity="error",
                path=path,
                message=f"could not parse PVM extension data as YAML: {exc}",
            ),
        )
        return None

    if not isinstance(payload, Mapping):
        issues.append(
            Issue(
                code="PVM_BAD_YAML",
                severity="error",
                path=path,
                message="PVM extension data must parse to a mapping",
            ),
        )
        return None

    return payload


def find_pvm_extension(obj: Mapping[str, Any], path: str, issues: list[Issue]) -> Any | None:  # noqa: ANN401
    """Return the parsed payload of the single PVM extension in obj, if any.

    Looks at obj["custom_extensions"] for exactly one entry whose
    vendor_name is "PVM", parses its "data" string as YAML (which also
    accepts JSON), and returns the resulting mapping. Appends PVM_BAD_YAML
    for parse failures, non-mapping payloads, or a missing "data" key, and
    PVM_DUPLICATE_EXTENSION when more than one PVM entry is present. Returns
    None when there is no PVM extension or an issue was raised.
    """
    extensions = obj.get("custom_extensions")
    if not extensions:
        return None

    pvm_entries = [entry for entry in extensions if entry.get("vendor_name") == _VENDOR_NAME]
    if not pvm_entries:
        return None

    if len(pvm_entries) > 1:
        issues.append(
            Issue(
                code="PVM_DUPLICATE_EXTENSION",
                severity="error",
                path=path,
                message=f"found {len(pvm_entries)} PVM extensions, expected at most one",
            ),
        )
        return None

    entry = pvm_entries[0]
    if "data" not in entry:
        issues.append(
            Issue(
                code="PVM_BAD_YAML",
                severity="error",
                path=path,
                message="PVM extension is missing the 'data' key",
            ),
        )
        return None

    return _parse_payload(entry["data"], path, issues)
