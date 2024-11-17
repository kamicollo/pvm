import datasets
import ibis
import polars as pl
import pytest
from ibis import _
from polars.testing import assert_frame_equal, assert_frame_not_equal
from pvm.fields import Field, QuantityField, RateField
from pvm.pvm import PVM


@pytest.fixture
def sales_dataset() -> ibis.Table:
    con = ibis.polars.connect({"sales": datasets.sales.raw})
    return con.table("sales")


@pytest.fixture
def revenue_graph() -> ibis.deferred.Deferred:
    price = RateField(
        "unit_price",
        definition=(_.volume * _.unit_price).sum() / _.volume.sum(),
        components=[
            QuantityField(
                "price_in_lc",
                definition=(_.volume * _.price_in_lc).sum() / _.volume.sum(),
            ),
            RateField(
                "fx_rate", definition=(_.volume * _.fx_rate).sum() / _.volume.sum()
            ),
        ],
    )

    revenue = Field(
        "revenue",
        definition=_.revenue.sum(),
        components=[
            price,
            QuantityField(
                "volume",
                definition=_.volume.sum(),
            ),
            Field("flat_fee", definition=_.flat_fee.sum()),
        ],
    )
    return revenue


def test_aggregation_correctness_country_sku(
    sales_dataset: ibis.Table, revenue_graph: ibis.deferred.Deferred
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
        datasets.sales.aggregate_by_country_sku.with_columns(
            pl.lit(0.0).alias("revenue_rec"),
            pl.col("period").cast(pl.String),
        ),
        check_dtypes=False,
        check_column_order=False,
        check_row_order=False,
        check_exact=False,
        atol=1e-1,
    )


def test_aggregation_correctness_no_hierarchy(
    sales_dataset: ibis.Table, revenue_graph: ibis.deferred.Deferred
):
    pvm = PVM().set_data(sales_dataset).set_periods(_.year, ["2020", "2021"])

    pvm.set_graph(revenue_graph)

    result = pvm.aggregated.to_polars()

    assert_frame_equal(
        result,
        datasets.sales.aggregate.with_columns(
            pl.lit(0.0).alias("revenue_rec"),
            pl.col("period").cast(pl.String),
        ),
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
