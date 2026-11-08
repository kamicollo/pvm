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
model. The schema only describes **what the nodes are** (type) and **how they
decompose** (tree/DAG structure).

## Design decisions

| Topic | Decision |
|---|---|
| Placement | Hybrid: per-metric extension carries a default `kind`; one document-level extension carries graph structure and per-graph kind overrides. |
| Source of truth for `kind` | A metric's role depends on the graph (e.g. `total_volume` is a `quantity` in a revenue graph but a plain `measure` in its own graph). Effective kind = graph override, else the metric's default `kind`. |
| Payload encoding | YAML in a block scalar (`data: \|`). The parser uses `yaml.safe_load`, so JSON payloads are also accepted (JSON is YAML). |
| Node references | Metric name, optionally `dataset.metric`. |
| Structure | Per-graph map of `parent: [children]`. Shared nodes allowed (DAG), cycles rejected. |
| Kinds | `measure`, `rate`, `quantity`, `reconciliation`. Composite rate is inferred. |
| Metrics | Every node must be backed by an Ossie metric (with its own expression). |
| Versioning | `version` inside each payload; the validator rejects unknown versions. |

Ossie's `custom_extensions[].data` is an opaque string, so Ossie itself sees no
structure. All validation of the payload is PVM's responsibility.
`custom_extensions` is accepted on the document, datasets, fields, metrics and
relationships, so the hybrid placement is permitted by Ossie.

## Format

The vendor name is `PVM` (exact, case-sensitive). At most one `PVM` extension
per object.

### Metric-level extension: default node kind (optional)

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
      kind: rate
```

The metric `kind` is the role the metric plays unless a graph says otherwise.
It is optional: a metric whose role differs per graph can omit it, as long as
every graph that uses it assigns a kind (see below).

`kind` is one of:

| kind | Meaning | PVM class |
|---|---|---|
| `measure` | Additive measure that can decompose | `Measure` |
| `rate` | Per-unit value (price, FX rate, ...) | `RateMeasure` |
| `quantity` | Volume-like value | `QuantityMeasure` |
| `reconciliation` | Explicit residual node | `ReconciliationMeasure` |

A rate whose components are all rates is a `CompositeRateMeasure`. That is
inferred from the structure and not declared.

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
          total_revenue: [avg_price, total_volume]
          avg_price: [avg_price_in_lc, avg_fx_rate]
      volume:
        root: total_volume
        kinds:
          total_volume: measure   # quantity by default, measure here
        components:
          total_volume: [volume_east, volume_west]
```

- `graphs` is a map; the key is the graph name (unique by construction).
- `root` references the top-level metric.
- `kinds` (optional) maps a node to a kind, overriding the metric's default
  for this graph only. Keys must be nodes of the graph. Within one graph a
  node has exactly one kind, even when shared by several parents.
- `components` maps a parent to the list of its children. Leaves are
  implicit: any reference that never appears as a key is a leaf. Order of
  children is not significant.
- The node set of a graph is `root` plus every key and every child.

Why a map and not a nested tree: a node can be shared by several parents (for
example `volume` under both `revenue` and `cost`). Nesting would duplicate the
node and nothing would tie the copies together. With the map, a node is named
once and referenced many times.

### References

A reference is `metric` or `dataset.metric`.

- `dataset.metric` resolves to a dataset-scoped metric.
- A bare name resolves to a model-scoped metric, or to a dataset-scoped one if
  that name is unique across the whole model.
- A bare name that matches more than one metric is an error
  (`PVM_AMBIGUOUS_REF`); qualify it.

## Validation rules

Rules mirror the checks in `src/pvm/measures/measures.py`, so a document that
passes validation can always be turned into valid measure objects later.

Extension syntax:

- Payload parses as YAML and is a mapping. At most one `PVM` extension per
  object. `version` is present and supported.
- Payload matches the pydantic model (unknown keys rejected, `kind` is a known
  enum value).

References:

- Every reference resolves to exactly one metric.
- Every node of a graph resolves to a metric (nodes must be backed by a
  metric).
- Every node has an effective kind: a `kinds` override in the graph, else the
  metric's default `kind` (`PVM_MISSING_KIND` otherwise).
- Every key in `kinds` is a node of that graph.
- All type rules below apply to **effective** kinds, per graph.
- `root` has effective kind `measure`.

Structure:

- The graph is acyclic.
- Every node is reachable from `root`.
- A parent lists each child at most once.

Type constraints:

- `measure` with children: may have at most one `rate` child and at most one
  `quantity` child, and they must come as a pair (both or neither); any
  number of other `measure` children (summed) are allowed.
- `rate` and `quantity` nodes cannot have `measure` children.
- A `rate` whose children are all `rate` is composite (at least one child).
  Composite rates cannot have `quantity` or other child kinds.
- `reconciliation` nodes are leaves and may only be children of a `measure`.
- `rate`/`quantity`/`reconciliation` cannot be a graph `root`.
- Leaves of kind `measure` are allowed (the metric expression is their
  definition).

Warnings (do not fail validation):

- A metric has a PVM `kind` but is not part of any graph.
- A `kinds` override equals the metric's default (redundant).
- A metric used in a graph has no `datatype`, or a non-numeric one.

Cross-document checks that need the semantic model (e.g. a `rate` metric
expression actually being a ratio) are not attempted.

## Validator

New package `src/pvm/ossie/` with no dependency on Ibis:

```text
pvm/ossie/
  __init__.py    public API
  models.py      pydantic models: MetricExtension, GraphsExtension, Graph, NodeKind
  extract.py     locate the PVM extension(s), safe_load payloads
  refs.py        metric index and reference resolution
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

Keep `total_volume` and `total_revenue`; add rate metrics and default kinds
(overridden per graph where a metric plays another role):

| metric | expression | default kind |
|---|---|---|
| `total_volume` | `SUM(volume)` | quantity |
| `avg_price_in_lc` | `SUM(volume * price_in_lc) / SUM(volume)` | rate |
| `avg_fx_rate` | `SUM(volume * price) / SUM(volume * price_in_lc)` | rate |
| `avg_price` | `SUM(volume * price) / SUM(volume)` | rate |
| `total_revenue` | `SUM(revenue)` | measure |

```yaml
graphs:
  revenue:
    root: total_revenue
    components:
      total_revenue: [avg_price, total_volume]
      avg_price: [avg_price_in_lc, avg_fx_rate]
```

### `fake_sales.yaml`

`total_volume`, `total_revenue`, `total_cost`, `total_profit` and `avg_price`
already exist. Add `avg_price_in_lc`, `avg_fx_rate`, `avg_unit_cost`,
`avg_cost_in_lc`, `avg_cost_fx_rate` and `total_flat_fee`, with kinds, and two
graphs: `revenue` (price × volume + flat fee, with `total_volume` shared) and
`cost` (unit cost × volume, sharing `total_volume`). The exact shape is taken
from the existing PVM tests and notebooks.

`olist.yaml` is left unchanged for now.

Both files are plain Ossie documents; non-PVM tools ignore the extension.
They need to be regenerated or edited by hand consistently: check whether a
generator produces these files before hand-editing.

## Tests

- Valid: `mini_fx.yaml` and `fake_sales.yaml` produce no errors (parametrised
  over every file in `src/datasets/ossie/`, so `olist.yaml` is also checked
  and stays valid without graphs).
- One case per error code: bad YAML, unknown version, unknown kind, unresolved
  ref, ambiguous ref, missing effective kind, `kinds` key not in graph,
  override changing validity (same metric valid in one graph, invalid in
  another), cycle, unreachable node,
  duplicate child, rate+quantity pairing, rate with measure child, composite
  with a non-rate child, reconciliation not a leaf, non-measure root.
- JSON payload accepted.
- CLI exit codes.

## Open questions

1. **Subtraction.** PVM's `calculated_definition` sums `measure` children, so
   `profit = revenue - cost` cannot be expressed as a graph unless the cost
   node is defined with a negative sign in its metric. The spec has no sign or
   operator; decide whether profit graphs are in scope for `fake_sales`.
2. **Node name vs. column name.** PVM looks up columns by measure name, while
   metric names here differ (`total_revenue` vs. `revenue`). The loader (out
   of scope) will need a name mapping rule; the spec may later need an
   optional `alias`.
3. **Root kind.** Restricting `root` to `measure` is a choice; relax it if
   rate-rooted graphs are needed.
