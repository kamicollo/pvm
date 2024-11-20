import datasets
import ibis
import pytest
from ibis import _
from polars.testing import assert_frame_equal
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
                "fx_rate",
                definition=(_.volume * _.fx_rate * _.price_in_lc).sum()
                / (_.price_in_lc * _.volume).sum(),
            ),
        ],
    )

    return Field(
        "revenue",
        definition=_.revenue.sum(),
        reconcile=False,
        components=[
            price,
            QuantityField(
                "volume",
                definition=_.volume.sum(),
            ),
            Field("flat_fee", definition=_.flat_fee.sum()),
        ],
    )


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

    result = pvm.calculate_effects().to_polars().sort("country", "sku")
    expected = datasets.sales.effects_by_country_sku.sort("country", "sku")

    assert_frame_equal(
        result,
        expected,
        check_column_order=False,
        check_row_order=True,
        check_dtypes=False,
        atol=1e-2,
    )


def test_aggregation_correctness_customer_sku(
    sales_dataset: ibis.Table, revenue_graph: ibis.deferred.Deferred
):
    pvm = (
        PVM()
        .set_data(sales_dataset)
        .set_periods(_.year, ["2020", "2021"])
        .set_hierarchy([_.customer, _.sku])
    )

    pvm.set_graph(revenue_graph)

    result = pvm.calculate_effects().to_polars().sort("customer", "sku")
    expected = datasets.sales.effects_by_customer_sku.sort("customer", "sku")

    assert_frame_equal(
        result,
        expected,
        check_column_order=False,
        check_row_order=True,
        check_dtypes=False,
        atol=1e-2,
    )
