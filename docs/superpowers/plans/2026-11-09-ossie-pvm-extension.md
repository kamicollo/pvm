# PVM Ossie Vendor Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a validator (library + CLI) for the `PVM` Ossie vendor extension and update the Ossie datasets to carry graphs.

**Architecture:** New Ibis-free package `src/pvm/ossie/`, layered: parse → Ossie SDK/minimal structure check → payload syntax (pydantic + expression parser) → reference/structure/type rules. Every layer collects all its issues; later layers are skipped if an earlier one has errors. Dataset YAMLs are hand-edited (no generator exists; verified by grep).

**Tech Stack:** Python ≥3.12, pydantic, pyyaml, apache-ossie (optional), pytest, ruff/mypy/ty.

**Spec:** `docs/ossie-pvm-extension.md`

## Global Constraints

- Vendor name is `PVM` (exact, case-sensitive); at most one per object.
- Payload: `yaml.safe_load` (JSON accepted); `version: 1` only; unknown keys rejected.
- Roles: `measure` (default), `rate`, `quantity`. Effective role = graph `roles` override → metric default → `measure`.
- Grammar: `expression := term (("+"|"-") term)*`, `term := ["-"] name ["*" name]`, `name := [A-Za-z_][A-Za-z0-9_]*`. No parentheses/division/literals.
- Dependencies: `pydantic`, `pyyaml` go in optional extra `pvm[ossie]`; `apache-ossie` stays in dependency group `ossie`. `pvm.ossie` must not import Ibis.
- Public API: `validate_document(source: str | Path | Mapping[str, Any]) -> ValidationReport`; `Issue(code, severity: Literal["error","warning"], path, message)` frozen dataclass; `ValidationReport(issues: list[Issue])` frozen, with `.ok` and `.raise_for_errors()`.
- CLI: `python -m pvm.ossie validate FILE [FILE ...]`, exit 1 on any error.
- Code is fully typed; `make lint` and `make test` must pass after each task. No `reconcile`/`method` in schema.

## Review Focus

- Empty file / non-mapping top-level YAML (e.g. a list) → error report, no traceback.
- `custom_extensions` present but `null`, or `data` missing/non-string → issue, no crash.
- Self-referencing component (`a: a + b`) → `PVM_CYCLE`, not recursion error.
- Root is a leaf (no `components`) and `graphs: {}` / graph without `components` → valid.
- Metric name defined at both model and dataset level (ambiguity), and a name used only in expressions but missing from metrics.
- Same name repeated across terms with opposite sign (`a - a`) → duplicate-name error.
- Nonexistent file passed to CLI → exit 1 with message, not traceback.

---

### Task 1: Package skeleton, models, extraction, report types

**Files:**
- Create: `src/pvm/ossie/__init__.py`, `models.py`, `extract.py`, `report.py`
- Modify: `pyproject.toml` (add `pydantic>=2`, `pyyaml>=6` to new `[project.optional-dependencies] ossie`; also add to `[dependency-groups] ossie` so the default dev env has them)
- Test: `tests/test_ossie/test_extract.py`

**Interfaces:**
- Produces (`report.py`): `Issue`, `ValidationReport` per Global Constraints (`raise_for_errors` raises `ValueError` listing error issues).
- Produces (`models.py`): `NodeRole(StrEnum)` {measure, rate, quantity}; `MetricExtension(version: int, role: NodeRole = measure)`; `Graph(root: str, roles: dict[str, NodeRole] = {}, components: dict[str, str] = {})`; `GraphsExtension(version: int, graphs: dict[str, Graph])`. All `extra="forbid"`; version checked by `SUPPORTED_VERSIONS = {1}` in the validate layer (code `PVM_UNKNOWN_VERSION`).
- Produces (`extract.py`): `find_pvm_extension(obj: Mapping[str, Any], path: str, issues: list[Issue]) -> Any | None` — returns the parsed payload (`yaml.safe_load` of `data`) for the single `PVM` entry in `obj["custom_extensions"]`, else `None`; appends `PVM_BAD_YAML` (parse failure / non-mapping payload / missing `data`) and `PVM_DUPLICATE_EXTENSION` issues.

- [ ] **Step 1: Write failing tests** — `test_yaml_payload`, `test_json_payload` (JSON string parses to same dict), `test_no_pvm_extension_returns_none` (other vendor ignored; `custom_extensions: null` ok), `test_bad_yaml_issue` (`PVM_BAD_YAML`), `test_non_mapping_payload_issue`, `test_duplicate_pvm_extension_issue` (`PVM_DUPLICATE_EXTENSION`), `test_report_ok_and_raise` (warning-only report is `ok`; error report raises `ValueError`).
- [ ] **Step 2:** Run `pytest tests/test_ossie/test_extract.py -v` → FAIL (import error).
- [ ] **Step 3:** Implement the modules above.
- [ ] **Step 4:** Run tests → PASS; `make lint`.
- [ ] **Step 5:** Commit `feat(ossie): extension models and extraction`.

### Task 2: Operand expression parser

**Files:**
- Create: `src/pvm/ossie/expr.py`
- Test: `tests/test_ossie/test_expr.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) Term(names: tuple[str, ...], negated: bool)` with `is_product` property (`len(names) == 2`); `class ExprError(ValueError)`; `parse_expression(text: str) -> list[Term]`.

- [ ] **Step 1: Write failing tests** — parametrised: `"a"` → one single; `"a * b"` product; `"a - b"` → `[a, -b]`; `"-a + b"` → `[-a, b]`; `"a*b + c - d*e"` → 3 terms, 2 products. Errors (`ExprError`): `""`, `"a +"`, `"(a)"`, `"a / b"`, `"a * b * c"`, `"2 * a"`, `"a b"`, `"a-b.c"`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `parse_expression` with a small regex tokenizer and recursive descent over the grammar (no python-pest).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(ossie): operand expression parser`.

### Task 3: Metric index and reference resolution

**Files:**
- Create: `src/pvm/ossie/refs.py`
- Test: `tests/test_ossie/test_refs.py`

**Interfaces:**
- Consumes: `find_pvm_extension`, `MetricExtension`, `Issue`.
- Produces: `@dataclass(frozen=True) MetricInfo(name: str, datatype: str | None, location: str, default_role: NodeRole | None)`; `build_metric_index(doc: Mapping[str, Any], issues: list[Issue]) -> dict[str, list[MetricInfo]]` — collects document-level `metrics` and each `datasets[i].metrics`, validating each metric's PVM extension against `MetricExtension` (`PVM_BAD_EXTENSION` for pydantic errors, `PVM_UNKNOWN_VERSION`, `PVM_UNKNOWN_ROLE`); `resolve(index, name, path, issues) -> MetricInfo | None` emitting `PVM_UNRESOLVED_NAME` / `PVM_AMBIGUOUS_REF`.

- [ ] **Step 1: Write failing tests** — index collects model + dataset metrics; same name in two places → `PVM_AMBIGUOUS_REF`; missing → `PVM_UNRESOLVED_NAME`; bad role string → `PVM_UNKNOWN_ROLE`; `datasets` missing/`null` tolerated.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(ossie): metric index and reference resolution`.

### Task 4: Graph validation rules

**Files:**
- Create: `src/pvm/ossie/validate.py` (graph part)
- Test: `tests/test_ossie/test_graph_rules.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: `validate_graphs(doc: Mapping[str, Any], index: dict[str, list[MetricInfo]], issues: list[Issue]) -> None`. Issue paths follow spec style, e.g. `custom_extensions[PVM].graphs.revenue.components.avg_price`.

Error codes (exact): `PVM_UNKNOWN_VERSION`, `PVM_BAD_EXTENSION`, `PVM_BAD_EXPRESSION`, `PVM_INVALID_NODE_NAME`, `PVM_UNRESOLVED_NAME`, `PVM_AMBIGUOUS_REF`, `PVM_ROLE_KEY_NOT_NODE`, `PVM_CYCLE`, `PVM_UNREACHABLE`, `PVM_DUPLICATE_NAME`, `PVM_BAD_PRODUCT`, `PVM_MEASURE_BAD_SINGLE`, `PVM_RATE_MIXED`, `PVM_RATE_BAD_SINGLE`, `PVM_QUANTITY_NEEDS_PRODUCT`.
Warning codes: `PVM_ROLE_UNUSED`, `PVM_ROLE_REDUNDANT`, `PVM_REC_SUFFIX`, `PVM_BAD_DATATYPE`.

- [ ] **Step 1: Write failing tests** — a `make_doc(metrics: dict[str, tuple[str | None, str | None]], graphs: dict[str, Any])` helper (name → (datatype, role)); one test per code above (spec "Tests" list), plus: same metric valid as `quantity` in one graph and `measure` via `roles` in another; shared node (DAG) valid; self-reference → `PVM_CYCLE`; `a - a` → `PVM_DUPLICATE_NAME`; root-only graph valid; each warning. Assert on `{i.code for i in report.issues}` and severity.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement per spec "Validation rules". Per graph: parse expressions → resolve names → `roles` keys → effective roles → cycle detection (iterative DFS) → reachability from root → per-parent type rules (measure: ≤1 product, singles all measure; rate: exactly one product alone, or ≥1 singles all rate; quantity: exactly one product alone; product = one rate + one quantity). Skip type rules for a graph with cycles or unresolved names. Warnings after all graphs.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(ossie): graph validation rules`.

### Task 5: `validate_document` and public API

**Files:**
- Modify: `src/pvm/ossie/validate.py`, `src/pvm/ossie/__init__.py` (export `validate_document`, `Issue`, `ValidationReport`)
- Test: `tests/test_ossie/test_validate_document.py`

**Interfaces:**
- Produces: `validate_document(source: str | Path | Mapping[str, Any]) -> ValidationReport`. `Path` is read; a `str` naming an existing file is read, otherwise treated as YAML text. Codes: `PVM_BAD_YAML` (unparsable/non-mapping top level), `OSSIE_INVALID` (SDK failure), `PVM_BAD_STRUCTURE` (minimal check: `datasets`, `metrics`, `custom_extensions` have the right types), warning `OSSIE_SDK_SKIPPED` when `apache-ossie` is not importable.

- [ ] **Step 1: Write failing tests** — dict, YAML string and `Path` inputs agree; empty file and list top-level → error report; `datasets` of wrong type → `PVM_BAD_STRUCTURE`; SDK missing (monkeypatched import failure) → `OSSIE_SDK_SKIPPED` warning and PVM payloads still validated; layer skipping (error in layer 2/3 suppresses layer 4 issues).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement layers 1–4 (inspect the installed `apache-ossie` package for the `OssieDocument` import path first).
- [ ] **Step 4:** Run → PASS; `make lint`.
- [ ] **Step 5:** Commit `feat(ossie): validate_document`.

### Task 6: CLI

**Files:**
- Create: `src/pvm/ossie/__main__.py`
- Test: `tests/test_ossie/test_cli.py`

**Interfaces:**
- Produces: `main(argv: Sequence[str] | None = None) -> int`, subcommand `validate FILE...`; prints `FILE: severity CODE at ISSUE_PATH: message` per issue; returns 1 if any file has errors or cannot be read, else 0.

- [ ] **Step 1: Write failing tests** — call `main` directly: valid file → 0; cycle file → 1 with `PVM_CYCLE` in output; warning-only → 0; nonexistent file → 1 (no exception); one bad among several → 1. One subprocess test of `python -m pvm.ossie validate <file>`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement with `argparse`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(ossie): validate CLI`.

### Task 7: Dataset updates

**Files:**
- Modify: `src/datasets/ossie/mini_fx.yaml`, `src/datasets/ossie/fake_sales.yaml` (`olist.yaml` untouched)
- Test: `tests/test_ossie/test_datasets.py`

**Interfaces:**
- Consumes: `validate_document`.

- [ ] **Step 1: Write failing test** — parametrised over `src/datasets/ossie/*.yaml`: `validate_document(path).ok`; for `mini_fx`/`fake_sales`, assert the PVM payload declares graphs `{revenue}` / `{revenue, cost, profit}` and the report has no warnings.
- [ ] **Step 2:** Run → FAIL (graph assertions).
- [ ] **Step 3:** Edit `mini_fx.yaml`: `total_volume` role `quantity`; add `avg_price_in_lc`, `avg_fx_rate`, `avg_price` (rate, spec expressions); document-level `custom_extensions` with the `revenue` graph. Edit `fake_sales.yaml`: add `avg_price_in_lc`, `avg_fx_rate`, `avg_unit_cost`, `avg_cost_in_lc`, `avg_cost_fx_rate` (rates, volume-weighted, built from the file's fields), `total_flat_fee` (`SUM(flat_fee)`); `quantity` on `total_volume`, `rate` on `avg_price` and the `avg_*` metrics; add the three spec graphs. All `datatype`s numeric. Metric extensions use `data: |` with `version: 1` / `role: ...`.
- [ ] **Step 4:** Run tests → PASS; `python -m pvm.ossie validate src/datasets/ossie/*.yaml` exits 0; `make test` passes (anything loading these YAMLs must tolerate `custom_extensions`).
- [ ] **Step 5:** Commit `feat(datasets): add PVM graphs to ossie datasets`.

### Task 8: Docs and final check

**Files:**
- Modify: `docs/ossie-pvm-extension.md` (status `draft` → `implemented`), `README.md` (short note: `pip install pvm[ossie]`, CLI usage)

- [ ] **Step 1:** Add docs.
- [ ] **Step 2:** Run `make lint && make test_cov`; confirm every error code is exercised.
- [ ] **Step 3:** Commit `docs: ossie extension usage`.

---

## Self-Review

- Spec coverage: format/models (T1), grammar (T2), references/ambiguity/invalid names (T3–T4), all rules and warnings (T4), layers and SDK fallback (T5), CLI (T6), datasets and olist-stays-valid (T7), dependencies (T1), spec test list (T2–T7).
- Spec open questions (sign semantics, name mapping) belong to the out-of-scope loader.
- `PVM_INVALID_NODE_NAME` fires when a key or expression name used as a node fails the name grammar.
