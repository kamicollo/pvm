import ibis
import ibis.backends
import polars
import pytest
from ibis import deferred
from polars.testing import assert_frame_equal
from pvm.measures import CompositeRateMeasure, Measure, QuantityMeasure, RateMeasure


def test_measure_creation():
    field = Measure(name="test", definition=deferred)
    assert field.name == "test"
    assert field.components == []


def test_measure_without_definition_or_components():
    with pytest.raises(ValueError, match="must have either components or a definition"):
        Measure(name="test")


def test_rate_quantity_combination():
    rate = RateMeasure(name="rate", definition=deferred)
    quantity = QuantityMeasure(name="qty", definition=deferred)
    field = Measure(name="total", components=[rate, quantity])

    assert field.rate == rate
    assert field.quantity == quantity
    assert field.other_components == []


def test_multiple_rate_components():
    with pytest.raises(ValueError, match="multiple rate components"):
        Measure(
            name="test",
            components=[
                RateMeasure(name="rate1", definition=deferred),
                RateMeasure(name="rate2", definition=deferred),
            ],
        )


def test_rate_without_quantity():
    with pytest.raises(ValueError, match="missing a quantity component"):
        Measure(name="test", components=[RateMeasure(name="rate", definition=deferred)])


def test_quantity_without_rate():
    with pytest.raises(ValueError, match="missing a rate component"):
        Measure(
            name="test", components=[QuantityMeasure(name="qty", definition=deferred)]
        )


def test_reconciliation_measure():
    rate = RateMeasure(name="rate", definition=deferred)
    quantity = QuantityMeasure(name="qty", definition=deferred)
    field = Measure(
        name="total", definition=deferred, components=[rate, quantity], reconcile=True
    )
    assert any(c.name == "total_rec" for c in field.components)
    assert field.reconciliation_field is not None


def test_measure_reconcile_default():
    field = Measure(name="test", definition=deferred)
    assert field.reconcile is True  # Default should be True


def test_measure_no_reconciliation():
    rate = RateMeasure(name="rate", definition=deferred)
    quantity = QuantityMeasure(name="qty", definition=deferred)
    field = Measure(
        name="total", definition=deferred, components=[rate, quantity], reconcile=False
    )

    assert field.reconciliation_field is None


def test_rate_quantity_measure_reconcile_defaults():
    rate = RateMeasure(name="rate", definition=deferred)
    quantity = QuantityMeasure(name="qty", definition=deferred)

    assert rate.reconcile is False
    assert quantity.reconcile is False


def test_reconciliation_with_explicit_reconcile():
    rate = RateMeasure(name="rate", definition=deferred.rate)
    quantity = QuantityMeasure(name="qty", definition=deferred.qty)
    field = Measure(
        name="total",
        definition=deferred.total,
        components=[rate, quantity],
        reconcile=False,
    )

    df = polars.DataFrame({"rate": [1], "qty": [3], "total": [4]})

    con = ibis.polars.connect(tables={"df": df})
    t = con.table("df")

    assert_frame_equal(
        t.select([f.formula for f in field.get_flattened_graph()]).to_polars(),
        df,
        check_column_order=False,
    )


def test_reconciliation_calculation_correctness():
    rate = RateMeasure(name="rate", definition=deferred.rate)
    quantity = QuantityMeasure(name="qty", definition=deferred.qty)
    field = Measure(
        name="total", definition=deferred.total, components=[rate, quantity]
    )

    df = polars.DataFrame({"rate": [1], "qty": [3], "total": [4]}).with_columns(
        (polars.col("total") - (polars.col("rate") * polars.col("qty"))).alias(
            "total_rec"
        )
    )

    con = ibis.polars.connect(tables={"df": df})
    t = con.table("df")

    # Verify reconciliation field returns correct values
    assert_frame_equal(
        t.select(
            field.reconciliation_field.formula.name(field.reconciliation_field.name)
        ).to_polars(),
        df.select("total_rec"),
    )


def test_nested_flattened_graph():
    # Create nested structure:
    # measure1
    #   |- rate1
    #   |- qty1
    #   |- measure2
    #        |- rate2
    #        |- qty2

    rate1 = RateMeasure(name="rate1", definition=deferred)
    qty1 = QuantityMeasure(name="qty1", definition=deferred)

    rate2 = RateMeasure(name="rate2", definition=deferred)
    qty2 = QuantityMeasure(name="qty2", definition=deferred)
    field2 = Measure(name="nested", components=[rate2, qty2])

    field1 = Measure(name="main", components=[rate1, qty1, field2])

    graph = field1.get_flattened_graph()

    assert len(graph) == 6  # field1, rate1, qty1, field2, rate2, qty2
    assert all(item in graph for item in [field1, rate1, qty1, field2, rate2, qty2])


def test_multiple_quantity_components():
    # Create multiple quantity components
    qty1 = QuantityMeasure(name="qty1", definition=deferred)
    qty2 = QuantityMeasure(name="qty2", definition=deferred)

    # Attempt to create measure with multiple quantities
    with pytest.raises(
        ValueError, match="has multiple quantity components which is not supported"
    ):
        Measure(name="test_measure", components=[qty1, qty2])


def test_measure_without_calculated_definition():
    field = Measure(name="test", definition=deferred)

    assert field.calculated_definition is None
    assert field.formula is not None


def test_formula_calculated_definition():
    rate2 = RateMeasure(name="rate2", definition=deferred)
    qty2 = QuantityMeasure(name="qty2", definition=deferred)
    field2 = Measure(name="nested", components=[rate2, qty2])

    assert field2.definition is None
    assert field2.formula is not None


def test_formula_priority():
    # Create measure with both types of definitions
    rate = RateMeasure(name="rate2", definition=deferred.z)
    qty = QuantityMeasure(name="qty2", definition=deferred.y)
    field = Measure(name="test", definition=deferred.x, components=[rate, qty])

    df = polars.DataFrame({"x": [1], "y": [3], "z": [5]})
    con = ibis.polars.connect(tables={"df": df})
    t = con.table("df")

    # Verify formula returns original definition
    assert_frame_equal(t.select(field.formula).to_polars(), df.select("x"))


def test_formula_correctness():
    # Create measure with both types of definitions
    rate = RateMeasure(name="rate2", definition=deferred.z)
    qty = QuantityMeasure(name="qty2", definition=deferred.y)
    field = Measure(name="test", components=[rate, qty])

    df = polars.DataFrame({"x": [1], "y": [3], "z": [5]}).with_columns(
        (polars.col("y") * polars.col("z")).alias("test")
    )
    con = ibis.polars.connect(tables={"df": df})
    t = con.table("df")

    # Verify formula returns correct values
    assert_frame_equal(
        t.select(field.formula.name("test")).to_polars(), df.select("test")
    )


def test_formula_correctness_with_other_measure():
    # Create measure with both types of definitions
    rate = RateMeasure(name="rate2", definition=deferred.z)
    qty = QuantityMeasure(name="qty2", definition=deferred.y)
    other = Measure(name="other", definition=deferred.o)
    field = Measure(name="test", components=[rate, qty, other])

    df = polars.DataFrame({"x": [1], "y": [3], "z": [5], "o": 7}).with_columns(
        (polars.col("y") * polars.col("z") + polars.col("o")).alias("test")
    )
    con = ibis.polars.connect(tables={"df": df})
    t = con.table("df")

    # Verify formula returns correct values
    assert_frame_equal(
        t.select(field.formula.name("test")).to_polars(), df.select("test")
    )


def test_formula_correctness_with_multiple_other_measures():
    # Create measure with both types of definitions
    rate = RateMeasure(name="rate2", definition=deferred.z)
    qty = QuantityMeasure(name="qty2", definition=deferred.y)
    other = Measure(name="other", definition=deferred.o)
    other2 = Measure(name="other", definition=deferred.o2)
    field = Measure(name="test", components=[rate, qty, other, other2])

    df = polars.DataFrame(
        {"x": [1], "y": [3], "z": [5], "o": 7, "o2": 10}
    ).with_columns(
        (polars.col("y") * polars.col("z") + polars.col("o") + polars.col("o2")).alias(
            "test"
        )
    )
    con = ibis.polars.connect(tables={"df": df})
    t = con.table("df")

    # Verify formula returns correct values
    assert_frame_equal(
        t.select(field.formula.name("test")).to_polars(), df.select("test")
    )


def test_composite_rate_measure_creation():
    rate1 = RateMeasure(name="rate1", definition=deferred.r1)
    rate2 = RateMeasure(name="rate2", definition=deferred.r2)
    composite = CompositeRateMeasure(name="composite", components=[rate1, rate2])

    assert composite.name == "composite"
    assert len(composite.components) == 2
    assert all(isinstance(c, RateMeasure) for c in composite.components)


def test_composite_rate_measure_validation_errors():
    rate = RateMeasure(name="rate", definition=deferred.r)
    qty = QuantityMeasure(name="qty", definition=deferred.q)

    # Test empty components
    with pytest.raises(ValueError, match="must have at least one rate component"):
        CompositeRateMeasure(name="test", components=[])

    # Test non-RateMeasure component
    with pytest.raises(ValueError, match="can only have RateMeasure components"):
        CompositeRateMeasure(name="test", components=[rate, qty])

    # Test direct definition
    with pytest.raises(ValueError, match="cannot have a direct definition"):
        CompositeRateMeasure(name="test", components=[rate], definition=deferred.x)


def test_composite_rate_measure_calculated_definition():
    rate1 = RateMeasure(name="rate1", definition=deferred.r1)
    rate2 = RateMeasure(name="rate2", definition=deferred.r2)
    composite = CompositeRateMeasure(name="composite", components=[rate1, rate2])

    df = polars.DataFrame({"r1": [1], "r2": [2]})
    con = ibis.polars.connect(tables={"df": df})
    t = con.table("df")

    result = t.select(composite.formula.name("result")).to_polars()

    expected = polars.DataFrame({"result": [3]})
    assert_frame_equal(result, expected)


def test_composite_rate_measure_properties():
    # Setup test components
    rate1 = RateMeasure(name="rate1", definition=deferred.r1)
    rate2 = RateMeasure(name="rate2", definition=deferred.r2)
    composite = CompositeRateMeasure(name="composite", components=[rate1, rate2])

    # Test rate property returns None
    assert composite.rate is None

    # Test rates property returns correct components
    assert len(composite.rates) == 2
    assert isinstance(composite.rates, list)
    assert all(isinstance(r, RateMeasure) for r in composite.rates)
    assert rate1 in composite.rates
    assert rate2 in composite.rates


def test_rate_measures_cannot_have_simple_components():
    rate = RateMeasure(name="rate", definition=deferred)
    qty = QuantityMeasure(name="qty", definition=deferred)
    simple = Measure(name="simple", definition=deferred)

    with pytest.raises(
        ValueError, match="type RateMeasure cannot have simple components"
    ):
        RateMeasure(name="test", components=[rate, qty, simple])


def test_quantity_measures_cannot_have_simple_components():
    rate = RateMeasure(name="rate", definition=deferred)
    qty = QuantityMeasure(name="qty", definition=deferred)
    simple = Measure(name="simple", definition=deferred)

    with pytest.raises(
        ValueError, match="type QuantityMeasure cannot have simple components"
    ):
        QuantityMeasure(name="test", components=[rate, qty, simple])
