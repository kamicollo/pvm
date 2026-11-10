"""Tests that the bundled Ossie datasets carry valid PVM graphs.

Parametrised over every file in src/datasets/ossie/ so olist.yaml (which
carries no PVM extension) stays covered without graphs, while mini_fx and
fake_sales are additionally checked for the specific graphs they declare.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pvm.ossie import validate_document
from pvm.ossie.extract import find_pvm_extension
from pvm.ossie.report import Issue

_DATASETS_DIR = Path(__file__).resolve().parents[2] / "src" / "datasets" / "ossie"
_DATASET_FILES = sorted(p.name for p in _DATASETS_DIR.glob("*.yaml"))

_EXPECTED_GRAPHS = {
    "mini_fx.yaml": {"revenue"},
    "fake_sales.yaml": {"revenue", "cost", "profit"},
}


@pytest.mark.parametrize("filename", _DATASET_FILES)
def test_dataset_validates_ok(filename: str) -> None:
    report = validate_document(_DATASETS_DIR / filename)
    assert report.ok, report.issues


@pytest.mark.parametrize("filename", sorted(_EXPECTED_GRAPHS))
def test_dataset_declares_expected_graphs(filename: str) -> None:
    doc = yaml.safe_load((_DATASETS_DIR / filename).read_text())
    issues: list[Issue] = []
    payload = find_pvm_extension(doc, "$", issues)

    assert issues == []
    assert payload is not None
    assert set(payload.get("graphs", {})) == _EXPECTED_GRAPHS[filename]


@pytest.mark.parametrize("filename", sorted(_EXPECTED_GRAPHS))
def test_dataset_has_no_warnings(filename: str) -> None:
    report = validate_document(_DATASETS_DIR / filename)
    assert report.issues == []
