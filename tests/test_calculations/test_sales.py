import datasets
import ibis
import polars as pl
import pytest
from ibis import _
from polars.testing import assert_frame_equal
from pvm.fields import Field, QuantityField, RateField
from pvm.pvm import PVM


@pytest.fixture
def sales_dataset() -> ibis.Table:
    con = ibis.polars.connect({"sales": datasets.sales.raw})
    return con.table("sales")


def test_aggregation_correctness(sales_dataset: ibis.Table):
    pvm = (
        PVM()
        .set_data(sales_dataset)
        .set_periods(_.year, ["2020", "2021"])
        .set_hierarchy([_.country, _.sku])
    )

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

    pvm.set_graph(revenue)

    result = pvm.aggregated.to_polars()

    assert_frame_equal(
        result,
        datasets.sales.aggregate.with_columns(
            pl.lit(0.0).alias("unit_price_rec"),
            pl.lit(0.0).alias("revenue_rec"),
            pl.col("period").cast(pl.String),
        ),
        check_dtypes=False,
        check_column_order=False,
        check_row_order=False,
        check_exact=False,
        atol=1e-1,
    )
