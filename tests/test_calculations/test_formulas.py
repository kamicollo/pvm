import ibis
import polars as pl
from ibis import _
from polars.testing import assert_frame_equal
from pvm.fields import Field
from pvm.pvm import PVM


def test_correctness_country_sku(
    sales_dataset: ibis.Table,
    revenue_graph: Field,
    effects_by_country_sku: pl.DataFrame,
):
    """Tests basic correctness of the PVM calculation for country-sku hierarchy."""
    pvm = (
        PVM()
        .set_data(sales_dataset)
        .set_periods(_.year, ["2020", "2021"])
        .set_hierarchy([_.country, _.sku])
    )

    pvm.set_graph(revenue_graph)

    result = pvm.calculate_effects().to_polars().sort("country", "sku")

    assert_frame_equal(
        # drop reconciliation fields as we're not that interested in them
        result.drop([c for c in result.columns if "_rec_" in c]),
        effects_by_country_sku,
        check_column_order=False,
        check_row_order=True,
        check_dtypes=False,
        atol=1e-2,
    )


def test_aggregation_correctness_new_discontinued(
    sales_dataset: ibis.Table,
    revenue_graph: Field,
    effects_by_customer_sku: pl.DataFrame,
):
    """Tests correctness of the PVM calculation with new/discontinued items."""
    pvm = (
        PVM()
        .set_data(sales_dataset)
        .set_periods(_.year, ["2020", "2021"])
        .set_hierarchy([_.customer, _.sku])
    )

    pvm.set_graph(revenue_graph)

    result = pvm.calculate_effects().to_polars().sort("customer", "sku")

    assert_frame_equal(
        # drop reconciliation fields as we're not that interested in them
        result.drop([c for c in result.columns if "_rec_" in c]),
        effects_by_customer_sku,
        check_column_order=False,
        check_row_order=True,
        check_dtypes=False,
        atol=1e-2,
    )


def test_dataset_with_composite_rate(
    sales_dataset: ibis.Table,
    composite_profit_graph: Field,
    composite_profit_effects_by_country_sku: pl.DataFrame,
):
    """Tests correctness of calculations when a graph includes a composite rate field."""
    pvm = (
        PVM()
        .set_data(sales_dataset)
        .set_periods(_.year, ["2020", "2021"])
        .set_hierarchy([_.country, _.sku])
    )

    pvm.set_graph(composite_profit_graph)

    tbl = pvm.calculate_effects()
    result = tbl.to_polars().sort("country", "sku")

    assert_frame_equal(
        # drop reconciliation fields as we're not that interested in them
        result.drop([c for c in result.columns if "_rec_" in c]),
        composite_profit_effects_by_country_sku,
        check_column_order=False,
        check_row_order=True,
        check_dtypes=False,
        atol=1e-2,
    )


def test_dataset_with_parent_simple(
    sales_dataset: ibis.Table,
    profit_graph: Field,
    profit_effects_by_country_sku: pl.DataFrame,
):
    """Tests correctness of calculations when the top level field is a simple one."""

    pvm = (
        PVM()
        .set_data(sales_dataset)
        .set_periods(_.year, ["2020", "2021"])
        .set_hierarchy([_.country, _.sku])
    )

    pvm.set_graph(profit_graph)

    tbl = pvm.calculate_effects()
    result = tbl.to_polars().sort("country", "sku")

    assert_frame_equal(
        # drop reconciliation fields as we're not that interested in them
        result.drop([c for c in result.columns if "_rec_" in c]),
        profit_effects_by_country_sku,
        check_column_order=False,
        check_row_order=True,
        check_dtypes=False,
        atol=1e-2,
    )


def test_correctness_quantity_components_new_discontinued(
    sales_dataset: ibis.Table,
    cost_graph: Field,
    cost_effects_by_customer_sku: pl.DataFrame,
):
    """Tests correctness of calculations when the graph includes a volume field that has components."""
    pvm = (
        PVM()
        .set_data(sales_dataset)
        .set_periods(_.year, ["2020", "2021"])
        .set_hierarchy([_.customer, _.sku])
    )

    pvm.set_graph(cost_graph)

    tbl = pvm.calculate_effects()
    result = tbl.to_polars().sort("customer", "sku")

    assert_frame_equal(
        # drop reconciliation fields as we're not that interested in them
        result.drop([c for c in result.columns if "_rec_" in c]),
        cost_effects_by_customer_sku,
        check_column_order=False,
        check_row_order=True,
        check_dtypes=False,
        atol=1e-2,
    )


def test_aggregation_with_quantity_components(
    sales_dataset: ibis.Table,
    cost_graph: Field,
    cost_effects_by_country_sku: pl.DataFrame,
):
    """Tests correctness of calculations when a graph includes a volume field that has components."""
    pvm = (
        PVM()
        .set_data(sales_dataset)
        .set_periods(_.year, ["2020", "2021"])
        .set_hierarchy([_.country, _.sku])
    )

    pvm.set_graph(cost_graph)

    result = pvm.calculate_effects().to_polars().sort("country", "sku")

    assert_frame_equal(
        # drop reconciliation fields as we're not that interested in them
        result.drop([c for c in result.columns if "_rec_" in c]),
        cost_effects_by_country_sku,
        check_column_order=False,
        check_row_order=True,
        check_dtypes=False,
        atol=1e-2,
    )
