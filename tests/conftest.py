import datasets
import ibis
import polars as pl
import pytest
from ibis import _
from pvm.measures import CompositeRateMeasure, Measure, QuantityMeasure, RateMeasure


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
def cost_effects_by_customer_sku() -> pl.DataFrame:
    return datasets.sales.cost_effects_by_customer_sku.sort("customer", "sku")


@pytest.fixture(scope="module")
def profit_effects_by_country_sku() -> pl.DataFrame:
    return datasets.sales.profit_effects_by_country_sku.sort("country", "sku")


@pytest.fixture(scope="module")
def composite_profit_effects_by_country_sku() -> pl.DataFrame:
    return datasets.sales.composite_profit_effects_by_country_sku.sort("country", "sku")


@pytest.fixture(scope="module")
def aggregate() -> pl.DataFrame:
    return datasets.sales.aggregate


@pytest.fixture(scope="module")
def revenue_graph() -> Measure:
    price = RateMeasure(
        "unit_price",
        definition=(_.volume * _.unit_price).sum() / _.volume.sum(),
        reconcile=True,
        components=[
            QuantityMeasure(
                "price_in_lc",
                definition=(_.volume * _.price_in_lc).sum() / _.volume.sum(),
            ),
            RateMeasure(
                "fx_rate",
                definition=(_.volume * _.fx_rate * _.price_in_lc).sum()
                / (_.price_in_lc * _.volume).sum(),
            ),
        ],
    )

    return Measure(
        "revenue",
        definition=_.revenue.sum(),
        components=[
            price,
            QuantityMeasure(
                "volume",
                definition=_.volume.sum(),
            ),
            Measure("flat_fee", definition=_.flat_fee.sum()),
        ],
    )


@pytest.fixture
def cost_graph() -> Measure:
    cost = Measure(
        "cost",
        definition=-_.cost.sum(),
        components=[
            QuantityMeasure(
                "cost_volume",
                definition=_.volume.sum(),
                components=[
                    RateMeasure(
                        "yield_rate",
                        definition=_.volume.sum() / _.raw_material.sum(),
                    ),
                    QuantityMeasure(
                        "raw_material",
                        definition=_.raw_material.sum(),
                    ),
                ],
            ),
            RateMeasure(
                "unit_cost",
                definition=(-_.unit_cost * _.volume).sum() / _.volume.sum(),
            ),
        ],
    )

    return cost


@pytest.fixture
def profit_graph(revenue_graph: Measure, cost_graph: Measure) -> Measure:
    return Measure(
        "profit",
        definition=_.revenue.sum() - _.cost.sum(),
        components=[revenue_graph, cost_graph],
    )


@pytest.fixture
def composite_profit_graph(revenue_graph: Measure, cost_graph: Measure) -> Measure:
    composite_rate = CompositeRateMeasure(
        "unit_profit",
        components=[
            revenue_graph.rate,  # type: ignore
            cost_graph.rate,  # type: ignore
        ],
    )

    other_components = revenue_graph.other_components + cost_graph.other_components
    components = [composite_rate, revenue_graph.quantity] + other_components

    return Measure(
        "profit",
        definition=_.revenue.sum() - _.cost.sum(),
        components=components,  # type: ignore
    )
