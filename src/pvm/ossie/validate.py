"""Graph validation rules for the PVM vendor extension.

Implements the "References", "Structure", "Type constraints" and warning
rules of docs/ossie-pvm-extension.md for the document-level ``graphs``
extension.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from pvm.ossie.expr import ExprError, Term, parse_expression
from pvm.ossie.extract import find_pvm_extension
from pvm.ossie.models import SUPPORTED_VERSIONS, Graph, GraphsExtension, NodeRole
from pvm.ossie.refs import MetricInfo, resolve
from pvm.ossie.report import Issue

_EXT_PATH = "custom_extensions[PVM]"
_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMERIC_TYPES = frozenset(
    {"integer", "float", "decimal", "number", "double", "long", "int", "bigint", "numeric"},
)
_REC_SUFFIX = "_rec"


def _error(code: str, path: str, message: str) -> Issue:
    return Issue(code=code, severity="error", path=path, message=message)


def _warning(code: str, path: str, message: str) -> Issue:
    return Issue(code=code, severity="warning", path=path, message=message)


@dataclass
class _GraphState:
    """Working data for validating one graph."""

    name: str
    graph: Graph
    path: str
    terms: dict[str, list[Term]] = field(default_factory=dict)
    node_paths: dict[str, str] = field(default_factory=dict)
    infos: dict[str, MetricInfo] = field(default_factory=dict)
    parse_failed: bool = False
    unresolved: bool = False

    def children(self, node: str) -> list[str]:
        return [name for term in self.terms.get(node, []) for name in term.names]


def _is_role_error(error: ValidationError) -> bool:
    """Whether every problem is an invalid role enum value inside a graph's `roles`."""
    return all(e["type"] == "enum" and len(e["loc"]) == 4 and e["loc"][2] == "roles" for e in error.errors())  # noqa: PLR2004


def _load_extension(payload: Any, issues: list[Issue]) -> GraphsExtension | None:  # noqa: ANN401
    try:
        extension = GraphsExtension.model_validate(payload)
    except ValidationError as exc:
        code = "PVM_UNKNOWN_ROLE" if _is_role_error(exc) else "PVM_BAD_EXTENSION"
        issues.append(_error(code, _EXT_PATH, f"invalid PVM graphs extension: {exc}"))
        return None
    if extension.version not in SUPPORTED_VERSIONS:
        issues.append(
            _error("PVM_UNKNOWN_VERSION", _EXT_PATH, f"unsupported PVM extension version {extension.version!r}")
        )
        return None
    return extension


def _check_name(name: str, path: str, issues: list[Issue]) -> bool:
    if _NAME_RE.fullmatch(name):
        return True
    issues.append(_error("PVM_INVALID_NODE_NAME", path, f"{name!r} is not a valid node name"))
    return False


def _expr_error_code(text: str, index: Mapping[str, list[MetricInfo]]) -> str:
    """Blame an invalid metric name (rather than syntax) when one appears in the text."""
    if any(not _NAME_RE.fullmatch(name) and name in text for name in index):
        return "PVM_INVALID_NODE_NAME"
    return "PVM_BAD_EXPRESSION"


def _parse_components(state: _GraphState, index: Mapping[str, list[MetricInfo]], issues: list[Issue]) -> None:
    root_path = f"{state.path}.root"
    state.node_paths[state.graph.root] = root_path
    if not _check_name(state.graph.root, root_path, issues):
        state.parse_failed = True
    for key, text in state.graph.components.items():
        path = f"{state.path}.components.{key}"
        state.node_paths.setdefault(key, path)
        if not _check_name(key, path, issues):
            state.parse_failed = True
            continue
        try:
            state.terms[key] = parse_expression(text)
        except ExprError as exc:
            state.parse_failed = True
            issues.append(_error(_expr_error_code(text, index), path, str(exc)))
            continue
        for name in state.children(key):
            state.node_paths.setdefault(name, path)


def _resolve_nodes(state: _GraphState, index: Mapping[str, list[MetricInfo]], issues: list[Issue]) -> None:
    for node, path in state.node_paths.items():
        if not _NAME_RE.fullmatch(node):
            continue
        info = resolve(index, node, path, issues)
        if info is None:
            state.unresolved = True
        else:
            state.infos[node] = info


def _check_role_keys(state: _GraphState, issues: list[Issue]) -> None:
    for key in state.graph.roles:
        path = f"{state.path}.roles.{key}"
        if not _check_name(key, path, issues):
            continue
        if key not in state.node_paths:
            issues.append(_error("PVM_ROLE_KEY_NOT_NODE", path, f"{key!r} is not a node of graph {state.name!r}"))


def _check_duplicates(state: _GraphState, issues: list[Issue]) -> None:
    for key in state.terms:
        names = state.children(key)
        for dup in sorted({n for n in names if names.count(n) > 1}):
            path = f"{state.path}.components.{key}"
            issues.append(
                _error("PVM_DUPLICATE_NAME", path, f"{dup!r} appears more than once in the expression of {key!r}")
            )


def _find_cycle(state: _GraphState) -> bool:
    """Return whether the components graph has a cycle (iterative DFS)."""
    done: set[str] = set()
    for start in state.terms:
        if start in done:
            continue
        on_path = {start}
        stack = [(start, iter(state.children(start)))]
        while stack:
            node, it = stack[-1]
            child = next(it, None)
            if child is None:
                stack.pop()
                on_path.discard(node)
                done.add(node)
            elif child in on_path:
                return True
            elif child not in done and child in state.terms:
                on_path.add(child)
                stack.append((child, iter(state.children(child))))
    return False


def _reachable(state: _GraphState) -> set[str]:
    seen = {state.graph.root}
    todo = [state.graph.root]
    while todo:
        for child in state.children(todo.pop()):
            if child not in seen:
                seen.add(child)
                todo.append(child)
    return seen


def _check_reachability(state: _GraphState, issues: list[Issue]) -> None:
    reachable = _reachable(state)
    for node, path in state.node_paths.items():
        if node not in reachable:
            issues.append(
                _error("PVM_UNREACHABLE", path, f"node {node!r} is not reachable from root {state.graph.root!r}")
            )


def _effective_role(state: _GraphState, node: str) -> NodeRole:
    override = state.graph.roles.get(node)
    if override is not None:
        return override
    return state.infos[node].default_role or NodeRole.measure


def _check_product(state: _GraphState, term: Term, path: str, issues: list[Issue]) -> None:
    roles = sorted(_effective_role(state, n).value for n in term.names)
    if roles != [NodeRole.quantity.value, NodeRole.rate.value]:
        msg = f"product {' * '.join(term.names)} must be one rate times one quantity, got {roles}"
        issues.append(_error("PVM_BAD_PRODUCT", path, msg))


def _check_measure_parent(
    state: _GraphState, singles: list[Term], products: list[Term], path: str, issues: list[Issue]
) -> None:
    if len(products) > 1:
        issues.append(_error("PVM_BAD_PRODUCT", path, "a measure parent allows at most one product"))
    for term in singles:
        role = _effective_role(state, term.names[0])
        if role is not NodeRole.measure:
            issues.append(
                _error("PVM_MEASURE_BAD_SINGLE", path, f"{term.names[0]!r} is a {role.value}, expected a measure")
            )


def _check_rate_parent(
    state: _GraphState, singles: list[Term], products: list[Term], path: str, issues: list[Issue]
) -> None:
    if products and (singles or len(products) > 1):
        issues.append(_error("PVM_RATE_MIXED", path, "a rate parent is either one product or only rate singles"))
        return
    for term in singles:
        role = _effective_role(state, term.names[0])
        if role is not NodeRole.rate:
            issues.append(_error("PVM_RATE_BAD_SINGLE", path, f"{term.names[0]!r} is a {role.value}, expected a rate"))


def _check_types(state: _GraphState, issues: list[Issue]) -> None:
    for key, terms in state.terms.items():
        path = f"{state.path}.components.{key}"
        products = [t for t in terms if t.is_product]
        singles = [t for t in terms if not t.is_product]
        for product in products:
            _check_product(state, product, path, issues)
        role = _effective_role(state, key)
        if role is NodeRole.measure:
            _check_measure_parent(state, singles, products, path, issues)
        elif role is NodeRole.rate:
            _check_rate_parent(state, singles, products, path, issues)
        elif singles or len(products) != 1:
            issues.append(_error("PVM_QUANTITY_NEEDS_PRODUCT", path, f"quantity {key!r} must be exactly one product"))


def _graph_warnings(state: _GraphState, issues: list[Issue]) -> None:
    for node, path in state.node_paths.items():
        if node.endswith(_REC_SUFFIX):
            issues.append(
                _warning("PVM_REC_SUFFIX", path, f"node {node!r} ends in {_REC_SUFFIX!r}, reserved for reconciliation")
            )
        info = state.infos.get(node)
        if info is not None and (info.datatype is None or info.datatype.lower() not in _NUMERIC_TYPES):
            issues.append(
                _warning("PVM_BAD_DATATYPE", path, f"metric {node!r} has no numeric datatype ({info.datatype!r})")
            )
    for key, role in state.graph.roles.items():
        info = state.infos.get(key)
        if info is not None and role is (info.default_role or NodeRole.measure):
            issues.append(
                _warning(
                    "PVM_ROLE_REDUNDANT", f"{state.path}.roles.{key}", f"role {role.value!r} equals the metric default"
                )
            )


def _validate_graph(state: _GraphState, index: Mapping[str, list[MetricInfo]], issues: list[Issue]) -> None:
    _parse_components(state, index, issues)
    _resolve_nodes(state, index, issues)
    _check_role_keys(state, issues)
    _check_duplicates(state, issues)
    if _find_cycle(state):
        issues.append(_error("PVM_CYCLE", state.path, f"graph {state.name!r} contains a cycle"))
        return
    if not state.parse_failed:
        _check_reachability(state, issues)
    if not (state.parse_failed or state.unresolved):
        _check_types(state, issues)
    _graph_warnings(state, issues)


def _warn_unused(index: Mapping[str, list[MetricInfo]], used: Iterable[str], issues: list[Issue]) -> None:
    used_names = set(used)
    for name, infos in index.items():
        if name in used_names:
            continue
        issues.extend(
            _warning(
                "PVM_ROLE_UNUSED",
                f"{info.location}.custom_extensions[PVM]",
                f"metric {name!r} has a role but is in no graph",
            )
            for info in infos
            if info.default_role is not None
        )


def validate_graphs(doc: Mapping[str, Any], index: dict[str, list[MetricInfo]], issues: list[Issue]) -> None:
    """Validate the document-level PVM graphs extension, appending to issues."""
    payload = find_pvm_extension(doc, _EXT_PATH, issues)
    used: set[str] = set()
    if payload is not None:
        extension = _load_extension(payload, issues)
        if extension is None:
            return
        for name, graph in extension.graphs.items():
            state = _GraphState(name=name, graph=graph, path=f"{_EXT_PATH}.graphs.{name}")
            _validate_graph(state, index, issues)
            used.update(state.node_paths)
    elif doc.get("custom_extensions") and any(
        isinstance(e, Mapping) and e.get("vendor_name") == "PVM" for e in doc["custom_extensions"]
    ):
        return
    _warn_unused(index, used, issues)
