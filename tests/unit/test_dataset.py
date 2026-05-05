"""Tests for :class:`antalens.data.dataset.Dataset`."""

from __future__ import annotations

from datetime import date, datetime

import polars as pl
import pytest

from antalens.data.dataset import ComparedDataset, Dataset
from antalens.data.schema import Schema

# ─── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def simple_df() -> pl.DataFrame:
    """A simple 4-row dataset with time, fuel category, and load."""
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
            "co2": [10.0, 0.0, 11.0, 0.0],
        }
    )


@pytest.fixture
def hourly_df() -> pl.DataFrame:
    """24 hours of synthetic load data, single category."""
    return pl.DataFrame(
        {
            "ts": [datetime(2025, 1, 1, h) for h in range(24)],
            "load": [50.0 + h for h in range(24)],
        }
    )


# ─── construction ──────────────────────────────────────────────────────────


def test_constructs_from_lazyframe(simple_df: pl.DataFrame) -> None:
    ds = Dataset(simple_df.lazy())
    assert ds.schema.time_col == "ts"
    assert "load" in ds.schema.numeric_cols
    assert "fuel" in ds.schema.categorical_cols


def test_accepts_explicit_schema(simple_df: pl.DataFrame) -> None:
    custom = Schema(
        time_col="ts",
        categorical_cols={"fuel": ["nuclear", "wind"]},
        numeric_cols=["load"],  # deliberately omit co2
    )
    ds = Dataset(simple_df.lazy(), schema=custom)
    assert ds.schema is custom
    assert ds.schema.numeric_cols == ["load"]


def test_accepts_name(simple_df: pl.DataFrame) -> None:
    ds = Dataset(simple_df.lazy(), name="my-study")
    assert ds.name == "my-study"


def test_repr_is_informative(simple_df: pl.DataFrame) -> None:
    ds = Dataset(simple_df.lazy())
    r = repr(ds)
    assert "Dataset" in r
    assert "ts" in r
    assert "load" in r


# ─── filter — area / variable / column kwargs ──────────────────────────────


def test_filter_by_single_value(simple_df: pl.DataFrame) -> None:
    ds = Dataset(simple_df.lazy())
    out = ds.filter(fuel="nuclear").to_dataframe()
    assert out.height == 2
    assert set(out["fuel"].to_list()) == {"nuclear"}


def test_filter_by_list_of_values(simple_df: pl.DataFrame) -> None:
    ds = Dataset(simple_df.lazy())
    out = ds.filter(fuel=["nuclear", "wind"]).to_dataframe()
    assert out.height == 4  # both kept


def test_filter_unknown_column_raises(simple_df: pl.DataFrame) -> None:
    ds = Dataset(simple_df.lazy())
    with pytest.raises(ValueError, match="does not match any column"):
        ds.filter(missing="x")


def test_filter_returns_new_instance(simple_df: pl.DataFrame) -> None:
    ds = Dataset(simple_df.lazy())
    other = ds.filter(fuel="nuclear")
    assert other is not ds
    # Original unchanged
    assert ds.to_dataframe().height == 4


def test_filter_chains(simple_df: pl.DataFrame) -> None:
    ds = Dataset(simple_df.lazy())
    out = (
        ds.filter(fuel="nuclear")
        .filter(date_range=(datetime(2025, 1, 1, 0), datetime(2025, 1, 1, 10)))
        .to_dataframe()
    )
    assert out.height == 1
    assert out["load"][0] == 50.0


# ─── filter — date_range ───────────────────────────────────────────────────


def test_filter_date_range_with_datetimes(simple_df: pl.DataFrame) -> None:
    ds = Dataset(simple_df.lazy())
    out = ds.filter(date_range=(datetime(2025, 1, 1, 6), datetime(2025, 1, 1, 12))).to_dataframe()
    assert out.height == 2  # both bounds inclusive


def test_filter_date_range_with_iso_strings(simple_df: pl.DataFrame) -> None:
    ds = Dataset(simple_df.lazy())
    out = ds.filter(date_range=("2025-01-01T06:00", "2025-01-01T12:00")).to_dataframe()
    assert out.height == 2


def test_filter_date_range_with_date_only(simple_df: pl.DataFrame) -> None:
    ds = Dataset(simple_df.lazy())
    # Date-only strings parsed as midnight
    out = ds.filter(date_range=("2025-01-01", "2025-01-02")).to_dataframe()
    assert out.height == 4  # all of 2025-01-01 falls in [00:00, next day 00:00]


def test_filter_date_range_invalid_string_raises(simple_df: pl.DataFrame) -> None:
    ds = Dataset(simple_df.lazy())
    with pytest.raises(ValueError, match="could not parse"):
        ds.filter(date_range=("not-a-date", "2025-01-02"))


def test_filter_date_range_without_time_col_raises() -> None:
    df = pl.DataFrame({"x": [1.0, 2.0]})
    ds = Dataset(df.lazy())
    with pytest.raises(ValueError, match="requires a time column"):
        ds.filter(date_range=(date(2025, 1, 1), date(2025, 1, 2)))


# ─── resample ──────────────────────────────────────────────────────────────


def test_resample_to_coarser_freq(hourly_df: pl.DataFrame) -> None:
    ds = Dataset(hourly_df.lazy())
    out = ds.resample("6h", agg="mean").to_dataframe()
    assert out.height == 4  # 24h / 6h = 4 buckets
    # First bucket should average hours 0-5 = (50+51+52+53+54+55)/6 = 52.5
    assert out["load"][0] == pytest.approx(52.5)


def test_resample_with_dict_agg(hourly_df: pl.DataFrame) -> None:
    ds = Dataset(hourly_df.lazy())
    out = ds.resample("12h", agg={"load": "max"}).to_dataframe()
    assert out.height == 2
    # First bucket max of hours 0-11 = 50 + 11 = 61
    assert out["load"][0] == 61.0


def test_resample_preserves_categories(simple_df: pl.DataFrame) -> None:
    """Resampling with a categorical column groups by it."""
    ds = Dataset(simple_df.lazy())
    out = ds.resample("1d", agg="mean").to_dataframe().sort("fuel")
    # Should have one row per fuel type
    assert out.height == 2
    assert set(out["fuel"].to_list()) == {"nuclear", "wind"}


def test_resample_without_time_col_raises() -> None:
    df = pl.DataFrame({"x": [1.0, 2.0]})
    ds = Dataset(df.lazy())
    with pytest.raises(ValueError, match="requires a time column"):
        ds.resample("1d")


# ─── compare ───────────────────────────────────────────────────────────────


def test_compare_returns_compared_dataset(hourly_df: pl.DataFrame) -> None:
    ds_a = Dataset(hourly_df.lazy(), name="2025")
    ds_b = Dataset(hourly_df.lazy(), name="2030")
    compared = ds_a.compare(ds_b, label_a="2025", label_b="2030")
    assert isinstance(compared, ComparedDataset)
    assert compared.label_a == "2025"
    assert compared.label_b == "2030"


def test_compare_concatenates_with_series_column(hourly_df: pl.DataFrame) -> None:
    ds_a = Dataset(hourly_df.lazy())
    ds_b = Dataset(hourly_df.lazy())
    compared = ds_a.compare(ds_b, label_a="A", label_b="B")
    df = compared.to_dataframe()
    assert df.height == 48  # 24 + 24
    assert "__series__" in df.columns
    assert set(df["__series__"].to_list()) == {"A", "B"}


def test_compared_dataset_supports_filter(hourly_df: pl.DataFrame) -> None:
    """Chain methods continue to work on a ComparedDataset.

    The result of chaining is a plain Dataset (not ComparedDataset), but
    the underlying ``__series__`` discriminator is preserved so plot
    builders can still split the two series.
    """
    ds_a = Dataset(hourly_df.lazy())
    ds_b = Dataset(hourly_df.lazy())
    compared = ds_a.compare(ds_b)
    # Filter to first 6 hours of each series
    narrowed = compared.filter(date_range=(datetime(2025, 1, 1, 0), datetime(2025, 1, 1, 5)))
    df = narrowed.to_dataframe()
    assert df.height == 12  # 6 + 6
    # __series__ column survives the filter
    assert "__series__" in df.columns
    assert set(df["__series__"].to_list()) == {"A", "B"}


# ─── pipe ──────────────────────────────────────────────────────────────────


def test_pipe_applies_function(hourly_df: pl.DataFrame) -> None:
    ds = Dataset(hourly_df.lazy())

    def take_first_six(d: Dataset) -> Dataset:
        return d.filter(date_range=(datetime(2025, 1, 1, 0), datetime(2025, 1, 1, 5)))

    out = ds.pipe(take_first_six).to_dataframe()
    assert out.height == 6


# ─── escape hatches ────────────────────────────────────────────────────────


def test_to_dataframe_returns_polars(simple_df: pl.DataFrame) -> None:
    ds = Dataset(simple_df.lazy())
    df = ds.to_dataframe()
    assert isinstance(df, pl.DataFrame)
    assert df.height == 4


def test_to_pandas_returns_pandas(simple_df: pl.DataFrame) -> None:
    import pandas as pd

    ds = Dataset(simple_df.lazy())
    df = ds.to_pandas()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 4


def test_to_lazy_returns_lazyframe(simple_df: pl.DataFrame) -> None:
    ds = Dataset(simple_df.lazy())
    assert isinstance(ds.to_lazy(), pl.LazyFrame)


def test_columns_property(simple_df: pl.DataFrame) -> None:
    ds = Dataset(simple_df.lazy())
    assert ds.columns == ["ts", "fuel", "load", "co2"]


# ─── immutability ──────────────────────────────────────────────────────────


def test_chain_methods_dont_mutate_original(simple_df: pl.DataFrame) -> None:
    ds = Dataset(simple_df.lazy())
    _ = ds.filter(fuel="nuclear")
    _ = ds.resample("1d")
    # Original still has all data
    assert ds.to_dataframe().height == 4


def test_dataset_uses_slots() -> None:
    """Dataset uses __slots__ so it has no __dict__."""
    ds = Dataset(pl.DataFrame({"x": [1]}).lazy())
    assert not hasattr(ds, "__dict__")


# ─── subclass preservation ─────────────────────────────────────────────────


class _MyDataset(Dataset):
    """A dummy subclass to verify _with returns the correct type."""


def test_with_preserves_subclass(simple_df: pl.DataFrame) -> None:
    """Chain methods on a subclass return the subclass, not Dataset."""
    ds = _MyDataset(simple_df.lazy())
    filtered = ds.filter(fuel="nuclear")
    assert isinstance(filtered, _MyDataset)
    resampled = ds.resample("1d")
    assert isinstance(resampled, _MyDataset)
