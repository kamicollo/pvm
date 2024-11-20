import ibis
import polars as pl
from ibis import _
from polars.testing import assert_frame_equal, assert_frame_not_equal
from pvm import PERIOD_COLUMN
from pvm.fields import Field
from pvm.pvm import PVM


def test_aggregation_correctness_country_sku(
    sales_dataset: ibis.Table,
    revenue_graph: Field,
    aggregate_by_country_sku: pl.DataFrame,
):
    pvm = (
        PVM()
        .set_data(sales_dataset)
        .set_periods(_.year, ["2020", "2021"])
        .set_hierarchy([_.country, _.sku])
    )

    pvm.set_graph(revenue_graph)

    result = pvm.aggregated.to_polars()

    assert_frame_equal(
        result,
        aggregate_by_country_sku.with_columns(
            pl.lit(0.0).alias("revenue_rec"),
            pl.lit(0.0).alias("unit_price_rec"),
            pl.col("period").cast(pl.String),
        )
        .rename({"period": PERIOD_COLUMN})
        .drop(
            ["profit", "cost", "unit_cost", "raw_material", "yield_rate", "cost_volume"]
        ),
        check_dtypes=False,
        check_column_order=False,
        check_row_order=False,
        check_exact=False,
        atol=1e-1,
    )


def test_aggregation_correctness_country_sku_profit_graph(
    sales_dataset: ibis.Table,
    profit_graph: Field,
    aggregate_by_country_sku: pl.DataFrame,
):
    pvm = (
        PVM()
        .set_data(sales_dataset)
        .set_periods(_.year, ["2020", "2021"])
        .set_hierarchy([_.country, _.sku])
    )

    pvm.set_graph(profit_graph)

    result = pvm.aggregated.to_polars()

    assert_frame_equal(
        result,
        aggregate_by_country_sku.with_columns(
            pl.lit(0.0).alias("revenue_rec"),
            pl.lit(0.0).alias("cost_rec"),
            pl.lit(0.0).alias("unit_price_rec"),
            pl.col("period").cast(pl.String),
        ).rename({"period": PERIOD_COLUMN}),
        check_dtypes=False,
        check_column_order=False,
        check_row_order=False,
        check_exact=False,
        atol=1e-1,
    )


def test_aggregation_correctness_no_hierarchy(
    sales_dataset: ibis.Table, revenue_graph: Field, aggregate: pl.DataFrame
):
    pvm = PVM().set_data(sales_dataset).set_periods(_.year, ["2020", "2021"])

    pvm.set_graph(revenue_graph)

    result = pvm.aggregated.to_polars()

    assert_frame_equal(
        result,
        aggregate.with_columns(
            pl.lit(0.0).alias("revenue_rec"),
            pl.lit(0.0).alias("unit_price_rec"),
            pl.col("period").cast(pl.String),
        ).rename({"period": PERIOD_COLUMN}),
        check_dtypes=False,
        check_column_order=False,
        check_row_order=False,
        check_exact=False,
        atol=1e-1,
    )


def test_graph_resets_aggregation(sales_dataset: ibis.Table):
    pvm = PVM().set_data(sales_dataset)
    pvm.set_graph(Field("revenue", definition=_.revenue.sum())).set_periods(
        _.year, ["2020", "2021"]
    )

    p1 = pvm.aggregated.to_polars()

    # reset the graph
    pvm.set_graph(Field("cost", definition=_.cost.sum()))
    p2 = pvm.aggregated.to_polars()
    assert_frame_not_equal(p1, p2)


def test_data_resets_aggregation(sales_dataset: ibis.Table):
    pvm = PVM().set_data(sales_dataset)
    pvm.set_graph(Field("revenue", definition=_.revenue.sum())).set_periods(
        _.year, ["2020", "2021"]
    )

    p1 = pvm.aggregated.to_polars()

    # reset the data
    new_sales_dataset = sales_dataset.filter(_.year.cast(str) == "2021")
    pvm.set_data(new_sales_dataset)
    p2 = pvm.aggregated.to_polars()
    assert_frame_not_equal(p1, p2)


def test_period_resets_aggregation(sales_dataset: ibis.Table):
    pvm = PVM().set_data(sales_dataset)
    pvm.set_graph(Field("revenue", definition=_.revenue.sum())).set_periods(
        _.year, ["2020", "2021"]
    )

    p1 = pvm.aggregated.to_polars()

    # reset the periods
    pvm.set_periods(_.year, ["2021"])
    p2 = pvm.aggregated.to_polars()
    assert_frame_not_equal(p1, p2)


def test_hierarchy_resets_aggregation(sales_dataset: ibis.Table):
    pvm = PVM().set_data(sales_dataset)
    pvm.set_graph(Field("revenue", definition=_.revenue.sum())).set_periods(
        _.year, ["2020", "2021"]
    ).set_hierarchy([_.country])

    p1 = pvm.aggregated.to_polars()

    # reset the hierarchy
    pvm.set_hierarchy([_.sku])
    p2 = pvm.aggregated.to_polars()
    assert_frame_not_equal(p1, p2)
