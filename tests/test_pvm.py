import ibis
import polars as pl
from polars.testing import assert_frame_equal
from pvm import PERIOD_COLUMN
from pvm.fields import Field, QuantityField, RateField
from pvm.pvm import PVM


def test_pvm_basic_initialization():
    df = pl.DataFrame({"rate": [10, 12], "qty": [100, 120], "period": ["2023", "2024"]})

    con = ibis.polars.connect({"df": df})
    t = con.table("df")

    pvm = PVM().set_data(t)

    assert pvm.data == t
    assert pvm.hierarchy == []


def test_pvm_setter_methods():
    df = pl.DataFrame({"rate": [10, 12], "qty": [100, 120], "period": ["2023", "2024"]})

    con = ibis.polars.connect({"df": df})
    t = con.table("df")

    # Create components
    rate = RateField(name="rate", definition=ibis.deferred.rate)
    qty = QuantityField(name="qty", definition=ibis.deferred.qty)
    field = Field(name="total", components=[rate, qty])

    # Test method chaining
    pvm = (
        PVM()
        .set_data(t)
        .set_graph(field)
        .set_periods(ibis.deferred.period, ["2023", "2024"])
    )

    assert pvm.period_expression.resolve(t).to_polars().name == "period"
    assert pvm.period_order == ["2023", "2024"]
    assert pvm.graph == field


def test_pvm_with_hierarchy():
    df = pl.DataFrame(
        {
            "rate": [10, 12, 15, 18],
            "qty": [100, 120, 150, 180],
            "period": ["2023", "2024", "2023", "2024"],
            "region": ["NA", "NA", "EU", "EU"],
        }
    )

    con = ibis.polars.connect({"df": df})
    t = con.table("df")

    rate = RateField(
        name="rate",
        definition=(ibis.deferred.qty * ibis.deferred.rate).sum()
        / ibis.deferred.qty.sum(),
    )
    qty = QuantityField(name="qty", definition=ibis.deferred.qty.sum())
    field = Field(name="revenue", components=[rate, qty])

    pvm = (
        PVM()
        .set_data(t)
        .set_graph(field)
        .set_periods(ibis.deferred.period, ["2023", "2024"])
        .set_hierarchy([ibis.deferred.region])
    )

    result = pvm.aggregated.to_polars()

    assert_frame_equal(
        result,
        df.group_by(["region", "period"])
        .agg(
            [
                pl.col("qty").sum(),
                (pl.col("rate") * pl.col("qty")).sum().alias("revenue"),
            ]
        )
        .with_columns((pl.col("revenue") / pl.col("qty")).alias("rate"))
        .rename({"period": PERIOD_COLUMN}),
        check_column_order=False,
        check_row_order=False,
        check_dtypes=False,
    )


def test_pvm_aggregation():
    df = pl.DataFrame({"rate": [10, 12], "qty": [100, 120], "period": ["2023", "2024"]})

    con = ibis.polars.connect({"df": df})
    t = con.table("df")

    rate = RateField(name="rate", definition=ibis.deferred.rate.sum())
    qty = QuantityField(name="qty", definition=ibis.deferred.qty.sum())
    field = Field(name="total", components=[rate, qty])

    pvm = (
        PVM()
        .set_data(t)
        .set_graph(field)
        .set_periods(ibis.deferred.period, ["2023", "2024"])
    )

    result = pvm.aggregated.to_polars()

    assert_frame_equal(
        result,
        df.with_columns((pl.col("qty") * pl.col("rate")).alias("total")).rename(
            {"period": PERIOD_COLUMN}
        ),
        check_column_order=False,
        check_row_order=False,
        check_dtypes=False,
    )


def test_pvm_aggregation_with_reconciliation_field():
    df = pl.DataFrame(
        {
            "rate": [10, 12],
            "qty": [100, 120],
            "total": [1000, 1440],
            "period": ["2023", "2024"],
        }
    )

    con = ibis.polars.connect({"df": df})
    t = con.table("df")

    rate = RateField(name="rate", definition=ibis.deferred.rate.sum())
    qty = QuantityField(name="qty", definition=ibis.deferred.qty.sum())
    field = Field(
        name="total", definition=ibis.deferred.total.sum(), components=[rate, qty]
    )

    pvm = (
        PVM()
        .set_data(t)
        .set_graph(field)
        .set_periods(ibis.deferred.period, ["2023", "2024"])
    )

    result = pvm.aggregated.to_polars()

    assert_frame_equal(
        result,
        df.with_columns(
            (pl.col("total") - pl.col("qty") * pl.col("rate")).alias("total_rec"),
        ).rename({"period": PERIOD_COLUMN}),
        check_column_order=False,
        check_row_order=False,
        check_dtypes=False,
    )


def test_pvm_aggregation_with_reconciliation_difference():
    df = pl.DataFrame(
        {
            "rate": [10, 12],
            "qty": [100, 120],
            "total": [900, 1540],
            "period": ["2023", "2024"],
        }
    )

    con = ibis.polars.connect({"df": df})
    t = con.table("df")

    rate = RateField(name="rate", definition=ibis.deferred.rate.sum())
    qty = QuantityField(name="qty", definition=ibis.deferred.qty.sum())
    field = Field(
        name="total", definition=ibis.deferred.total.sum(), components=[rate, qty]
    )

    pvm = (
        PVM()
        .set_data(t)
        .set_graph(field)
        .set_periods(ibis.deferred.period, ["2023", "2024"])
    )

    result = pvm.aggregated.to_polars()

    assert_frame_equal(
        result,
        df.with_columns(
            (pl.col("total") - pl.col("qty") * pl.col("rate")).alias("total_rec"),
        ).rename({"period": PERIOD_COLUMN}),
        check_column_order=False,
        check_row_order=False,
        check_dtypes=False,
    )


def test_pvm_set_periods():
    df = pl.DataFrame({"rate": [10, 12], "qty": [100, 120], "period": [2023, 2024]})

    con = ibis.polars.connect({"df": df})
    t = con.table("df")

    pvm = PVM().set_data(t)

    # Test setting periods
    pvm.set_periods(ibis.deferred.period, ["2023", "2024"])

    assert pvm.period_order == ["2023", "2024"]

    # Test period expression casting
    assert pvm.period_expression.resolve(t).to_polars().dtype == pl.String


def test_pvm_aggregated_no_data():
    pvm = PVM()
    try:
        pvm.aggregated
    except ValueError as e:
        assert str(e) == "Data source is not set"


def test_pvm_aggregated_no_period_expression():
    df = pl.DataFrame({"rate": [10, 12], "qty": [100, 120], "period": ["2023", "2024"]})
    con = ibis.polars.connect({"df": df})
    t = con.table("df")
    pvm = PVM().set_data(t)
    try:
        pvm.aggregated
    except ValueError as e:
        assert str(e) == "Period expression is not set"


def test_pvm_aggregated_no_period_order():
    df = pl.DataFrame({"rate": [10, 12], "qty": [100, 120], "period": ["2023", "2024"]})
    con = ibis.polars.connect({"df": df})
    t = con.table("df")
    pvm = PVM().set_data(t).set_periods(ibis.deferred.period, None)
    try:
        pvm.aggregated
    except ValueError as e:
        assert str(e) == "Period order is not set"


def test_pvm_aggregated_no_graph():
    df = pl.DataFrame({"rate": [10, 12], "qty": [100, 120], "period": ["2023", "2024"]})
    con = ibis.polars.connect({"df": df})
    t = con.table("df")
    pvm = PVM().set_data(t).set_periods(ibis.deferred.period, ["2023", "2024"])
    try:
        pvm.aggregated
    except ValueError as e:
        assert str(e) == "Calculation graph is not set"


def test_pvm_get_wide_table():
    df = pl.DataFrame(
        {
            "rate": [10, 12, 15, 18],
            "qty": [100, 120, 150, 180],
            "period": ["2023", "2024", "2023", "2024"],
            "region": ["NA", "NA", "EU", "EU"],
        }
    )

    con = ibis.polars.connect({"df": df})
    t = con.table("df")

    rate = RateField(
        name="rate",
        definition=(ibis.deferred.qty * ibis.deferred.rate).sum()
        / ibis.deferred.qty.sum(),
    )
    qty = QuantityField(name="qty", definition=ibis.deferred.qty.sum())
    field = Field(name="revenue", components=[rate, qty])

    pvm = (
        PVM()
        .set_data(t)
        .set_graph(field)
        .set_periods(ibis.deferred.period, ["2023", "2024"])
        .set_hierarchy([ibis.deferred.region])
    )

    result = pvm.get_wide_table().to_polars()

    expected = (
        df.group_by(["region", "period"])
        .agg(
            [
                pl.col("qty").sum(),
                (pl.col("rate") * pl.col("qty")).sum().alias("revenue"),
            ]
        )
        .with_columns((pl.col("revenue") / pl.col("qty")).alias("rate"))
        .pivot(
            values=["revenue", "rate", "qty"],
            index="region",
            on="period",
            aggregate_function="sum",
        )
        .fill_null(0)
    )

    assert_frame_equal(
        result,
        expected,
        check_column_order=False,
        check_row_order=False,
        check_dtypes=False,
    )


def test_pvm_get_wide_table_one_column():
    df = pl.DataFrame(
        {
            "qty": [100, 120, 150, 180],
            "period": ["2023", "2024", "2023", "2024"],
            "region": ["NA", "NA", "EU", "EU"],
        }
    )

    con = ibis.polars.connect({"df": df})
    t = con.table("df")
    qty = QuantityField(name="qty", definition=ibis.deferred.qty.sum())

    pvm = (
        PVM()
        .set_data(t)
        .set_graph(qty)
        .set_periods(ibis.deferred.period, ["2023", "2024"])
        .set_hierarchy([ibis.deferred.region])
    )

    result = pvm.get_wide_table().to_polars()

    expected = (
        df.group_by(["region", "period"])
        .agg(
            [
                pl.col("qty").sum(),
            ]
        )
        .pivot(
            values=["qty"],
            index="region",
            on="period",
            aggregate_function="sum",
        )
        .fill_null(0)
    )

    assert_frame_equal(
        result,
        expected,
        check_column_order=False,
        check_row_order=False,
        check_dtypes=False,
    )


def test_pvm_get_wide_table_no_graph():
    df = pl.DataFrame({"rate": [10, 12], "qty": [100, 120], "period": ["2023", "2024"]})
    con = ibis.polars.connect({"df": df})
    t = con.table("df")
    pvm = PVM().set_data(t).set_periods(ibis.deferred.period, ["2023", "2024"])
    try:
        pvm.get_wide_table()
    except ValueError as e:
        assert str(e) == "Calculation graph is not set"


def test_pvm_calculate_effects_no_period_order():
    df = pl.DataFrame({"rate": [10, 12], "qty": [100, 120], "period": ["2023", "2024"]})
    con = ibis.polars.connect({"df": df})
    t = con.table("df")
    pvm = (
        PVM()
        .set_data(t)
        .set_graph(Field(name="total", definition=ibis.deferred.qty.sum()))
    )
    try:
        pvm.calculate_effects()
    except ValueError as e:
        assert str(e) == "Calculation requires at least two periods"


def test_pvm_calculate_effects_one_period():
    df = pl.DataFrame({"rate": [10, 12], "qty": [100, 120], "period": ["2023", "2024"]})
    con = ibis.polars.connect({"df": df})
    t = con.table("df")
    pvm = (
        PVM()
        .set_data(t)
        .set_periods(ibis.deferred.period, ["2023"])
        .set_graph(Field(name="total", definition=ibis.deferred.qty.sum()))
    )
    assert pvm.aggregated.to_polars() is not None
    assert pvm.get_wide_table().to_polars() is not None
    try:
        pvm.calculate_effects()
    except ValueError as e:
        assert str(e) == "Calculation requires at least two periods"


def test_pvm_calculate_effects_no_graph():
    df = pl.DataFrame({"rate": [10, 12], "qty": [100, 120], "period": ["2023", "2024"]})
    con = ibis.polars.connect({"df": df})
    t = con.table("df")
    pvm = PVM().set_data(t).set_periods(ibis.deferred.period, ["2023", "2024"])
    try:
        pvm.calculate_effects()
    except ValueError as e:
        assert str(e) == "Calculation graph is not set"
