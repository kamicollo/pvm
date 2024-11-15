import ibis
import ibis.backends
import polars
import pytest
from ibis import deferred
from polars.testing import assert_frame_equal
from pvm.fields import CompositeRateField, Field, QuantityField, RateField


def test_field_creation():
    field = Field(name="test", definition=deferred)
    assert field.name == "test"
    assert field.type == "simple"
    assert field.components == []


def test_field_without_definition_or_components():
    with pytest.raises(ValueError, match="must have either components or a definition"):
        Field(name="test")


def test_rate_quantity_combination():
    rate = RateField(name="rate", definition=deferred)
    quantity = QuantityField(name="qty", definition=deferred)
    field = Field(name="total", components=[rate, quantity])

    assert field.rate == rate
    assert field.quantity == quantity
    assert field.other_components == []


def test_multiple_rate_components():
    with pytest.raises(ValueError, match="multiple rate components"):
        Field(
            name="test",
            components=[
                RateField(name="rate1", definition=deferred),
                RateField(name="rate2", definition=deferred),
            ],
        )


def test_rate_without_quantity():
    with pytest.raises(ValueError, match="missing a quantity component"):
        Field(name="test", components=[RateField(name="rate", definition=deferred)])


def test_quantity_without_rate():
    with pytest.raises(ValueError, match="missing a rate component"):
        Field(name="test", components=[QuantityField(name="qty", definition=deferred)])


def test_reconciliation_field():
    rate = RateField(name="rate", definition=deferred)
    quantity = QuantityField(name="qty", definition=deferred)
    field = Field(name="total", definition=deferred, components=[rate, quantity])
    assert any(c.name == "total_rec" for c in field.components)
    assert field.reconciliation_field is not None


def test_reconciliation_calculation_correctness():
    rate = RateField(name="rate", definition=deferred.rate)
    quantity = QuantityField(name="qty", definition=deferred.qty)
    field = Field(name="total", definition=deferred.total, components=[rate, quantity])

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
    # field1
    #   |- rate1
    #   |- qty1
    #   |- field2
    #        |- rate2
    #        |- qty2

    rate1 = RateField(name="rate1", definition=deferred)
    qty1 = QuantityField(name="qty1", definition=deferred)

    rate2 = RateField(name="rate2", definition=deferred)
    qty2 = QuantityField(name="qty2", definition=deferred)
    field2 = Field(name="nested", components=[rate2, qty2])

    field1 = Field(name="main", components=[rate1, qty1, field2])

    graph = field1.get_flattened_graph()

    assert len(graph) == 6  # field1, rate1, qty1, field2, rate2, qty2
    assert all(item in graph for item in [field1, rate1, qty1, field2, rate2, qty2])


def test_multiple_quantity_components():
    # Create multiple quantity components
    qty1 = QuantityField(name="qty1", definition=deferred)
    qty2 = QuantityField(name="qty2", definition=deferred)

    # Attempt to create field with multiple quantities
    with pytest.raises(
        ValueError, match="has multiple quantity components which is not supported"
    ):
        Field(name="test_field", components=[qty1, qty2])


def test_field_without_calculated_definition():
    field = Field(name="test", definition=deferred)

    assert field.calculated_definition is None
    assert field.formula is not None


def test_formula_calculated_definition():
    rate2 = RateField(name="rate2", definition=deferred)
    qty2 = QuantityField(name="qty2", definition=deferred)
    field2 = Field(name="nested", components=[rate2, qty2])

    assert field2.definition is None
    assert field2.formula is not None


def test_formula_priority():
    # Create field with both types of definitions
    rate = RateField(name="rate2", definition=deferred.z)
    qty = QuantityField(name="qty2", definition=deferred.y)
    field = Field(name="test", definition=deferred.x, components=[rate, qty])

    df = polars.DataFrame({"x": [1], "y": [3], "z": [5]})
    con = ibis.polars.connect(tables={"df": df})
    t = con.table("df")

    # Verify formula returns original definition
    assert_frame_equal(t.select(field.formula).to_polars(), df.select("x"))


def test_formula_correctness():
    # Create field with both types of definitions
    rate = RateField(name="rate2", definition=deferred.z)
    qty = QuantityField(name="qty2", definition=deferred.y)
    field = Field(name="test", components=[rate, qty])

    df = polars.DataFrame({"x": [1], "y": [3], "z": [5]}).with_columns(
        (polars.col("y") * polars.col("z")).alias("test")
    )
    con = ibis.polars.connect(tables={"df": df})
    t = con.table("df")

    # Verify formula returns correct values
    assert_frame_equal(
        t.select(field.formula.name("test")).to_polars(), df.select("test")
    )


def test_formula_correctness_with_other_field():
    # Create field with both types of definitions
    rate = RateField(name="rate2", definition=deferred.z)
    qty = QuantityField(name="qty2", definition=deferred.y)
    other = Field(name="other", definition=deferred.o)
    field = Field(name="test", components=[rate, qty, other])

    df = polars.DataFrame({"x": [1], "y": [3], "z": [5], "o": 7}).with_columns(
        (polars.col("y") * polars.col("z") + polars.col("o")).alias("test")
    )
    con = ibis.polars.connect(tables={"df": df})
    t = con.table("df")

    # Verify formula returns correct values
    assert_frame_equal(
        t.select(field.formula.name("test")).to_polars(), df.select("test")
    )


def test_formula_correctness_with_multiple_other_field():
    # Create field with both types of definitions
    rate = RateField(name="rate2", definition=deferred.z)
    qty = QuantityField(name="qty2", definition=deferred.y)
    other = Field(name="other", definition=deferred.o)
    other2 = Field(name="other", definition=deferred.o2)
    field = Field(name="test", components=[rate, qty, other, other2])

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


def test_composite_rate_field_creation():
    rate1 = RateField(name="rate1", definition=deferred.r1)
    rate2 = RateField(name="rate2", definition=deferred.r2)
    composite = CompositeRateField(name="composite", components=[rate1, rate2])

    assert composite.name == "composite"
    assert composite.type == "rate"
    assert len(composite.components) == 2
    assert all(isinstance(c, RateField) for c in composite.components)


def test_composite_rate_field_validation_errors():
    rate = RateField(name="rate", definition=deferred.r)
    qty = QuantityField(name="qty", definition=deferred.q)

    # Test empty components
    with pytest.raises(ValueError, match="must have at least one rate component"):
        CompositeRateField(name="test", components=[])

    # Test non-RateField component
    with pytest.raises(ValueError, match="can only have RateField components"):
        CompositeRateField(name="test", components=[rate, qty])

    # Test direct definition
    with pytest.raises(ValueError, match="cannot have a direct definition"):
        CompositeRateField(name="test", components=[rate], definition=deferred.x)


def test_composite_rate_calculated_definition():
    rate1 = RateField(name="rate1", definition=deferred.r1)
    rate2 = RateField(name="rate2", definition=deferred.r2)
    composite = CompositeRateField(name="composite", components=[rate1, rate2])

    df = polars.DataFrame({"r1": [1], "r2": [2]})
    con = ibis.polars.connect(tables={"df": df})
    t = con.table("df")

    result = t.select(composite.formula.name("result")).to_polars()

    expected = polars.DataFrame({"result": [3]})
    assert_frame_equal(result, expected)


def test_composite_rate_field_properties():
    # Setup test components
    rate1 = RateField(name="rate1", definition=deferred.r1)
    rate2 = RateField(name="rate2", definition=deferred.r2)
    composite = CompositeRateField(name="composite", components=[rate1, rate2])

    # Test rate property returns None
    assert composite.rate is None

    # Test rates property returns correct components
    assert len(composite.rates) == 2
    assert isinstance(composite.rates, list)
    assert all(isinstance(r, RateField) for r in composite.rates)
    assert rate1 in composite.rates
    assert rate2 in composite.rates
