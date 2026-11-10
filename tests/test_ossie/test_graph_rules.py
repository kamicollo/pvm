"""Tests for pvm.ossie.validate.validate_graphs."""

from __future__ import annotations

import json
from typing import Any

import pytest

from pvm.ossie.refs import build_metric_index
from pvm.ossie.report import Issue
from pvm.ossie.validate import validate_graphs

Metrics = dict[str, tuple[str | None, str | None]]

BASE: Metrics = {
    "total": ("Float", None),
    "price": ("Float", "rate"),
    "volume": ("Float", "quantity"),
    "fee": ("Float", None),
    "other": ("Float", None),
}


def _ext(payload: Any) -> list[dict[str, str]]:  # noqa: ANN401
    return [{"vendor_name": "PVM", "data": json.dumps(payload)}]


def make_doc(
    metrics: Metrics, graphs: dict[str, Any] | None = None, version: int = 1
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for name, (datatype, role) in metrics.items():
        entry: dict[str, Any] = {"name": name}
        if datatype is not None:
            entry["datatype"] = datatype
        if role is not None:
            entry["custom_extensions"] = _ext({"version": 1, "role": role})
        entries.append(entry)
    doc: dict[str, Any] = {"metrics": entries}
    if graphs is not None:
        doc["custom_extensions"] = _ext({"version": version, "graphs": graphs})
    return doc


def run(doc: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    index = build_metric_index(doc, issues)
    validate_graphs(doc, index, issues)
    return issues


def clean(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.code != "PVM_ROLE_UNUSED"]


def codes(issues: list[Issue]) -> set[str]:
    return {i.code for i in issues}


def g(
    root: str,
    components: dict[str, str] | None = None,
    roles: dict[str, str] | None = None,
) -> dict[str, Any]:
    graph: dict[str, Any] = {"root": root, "components": components or {}}
    if roles is not None:
        graph["roles"] = roles
    return graph


def test_valid_graph_has_no_issues() -> None:
    doc = make_doc(BASE, {"r": g("total", {"total": "price * volume + fee"})})
    assert run(doc) == []


def test_root_only_graph_valid() -> None:
    assert clean(run(make_doc(BASE, {"r": g("total")}))) == []


def test_shared_node_dag_valid() -> None:
    metrics = {**BASE, "a": ("Float", None), "b": ("Float", None)}
    graphs = {
        "r": g("total", {"total": "a + b", "a": "other + fee", "b": "other + fee"})
    }
    # `other` shared: a and b are measures so singles are measures
    assert clean(run(make_doc(metrics, graphs))) == []


def test_same_metric_different_roles_per_graph() -> None:
    graphs = {
        "r": g("total", {"total": "price * volume"}),
        "v": g("volume", {"volume": "fee + other"}, roles={"volume": "measure"}),
    }
    assert run(make_doc(BASE, graphs)) == []


def test_no_extension_no_issues_without_roles() -> None:
    assert run(make_doc({"total": ("Float", None)})) == []


def test_unknown_version() -> None:
    assert "PVM_UNKNOWN_VERSION" in codes(
        run(make_doc(BASE, {"r": g("total")}, version=99))
    )


def test_bad_extension() -> None:
    doc = make_doc(BASE, {"r": {"root": "total", "bogus": 1}})
    assert "PVM_BAD_EXTENSION" in codes(run(doc))


def test_unknown_role() -> None:
    doc = make_doc(BASE, {"r": g("total", roles={"total": "weird"})})
    assert codes(run(doc)) == {"PVM_UNKNOWN_ROLE"}


def test_bad_expression() -> None:
    doc = make_doc(BASE, {"r": g("total", {"total": "price *"})})
    assert "PVM_BAD_EXPRESSION" in codes(run(doc))


@pytest.mark.parametrize(
    "graph",
    [
        g("bad name"),
        g("total", {"bad.key": "price + fee"}),
        g("total", {"total": "price + fee"}, roles={"bad name": "measure"}),
    ],
)
def test_invalid_node_name(graph: dict[str, Any]) -> None:
    assert "PVM_INVALID_NODE_NAME" in codes(run(make_doc(BASE, {"r": graph})))


def test_invalid_metric_name_in_expression() -> None:
    metrics = {**BASE, "my metric": ("Float", None)}
    doc = make_doc(metrics, {"r": g("total", {"total": "my metric + fee"})})
    assert "PVM_INVALID_NODE_NAME" in codes(run(doc))


def test_unresolved_name() -> None:
    doc = make_doc(BASE, {"r": g("total", {"total": "fee + nope"})})
    assert "PVM_UNRESOLVED_NAME" in codes(run(doc))


def test_ambiguous_ref() -> None:
    doc = make_doc(BASE, {"r": g("total", {"total": "fee + other"})})
    doc["datasets"] = [{"metrics": [{"name": "fee", "datatype": "Float"}]}]
    assert "PVM_AMBIGUOUS_REF" in codes(run(doc))


def test_role_key_not_node() -> None:
    doc = make_doc(
        BASE, {"r": g("total", {"total": "fee + other"}, roles={"price": "rate"})}
    )
    assert "PVM_ROLE_KEY_NOT_NODE" in codes(run(doc))


@pytest.mark.parametrize(
    "components",
    [
        {"total": "fee + other", "other": "total + fee"},
        {"total": "total + fee"},
    ],
)
def test_cycle(components: dict[str, str]) -> None:
    result = codes(run(make_doc(BASE, {"r": g("total", components)})))
    assert "PVM_CYCLE" in result


def test_unreachable_component_key() -> None:
    doc = make_doc(
        BASE, {"r": g("total", {"total": "fee + other", "price": "fee + other"})}
    )
    assert "PVM_UNREACHABLE" in codes(run(doc))


def test_duplicate_name() -> None:
    for expr in ("fee + fee", "fee - fee"):
        assert "PVM_DUPLICATE_NAME" in codes(
            run(make_doc(BASE, {"r": g("total", {"total": expr})}))
        )


def test_bad_product() -> None:
    doc = make_doc(BASE, {"r": g("total", {"total": "fee * other"})})
    assert "PVM_BAD_PRODUCT" in codes(run(doc))


def test_measure_bad_single() -> None:
    doc = make_doc(BASE, {"r": g("total", {"total": "fee + price"})})
    assert "PVM_MEASURE_BAD_SINGLE" in codes(run(doc))


def test_rate_mixed() -> None:
    metrics = {**BASE, "p2": ("Float", "rate")}
    doc = make_doc(metrics, {"r": g("p2", {"p2": "price * volume + price"})})
    assert "PVM_RATE_MIXED" in codes(run(doc))


def test_rate_bad_single() -> None:
    doc = make_doc(BASE, {"r": g("price", {"price": "fee + other"})})
    assert "PVM_RATE_BAD_SINGLE" in codes(run(doc))


def test_rate_composite_valid() -> None:
    metrics = {**BASE, "p2": ("Float", "rate"), "p3": ("Float", "rate")}
    assert clean(run(make_doc(metrics, {"r": g("p2", {"p2": "p3 - price"})}))) == []


def test_quantity_needs_product() -> None:
    doc = make_doc(BASE, {"r": g("volume", {"volume": "fee + other"})})
    assert "PVM_QUANTITY_NEEDS_PRODUCT" in codes(run(doc))


def test_cycle_skips_type_rules() -> None:
    doc = make_doc(
        BASE, {"r": g("total", {"total": "price + other", "other": "total + fee"})}
    )
    assert codes(clean(run(doc))) == {"PVM_CYCLE"}


def test_role_unused_warning() -> None:
    issues = run(make_doc(BASE, {"r": g("total", {"total": "fee + other"})}))
    unused = [i for i in issues if i.code == "PVM_ROLE_UNUSED"]
    assert {i.severity for i in unused} == {"warning"}
    assert len(unused) == 2


def test_role_redundant_warning() -> None:
    doc = make_doc(
        BASE, {"r": g("total", {"total": "price * volume"}, roles={"price": "rate"})}
    )
    issues = run(doc)
    assert codes(issues) == {"PVM_ROLE_REDUNDANT"}
    assert issues[0].severity == "warning"


def test_rec_suffix_warning() -> None:
    metrics = {**BASE, "x_rec": ("Float", None)}
    issues = run(make_doc(metrics, {"r": g("total", {"total": "x_rec + fee"})}))
    assert {i.code for i in issues if i.severity == "warning"} >= {"PVM_REC_SUFFIX"}


@pytest.mark.parametrize("datatype", [None, "String"])
def test_bad_datatype_warning(datatype: str | None) -> None:
    metrics = {**BASE, "fee": (datatype, None)}
    issues = run(make_doc(metrics, {"r": g("total", {"total": "fee + other"})}))
    assert "PVM_BAD_DATATYPE" in codes(issues)


def test_numeric_datatypes_case_insensitive() -> None:
    metrics = {**BASE, "fee": ("integer", None), "other": ("DECIMAL", None)}
    assert "PVM_BAD_DATATYPE" not in codes(
        run(make_doc(metrics, {"r": g("total", {"total": "fee + other"})}))
    )
