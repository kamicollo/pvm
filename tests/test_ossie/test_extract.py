"""Tests for pvm.ossie.extract.find_pvm_extension."""

from __future__ import annotations

import pytest

from pvm.ossie.extract import find_pvm_extension
from pvm.ossie.report import Issue, ValidationReport


def test_yaml_payload() -> None:
    obj = {
        "custom_extensions": [
            {"vendor_name": "PVM", "data": "version: 1\nrole: rate\n"},
        ],
    }
    issues: list[Issue] = []
    payload = find_pvm_extension(obj, "root", issues)
    assert payload == {"version": 1, "role": "rate"}
    assert issues == []


def test_json_payload() -> None:
    obj = {
        "custom_extensions": [
            {"vendor_name": "PVM", "data": '{"version": 1, "role": "rate"}'},
        ],
    }
    issues: list[Issue] = []
    payload = find_pvm_extension(obj, "root", issues)
    assert payload == {"version": 1, "role": "rate"}
    assert issues == []


def test_no_pvm_extension_returns_none() -> None:
    obj = {
        "custom_extensions": [
            {"vendor_name": "OTHER", "data": "foo: bar"},
        ],
    }
    issues: list[Issue] = []
    payload = find_pvm_extension(obj, "root", issues)
    assert payload is None
    assert issues == []


def test_no_custom_extensions_key_returns_none() -> None:
    obj: dict[str, object] = {}
    issues: list[Issue] = []
    payload = find_pvm_extension(obj, "root", issues)
    assert payload is None
    assert issues == []


def test_null_custom_extensions_returns_none() -> None:
    obj = {"custom_extensions": None}
    issues: list[Issue] = []
    payload = find_pvm_extension(obj, "root", issues)
    assert payload is None
    assert issues == []


def test_bad_yaml_issue() -> None:
    obj = {
        "custom_extensions": [
            {"vendor_name": "PVM", "data": "key: [unterminated"},
        ],
    }
    issues: list[Issue] = []
    payload = find_pvm_extension(obj, "root", issues)
    assert payload is None
    assert len(issues) == 1
    assert issues[0].code == "PVM_BAD_YAML"
    assert issues[0].severity == "error"
    assert issues[0].path == "root"


def test_non_mapping_payload_issue() -> None:
    obj = {
        "custom_extensions": [
            {"vendor_name": "PVM", "data": "- 1\n- 2\n"},
        ],
    }
    issues: list[Issue] = []
    payload = find_pvm_extension(obj, "root", issues)
    assert payload is None
    assert len(issues) == 1
    assert issues[0].code == "PVM_BAD_YAML"


def test_missing_data_key_issue() -> None:
    obj = {
        "custom_extensions": [
            {"vendor_name": "PVM"},
        ],
    }
    issues: list[Issue] = []
    payload = find_pvm_extension(obj, "root", issues)
    assert payload is None
    assert len(issues) == 1
    assert issues[0].code == "PVM_BAD_YAML"


def test_non_mapping_entry_is_skipped() -> None:
    obj = {
        "custom_extensions": [
            "not-a-mapping",
            {"vendor_name": "PVM", "data": "version: 1"},
        ],
    }
    issues: list[Issue] = []
    payload = find_pvm_extension(obj, "root", issues)
    assert payload == {"version": 1}
    assert issues == []


def test_non_list_custom_extensions_returns_none() -> None:
    obj = {"custom_extensions": "not-a-list"}
    issues: list[Issue] = []
    payload = find_pvm_extension(obj, "root", issues)
    assert payload is None
    assert issues == []


def test_non_string_data_issue() -> None:
    obj = {
        "custom_extensions": [
            {"vendor_name": "PVM", "data": 123},
        ],
    }
    issues: list[Issue] = []
    payload = find_pvm_extension(obj, "root", issues)
    assert payload is None
    assert len(issues) == 1
    assert issues[0].code == "PVM_BAD_YAML"


def test_duplicate_pvm_extension_issue() -> None:
    obj = {
        "custom_extensions": [
            {"vendor_name": "PVM", "data": "version: 1"},
            {"vendor_name": "PVM", "data": "version: 1"},
        ],
    }
    issues: list[Issue] = []
    payload = find_pvm_extension(obj, "root", issues)
    assert payload is None
    assert len(issues) == 1
    assert issues[0].code == "PVM_DUPLICATE_EXTENSION"
    assert issues[0].severity == "error"


def test_report_ok_and_raise() -> None:
    warning_report = ValidationReport(
        issues=[Issue(code="PVM_WARN", severity="warning", path="x", message="m")],
    )
    assert warning_report.ok
    warning_report.raise_for_errors()  # should not raise

    error_report = ValidationReport(
        issues=[Issue(code="PVM_ERR", severity="error", path="x", message="bad thing")],
    )
    assert not error_report.ok
    with pytest.raises(ValueError, match="bad thing"):
        error_report.raise_for_errors()
