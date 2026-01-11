"""
Caching utilities for test datasets.

Downloads and caches CSV data locally to avoid network requests during tests.
"""

import hashlib
import pathlib

import polars as pl

CACHE_DIR = pathlib.Path(__file__).parent / ".cache"


def get_cache_path(url: str) -> pathlib.Path:
    """Generate a cache file path based on URL hash."""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]  # noqa: S324
    return CACHE_DIR / f"{url_hash}.csv"


def read_csv_cached(
    url: str,
    skip_rows: int = 0,
    force_refresh: bool = False,
) -> pl.DataFrame:
    """
    Read CSV with local file caching.

    Args:
        url: The URL to fetch the CSV from.
        skip_rows: Number of rows to skip when reading.
        force_refresh: If True, bypass cache and re-download.

    Returns:
        A polars DataFrame with the CSV data.

    """
    cache_path = get_cache_path(url)

    if not force_refresh and cache_path.exists():
        # Read from local cache
        return pl.read_csv(cache_path, skip_rows=skip_rows)

    # Ensure cache directory exists
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Download and cache
    df_full = pl.read_csv(url)
    df_full.write_csv(cache_path)

    # Return with skip_rows applied
    if skip_rows > 0:
        return pl.read_csv(cache_path, skip_rows=skip_rows)
    return df_full


def clear_cache() -> None:
    """Clear all cached CSV files."""
    if CACHE_DIR.exists():
        for file in CACHE_DIR.glob("*.csv"):
            file.unlink()
