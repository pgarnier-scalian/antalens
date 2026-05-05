"""Tests for :mod:`antalens.data.loaders`."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

from antalens.data.dataset import Dataset
from antalens.data.loaders import from_dataframe, load_csv, load_parquet

# ─── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def sample_df() -> pl.DataFrame:
    """A minimal time-series DataFrame for round-trip tests."""
    return pl.DataFrame(
        {
            "ts": [
                datetime(2025, 1, 1, 0),
                datetime(2025, 1, 1, 6),
                datetime(2025, 1, 1, 12),
                datetime(2025, 1, 1, 18),
            ],
            "fuel": ["nuclear", "wind", "nuclear", "wind"],
            "load": [50.0, 30.0, 55.0, 35.0],
        }
    )


# ─── load_parquet ──────────────────────────────────────────────────────────


def test_load_parquet_single_file(tmp_path: Path, sample_df: pl.DataFrame) -> None:
    path = tmp_path / "data.parquet"
    sample_df.write_parquet(path)

    ds = load_parquet(path)
    assert isinstance(ds, Dataset)
    assert ds.to_dataframe().equals(sample_df)


def test_load_parquet_infers_schema(tmp_path: Path, sample_df: pl.DataFrame) -> None:
    path = tmp_path / "data.parquet"
    sample_df.write_parquet(path)

    ds = load_parquet(path)
    assert ds.schema.time_col == "ts"
    assert "load" in ds.schema.numeric_cols
    assert "fuel" in ds.schema.categorical_cols


def test_load_parquet_with_string_path(tmp_path: Path, sample_df: pl.DataFrame) -> None:
    path = tmp_path / "data.parquet"
    sample_df.write_parquet(path)

    # Pass the string form rather than Path
    ds = load_parquet(str(path))
    assert ds.to_dataframe().height == 4


def test_load_parquet_concatenates_list(tmp_path: Path, sample_df: pl.DataFrame) -> None:
    p1 = tmp_path / "a.parquet"
    p2 = tmp_path / "b.parquet"
    sample_df.write_parquet(p1)
    sample_df.write_parquet(p2)

    ds = load_parquet([p1, p2])
    assert ds.to_dataframe().height == 8  # 4 + 4


def test_load_parquet_glob_pattern(tmp_path: Path, sample_df: pl.DataFrame) -> None:
    sample_df.write_parquet(tmp_path / "year_2025.parquet")
    sample_df.write_parquet(tmp_path / "year_2030.parquet")

    ds = load_parquet(str(tmp_path / "year_*.parquet"))
    assert ds.to_dataframe().height == 8


def test_load_parquet_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="No file at"):
        load_parquet(tmp_path / "nonexistent.parquet")


def test_load_parquet_empty_list_raises() -> None:
    with pytest.raises(ValueError, match="empty list"):
        load_parquet([])


def test_load_parquet_validates_each_path_in_list(tmp_path: Path) -> None:
    real = tmp_path / "real.parquet"
    pl.DataFrame({"x": [1]}).write_parquet(real)

    with pytest.raises(FileNotFoundError):
        load_parquet([real, tmp_path / "missing.parquet"])


def test_load_parquet_passes_kwargs_to_polars(tmp_path: Path, sample_df: pl.DataFrame) -> None:
    """Extra read_kwargs reach polars.scan_parquet."""
    path = tmp_path / "data.parquet"
    sample_df.write_parquet(path)

    # n_rows is a polars-supported kwarg
    ds = load_parquet(path, n_rows=2)
    assert ds.to_dataframe().height == 2


def test_load_parquet_time_col_override(tmp_path: Path, sample_df: pl.DataFrame) -> None:
    path = tmp_path / "data.parquet"
    sample_df.write_parquet(path)

    # Force "no time column"
    ds = load_parquet(path, time_col="")
    assert ds.schema.time_col is None


def test_load_parquet_with_name(tmp_path: Path, sample_df: pl.DataFrame) -> None:
    path = tmp_path / "data.parquet"
    sample_df.write_parquet(path)

    ds = load_parquet(path, name="my-study")
    assert ds.name == "my-study"


# ─── load_csv ──────────────────────────────────────────────────────────────


def test_load_csv_round_trip(tmp_path: Path, sample_df: pl.DataFrame) -> None:
    path = tmp_path / "data.csv"
    sample_df.write_csv(path)

    ds = load_csv(path)
    assert isinstance(ds, Dataset)
    df = ds.to_dataframe()
    assert df.height == 4
    assert "fuel" in df.columns


def test_load_csv_parses_dates_by_default(tmp_path: Path, sample_df: pl.DataFrame) -> None:
    path = tmp_path / "data.csv"
    sample_df.write_csv(path)

    ds = load_csv(path)
    assert ds.schema.time_col == "ts"


def test_load_csv_can_disable_date_parsing(tmp_path: Path, sample_df: pl.DataFrame) -> None:
    path = tmp_path / "data.csv"
    sample_df.write_csv(path)

    ds = load_csv(path, parse_dates=False)
    # Without date parsing, ts is a string column; schema falls back
    # to name-based detection, which still picks "ts" as time col.
    # The point is the dtype is no longer datetime.
    df = ds.to_dataframe()
    assert df["ts"].dtype == pl.String


def test_load_csv_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_csv(tmp_path / "nope.csv")


def test_load_csv_rejects_try_parse_dates_kwarg(tmp_path: Path, sample_df: pl.DataFrame) -> None:
    path = tmp_path / "data.csv"
    sample_df.write_csv(path)

    with pytest.raises(TypeError, match="parse_dates"):
        load_csv(path, try_parse_dates=True)


# ─── from_dataframe ────────────────────────────────────────────────────────


def test_from_dataframe_polars_dataframe(sample_df: pl.DataFrame) -> None:
    ds = from_dataframe(sample_df)
    assert isinstance(ds, Dataset)
    assert ds.to_dataframe().equals(sample_df)


def test_from_dataframe_polars_lazyframe(sample_df: pl.DataFrame) -> None:
    ds = from_dataframe(sample_df.lazy())
    assert ds.to_dataframe().equals(sample_df)


def test_from_dataframe_pandas() -> None:
    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    import pandas as pd

    pdf = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=3, freq="h"),
            "load": [10.0, 11.0, 12.0],
        }
    )
    ds = from_dataframe(pdf)
    df = ds.to_dataframe()
    assert df.height == 3
    assert ds.schema.time_col == "timestamp"


def test_from_dataframe_rejects_unknown_type() -> None:
    with pytest.raises(TypeError, match="expected a polars/pandas"):
        from_dataframe([1, 2, 3])  # type: ignore[arg-type]


def test_from_dataframe_passes_name(sample_df: pl.DataFrame) -> None:
    ds = from_dataframe(sample_df, name="experiment-1")
    assert ds.name == "experiment-1"


def test_from_dataframe_time_col_override(sample_df: pl.DataFrame) -> None:
    ds = from_dataframe(sample_df, time_col="")
    assert ds.schema.time_col is None


# ─── public namespace ───────────────────────────────────────────────────────


def test_io_namespace_re_exports() -> None:
    """The public ``antalens.io`` namespace exposes all Phase 1 loaders."""
    from antalens import io

    assert hasattr(io, "load_parquet")
    assert hasattr(io, "load_csv")
    assert hasattr(io, "from_dataframe")
