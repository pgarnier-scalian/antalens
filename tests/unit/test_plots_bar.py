"""Tests for :class:`antalens.plots.bar.BarPlot`."""

from __future__ import annotations

import polars as pl
import pytest

from antalens.data.dataset import Dataset
from antalens.plots.bar import BarPlot

# ─── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def categorical_df() -> pl.DataFrame:
    """Three categories with multiple observations each."""
    return pl.DataFrame(
        {
            "fuel": ["nuclear"] * 3 + ["wind"] * 3 + ["gas"] * 3,
            "load": [50.0, 55.0, 60.0, 20.0, 25.0, 30.0, 80.0, 85.0, 90.0],
        }
    )


# ─── construction & validation ─────────────────────────────────────────────


def test_constructs_with_minimum_args(categorical_df: pl.DataFrame) -> None:
    ds = Dataset(categorical_df.lazy())
    plot = BarPlot(ds, x="fuel", y="load")
    assert plot.x == "fuel"
    assert plot.y == "load"
    assert plot.agg == "mean"  # default
    assert plot.orientation == "v"


def test_rejects_unknown_x(categorical_df: pl.DataFrame) -> None:
    ds = Dataset(categorical_df.lazy())
    with pytest.raises(ValueError, match="x='missing'"):
        BarPlot(ds, x="missing", y="load")


def test_rejects_unknown_y(categorical_df: pl.DataFrame) -> None:
    ds = Dataset(categorical_df.lazy())
    with pytest.raises(ValueError, match="y='missing'"):
        BarPlot(ds, x="fuel", y="missing")


def test_rejects_invalid_sort(categorical_df: pl.DataFrame) -> None:
    ds = Dataset(categorical_df.lazy())
    with pytest.raises(ValueError, match="sort"):
        BarPlot(ds, x="fuel", y="load", sort="random")  # type: ignore[arg-type]


def test_rejects_invalid_orientation(categorical_df: pl.DataFrame) -> None:
    ds = Dataset(categorical_df.lazy())
    with pytest.raises(ValueError, match="orientation"):
        BarPlot(ds, x="fuel", y="load", orientation="diagonal")  # type: ignore[arg-type]


# ─── build: structure ──────────────────────────────────────────────────────


def test_build_returns_one_bar_trace(categorical_df: pl.DataFrame) -> None:
    ds = Dataset(categorical_df.lazy())
    fig = BarPlot(ds, x="fuel", y="load").build()
    assert len(fig.data) == 1
    assert fig.data[0].type == "bar"


def test_build_one_bar_per_category(categorical_df: pl.DataFrame) -> None:
    ds = Dataset(categorical_df.lazy())
    fig = BarPlot(ds, x="fuel", y="load").build()
    # 3 fuels in fixture
    assert len(fig.data[0].x) == 3


def test_build_aggregates_with_mean(categorical_df: pl.DataFrame) -> None:
    """Default mean: nuclear=(50+55+60)/3=55, wind=25, gas=85."""
    ds = Dataset(categorical_df.lazy())
    fig = BarPlot(ds, x="fuel", y="load", agg="mean").build()
    by_cat = dict(zip(fig.data[0].x, fig.data[0].y, strict=False))
    assert by_cat["nuclear"] == pytest.approx(55.0)
    assert by_cat["wind"] == pytest.approx(25.0)
    assert by_cat["gas"] == pytest.approx(85.0)


def test_build_aggregates_with_sum(categorical_df: pl.DataFrame) -> None:
    ds = Dataset(categorical_df.lazy())
    fig = BarPlot(ds, x="fuel", y="load", agg="sum").build()
    by_cat = dict(zip(fig.data[0].x, fig.data[0].y, strict=False))
    assert by_cat["nuclear"] == pytest.approx(165.0)
    assert by_cat["wind"] == pytest.approx(75.0)
    assert by_cat["gas"] == pytest.approx(255.0)


def test_build_aggregates_with_max(categorical_df: pl.DataFrame) -> None:
    ds = Dataset(categorical_df.lazy())
    fig = BarPlot(ds, x="fuel", y="load", agg="max").build()
    by_cat = dict(zip(fig.data[0].x, fig.data[0].y, strict=False))
    assert by_cat["nuclear"] == 60.0
    assert by_cat["gas"] == 90.0


# ─── sort behavior ─────────────────────────────────────────────────────────


def test_sort_descending_orders_by_aggregate(
    categorical_df: pl.DataFrame,
) -> None:
    ds = Dataset(categorical_df.lazy())
    fig = BarPlot(ds, x="fuel", y="load", sort="desc").build()
    # gas (85) > nuclear (55) > wind (25)
    assert list(fig.data[0].x) == ["gas", "nuclear", "wind"]


def test_sort_ascending_orders_by_aggregate(
    categorical_df: pl.DataFrame,
) -> None:
    ds = Dataset(categorical_df.lazy())
    fig = BarPlot(ds, x="fuel", y="load", sort="asc").build()
    assert list(fig.data[0].x) == ["wind", "nuclear", "gas"]


def test_no_sort_keeps_data_order(categorical_df: pl.DataFrame) -> None:
    ds = Dataset(categorical_df.lazy())
    fig = BarPlot(ds, x="fuel", y="load").build()
    # Order isn't guaranteed but result should have all 3 categories
    assert set(fig.data[0].x) == {"nuclear", "wind", "gas"}


# ─── orientation ───────────────────────────────────────────────────────────


def test_horizontal_swaps_x_and_y(categorical_df: pl.DataFrame) -> None:
    ds = Dataset(categorical_df.lazy())
    fig = BarPlot(ds, x="fuel", y="load", orientation="h", sort="desc").build()
    # In horizontal mode, the trace.x is values and trace.y is categories
    assert "gas" in fig.data[0].y
    assert fig.data[0].orientation == "h"


def test_horizontal_axis_labels_swap(categorical_df: pl.DataFrame) -> None:
    ds = Dataset(categorical_df.lazy())
    fig = BarPlot(ds, x="fuel", y="load", orientation="h").build()
    # In horizontal, x-axis shows the aggregated value, y-axis the category
    assert "load" in fig.layout.xaxis.title.text
    assert fig.layout.yaxis.title.text == "fuel"


# ─── theme & accessor ─────────────────────────────────────────────────────


def test_build_applies_theme(categorical_df: pl.DataFrame) -> None:
    from antalens.theme import DARK

    ds = Dataset(categorical_df.lazy())
    fig = BarPlot(ds, x="fuel", y="load").build()
    assert fig.layout.paper_bgcolor.lower() == DARK.paper_bgcolor.lower()


def test_accessor_returns_pane(categorical_df: pl.DataFrame) -> None:
    import panel as pn

    ds = Dataset(categorical_df.lazy())
    pane = ds.plot.bar(x="fuel", y="load")
    assert isinstance(pane, pn.pane.Plotly)


# ─── event extractor ──────────────────────────────────────────────────────


def test_event_extractors_includes_bar_click(
    categorical_df: pl.DataFrame,
) -> None:
    ds = Dataset(categorical_df.lazy())
    plot = BarPlot(ds, x="fuel", y="load")
    extractors = plot.event_extractors()
    assert "bar_click" in extractors
