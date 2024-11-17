"""Datasets module."""

import polars as pl

sales = pl.read_parquet("data/sales.parquet")
