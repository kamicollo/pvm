import pathlib

import polars as pl
import pytest

from datasets import build_olist
from datasets.build_olist import convert_csv_to_parquet


def test_convert_csv_to_parquet_writes_matching_files(tmp_path: pathlib.Path) -> None:
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "out"
    raw_dir.mkdir()
    out_dir.mkdir()
    pl.DataFrame({"order_id": ["a", "b"], "price": [1.5, 2.0]}).write_csv(
        raw_dir / "olist_orders_dataset.csv"
    )
    pl.DataFrame({"seller_id": ["s1"]}).write_csv(raw_dir / "olist_sellers_dataset.csv")

    written = convert_csv_to_parquet(raw_dir, out_dir)

    assert written == [
        out_dir / "olist_orders_dataset.parquet",
        out_dir / "olist_sellers_dataset.parquet",
    ]
    assert pl.read_parquet(out_dir / "olist_orders_dataset.parquet").equals(
        pl.DataFrame({"order_id": ["a", "b"], "price": [1.5, 2.0]}),
    )
    assert pl.read_parquet(out_dir / "olist_sellers_dataset.parquet").columns == [
        "seller_id"
    ]


def test_convert_csv_to_parquet_ignores_non_csv_files(tmp_path: pathlib.Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "notes.txt").write_text("not data")
    pl.DataFrame({"x": [1]}).write_csv(raw_dir / "data.csv")

    written = convert_csv_to_parquet(raw_dir, tmp_path)

    assert [p.name for p in written] == ["data.parquet"]


def test_convert_csv_to_parquet_raises_when_no_csv(tmp_path: pathlib.Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="make download_olist"):
        convert_csv_to_parquet(raw_dir, tmp_path)


def test_main_converts_and_reports_each_file(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "out"
    raw_dir.mkdir()
    out_dir.mkdir()
    pl.DataFrame({"x": [1]}).write_csv(raw_dir / "data.csv")
    monkeypatch.setattr(build_olist, "RAW_DIR", raw_dir)
    monkeypatch.setattr(build_olist, "OLIST_DIR", out_dir)

    build_olist.main()

    assert (out_dir / "data.parquet").exists()
    assert capsys.readouterr().out == "wrote data.parquet\n"
