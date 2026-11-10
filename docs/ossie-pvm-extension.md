# Spec: PVM vendor extension for Ossie

Status: draft. Implements Phase 1 of [ossie-integration.md](ossie-integration.md)
(Option 1: Ossie is the semantic model, PVM graph is a vendor extension).

## Scope

In scope:

1. The format of the `PVM` vendor extension (tree structure and node types only).
2. A validator for that extension (and the document it lives in).
3. Updating the Ossie datasets in `src/datasets/ossie/` to carry graphs.

Out of scope (later phases):

- Loading Ossie documents into the `pvm` API and compiling to Ibis.
- Dataset binding, joins, expression parsing.
- Export from `pvm` objects to Ossie.

### Deliberately **not** in the schema

`reconcile` flags and the calculation `method` (CLASSIC etc.) are
calculation-time properties. They belong to the API call, not to the persisted
model. Reconciliation nodes are injected into the graph by PVM when needed and
are not declared. The schema only describes **what role each node plays** and
**how nodes combine** (DAG structure and operands).

## Design decisions

| Topic | Decision |
|---|---|
| Placement | Hybrid: a per-metric extension carries a default `role`; one document-level extension carries graphs and per-graph role overrides. |
| Roles | `rate`, `quantity`, `measure`. A metric with no role is a `measure`. |
| Role is per graph | The same metric can play different roles in different graphs (e.g. `total_volume` is a `quantity` in a revenue graph, a `measure` in its own). Effective role = graph override, else metric default, else `measure`. |
| Payload encoding | YAML in a block scalar (`data: \|`). The parser uses `yaml.safe_load`, so JSON payloads are also accepted (JSON is YAML). |
| Node references | Ossie metric names only. A name used in a graph must identify exactly one metric in the model. |
| Structure | Per-graph map of `parent: operand expression`. Shared nodes allowed (DAG), cycles rejected. |
| Operands | Explicit expression per parent using `+`, `-`, `*` (see grammar). |
| Metrics | Every node must be backed by an Ossie metric (with its own expression). |
| Versioning | `version` inside each payload; the validator rejects unknown versions. |

Ossie's `custom_extensions[].data` is an opaque string, so Ossie itself sees no
structure. All validation of the payload is PVM's responsibility.
`custom_extensions` is accepted on the document, datasets, fields, metrics and
relationships, so the hybrid placement is permitted by Ossie.

## Format

The vendor name is `PVM` (exact, case-sensitive). At most one `PVM` extension
per object.

### Metric-level extension: default role (optional)

```yaml
metrics:
- name: avg_price
  expression:
    sql: SUM(volume * price) / SUM(volume)
  datatype: Float
  custom_extensions:
  - vendor_name: PVM
    data: |
      version: 1
      role: rate
```

`role` is the role the metric plays unless a graph says otherwise. Omit the
extension entirely for plain measures.

| role | Meaning | PVM class |
|---|---|---|
| `measure` (default) | Additive measure that can decompose | `Measure` |
| `rate` | Per-unit value (price, FX rate, ...) | `RateMeasure` |
| `quantity` | Volume-like value | `QuantityMeasure` |

`measure` is a valid value so that a graph can override a metric's default
`rate`/`quantity` back to a measure.

### Document-level extension: graphs

```yaml
custom_extensions:
- vendor_name: PVM
  data: |
    version: 1
    graphs:
      revenue:
        root: total_revenue
        components:
          total_revenue: avg_price * total_volume + total_flat_fee
          avg_price: avg_price_in_lc + avg_fx_rate
      volume:
        root: total_volume
        roles:
          total_volume: measure   # quantity by default, measure here
        components:
          total_volume: volume_east + volume_west
      profit:
        root: total_profit
        components:
          total_profit: total_revenue - total_cost
```

- `graphs` is a map; the key is the graph name (unique by construction).
- `root` is a metric name; any role is allowed.
- `roles` (optional) maps a node to a role, overriding the metric's default
  for this graph only. Keys must be nodes of the graph. Within one graph a
  node has exactly one role, even when shared by several parents.
- `components` maps a parent to the expression that combines its children.
  Leaves are implicit: any name that never appears as a key is a leaf.
- The node set of a graph is `root` plus every key and every name used in an
  expression.

Why a map and not a nested tree: a node can be shared by several parents (for
example `total_volume` under both revenue and cost). Nesting would duplicate
the node and nothing would tie the copies together.

### Operand expressions

```text
expression := term (("+" | "-") term)*
term       := ["-"] name ["*" name]
name       := [A-Za-z_][A-Za-z0-9_]*
```

- No parentheses, division or numeric literals.
- A term with `*` is a **product** and must be exactly one `rate` times one
  `quantity` (either order).
- A term without `*` is a **single**.
- `-` negates a term. `a - b` means `a + (-b)`: the loader negates the
  child's value and effects.
- For rate parents, `+` follows PVM's composite semantics: the child rates'
  effects add up, even where the rate values themselves do not.

Names must follow the `name` grammar to be usable in expressions; a metric that
does not (spaces, dots, ...) cannot be a node (`PVM_INVALID_NODE_NAME`).

### References

A reference is an Ossie metric name, with no dataset qualifier. Resolution
looks at all model-scoped and dataset-scoped metrics; a name that matches more
than one is an error (`PVM_AMBIGUOUS_REF`), and the metric must be renamed.

## Validation rules

Rules mirror the checks in `src/pvm/measures/measures.py`, so a document that
passes validation can always be turned into valid measure objects later.

Extension syntax:

- Payload parses as YAML and is a mapping. At most one `PVM` extension per
  object. `version` is present and supported.
- Payload matches the pydantic model (unknown keys rejected, `role` is a known
  enum value).
- Every expression parses against the grammar above.

References:

- Every name resolves to exactly one metric.
- Every key in `roles` is a node of that graph.
- All type rules below apply to **effective** roles, per graph.

Structure:

- The graph is acyclic.
- Every node is reachable from `root`; every key in `components` is a node
  reachable from `root`.
- A name appears at most once in one parent's expression.

Type constraints (for a parent with effective role R):

- `measure`: at most one product, any number of singles; all singles are
  `measure`.
- `rate`: either exactly one product and nothing else, or one or more singles
  that are all `rate` (composite rate).
- `quantity`: exactly one product and nothing else.
- A product has exactly one `rate` and one `quantity` operand.
- Leaves of any role are allowed (the metric expression is their definition).

Warnings (do not fail validation):

- A metric has a PVM `role` but is not part of any graph.
- A `roles` override equals the metric's default (redundant).
- A node name ends in `_rec`, which PVM uses for injected reconciliation
  nodes.
- A metric used in a graph has no `datatype`, or a non-numeric one.

Cross-document checks that need the semantic model (e.g. a `rate` metric
expression actually being a ratio) are not attempted.

## Validator

New package `src/pvm/ossie/` with no dependency on Ibis:

```text
pvm/ossie/
  __init__.py    public API
  models.py      pydantic models: MetricExtension, GraphsExtension, Graph, NodeRole
  extract.py     locate the PVM extension(s), safe_load payloads
  refs.py        metric index and name resolution
  expr.py        parser for operand expressions
  validate.py    rules above, returns ValidationReport
  __main__.py    CLI
```

Public API:

```python
def validate_document(source: str | Path | Mapping[str, Any]) -> ValidationReport: ...

@dataclass(frozen=True)
class Issue:
    code: str         # e.g. "PVM_CYCLE"
    severity: Literal["error", "warning"]
    path: str         # e.g. "custom_extensions[PVM].graphs.revenue.components.avg_price"
    message: str

@dataclass(frozen=True)
class ValidationReport:
    issues: list[Issue]
    @property
    def ok(self) -> bool: ...
    def raise_for_errors(self) -> None: ...
```

Layers, in order; later layers are skipped if an earlier one fails:

1. Parse YAML/JSON.
2. Validate the Ossie document with the `apache-ossie` SDK
   (`OssieDocument`), if installed. If it is not installed, run only a
   minimal structural check of what PVM needs (`datasets`, `metrics`,
   `custom_extensions`) and report a warning that full Ossie validation was
   skipped.
3. Parse and validate the PVM payloads (syntax rules).
4. Resolve references and check structure/type rules.

Collect all issues in a layer rather than stopping at the first.

CLI:

```text
python -m pvm.ossie validate FILE [FILE ...]   # exit 1 on any error
```

Dependencies: `pydantic` and `pyyaml` become dependencies of an `ossie`
optional extra (`pvm[ossie]`); the `apache-ossie` SDK stays in the existing
`ossie` dependency group.

## Dataset updates

Ossie metrics cannot reference other metrics, so each node needs a standalone
expression. Where a node is a ratio, its expression is the volume-weighted
aggregate.

### `mini_fx.yaml`

Keep `total_volume` and `total_revenue`; add rate metrics. Default roles are
set only where they are not `measure`:

| metric | expression | default role |
|---|---|---|
| `total_volume` | `SUM(volume)` | quantity |
| `avg_price_in_lc` | `SUM(volume * price_in_lc) / SUM(volume)` | rate |
| `avg_fx_rate` | `SUM(volume * price) / SUM(volume * price_in_lc)` | rate |
| `avg_price` | `SUM(volume * price) / SUM(volume)` | rate |
| `total_revenue` | `SUM(revenue)` | (measure) |

```yaml
graphs:
  revenue:
    root: total_revenue
    components:
      total_revenue: avg_price * total_volume
      avg_price: avg_price_in_lc + avg_fx_rate
```

### `fake_sales.yaml`

`total_volume`, `total_revenue`, `total_cost`, `total_profit` and `avg_price`
already exist. Add `avg_price_in_lc`, `avg_fx_rate`, `avg_unit_cost`,
`avg_cost_in_lc`, `avg_cost_fx_rate` and `total_flat_fee`, with default roles
(`rate` for the `avg_*` metrics, `quantity` for `total_volume`), and these
graphs. Costs stay positive; subtraction is expressed with `-`.

```yaml
graphs:
  revenue:
    root: total_revenue
    components:
      total_revenue: avg_price * total_volume + total_flat_fee
      avg_price: avg_price_in_lc + avg_fx_rate
  cost:
    root: total_cost
    components:
      total_cost: avg_unit_cost * total_volume
      avg_unit_cost: avg_cost_in_lc + avg_cost_fx_rate
  profit:
    root: total_profit
    components:
      total_profit: total_revenue - total_cost
      total_revenue: avg_price * total_volume + total_flat_fee
      total_cost: avg_unit_cost * total_volume
      avg_price: avg_price_in_lc + avg_fx_rate
      avg_unit_cost: avg_cost_in_lc + avg_cost_fx_rate
```

`total_volume` is shared by the revenue and cost branches of `profit`. The
exact `fx` rate expressions follow the field definitions in the file.

`olist.yaml` is left unchanged for now.

Both files are plain Ossie documents; non-PVM tools ignore the extension.
Check whether a generator produces these files before hand-editing.

## Tests

- Valid: every file in `src/datasets/ossie/` produces no errors (parametrised,
  so `olist.yaml` is also checked and stays valid without graphs).
- One case per error code: bad YAML, unknown version, unknown role, bad
  expression syntax, unresolved name, ambiguous name, invalid node name,
  `roles` key not in graph, cycle, unreachable node, duplicate name in an
  expression, product without exactly one rate and one quantity, measure
  parent with a rate/quantity single, rate parent mixing product and singles,
  composite with a non-rate single, quantity parent without a product.
- Same metric valid under different roles in two graphs.
- Negated terms (`a - b`, `-a + b`) parse.
- JSON payload accepted.
- CLI exit codes.

## Open questions

1. **Sign semantics in the loader.** `-` implies negating a child's value and
   effects when building PVM measures (which only sum). The loader (out of
   scope) must define this precisely, including for negated products.
2. **Name mapping.** PVM looks up columns by measure name; the loader (out of
   scope) decides how metric names map to the API. The schema uses only Ossie
   metric names.
