"""Datasets module."""

import pathlib
from functools import cached_property

import polars as pl

root_path = pathlib.Path(__file__).parent

__all__ = ["sales"]


class Sales:
    """Fake sales dataset."""

    # @cached_property
    @property
    def raw(self) -> pl.DataFrame:
        """Raw data."""
        return pl.read_csv(
            "https://docs.google.com/spreadsheets/d/e/2PACX-1vTIvyGpgrsYw6aRXTjIavZEClY6UYxmepEpD1hQomCC-NPa7Th5qFQ0nD0LvEmrhzgK4F6mv4tnYTp-/pub?gid=0&single=true&output=csv",
        )

    # @cached_property
    @property
    def aggregate(self) -> pl.DataFrame:
        """Aggregated data."""
        return pl.read_csv(
            "https://docs.google.com/spreadsheets/d/e/2PACX-1vTIvyGpgrsYw6aRXTjIavZEClY6UYxmepEpD1hQomCC-NPa7Th5qFQ0nD0LvEmrhzgK4F6mv4tnYTp-/pub?gid=1665578619&single=true&output=csv",
        )


sales = Sales()
