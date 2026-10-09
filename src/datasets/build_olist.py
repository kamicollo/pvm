"""Convert the raw Olist CSV exports into the parquet files read by ``datasets.olist``.

Run via ``make download_olist`` after the raw CSVs are in place.
"""

import pathlib

import polars as pl

OLIST_DIR: pathlib.Path = pathlib.Path(__file__).parent / "olist"
RAW_DIR: pathlib.Path = OLIST_DIR / "raw"


def convert_csv_to_parquet(
    raw_dir: pathlib.Path = RAW_DIR,
    out_dir: pathlib.Path = OLIST_DIR,
) -> list[pathlib.Path]:
    """Convert every CSV in ``raw_dir`` to a parquet file of the same name in ``out_dir``.

    Args:
        raw_dir: Directory containing the raw Olist CSV files.
        out_dir: Directory to write the parquet files to.

    Returns:
        The paths of the parquet files that were written.

    Raises:
        FileNotFoundError: If ``raw_dir`` contains no CSV files.

    """
    csv_paths = sorted(raw_dir.glob("*.csv"))
    if not csv_paths:
        msg = f"No CSV files found in {raw_dir}. Run `make download_olist` first."
        raise FileNotFoundError(msg)

    written: list[pathlib.Path] = []
    for csv_path in csv_paths:
        out_path = out_dir / csv_path.with_suffix(".parquet").name
        pl.read_csv(csv_path).write_parquet(out_path)
        written.append(out_path)
    return written


def main() -> None:
    """Convert the raw Olist CSVs and report each file written."""
    for path in convert_csv_to_parquet(RAW_DIR, OLIST_DIR):
        print(f"wrote {path.name}")


if __name__ == "__main__":
    main()
