# Integrating PVM with Apache Ossie

This document sketches ways for PVM to interoperate with
[Apache Ossie](https://github.com/apache/ossie), an emerging standard for
exchanging semantic models.

The proposed direction in this document is **Option 1: use Ossie as the
semantic model and carry the PVM decomposition graph as a PVM extension**.
Ibis is then used as the backend-independent execution and SQL compilation
layer.

The central design distinction is:

- **Ossie describes the semantic model and portable measure definitions.**
- **PVM describes the price-volume decomposition graph.**
- **Ibis is the backend-independent execution target.**

That separation is important because PVM currently stores `ibis.Deferred`
expressions directly in its measure objects, while Ossie stores expressions as
serialized strings. Ibis is an excellent execution abstraction, but it should
not become the persistence format for a semantic model.

## What Ossie provides

The current Ossie draft supports:

- datasets and their sources;
- fields, including row-level expressions;
- dataset-scoped metrics;
- model-scoped metrics;
- relationships between datasets;
- expression dialects;
- vendor-specific `custom_extensions`.

Ossie explicitly separates model declaration from query execution. Its
expression language describes a model rather than executing a query. Ossie also
has a draft [Relational Query Interface](https://github.com/apache/ossie/blob/main/core-spec/relational_semantics.md),
but that is a query semantics specification rather than a mature, general
purpose Ossie-to-Snowflake or Ossie-to-DuckDB execution library. This leaves
room for PVM to consume Ossie definitions and compile them to Ibis.

Useful references:

- [Ossie core specification](https://github.com/apache/ossie/blob/main/core-spec/spec.md)
- [Ossie expression language](https://github.com/apache/ossie/blob/main/core-spec/expression_language.md)
- [Ossie relational query semantics](https://github.com/apache/ossie/blob/main/core-spec/relational_semantics.md)
- [Ossie converters](https://github.com/apache/ossie-converters)
- [Ossie Python SDK](https://github.com/apache/ossie/tree/main/python)

### Extension behavior

Arbitrary unknown properties are not generally safe in an Ossie document. The
core schema uses `additionalProperties: false` at the document level and on
most core objects.

The intended extension mechanism is `custom_extensions`:

```yaml
custom_extensions:
  - vendor_name: PVM
    data: '{"graphs": []}'
```

The `data` value is an opaque JSON string. PVM-specific metadata can therefore
be carried without changing or invalidating the Ossie core schema.

## Proposed approach: Ossie as the semantic model, PVM as an extension

This is likely the most practical initial integration.

Ossie owns:

- datasets;
- source names;
- dimensions and fields;
- metric definitions;
- descriptions and data types.

PVM owns, in a `PVM` custom extension:

- decomposition graphs;
- whether a node is a `Measure`, `RateMeasure`, or `QuantityMeasure`;
- component relationships;
- reconciliation behavior;
- the PVM calculation method;
- PVM-specific effect-calculation metadata.

An illustrative document could look like this:

```yaml
version: 0.2.0.dev0
name: sales_pvm

datasets:
  - name: sales
    source: warehouse.sales
    fields:
      - name: volume
        expression:
          sql: volume
        datatype: Decimal

      - name: unit_price
        expression:
          sql: unit_price
        datatype: Decimal

      - name: price_in_lc
        expression:
          sql: price_in_lc
        datatype: Decimal

      - name: fx_rate
        expression:
          sql: fx_rate
        datatype: Decimal

      - name: revenue
        expression:
          sql: revenue
        datatype: Decimal

    metrics:
      - name: volume
        expression:
          sql: SUM(volume)
        datatype: Decimal

      - name: price_in_lc
        expression:
          sql: SUM(volume * price_in_lc) / SUM(volume)
        datatype: Decimal

      - name: fx_rate
        expression:
          sql: SUM(volume * fx_rate * price_in_lc)
                / SUM(price_in_lc * volume)
        datatype: Decimal

      - name: unit_price
        expression:
          sql: SUM(volume * unit_price) / SUM(volume)
        datatype: Decimal

      - name: revenue
        expression:
          sql: SUM(revenue)
        datatype: Decimal

custom_extensions:
  - vendor_name: PVM
    data: >-
      {
        "graphs": [
          {
            "name": "revenue",
            "root": "revenue",
            "method": "CLASSIC",
            "nodes": [
              {
                "name": "revenue",
                "kind": "measure",
                "reconcile": true,
                "components": ["unit_price", "volume"]
              },
              {
                "name": "unit_price",
                "kind": "rate",
                "components": ["price_in_lc", "fx_rate"]
              },
              {
                "name": "price_in_lc",
                "kind": "quantity",
                "components": []
              },
              {
                "name": "fx_rate",
                "kind": "rate",
                "components": []
              },
              {
                "name": "volume",
                "kind": "quantity",
                "components": []
              }
            ]
          }
        ]
      }
```

The exact PVM extension format is still to be designed, but it should be:

- reference-based, using names rather than deeply nested objects;
- explicitly acyclic;
- explicit about node kind;
- explicit about `reconcile`;
- independent of Ibis;
- versioned inside the extension payload.

### Runtime architecture

The runtime flow should be:

```text
Ossie YAML/JSON
      ↓
Ossie parser and validator
      ↓
PVM graph and semantic model loader
      ↓
Relationship-aware query planner
      ↓
Ibis expression
      ↓
DuckDB / Snowflake / another Ibis backend
```

An adapter would:

1. Load and validate the Ossie document.
2. Bind each Ossie dataset to an Ibis table.
3. Compile field and metric expressions into Ibis expressions.
4. Use relationship metadata to construct joins.
5. Apply filters, dimensions, and grouping.
6. Build the PVM aggregate and effect calculations.
7. Let Ibis generate backend-specific SQL and execute it.

This makes the integration an **Ossie execution adapter backed by Ibis**, not
an Ossie format converter. The Ossie converter ecosystem translates between
semantic model formats such as dbt, Snowflake semantic models, and LookML.
Ibis instead provides a runtime relational expression API and compiler.

### Dataset binding

An Ossie dataset's `source` is a logical or physical source name. It should
not be treated as an Ibis table object. Bind sources explicitly:

```python
model = PvmModel.from_ossie_yaml("sales.yaml")

model.bind_dataset("orders", orders_table)
model.bind_dataset("customers", customers_table)
```

The same Ossie document can then be used with DuckDB, Snowflake, Polars,
SQLite, or another Ibis backend.

### Joins and grouping

Ossie relationships can provide the metadata needed to construct joins:

```yaml
relationships:
  - name: orders_to_customers
    from: orders
    to: customers
    from_columns: [customer_id]
    to_columns: [id]
```

However, a relationship does not by itself determine a complete query plan.
The adapter still needs policies for:

- join type;
- which relationships to traverse;
- filter propagation;
- relationship cardinality;
- metric grain;
- pre-aggregation.

The draft Ossie Relational Query Interface leaves automatic join resolution
outside its scope. The PVM adapter should therefore own this planning logic,
with Ibis as the execution target.

### Grain-aware aggregation

Ibis provides portable relational operations, but it does not automatically
know how to prevent metric fan-out. For example, joining orders to a
many-to-one or many-to-many relation before aggregating revenue can duplicate
order rows.

The adapter may need to construct a plan like:

```text
orders
  → aggregate revenue by region

tickets
  → aggregate ticket count by region

aggregated orders
  → join aggregated tickets
```

rather than:

```text
orders
  → join tickets
  → group by region
  → aggregate everything
```

This is a semantic planning responsibility. Ibis can express either plan and
compile both to DuckDB or Snowflake SQL, but it cannot decide which plan is
correct without metadata from Ossie and PVM.

### Proposed API shape

A future API could look like:

```python
model = PvmModel.from_ossie_yaml("sales.yaml")

model.bind_dataset("orders", orders_table)
model.bind_dataset("customers", customers_table)

query = (
    model.query("revenue")
    .join("orders_to_customers")
    .group_by("region")
)

effects = query.calculate_effects()
```

Internally, this would produce an Ibis expression. The caller would not write
Snowflake- or DuckDB-specific SQL.

### Benefits

- Strong compatibility with Ossie.
- No change to the Ossie core schema.
- PVM graphs can evolve independently.
- Non-PVM tools can still consume the ordinary semantic model.
- The existing Python API can remain available.

### Cost

PVM needs a translation layer from Ossie expressions to Ibis expressions, or it
needs to retain a PVM-native representation of those expressions.

## Alternative 2: A PVM-native expression AST, with Ossie as an export format

This is the cleanest long-term design if PVM needs reliable backend
independence.

Instead of making SQL strings or Ibis expressions canonical, introduce a small
PVM expression intermediate representation:

```python
@dataclass(frozen=True)
class Column:
    name: str


@dataclass(frozen=True)
class Sum:
    expression: Expression


@dataclass(frozen=True)
class Multiply:
    left: Expression
    right: Expression


@dataclass(frozen=True)
class Divide:
    numerator: Expression
    denominator: Expression
```

Then define compilers:

```text
PVM expression AST
        ├──> Ibis compiler
        ├──> Ossie SQL compiler
        └──> optional backend-specific compiler
```

A measure could be represented as:

```python
MeasureDefinition(
    name="price_in_lc",
    expression=Divide(
        numerator=Sum(Multiply(Column("volume"), Column("price_in_lc"))),
        denominator=Sum(Column("volume")),
    ),
)
```

The Ibis compiler would produce an expression equivalent to:

```python
(volume * price_in_lc).sum() / volume.sum()
```

The Ossie compiler would produce:

```sql
SUM(volume * price_in_lc) / SUM(volume)
```

### Benefits

- No SQL parser is required for the main execution path.
- No Ibis objects need to be serialized.
- Backend independence is explicit.
- Ibis and Ossie can be generated from the same expression semantics.
- The supported expression vocabulary can be validated.

### Cost

- PVM must define and maintain an expression language.
- PVM needs an Ossie SQL serializer.
- Existing users who pass arbitrary `ibis.Deferred` expressions need a
  compatibility path.

This is the strongest architecture if PVM is intended to become a reusable
semantic and decomposition engine rather than only a Python API.

## Alternative 3: Ossie SQL as the canonical expression language

In this approach, Ossie expressions are canonical:

```yaml
expression:
  sql: SUM(volume * unit_price) / SUM(volume)
```

PVM translates those expressions into Ibis at load time:

```text
Ossie YAML
   ↓
Ossie validation
   ↓
SQL/expression parser
   ↓
PVM expression tree
   ↓
Ibis expression
   ↓
PVM calculation
```

This gives the best interoperability with Ossie documents produced by other
tools, but it is more difficult than it first appears:

1. Ossie expressions can contain fields, source columns, aggregate functions,
   dialect variants, and syntax that may not be directly representable in Ibis.
2. Ibis does not generally provide a parser for arbitrary SQL into Ibis
   expressions.
3. Ossie's portable SQL dialect and backend SQL dialects are not necessarily
   identical.
4. PVM must resolve Ossie namespaces correctly.

The current Ossie rules distinguish:

- field expressions, which refer to source columns;
- dataset-scoped metrics, which refer to local fields;
- model-scoped metrics, which use qualified `dataset.field` references;
- metrics, which cannot refer to other metrics in the current draft.

A parser-based approach is viable if PVM initially supports a documented
subset, such as:

- column references;
- `SUM`;
- `COUNT`;
- `COUNT DISTINCT`;
- arithmetic;
- `CASE`;
- null handling;
- basic comparisons.

Unsupported expressions should be rejected explicitly rather than silently
falling back to a different interpretation.

## Alternative 4: Keep Ibis expressions and use Ossie as metadata

The smallest change is to keep the current API:

```python
Measure(
    "revenue",
    definition=_.revenue.sum(),
    components=[...],
)
```

PVM could add methods such as:

```python
graph.to_ossie(...)
```

The generated Ossie document would contain semantic names and metadata, while
the actual Ibis expressions would be stored in a PVM extension.

PVM should not serialize Python or Ibis object representations. They are
implementation-specific and unstable across versions. A safer compatibility
API would require a serializable expression alongside the Ibis expression:

```python
Measure(
    "revenue",
    definition=_.revenue.sum(),
    expression="SUM(revenue)",
)
```

### Benefits

- Smallest change to the current package.
- Existing notebook usage remains unchanged.
- No expression parser is required.

### Cost

- Ossie consumers cannot execute the PVM expressions without PVM.
- The semantic document is not self-contained.
- Ibis remains part of the model-authoring contract.

This is best treated as a compatibility mode rather than the final
architecture.

## How Ibis should fit

Ibis should be the execution compiler target.

A useful API could look like:

```python
document = PvmModel.from_ossie_yaml("sales.yaml")

table = ibis.table(
    {
        "volume": "decimal(18, 2)",
        "unit_price": "decimal(18, 2)",
        "revenue": "decimal(18, 2)",
        "period": "string",
        "region": "string",
    },
    name="sales",
)

pvm = (
    document.graph("revenue")
    .bind(table)
    .set_periods(table.period, ["2023", "2024"])
    .set_hierarchy([table.region])
)

effects = pvm.calculate_effects()
```

### Dataset binding

Ossie's `source` is a logical or physical source name. It should not be
assumed to be an Ibis table object.

Use an explicit binding:

```python
bindings = {
    "sales": table,
}
```

or:

```python
model.bind_dataset("sales", table)
```

The same Ossie document can then be used with DuckDB, Snowflake, Polars,
SQLite, or another Ibis backend.

### Expression compilation

Expressions should be compiled against the bound table:

```python
compiled = expression_compiler.compile(
    metric_expression,
    table=table,
)
```

For the current API, deferred expressions can be used:

```python
ibis.deferred.volume.sum()
```

For more reliable compilation, table-bound expressions are preferable:

```python
table.volume.sum()
```

The compiler should resolve names through an explicit catalog rather than
relying on Python attribute lookup.

### Graph construction

The PVM extension should be converted into the existing measure classes:

```text
Measure
RateMeasure
QuantityMeasure
CompositeRateMeasure
```

The graph loader should validate:

- all referenced components exist;
- names are unique;
- there are no cycles;
- rate and quantity constraints are valid;
- each graph has one root;
- executable nodes have expressions;
- reconciliation settings are consistent.

The resulting graph can then be passed to the existing PVM calculation
pipeline.

## Recommended direction

Implement this in phases.

### Phase 1: Add a PVM extension to Ossie

Keep the existing Python API and define a stable serialized graph format:

```text
Ossie document
  ├── datasets
  ├── fields
  ├── metrics
  └── custom_extensions:
        vendor_name: PVM
        data:
          graph definitions
          node kinds
          relationships
          reconciliation flags
```

Initially, require that each graph node also have an Ossie metric definition.
This provides a useful interchange format without forcing an immediate rewrite.

### Phase 2: Add the Ossie-to-Ibis execution adapter

Implement a loader and adapter that:

- parses and validates the Ossie document;
- binds Ossie datasets to Ibis tables;
- resolves fields and metrics against those tables;
- constructs joins from explicitly selected relationships;
- performs grain-aware pre-aggregation where necessary;
- exposes the resulting Ibis expression to the existing PVM pipeline.

The adapter should be an execution integration, not an Ossie format converter.
Ossie converters translate between semantic model formats; Ibis compiles
relational expressions to backend SQL.

### Phase 3: Introduce a PVM expression abstraction

Move conceptually from:

```python
definition: ibis.Deferred | None
```

toward:

```python
definition: Expression | None
```

where `Expression` is preferably a PVM-native expression tree. Compile it to
Ibis only when a graph is bound to a table.

For backward compatibility, continue accepting `ibis.Deferred` as an
explicitly non-serializable expression type.

### Phase 4: Add Ossie import and export

Add APIs such as:

```python
PvmModel.from_ossie(document)
PvmModel.from_ossie_yaml(text)
graph.to_ossie()
graph.to_ossie_yaml()
```

The loader may use the Apache Ossie Python SDK when its API is stable enough,
but PVM should not depend on that SDK for execution. An internal validated
intermediate representation keeps the dependency optional.

### Phase 5: Support broader Ossie expression import

Only after graph interchange works should PVM add an Ossie SQL-to-PVM compiler.
Start with a documented subset and reject unsupported expressions explicitly.

## Division of responsibility

| Concern | Ossie | PVM | Ibis |
|---|---:|---:|---:|
| Dataset and source metadata | Yes | Consume | Bind |
| Fields and dimensions | Yes | Consume | Compile |
| Ordinary metric definitions | Yes | Consume | Compile |
| PVM graph structure | `PVM` extension | Yes | No |
| Rate and quantity semantics | `PVM` extension | Yes | No |
| Reconciliation | `PVM` extension | Yes | No |
| Backend-neutral execution | No | Orchestration | Yes |
| Backend SQL generation | No | No | Yes |
| Query execution | No | No | Yes |

## Guiding rule

Never make an `ibis.Deferred` object the canonical representation of a
persisted metric.

Use Ossie expressions or a PVM expression IR for persistence, then compile to
Ibis at execution time.
