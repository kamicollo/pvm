"""Datasets module."""

import pathlib
from functools import cached_property

import polars as pl

root_path = pathlib.Path(__file__).parent

__all__ = ["sales"]


class _Sales:
    """Fake sales dataset."""

    def get_url(self, gid: str) -> str:
        """Get the URL of the dataset."""
        return f"https://docs.google.com/spreadsheets/d/e/2PACX-1vTIvyGpgrsYw6aRXTjIavZEClY6UYxmepEpD1hQomCC-NPa7Th5qFQ0nD0LvEmrhzgK4F6mv4tnYTp-/pub?gid={gid}&single=true&output=csv"

    @cached_property
    def raw(self) -> pl.DataFrame:
        """Raw data."""
        return pl.read_csv(
            self.get_url("0"),
        )

    @cached_property
    def aggregate_by_country_sku(self) -> pl.DataFrame:
        """Aggregated data."""
        return pl.read_csv(
            self.get_url("238197282"),
        )

    @cached_property
    def aggregate(self) -> pl.DataFrame:
        """Aggregated data."""
        return pl.read_csv(
            self.get_url("405170366"),
        )

    @cached_property
    def effects_by_country_sku(self) -> pl.DataFrame:
        """Effects data."""
        return pl.read_csv(
            self.get_url("734704852"),
            skip_rows=25,
        )

    @cached_property
    def effects_by_customer_sku(self) -> pl.DataFrame:
        """Effects data."""
        return pl.read_csv(
            self.get_url("829016621"),
            skip_rows=56,
        )

    @cached_property
    def cost_effects_by_country_sku(self) -> pl.DataFrame:
        """Effects data."""
        return pl.read_csv(
            self.get_url("2074617120"),
            skip_rows=25,
        )

    @cached_property
    def cost_effects_by_customer_sku(self) -> pl.DataFrame:
        """Effects data."""
        return pl.read_csv(
            self.get_url("1832269939"),
            skip_rows=56,
        )

    @cached_property
    def profit_effects_by_country_sku(self) -> pl.DataFrame:
        """Effects data."""
        return pl.read_csv(
            self.get_url("890734484"),
            skip_rows=0,
        )


sales = _Sales()
