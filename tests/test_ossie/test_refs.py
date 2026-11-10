"""Tests for pvm.ossie.refs: metric index and reference resolution."""

from __future__ import annotations

from typing import Any

from pvm.ossie.models import NodeRole
from pvm.ossie.refs import MetricInfo, build_metric_index, resolve
from pvm.ossie.report import Issue


def _pvm_extension(data: str) -> list[dict[str, str]]:
    return [{"vendor_name": "PVM", "data": data}]


def test_index_collects_model_and_dataset_metrics() -> None:
    doc: dict[str, Any] = {
        "metrics": [
            {"name": "total_volume", "datatype": "Float"},
        ],
        "datasets": [
            {
                "metrics": [
                    {"name": "total_revenue", "datatype": "Float"},
                ],
            },
        ],
    }
    issues: list[Issue] = []
    index = build_metric_index(doc, issues)

    assert issues == []
    assert index["total_volume"] == [
        MetricInfo(
            name="total_volume",
            datatype="Float",
            location="metrics[0]",
            default_role=None,
        ),
    ]
    assert index["total_revenue"] == [
        MetricInfo(
            name="total_revenue",
            datatype="Float",
            location="datasets[0].metrics[0]",
            default_role=None,
        ),
    ]


def test_index_records_default_role_from_pvm_extension() -> None:
    doc: dict[str, Any] = {
        "metrics": [
            {
                "name": "avg_price",
                "datatype": "Float",
                "custom_extensions": _pvm_extension("version: 1\nrole: rate\n"),
            },
        ],
    }
    issues: list[Issue] = []
    index = build_metric_index(doc, issues)

    assert issues == []
    assert index["avg_price"][0].default_role == NodeRole.rate


def test_index_metric_without_datatype() -> None:
    doc: dict[str, Any] = {"metrics": [{"name": "m"}]}
    issues: list[Issue] = []
    index = build_metric_index(doc, issues)

    assert issues == []
    assert index["m"][0].datatype is None


def test_index_tolerates_missing_metrics_and_datasets() -> None:
    doc: dict[str, Any] = {}
    issues: list[Issue] = []
    index = build_metric_index(doc, issues)
    assert index == {}
    assert issues == []


def test_index_tolerates_null_datasets() -> None:
    doc: dict[str, Any] = {"metrics": [{"name": "m"}], "datasets": None}
    issues: list[Issue] = []
    index = build_metric_index(doc, issues)
    assert list(index) == ["m"]
    assert issues == []


def test_index_tolerates_null_dataset_metrics() -> None:
    doc: dict[str, Any] = {"datasets": [{"metrics": None}]}
    issues: list[Issue] = []
    index = build_metric_index(doc, issues)
    assert index == {}
    assert issues == []


def test_index_skips_non_mapping_dataset_entries() -> None:
    doc: dict[str, Any] = {"datasets": [None, "oops", {"metrics": [{"name": "m"}]}]}
    issues: list[Issue] = []
    index = build_metric_index(doc, issues)
    assert list(index) == ["m"]
    assert index["m"][0].location == "datasets[2].metrics[0]"
    assert issues == []


def test_index_skips_non_mapping_metric_entries() -> None:
    doc: dict[str, Any] = {"metrics": [None, "oops", 42, {"name": "m"}]}
    issues: list[Issue] = []
    index = build_metric_index(doc, issues)
    assert list(index) == ["m"]
    assert index["m"][0].location == "metrics[3]"
    assert issues == []


def test_index_skips_metric_without_name() -> None:
    doc: dict[str, Any] = {"metrics": [{"datatype": "Float"}]}
    issues: list[Issue] = []
    index = build_metric_index(doc, issues)
    assert index == {}
    assert issues == []


def test_index_unknown_version_issue() -> None:
    doc: dict[str, Any] = {
        "metrics": [
            {
                "name": "m",
                "custom_extensions": _pvm_extension("version: 2\nrole: rate\n"),
            },
        ],
    }
    issues: list[Issue] = []
    index = build_metric_index(doc, issues)

    assert index["m"][0].default_role is None
    assert len(issues) == 1
    assert issues[0].code == "PVM_UNKNOWN_VERSION"
    assert issues[0].severity == "error"
    assert issues[0].path == "metrics[0].custom_extensions[PVM]"


def test_index_unknown_role_issue() -> None:
    doc: dict[str, Any] = {
        "metrics": [
            {
                "name": "m",
                "custom_extensions": _pvm_extension("version: 1\nrole: bogus\n"),
            },
        ],
    }
    issues: list[Issue] = []
    index = build_metric_index(doc, issues)

    assert index["m"][0].default_role is None
    assert len(issues) == 1
    assert issues[0].code == "PVM_UNKNOWN_ROLE"
    assert issues[0].severity == "error"
    assert issues[0].path == "metrics[0].custom_extensions[PVM]"


def test_index_bad_extension_issue() -> None:
    doc: dict[str, Any] = {
        "metrics": [
            {
                "name": "m",
                "custom_extensions": _pvm_extension("role: rate\n"),  # missing version
            },
        ],
    }
    issues: list[Issue] = []
    index = build_metric_index(doc, issues)

    assert index["m"][0].default_role is None
    assert len(issues) == 1
    assert issues[0].code == "PVM_BAD_EXTENSION"
    assert issues[0].severity == "error"
    assert issues[0].path == "metrics[0].custom_extensions[PVM]"


def test_index_bad_extension_extra_key() -> None:
    doc: dict[str, Any] = {
        "metrics": [
            {
                "name": "m",
                "custom_extensions": _pvm_extension("version: 1\nbogus: 1\n"),
            },
        ],
    }
    issues: list[Issue] = []
    index = build_metric_index(doc, issues)

    assert index["m"][0].default_role is None
    assert len(issues) == 1
    assert issues[0].code == "PVM_BAD_EXTENSION"


def test_index_dataset_metric_path() -> None:
    doc: dict[str, Any] = {
        "datasets": [
            {
                "metrics": [
                    {
                        "name": "m",
                        "custom_extensions": _pvm_extension("version: 2\n"),
                    },
                ],
            },
        ],
    }
    issues: list[Issue] = []
    build_metric_index(doc, issues)
    assert issues[0].path == "datasets[0].metrics[0].custom_extensions[PVM]"


def test_index_propagates_bad_yaml_from_extract() -> None:
    doc: dict[str, Any] = {
        "metrics": [
            {"name": "m", "custom_extensions": _pvm_extension("key: [unterminated")},
        ],
    }
    issues: list[Issue] = []
    index = build_metric_index(doc, issues)
    assert index["m"][0].default_role is None
    assert len(issues) == 1
    assert issues[0].code == "PVM_BAD_YAML"


def test_resolve_found() -> None:
    index = {
        "m": [
            MetricInfo(
                name="m", datatype="Float", location="metrics[0]", default_role=None
            )
        ],
    }
    issues: list[Issue] = []
    info = resolve(index, "m", "graphs.g.root", issues)
    assert info is not None
    assert info.name == "m"
    assert issues == []


def test_resolve_unresolved_name() -> None:
    index: dict[str, list[MetricInfo]] = {}
    issues: list[Issue] = []
    info = resolve(index, "missing", "graphs.g.root", issues)
    assert info is None
    assert len(issues) == 1
    assert issues[0].code == "PVM_UNRESOLVED_NAME"
    assert issues[0].severity == "error"
    assert issues[0].path == "graphs.g.root"


def test_resolve_ambiguous_ref() -> None:
    index = {
        "m": [
            MetricInfo(
                name="m", datatype="Float", location="metrics[0]", default_role=None
            ),
            MetricInfo(
                name="m",
                datatype="Float",
                location="datasets[0].metrics[0]",
                default_role=None,
            ),
        ],
    }
    issues: list[Issue] = []
    info = resolve(index, "m", "graphs.g.root", issues)
    assert info is None
    assert len(issues) == 1
    assert issues[0].code == "PVM_AMBIGUOUS_REF"
    assert issues[0].severity == "error"
    assert issues[0].path == "graphs.g.root"
    assert "metrics[0]" in issues[0].message
    assert "datasets[0].metrics[0]" in issues[0].message
