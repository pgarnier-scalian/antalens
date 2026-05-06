"""Tests for reactive integration: Dataset filters bound to a Lens."""

from __future__ import annotations

from datetime import datetime

import polars as pl
import pytest

from antalens.data.dataset import Dataset
from antalens.lens import Lens

# ─── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def multi_area_df() -> pl.DataFrame:
    """Three areas, three days, two variables — enough to exercise filters."""
    return pl.DataFrame(
        {
            "ts": [datetime(2025, 1, d, 12) for d in [1, 2, 3]] * 3,
            "area": ["FR"] * 3 + ["DE"] * 3 + ["ES"] * 3,
            "load": [50.0, 51.0, 52.0, 60.0, 61.0, 62.0, 40.0, 41.0, 42.0],
        }
    )


# ─── static path unchanged ─────────────────────────────────────────────────


def test_static_filter_still_works(multi_area_df: pl.DataFrame) -> None:
    """No regression: passing static values produces the same result."""
    ds = Dataset(multi_area_df.lazy())
    out = ds.filter(area="FR").to_dataframe()
    assert out.height == 3
    assert set(out["area"].to_list()) == {"FR"}


def test_static_filter_has_no_reactive_bindings(
    multi_area_df: pl.DataFrame,
) -> None:
    ds = Dataset(multi_area_df.lazy())
    filtered = ds.filter(area="FR")
    assert filtered.watched_parameters == []


# ─── lens-bound filter ────────────────────────────────────────────────────


def test_lens_bound_filter_uses_current_value(
    multi_area_df: pl.DataFrame,
) -> None:
    ds = Dataset(multi_area_df.lazy())
    lens = Lens(area="DE")
    reactive = ds.filter(area=lens)

    out = reactive.to_dataframe()
    assert out.height == 3
    assert set(out["area"].to_list()) == {"DE"}


def test_lens_bound_filter_re_evaluates_on_change(
    multi_area_df: pl.DataFrame,
) -> None:
    """The same Dataset produces different results after lens mutation."""
    ds = Dataset(multi_area_df.lazy())
    lens = Lens(area="FR")
    reactive = ds.filter(area=lens)

    assert reactive.to_dataframe().height == 3  # FR rows

    lens.area = "DE"
    after = reactive.to_dataframe()
    assert after.height == 3
    assert set(after["area"].to_list()) == {"DE"}

    lens.area = "ES"
    again = reactive.to_dataframe()
    assert set(again["area"].to_list()) == {"ES"}


def test_lens_with_none_means_no_constraint(
    multi_area_df: pl.DataFrame,
) -> None:
    """When the lens parameter is None, the filter is a no-op."""
    ds = Dataset(multi_area_df.lazy())
    lens = Lens(area=None)
    reactive = ds.filter(area=lens)
    out = reactive.to_dataframe()
    assert out.height == 9  # all rows


def test_lens_lifts_to_dataframe_each_time(
    multi_area_df: pl.DataFrame,
) -> None:
    """Each to_dataframe call re-reads lens; results stay in sync."""
    ds = Dataset(multi_area_df.lazy())
    lens = Lens(area="FR")
    reactive = ds.filter(area=lens)

    snapshots = []
    for area in ["FR", "DE", "ES", "FR"]:
        lens.area = area
        snapshots.append(reactive.to_dataframe()["area"][0])

    assert snapshots == ["FR", "DE", "ES", "FR"]


def test_filter_area_without_area_column_raises() -> None:
    """filter(area=...) errors immediately if there's no 'area' column.

    Catches the case where a user wires a Lens to a dataset that doesn't
    have an area column. The error fires at filter() time, not at
    materialization, so the call site is the one flagged.
    """
    df = pl.DataFrame({"ts": [1, 2], "load": [10, 20]})
    ds = Dataset(df.lazy())

    with pytest.raises(ValueError, match="requires a column named 'area'"):
        ds.filter(area="FR")

    # Same applies for reactive bindings.
    lens = Lens(area="FR")
    with pytest.raises(ValueError, match="requires a column named 'area'"):
        ds.filter(area=lens)


# ─── lens-bound date_range ─────────────────────────────────────────────────


def test_lens_bound_date_range(multi_area_df: pl.DataFrame) -> None:
    ds = Dataset(multi_area_df.lazy())
    lens = Lens(dates=(datetime(2025, 1, 1), datetime(2025, 1, 2, 23, 59)))
    reactive = ds.filter(date_range=lens)

    out = reactive.to_dataframe()
    # Days 1 and 2, 3 areas each
    assert out.height == 6


def test_lens_date_range_updates_reactively(
    multi_area_df: pl.DataFrame,
) -> None:
    ds = Dataset(multi_area_df.lazy())
    lens = Lens(dates=(datetime(2025, 1, 1), datetime(2025, 1, 1, 23, 59)))
    reactive = ds.filter(date_range=lens)

    assert reactive.to_dataframe().height == 3  # 1 day x 3 areas

    # Widen the range
    lens.dates = (datetime(2025, 1, 1), datetime(2025, 1, 3, 23, 59))
    assert reactive.to_dataframe().height == 9  # all rows


# ─── explicit param reference ─────────────────────────────────────────────


def test_explicit_param_reference_works(multi_area_df: pl.DataFrame) -> None:
    """Pass lens.param.area instead of the whole lens."""
    ds = Dataset(multi_area_df.lazy())
    lens = Lens(area="ES")
    reactive = ds.filter(area=lens.param.area)
    assert set(reactive.to_dataframe()["area"].to_list()) == {"ES"}


def test_explicit_param_for_arbitrary_column(
    multi_area_df: pl.DataFrame,
) -> None:
    """A custom column kwarg can take a param reference even though
    no canonical Lens parameter exists for it."""
    HRLens = Lens.with_extras(custom_filter=__import__("param").String(default="FR"))
    lens = HRLens()

    ds = Dataset(multi_area_df.lazy())
    reactive = ds.filter(area=lens.param.custom_filter)
    assert set(reactive.to_dataframe()["area"].to_list()) == {"FR"}

    lens.custom_filter = "DE"  # type: ignore[attr-defined]
    assert set(reactive.to_dataframe()["area"].to_list()) == {"DE"}


# ─── watched_parameters API ────────────────────────────────────────────────


def test_watched_parameters_lists_all_bindings(
    multi_area_df: pl.DataFrame,
) -> None:
    ds = Dataset(multi_area_df.lazy())
    lens = Lens(area="FR")
    reactive = ds.filter(area=lens, date_range=lens)
    watched = reactive.watched_parameters
    assert len(watched) == 2
    # The order matches filter argument order
    assert lens.param.area in watched
    assert lens.param.dates in watched


def test_watched_parameters_empty_for_static(
    multi_area_df: pl.DataFrame,
) -> None:
    ds = Dataset(multi_area_df.lazy())
    assert ds.watched_parameters == []
    assert ds.filter(area="FR").watched_parameters == []


# ─── chain compatibility ───────────────────────────────────────────────────


def test_reactive_filter_chains_with_static_filter(
    multi_area_df: pl.DataFrame,
) -> None:
    """A reactive filter followed by a static one preserves both."""
    ds = Dataset(multi_area_df.lazy())
    lens = Lens(area="FR")
    chained = ds.filter(area=lens).filter(date_range=("2025-01-01", "2025-01-01T23:59"))
    out = chained.to_dataframe()
    assert out.height == 1
    assert out["area"][0] == "FR"

    # Still reactive on area
    lens.area = "DE"
    out = chained.to_dataframe()
    assert out.height == 1
    assert out["area"][0] == "DE"


def test_reactive_filter_chains_with_resample(
    multi_area_df: pl.DataFrame,
) -> None:
    """resample after a reactive filter bakes in the current lens value.

    Reactive filters and resample don't compose cleanly because resample
    changes the column set. The library warns and bakes in current values.
    Subsequent lens mutations don't propagate past the resample.
    """
    ds = Dataset(multi_area_df.lazy())
    lens = Lens(area="FR")

    with pytest.warns(UserWarning, match="resample"):
        chained = ds.filter(area=lens).resample("1d", agg="mean")

    out = chained.to_dataframe()
    assert out.height == 3
    # area was baked in; column may or may not survive — check load instead
    assert all(50.0 <= v <= 53.0 for v in out["load"].to_list())

    # Lens mutation does NOT update — that's the documented limitation
    lens.area = "DE"
    out_after = chained.to_dataframe()
    assert out_after.equals(out)


def test_reactive_filter_to_lazy_resolves(multi_area_df: pl.DataFrame) -> None:
    """to_lazy() returns an LF that reflects the current lens state."""
    ds = Dataset(multi_area_df.lazy())
    lens = Lens(area="FR")
    reactive = ds.filter(area=lens)

    out_fr = reactive.to_lazy().collect()
    assert set(out_fr["area"].to_list()) == {"FR"}

    lens.area = "DE"
    out_de = reactive.to_lazy().collect()
    assert set(out_de["area"].to_list()) == {"DE"}


# ─── ComparedDataset interaction ───────────────────────────────────────────


def test_compare_with_reactive_source_warns(
    multi_area_df: pl.DataFrame,
) -> None:
    """Comparing a reactive Dataset emits a warning until full support lands."""
    ds = Dataset(multi_area_df.lazy())
    lens = Lens(area="FR")
    reactive = ds.filter(area=lens)
    static = Dataset(multi_area_df.lazy())

    with pytest.warns(UserWarning, match="does not yet propagate"):
        reactive.compare(static)
