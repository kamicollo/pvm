"""Tests for the ``python -m pvm.ossie`` CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from pvm.ossie.__main__ import main

from .test_validate_document import _minimal_doc


def _write(tmp_path: Path, name: str, doc: dict[str, object]) -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(doc))
    return path


def _metric(name: str, **extra: object) -> dict[str, object]:
    return {
        "name": name,
        "datatype": "Float",
        "expression": {"sql": f"SUM({name})"},
        **extra,
    }


def _cycle_doc() -> dict[str, object]:
    doc = _minimal_doc(
        metrics=[
            _metric("total"),
            _metric("other"),
            _metric("fee"),
        ],
        custom_extensions=[
            {
                "vendor_name": "PVM",
                "data": json.dumps(
                    {
                        "version": 1,
                        "graphs": {
                            "r": {
                                "root": "total",
                                "components": {
                                    "total": "price + other",
                                    "other": "total + fee",
                                },
                            },
                        },
                    },
                ),
            },
        ],
    )
    doc["metrics"].append(_metric("price"))
    return doc


def _warning_only_doc() -> dict[str, object]:
    # No PVM custom_extensions at all: no errors, no warnings either from PVM
    # layers; use a doc that triggers OSSIE_SDK_SKIPPED-free, warning-only PVM
    # path instead: a role that's declared but unused in any graph.
    return _minimal_doc(
        metrics=[
            _metric(
                "total",
                custom_extensions=[
                    {"vendor_name": "PVM", "data": "version: 1\nrole: measure\n"}
                ],
            ),
        ],
        custom_extensions=[
            {
                "vendor_name": "PVM",
                "data": json.dumps({"version": 1, "graphs": {}}),
            },
        ],
    )


def test_valid_file_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path, "doc.yaml", _minimal_doc())
    exit_code = main(["validate", str(path)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert f"{path}: ok" in out


def test_cycle_file_returns_one_with_code_in_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path, "cycle.yaml", _cycle_doc())
    exit_code = main(["validate", str(path)])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "PVM_CYCLE" in out
    assert str(path) in out


def test_warning_only_file_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path, "warn.yaml", _warning_only_doc())
    exit_code = main(["validate", str(path)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "PVM_ROLE_UNUSED" in out


def test_nonexistent_file_returns_one_no_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "missing.yaml"
    exit_code = main(["validate", str(missing)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert str(missing) in captured.out + captured.err


def test_unreadable_file_returns_one_no_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path, "doc.yaml", _minimal_doc())
    path.chmod(0o000)
    try:
        exit_code = main(["validate", str(path)])
    finally:
        path.chmod(0o644)
    assert exit_code == 1
    captured = capsys.readouterr()
    assert str(path) in captured.out + captured.err


def test_one_bad_file_among_several_returns_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    good = _write(tmp_path, "good.yaml", _minimal_doc())
    missing = tmp_path / "missing.yaml"
    exit_code = main(["validate", str(good), str(missing)])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert f"{good}: ok" in out


def test_subprocess_cli_validates_file(tmp_path: Path) -> None:
    path = _write(tmp_path, "doc.yaml", _minimal_doc())
    result = subprocess.run(
        [sys.executable, "-m", "pvm.ossie", "validate", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert f"{path}: ok" in result.stdout
