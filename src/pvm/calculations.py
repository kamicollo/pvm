import polars as pl
from .fields import TotalField, RateField, QuantityField, OtherField
from typing import Union, List
from enum import Enum
import polars.selectors as cs


class CalculationMethod(Enum):
    CLASSIC = 0
    INVERSE = 1
    THREE_WAY = 2
    SYMMETRIC = 3


class PVM:
    def __init__(
        self,
        data: Union[pl.DataFrame, pl.LazyFrame],
        period_col: str,
        calculation_fields: TotalField,
        method_to_use: CalculationMethod = CalculationMethod.CLASSIC,
    ) -> None:
        self.set_data(data)
        self.set_period_column(period_col)
        self.set_calculation_fields(calculation_fields)
        self.method = method_to_use

    def set_data(self, data: Union[pl.DataFrame, pl.LazyFrame]):
        self.data = data

    def set_period_column(self, period_col: str, sorted_values=None):
        if period_col not in self.data.columns:
            raise IndexError(f"Column '{period_col}' not in dataframe")
        else:
            unique_values = self.data[period_col].unique().to_list()
            if not sorted_values:
                self.sorted_periods = sorted(unique_values)
            elif all(p in sorted_values for p in unique_values):
                self.sorted_periods = sorted_values
            else:
                missing_values = [p for p in unique_values if p not in sorted_values]
                raise IndexError(
                    f"Column '{period_col}' contains values '{','.join(missing_values)}' that are missing in the provided sorted list"
                )
            self.period_col = period_col
            self.next_periods = dict(
                zip(self.sorted_periods[:-1], self.sorted_periods[1:])
            )
            self.prev_periods = dict(
                zip(self.sorted_periods[1:], self.sorted_periods[:-1])
            )

    def set_calculation_fields(self, field: TotalField):
        self.field_hierarchy = field
        self.flat_fields = self._flatten_fields(field)
        self.all_calculation_fields = list(self.flat_fields.keys())
        self.setup_expressions()

    def _flatten_fields(self, field):
        result = {}
        if field.components:
            result[field.name] = field.components
            [result.update(self._flatten_fields(f)) for f in field.components]
        else:
            result[field.name] = None
        return result

    def add_change_col(self, field):
        self.change_calcs.append(
            (
                pl.coalesce(pl.col(field + "_next"), 0) - pl.coalesce(pl.col(field), 0)
            ).alias(field + "_change")
        )

    def setup_other_effects(self, fields: List[OtherField]):
        for o in fields:
            self.aggs.append(pl.sum(o.name))
            self.add_change_col(o.name)
            self.effect_calculations.append(
                pl.when(pl.col("status") != "like-for-like")
                .then(0)
                .otherwise(pl.col(o.name + "_change"))
                .alias(o.name + "_effect")
            )

    def setup_effect_calculations(
        self, total_field_name, vol_col: QuantityField, rate_col: RateField
    ):
        self.effect_calculations.append(
            pl.when(pl.col("status") != "like-for-like")
            .then(
                pl.when(pl.lit(total_field_name) == pl.lit(self.field_hierarchy.name))
                .then(pl.col(total_field_name + "_change"))
                .otherwise(0)
            )
            .otherwise(
                pl.col(vol_col.name + "_change") * pl.col("avg_" + rate_col.name)
            )
            .alias(vol_col.name + "_effect")
        )

        self.effect_calculations.append(
            pl.when(pl.col("status") != "like-for-like")
            .then(0)
            .otherwise(
                pl.col("avg_" + rate_col.name + "_change")
                * pl.col(vol_col.name + "_next")
            )
            .alias(rate_col.name + "_effect")
        )

    def setup_expressions(self):
        self.aggs = []
        self.post_aggs = []
        self.effect_calculations = []
        self.change_calcs = []
        for f, components in self.flat_fields.items():
            if components:
                field_name = f + "_calculated"
                self.aggs.append(pl.sum(f))
                self.add_change_col(f)
                self.add_change_col(field_name)

                rate_col = next(c for c in components if isinstance(c, RateField))
                vol_col = next(c for c in components if isinstance(c, QuantityField))
                other_cols = [c for c in components if isinstance(c, OtherField)]

                aggregated_rate_col_name = "avg_" + rate_col.name

                self.setup_other_effects(other_cols)

                # fields used to pre-aggregate data
                self.aggs.append(
                    (pl.col(rate_col.name) * pl.col(vol_col.name))
                    .sum()
                    .alias(field_name)
                )
                self.aggs.append(pl.sum(vol_col.name))

                self.post_aggs.append(
                    (pl.col(field_name) / pl.col(vol_col.name)).alias(
                        aggregated_rate_col_name
                    )
                )

                # fields used to calculate effects
                self.add_change_col(aggregated_rate_col_name)
                self.add_change_col(vol_col.name)
                self.setup_effect_calculations(f, vol_col=vol_col, rate_col=rate_col)

    def pre_aggregate(self, hierarchy: List) -> Union[pl.DataFrame, pl.LazyFrame]:
        # first, we pre-aggregate data to the level of calculation unit
        group_by_columns = [self.period_col] + hierarchy

        return (
            self.data.group_by(group_by_columns)
            .agg(self.aggs)
            .with_columns(self.post_aggs)
        )

    def join_periods(
        self, agg_data: Union[pl.DataFrame, pl.LazyFrame], hierarchy: List
    ):
        # get dtype of the period column
        period_col_dtype = agg_data.select(self.period_col).to_series().dtype
        # get all periods except the last one
        all_but_last_period = agg_data.filter(
            pl.col(self.period_col) != self.sorted_periods[-1]
        ).with_columns(
            pl.col(self.period_col)
            .map_dict(self.next_periods, return_dtype=period_col_dtype)
            .alias("_period_join_key")
        )

        # get all periods except the first one
        all_but_first_period = agg_data.filter(
            pl.col(self.period_col) != self.sorted_periods[0]
        ).rename({self.period_col: "_period_join_key"})

        # do an outer join of the two dfs
        paired_periods = (
            all_but_last_period.join(
                all_but_first_period,
                on=["_period_join_key"] + hierarchy,
                how="outer_coalesce",
                suffix="_next",
            )
            # remap "next period" columns to prior period to avoid nulls
            .with_columns(
                pl.col("_period_join_key")
                .map_dict(self.prev_periods, return_dtype=period_col_dtype)
                .alias("_prior_period_mapped"),
            )
            .with_columns(
                pl.when(pl.col(self.period_col).is_null())
                .then(pl.col("_prior_period_mapped"))
                .otherwise(pl.col(self.period_col))
                .alias(self.period_col),
            )
            .drop(["_prior_period_mapped", "_period_join_key"])
            # add a like-for-like status (overall)
        ).with_columns(
            pl.when(pl.col(self.field_hierarchy.name).is_null())
            .then(pl.lit("introduced"))
            .when(pl.col(self.field_hierarchy.name + "_next").is_null())
            .then(pl.lit("discontinued"))
            .otherwise(pl.lit("like-for-like"))
            .alias("status"),
            pl.lit("").alias("status_reason"),
        )

        return paired_periods

        # identify missing hierarchies by doing incremental joins
        for i in range(len(hierarchy)):
            join_cols = hierarchy[: i + 1]
            discontinued = (
                (
                    all_but_last_period.join(
                        all_but_first_period,
                        left_on=[self.period_col + "_next"] + join_cols,
                        right_on=[self.period_col] + join_cols,
                        how="anti",
                        suffix="_next",
                    )
                )
                .select(join_cols)
                .group_by(join_cols)
                .agg()
                .with_columns(pl.lit(1).alias("_indicator"))
            )

            introduced = (
                (
                    all_but_first_period.join(
                        all_but_last_period,
                        left_on=[self.period_col] + join_cols,
                        right_on=[self.period_col + "_next"] + join_cols,
                        how="anti",
                        suffix="_next",
                    )
                )
                .select(join_cols)
                .group_by(join_cols)
                .agg()
                .with_columns(pl.lit(1).alias("_indicator"))
            )

            paired_periods = (
                (
                    paired_periods.join(
                        discontinued, on=join_cols, how="left", suffix=""
                    )
                    .with_columns(
                        pl.when(
                            (pl.col("_indicator") == 1)
                            & (pl.col("status_reason") == "")
                        )
                        .then(pl.lit(",".join(join_cols)))
                        .otherwise(pl.col("status_reason"))
                        .alias("status_reason")
                    )
                    .drop("_indicator")
                )
                .join(introduced, on=join_cols, how="left", suffix="")
                .with_columns(
                    pl.when(
                        (pl.col("_indicator") == 1) & (pl.col("status_reason") == "")
                    )
                    .then(pl.lit(",".join(join_cols)))
                    .otherwise(pl.col("status_reason"))
                    .alias("status_reason")
                )
                .drop("_indicator")
            )

        return paired_periods  # .with_columns(pl.col("status_reason").str.split(","))

    def identify_missing_components(
        self,
        paired_periods: Union[pl.DataFrame, pl.LazyFrame],
        grouping_hierarchy: List,
    ):
        def missing_elements(*a):
            return ("baz",)

        return paired_periods.with_columns(
            pl.when(pl.col("status") == "like-for-like")
            .then("")
            .otherwise(pl.col(["status", "year"]).map_elements(missing_elements))
            .alias("hierarchy_mismatch")
        )

    def calculate(
        self,
        hierarchy: List[str],
        return_detail: bool = False,
    ):
        # calculate changes

        pre_agg_data = self.pre_aggregate(hierarchy)
        paired_data = self.join_periods(pre_agg_data, hierarchy)
        calculated = paired_data.with_columns(self.change_calcs).with_columns(
            self.effect_calculations
        )

        if return_detail:
            cols = calculated.columns
        else:
            cols = [
                c
                for c in calculated.columns
                if not c.endswith("_next") and not c.endswith("_change")
            ]

        return calculated.select(cols).with_columns(
            pl.sum_horizontal(cs.ends_with("effect")).alias("total_effect")
        )

    def summarize(self, calculated):
        return calculated.group_by("status", "status_reason").agg(
            (
                (
                    (
                        cs.contains("quantity")
                        | cs.contains("revenue")
                        | cs.ends_with("effect")
                    )
                    & (~cs.contains("calculated"))
                ).sum()
            ).round(1),
            pl.count(),
        )

    def find_largest_components(self, calculated, dimension, max_components=5):
        components = []
        # first, split between statuses
        introduced = calculated.filter(pl.col("status") == "introduced")
        discontinued = calculated.filter(pl.col("status") == "discontinued")
        like_for_like = calculated.filter(pl.col("status") == "like-for-like")

        # group introduced & discontinued by reason
        introductions = introduced.group_by("status_reason").agg(pl.sum("total_effect"))
        discontinuations = discontinued.group_by("status_reason").agg(
            pl.sum("total_effect")
        )

        for r in introductions.to_dicts():
            components.append(
                (
                    f"New: {r['status_reason']}",
                    False,
                    r["total_effect"],
                )
            )

        for r in discontinuations.to_dicts():
            components.append(
                (
                    f"Discontinued: {r['status_reason']}",
                    False,
                    r["total_effect"],
                )
            )

        top_volume_effects = like_for_like.sort(
            pl.col("quantity_effect").abs(), descending=True
        ).to_dicts()[:max_components]
        top_price_effects = like_for_like.sort(
            pl.col("price_effect").abs(), descending=True
        ).to_dicts()[:max_components]

        top_total_volume_effect = sum(
            [r["quantity_effect"] for r in top_volume_effects]
        )
        top_total_price_effect = sum([r["price_effect"] for r in top_price_effects])

        volume_effect_total = like_for_like["quantity_effect"].sum()
        price_effect_total = like_for_like["price_effect"].sum()

        for r in top_volume_effects:
            components.append(
                (
                    f"{r[dimension]} quantity effect",
                    False,
                    r["quantity_effect"],
                )
            )

        for r in top_price_effects:
            components.append(
                (
                    f"{r[dimension]} price effect",
                    False,
                    r["price_effect"],
                )
            )

        components.append(
            (
                "Other - volume effect" if top_volume_effects else "Volume effect",
                False,
                volume_effect_total - top_total_volume_effect,
            )
        )
        components.append(
            (
                "Other - price effect" if top_price_effects else "Price effect",
                False,
                price_effect_total - top_total_price_effect,
            )
        )

        return components
