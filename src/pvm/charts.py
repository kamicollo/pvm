import altair as alt
import polars as pl
from typing import Iterable, Tuple
import polars.selectors as cs


def waterfall(items: Iterable[Tuple[str, bool, float, str]], labelAngle=0) -> alt.Chart:
    graph_df = (
        pl.DataFrame(items, schema=["label", "is_total", "amount"])
        .with_columns(pl.col("amount").cumsum().alias("running_total"))
        .with_columns(
            pl.when(pl.col("is_total"))
            .then(0)
            .otherwise(pl.col("running_total") - pl.col("amount"))
            .alias("prev_running_total"),
            pl.when(pl.col("is_total"))
            .then(pl.lit(""))
            .otherwise(pl.col("amount").map_elements(lambda x: f"{x:+.1f}"))
            .alias("text_label"),
            pl.when(pl.col("is_total"))
            .then(pl.col("running_total").map_elements(lambda x: f"{x:.1f}"))
            .otherwise(pl.lit(""))
            .alias("total_text_label"),
            pl.when(pl.col("is_total"))
            .then(pl.lit("orange"))
            .when(pl.col("amount") < 0)
            .then(pl.lit("red"))
            .otherwise(pl.lit("green"))
            .alias("color"),
        )
        .with_columns(
            pl.when(pl.col("is_total"))
            .then(pl.col("running_total"))
            .otherwise(pl.col("prev_running_total") + pl.col("amount").abs() / 2)
            .alias("text_label_position"),
            pl.lit(1).alias("row_number"),
        )
        .drop("is_total")
        .with_columns(cs.float().round(1), pl.col("row_number").cumsum())
    )

    axis_labels = " : ".join(
        [
            f"datum.value =='{value}' ? '{label}'"
            for value, label in zip(
                graph_df["row_number"].to_list(), graph_df["label"].to_list()
            )
        ]
    )

    c = alt.Chart(graph_df).encode(
        alt.X(
            "row_number:N",
            axis=alt.Axis(
                labelAngle=labelAngle, labelExpr=axis_labels + " : ''", title=""
            ),
        ),
    )

    bars = c.mark_bar().encode(
        alt.Y("running_total"),
        alt.Y2("prev_running_total"),
        alt.Color("color", scale=None),
        alt.Tooltip(["running_total", "amount", "label"]),
    )

    brick_text = c.mark_text().encode(
        alt.Text("text_label"),
        alt.Y("text_label_position", title=""),
        alt.Tooltip(["running_total", "amount", "label"]),
    )

    totals_text = c.mark_text(dy=-10).encode(
        alt.Text("total_text_label"),
        alt.Y("text_label_position", title=""),
    )

    return bars + brick_text + totals_text
