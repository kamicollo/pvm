"""Tests for PVM.get_effects() hierarchy columns."""

import ibis
import polars as pl
import pytest
from ibis import _
from pvm.measures import Measure, QuantityMeasure, RateMeasure
from pvm.pvm import PVM


@pytest.fixture
def pvm_revenue(sales_dataset: ibis.Table, revenue_graph: Measure) -> PVM:
    return (
        PVM()
        .set_data(sales_dataset)
        .set_periods(_.year, ["2020", "2021"])
        .set_hierarchy([_.country, _.sku])
        .set_graph(revenue_graph)
    )


@pytest.fixture
def effects_revenue(pvm_revenue: PVM) -> pl.DataFrame:
    return pvm_revenue.get_effects().to_polars()


def test_get_effects_has_hierarchy_columns(effects_revenue: pl.DataFrame) -> None:
    """3-level revenue_graph produces exactly L1/L2/L3 — no L4."""
    assert {"L1", "L2", "L3"}.issubset(effects_revenue.columns)
    assert "L4" not in effects_revenue.columns


def test_get_effects_l1_always_root(effects_revenue: pl.DataFrame) -> None:
    """L1 is always the root measure name."""
    assert set(effects_revenue["L1"].unique().to_list()) == {"revenue"}


def test_get_effects_leaf_measures_only(effects_revenue: pl.DataFrame) -> None:
    """Only leaf measures appear; intermediates (revenue, unit_price) are excluded."""
    measures = set(effects_revenue["measure"].unique().to_list())
    assert "revenue" not in measures
    assert "unit_price" not in measures
    assert {"volume", "flat_fee", "price_in_lc", "fx_rate"}.issubset(measures)


def test_get_effects_l_column_values(effects_revenue: pl.DataFrame) -> None:
    """Ancestor path is correctly encoded in L1/L2/L3 for each leaf measure."""

    def ancestors(measure_name: str) -> tuple:
        row = (
            effects_revenue.filter(pl.col("measure") == measure_name)
            .select("L1", "L2", "L3")
            .unique()
        )
        assert row.shape[0] == 1, f"Expected unique ancestors for {measure_name}"
        return row.row(0)

    assert ancestors("volume") == ("revenue", "volume", "volume")
    assert ancestors("flat_fee") == ("revenue", "flat_fee", "flat_fee")
    assert ancestors("price_in_lc") == ("revenue", "unit_price", "price_in_lc")
    assert ancestors("fx_rate") == ("revenue", "unit_price", "fx_rate")


def test_get_effects_no_effect_columns_remain(effects_revenue: pl.DataFrame) -> None:
    """No raw wide-format __effect__ or __change__ columns leak into the output."""
    assert not any("__effect__" in c for c in effects_revenue.columns)
    assert not any("__change__" in c for c in effects_revenue.columns)
    assert {"measure", "period", "value", "L1", "L2", "L3"}.issubset(
        effects_revenue.columns
    )


def test_get_effects_two_level_graph(sales_dataset: ibis.Table) -> None:
    """A 2-level graph produces only L1/L2 — no L3."""
    simple_graph = Measure(
        "rev",
        definition=_.revenue.sum(),
        components=[
            RateMeasure(
                "price", definition=(_.volume * _.unit_price).sum() / _.volume.sum()
            ),
            QuantityMeasure("volume", definition=_.volume.sum()),
        ],
    )
    result = (
        PVM()
        .set_data(sales_dataset)
        .set_periods(_.year, ["2020", "2021"])
        .set_hierarchy([_.country])
        .set_graph(simple_graph)
        .get_effects()
        .to_polars()
    )
    assert "L1" in result.columns
    assert "L2" in result.columns
    assert "L3" not in result.columns
    assert set(result["L1"].unique().to_list()) == {"rev"}
    assert set(result["measure"].unique().to_list()) == {"price", "volume"}
