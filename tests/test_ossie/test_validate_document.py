"""Tests for pvm.ossie.validate_document and the public API."""

from __future__ import annotations

import builtins
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from pvm.ossie import Issue, ValidationReport, validate_document

_DATASETS_DIR = Path(__file__).resolve().parents[2] / "src" / "datasets" / "ossie"


def _minimal_doc(**extra: Any) -> dict[str, Any]:  # noqa: ANN401
    doc: dict[str, Any] = {
        "version": "0.2.0.dev0",
        "name": "x",
        "datasets": [{"name": "d", "source": "s"}],
    }
    doc.update(extra)
    return doc


def test_returns_validation_report() -> None:
    report = validate_document(_minimal_doc())
    assert isinstance(report, ValidationReport)
    assert report.ok
    assert report.issues == []


def test_dict_yaml_string_and_path_agree(tmp_path: Path) -> None:
    doc = _minimal_doc()
    text = yaml.safe_dump(doc)
    path = tmp_path / "doc.yaml"
    path.write_text(text)

    from_dict = validate_document(doc)
    from_string = validate_document(text)
    from_path = validate_document(path)

    assert from_dict.issues == from_string.issues == from_path.issues
    assert from_dict.ok


def test_str_naming_existing_file_is_read(tmp_path: Path) -> None:
    doc = _minimal_doc()
    path = tmp_path / "doc.yaml"
    path.write_text(yaml.safe_dump(doc))

    report = validate_document(str(path))
    assert report.ok


def test_long_text_not_treated_as_path() -> None:
    # Long enough that Path(...).is_file() raises OSError (name too long), which
    # must be treated as "not a path" rather than propagate.
    text = "name: " + "a" * 100_000
    report = validate_document(text)
    assert not report.ok
    assert report.issues[0].code == "OSSIE_INVALID"


def test_empty_text_is_bad_yaml() -> None:
    report = validate_document("")
    assert not report.ok
    assert [i.code for i in report.issues] == ["PVM_BAD_YAML"]


def test_list_top_level_is_bad_yaml() -> None:
    report = validate_document("- 1\n- 2\n")
    assert not report.ok
    assert [i.code for i in report.issues] == ["PVM_BAD_YAML"]


def test_unparsable_yaml_is_bad_yaml_no_traceback() -> None:
    report = validate_document("key: [unterminated")
    assert not report.ok
    assert report.issues[0].code == "PVM_BAD_YAML"


def test_wrong_datasets_type_is_bad_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def _fail_ossie_import(name: str, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        if name == "ossie" or name.startswith("ossie."):
            raise ImportError("ossie not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fail_ossie_import)

    doc = _minimal_doc(datasets="not-a-list")
    report = validate_document(doc)
    codes = [i.code for i in report.issues]
    assert "OSSIE_SDK_SKIPPED" in codes
    assert "PVM_BAD_STRUCTURE" in codes
    assert not report.ok


def test_sdk_missing_runs_pvm_payload_layers(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def _fail_ossie_import(name: str, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        if name == "ossie" or name.startswith("ossie."):
            raise ImportError("ossie not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fail_ossie_import)

    doc = _minimal_doc(
        metrics=[
            {
                "name": "total",
                "expression": {"sql": "SUM(x)"},
                "custom_extensions": [
                    {"vendor_name": "PVM", "data": "version: 1\nrole: not-a-role\n"}
                ],
            },
        ],
    )
    report = validate_document(doc)
    codes = [i.code for i in report.issues]
    assert codes[0] == "OSSIE_SDK_SKIPPED"
    assert "PVM_UNKNOWN_ROLE" in codes


def test_ossie_sdk_rejects_invalid_document() -> None:
    doc = _minimal_doc()
    del doc["name"]
    report = validate_document(doc)
    assert not report.ok
    assert report.issues[0].code == "OSSIE_INVALID"


def test_missing_version_is_ossie_invalid() -> None:
    doc = _minimal_doc()
    del doc["version"]
    report = validate_document(doc)
    assert not report.ok
    assert report.issues[0].code == "OSSIE_INVALID"


def test_null_valued_property_is_ossie_invalid() -> None:
    doc = _minimal_doc(name=None)
    report = validate_document(doc)
    assert not report.ok
    assert report.issues[0].code == "OSSIE_INVALID"


def test_layer_2_error_skips_later_layers() -> None:
    doc = _minimal_doc()
    del doc["name"]
    doc["metrics"] = [
        {
            "name": "total",
            "expression": {"sql": "SUM(x)"},
            "custom_extensions": [
                {"vendor_name": "PVM", "data": "version: 1\nrole: not-a-role\n"}
            ],
        },
    ]
    report = validate_document(doc)
    codes = [i.code for i in report.issues]
    assert codes == ["OSSIE_INVALID"]
    assert "PVM_UNKNOWN_ROLE" not in codes


def test_layer_3_error_skips_layer_4() -> None:
    doc = _minimal_doc(
        metrics=[
            {
                "name": "total",
                "expression": {"sql": "SUM(x)"},
                "custom_extensions": [
                    {"vendor_name": "PVM", "data": "version: 1\nrole: not-a-role\n"}
                ],
            },
        ],
        custom_extensions=[
            {
                "vendor_name": "PVM",
                "data": json.dumps(
                    {"version": 1, "graphs": {"g": {"root": "missing"}}}
                ),
            },
        ],
    )
    report = validate_document(doc)
    codes = [i.code for i in report.issues]
    assert codes == ["PVM_UNKNOWN_ROLE"]


def test_layer_4_resolves_graphs() -> None:
    doc = _minimal_doc(
        metrics=[
            {"name": "total", "expression": {"sql": "SUM(x)"}},
        ],
        custom_extensions=[
            {
                "vendor_name": "PVM",
                "data": json.dumps(
                    {"version": 1, "graphs": {"g": {"root": "missing"}}}
                ),
            },
        ],
    )
    report = validate_document(doc)
    assert [i.code for i in report.issues] == ["PVM_UNRESOLVED_NAME"]


def test_json_payload_accepted() -> None:
    doc = _minimal_doc(
        metrics=[
            {"name": "total", "expression": {"sql": "SUM(x)"}},
        ],
        custom_extensions=[
            {
                "vendor_name": "PVM",
                "data": json.dumps({"version": 1, "graphs": {"g": {"root": "total"}}}),
            },
        ],
    )
    report = validate_document(doc)
    assert report.ok


@pytest.mark.parametrize(
    "filename", sorted(p.name for p in _DATASETS_DIR.glob("*.yaml"))
)
def test_real_datasets_validate_ok(filename: str) -> None:
    report = validate_document(_DATASETS_DIR / filename)
    errors = [i for i in report.issues if i.severity == "error"]
    assert errors == [], errors
    assert report.ok


def test_issue_and_validation_report_exported() -> None:
    assert Issue is not None
    assert ValidationReport is not None
