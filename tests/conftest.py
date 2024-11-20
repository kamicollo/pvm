import datasets
import ibis
import polars as pl
import pytest
from ibis import _
from pvm.fields import Field, QuantityField, RateField


@pytest.fixture(scope="module")
def sales_dataset() -> ibis.Table:
    con = ibis.polars.connect({"sales": datasets.sales.raw})
    return con.table("sales")


@pytest.fixture(scope="module")
def effects_by_country_sku() -> pl.DataFrame:
    return datasets.sales.effects_by_country_sku.sort("country", "sku")


@pytest.fixture(scope="module")
def cost_effects_by_country_sku() -> pl.DataFrame:
    return datasets.sales.cost_effects_by_country_sku.sort("country", "sku")


@pytest.fixture(scope="module")
def effects_by_customer_sku() -> pl.DataFrame:
    return datasets.sales.effects_by_customer_sku.sort("customer", "sku")


@pytest.fixture(scope="module")
def aggregate_by_country_sku() -> pl.DataFrame:
    return datasets.sales.aggregate_by_country_sku.sort("country", "sku")


@pytest.fixture(scope="module")
def aggregate() -> pl.DataFrame:
    return datasets.sales.aggregate


@pytest.fixture(scope="module")
def revenue_graph() -> Field:
    price = RateField(
        "unit_price",
        definition=(_.volume * _.unit_price).sum() / _.volume.sum(),
        reconcile=True,
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
        components=[
            price,
            QuantityField(
                "volume",
                definition=_.volume.sum(),
            ),
            Field("flat_fee", definition=_.flat_fee.sum()),
        ],
    )


@pytest.fixture
def cost_graph() -> Field:
    cost = Field(
        "cost",
        definition=-_.cost.sum(),
        components=[
            QuantityField(
                "cost_volume",
                definition=_.volume.sum(),
                components=[
                    RateField(
                        "yield_rate",
                        definition=_.volume.sum() / _.raw_material.sum(),
                    ),
                    QuantityField(
                        "raw_material",
                        definition=_.raw_material.sum(),
                    ),
                ],
            ),
            RateField(
                "unit_cost",
                definition=(-_.unit_cost * _.volume).sum() / _.volume.sum(),
            ),
        ],
    )

    return cost


@pytest.fixture
def profit_graph(revenue_graph: Field, cost_graph: Field) -> Field:
    return Field(
        "profit",
        definition=_.revenue.sum() - _.cost.sum(),
        components=[revenue_graph, cost_graph],
    )
