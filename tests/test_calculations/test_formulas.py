import ibis
import polars as pl
import pytest
from ibis import _
from polars.testing import assert_frame_equal
from pvm.fields import Field
from pvm.pvm import PVM


def test_aggregation_correctness_country_sku(
    sales_dataset: ibis.Table,
    revenue_graph: Field,
    effects_by_country_sku: pl.DataFrame,
):
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


def test_aggregation_correctness_customer_sku(
    sales_dataset: ibis.Table,
    revenue_graph: Field,
    effects_by_customer_sku: pl.DataFrame,
):
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


def test_dataset_with_composite_rate():
    pytest.skip("Not implemented yet")


def test_dataset_with_quantity_components():
    pytest.skip("Not implemented yet")
