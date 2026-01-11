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
    measure = Measure(name="test")
    with pytest.raises(ValueError, match="must have either components or a definition"):
        _ = measure.formula  # Trigger validation


def test_rate_quantity_combination():
    rate = RateMeasure(name="rate", definition=deferred)
    quantity = QuantityMeasure(name="qty", definition=deferred)
    field = Measure(name="total", components=[rate, quantity])

    assert field.rate == rate
    assert field.quantity == quantity
    assert field.other_components == []


def test_multiple_rate_components():
    measure = Measure(
        name="test",
        components=[
            RateMeasure(name="rate1", definition=deferred),
            RateMeasure(name="rate2", definition=deferred),
        ],
    )
    with pytest.raises(ValueError, match="multiple rate components"):
        _ = measure.formula  # Trigger validation


def test_rate_without_quantity():
    measure = Measure(
        name="test", components=[RateMeasure(name="rate", definition=deferred)]
    )
    with pytest.raises(ValueError, match="missing a quantity component"):
        _ = measure.formula  # Trigger validation


def test_quantity_without_rate():
    measure = Measure(
        name="test", components=[QuantityMeasure(name="qty", definition=deferred)]
    )
    with pytest.raises(ValueError, match="missing a rate component"):
        _ = measure.formula  # Trigger validation


def test_reconciliation_measure():
    rate = RateMeasure(name="rate", definition=deferred)
    quantity = QuantityMeasure(name="qty", definition=deferred)
    field = Measure(
        name="total", definition=deferred, components=[rate, quantity], reconcile=True
    )
    # Trigger validation to add reconciliation field
    _ = field.formula
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

    # Trigger validation to add reconciliation field
    _ = field.formula

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
    measure = Measure(name="test_measure", components=[qty1, qty2])
    with pytest.raises(
        ValueError, match="has multiple quantity components which is not supported"
    ):
        _ = measure.formula  # Trigger validation


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
    empty_composite = CompositeRateMeasure(name="test", components=[])
    with pytest.raises(ValueError, match="must have at least one rate component"):
        _ = empty_composite.formula  # Trigger validation

    # Test non-RateMeasure component
    mixed_composite = CompositeRateMeasure(name="test", components=[rate, qty])
    with pytest.raises(ValueError, match="can only have RateMeasure components"):
        _ = mixed_composite.formula  # Trigger validation

    # Test direct definition
    def_composite = CompositeRateMeasure(
        name="test", components=[rate], definition=deferred.x
    )
    with pytest.raises(ValueError, match="cannot have a direct definition"):
        _ = def_composite.formula  # Trigger validation


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

    measure = RateMeasure(name="test", components=[rate, qty, simple])
    with pytest.raises(
        ValueError, match="type RateMeasure cannot have simple components"
    ):
        _ = measure.formula  # Trigger validation


def test_quantity_measures_cannot_have_simple_components():
    rate = RateMeasure(name="rate", definition=deferred)
    qty = QuantityMeasure(name="qty", definition=deferred)
    simple = Measure(name="simple", definition=deferred)

    measure = QuantityMeasure(name="test", components=[rate, qty, simple])
    with pytest.raises(
        ValueError, match="type QuantityMeasure cannot have simple components"
    ):
        _ = measure.formula  # Trigger validation


class TestMeasureValidationAndMutation:
    """Tests for on-demand validation and automatic invalidation on mutation."""

    def test_validation_is_deferred(self):
        """Test that invalid measures can be created without immediate error."""
        # This should NOT raise - validation is deferred
        measure = Measure(name="invalid")
        assert measure._validated is False

    def test_validation_triggered_on_formula_access(self):
        """Test that accessing formula triggers validation."""
        measure = Measure(name="test", definition=deferred)
        assert measure._validated is False
        _ = measure.formula
        assert measure._validated is True

    def test_validation_triggered_on_get_flattened_graph(self):
        """Test that get_flattened_graph triggers validation."""
        measure = Measure(name="test", definition=deferred)
        assert measure._validated is False
        _ = measure.get_flattened_graph()
        assert measure._validated is True

    def test_components_append_auto_invalidates(self):
        """Test that appending to components auto-invalidates."""
        measure = Measure(name="test", definition=deferred)
        _ = measure.formula  # Trigger validation
        assert measure._validated is True

        extra = Measure(name="extra", definition=deferred)
        measure.components.append(extra)
        assert measure._validated is False

    def test_components_extend_auto_invalidates(self):
        """Test that extending components auto-invalidates."""
        measure = Measure(name="test", definition=deferred)
        _ = measure.formula
        assert measure._validated is True

        measure.components.extend([Measure(name="a", definition=deferred)])
        assert measure._validated is False

    def test_components_remove_auto_invalidates(self):
        """Test that removing from components auto-invalidates."""
        comp = Measure(name="comp", definition=deferred)
        measure = Measure(name="test", components=[comp])
        _ = measure.formula
        assert measure._validated is True

        measure.components.remove(comp)
        assert measure._validated is False

    def test_components_pop_auto_invalidates(self):
        """Test that popping from components auto-invalidates."""
        comp = Measure(name="comp", definition=deferred)
        measure = Measure(name="test", components=[comp])
        _ = measure.formula
        assert measure._validated is True

        measure.components.pop()
        assert measure._validated is False

    def test_components_clear_auto_invalidates(self):
        """Test that clearing components auto-invalidates."""
        comp = Measure(name="comp", definition=deferred)
        measure = Measure(name="test", definition=deferred, components=[comp])
        _ = measure.formula
        assert measure._validated is True

        measure.components.clear()
        assert measure._validated is False

    def test_components_setitem_auto_invalidates(self):
        """Test that setting an item in components auto-invalidates."""
        comp1 = Measure(name="comp1", definition=deferred)
        comp2 = Measure(name="comp2", definition=deferred)
        measure = Measure(name="test", components=[comp1])
        _ = measure.formula
        assert measure._validated is True

        measure.components[0] = comp2
        assert measure._validated is False

    def test_components_iadd_auto_invalidates(self):
        """Test that += on components auto-invalidates."""
        measure = Measure(name="test", definition=deferred)
        _ = measure.formula
        assert measure._validated is True

        measure.components += [Measure(name="a", definition=deferred)]
        assert measure._validated is False

    def test_name_change_auto_invalidates(self):
        """Test that changing name auto-invalidates."""
        measure = Measure(name="test", definition=deferred)
        _ = measure.formula
        assert measure._validated is True

        measure.name = "new_name"
        assert measure._validated is False

    def test_definition_change_auto_invalidates(self):
        """Test that changing definition auto-invalidates."""
        measure = Measure(name="test", definition=deferred)
        _ = measure.formula
        assert measure._validated is True

        measure.definition = deferred.new_field
        assert measure._validated is False

    def test_reconcile_change_auto_invalidates(self):
        """Test that changing reconcile auto-invalidates."""
        measure = Measure(name="test", definition=deferred)
        _ = measure.formula
        assert measure._validated is True

        measure.reconcile = False
        assert measure._validated is False

    def test_components_reassignment_auto_invalidates(self):
        """Test that reassigning components auto-invalidates."""
        measure = Measure(name="test", definition=deferred)
        _ = measure.formula
        assert measure._validated is True

        measure.components = [Measure(name="new", definition=deferred)]
        assert measure._validated is False

    def test_mutation_and_revalidation(self):
        """Test that mutations can be made and revalidation works automatically."""
        rate = RateMeasure(name="rate", definition=deferred)
        qty = QuantityMeasure(name="qty", definition=deferred)
        measure = Measure(name="test", components=[rate, qty])

        # Initial validation
        _ = measure.formula
        assert measure._validated is True

        # Mutate: add a component (auto-invalidates)
        extra = Measure(name="extra", definition=deferred)
        measure.components.append(extra)
        assert measure._validated is False

        # Revalidate by accessing formula
        _ = measure.formula
        assert measure._validated is True
        assert extra in measure.components

    def test_reconciliation_not_duplicated_on_revalidation(self):
        """Test that reconciliation field is not added twice on revalidation."""
        rate = RateMeasure(name="rate", definition=deferred)
        qty = QuantityMeasure(name="qty", definition=deferred)
        measure = Measure(
            name="test",
            definition=deferred,
            components=[rate, qty],
            reconcile=True,
        )

        # First validation adds reconciliation
        _ = measure.formula
        rec_count_1 = sum(1 for c in measure.components if c.name == "test_rec")
        assert rec_count_1 == 1

        # Mutation triggers auto-invalidation
        measure.name = "test"  # Even same value triggers invalidation

        # Revalidate
        _ = measure.formula

        # Should still only have one reconciliation field
        rec_count_2 = sum(1 for c in measure.components if c.name == "test_rec")
        assert rec_count_2 == 1

    def test_mutation_workflow_add_rate_qty(self):
        """Test workflow: create measure, add rate/qty, validate automatically."""
        measure = Measure(name="test", definition=deferred)

        # Initially valid (has definition)
        _ = measure.formula
        assert measure._validated is True

        # Add rate and quantity (auto-invalidates)
        rate = RateMeasure(name="rate", definition=deferred)
        qty = QuantityMeasure(name="qty", definition=deferred)
        measure.components.extend([rate, qty])
        assert measure._validated is False

        # Access formula to revalidate and add reconciliation
        _ = measure.formula
        assert measure.reconciliation_field is not None

    def test_validation_error_after_mutation(self):
        """Test that invalid mutations are caught on revalidation."""
        rate1 = RateMeasure(name="rate1", definition=deferred)
        qty = QuantityMeasure(name="qty", definition=deferred)
        measure = Measure(name="test", components=[rate1, qty])

        # Initial validation passes
        _ = measure.formula

        # Add invalid second rate (auto-invalidates)
        rate2 = RateMeasure(name="rate2", definition=deferred)
        measure.components.append(rate2)
        assert measure._validated is False

        # Revalidation should fail
        with pytest.raises(ValueError, match="multiple rate components"):
            _ = measure.formula

        # Revalidation should fail
        with pytest.raises(ValueError, match="multiple rate components"):
            _ = measure.formula
