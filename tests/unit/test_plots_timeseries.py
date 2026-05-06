"""Tests for :class:`antalens.plots.timeseries.TimeSeriesPlot`."""

from __future__ import annotations

from datetime import datetime, timedelta
from itertools import pairwise

import polars as pl
import pytest

from antalens.data.dataset import Dataset
from antalens.lens import Lens
from antalens.plots.timeseries import TimeSeriesPlot

# ─── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def ts_df() -> pl.DataFrame:
    """3 days of hourly data for two fuels."""
    start = datetime(2025, 1, 1)
    return pl.DataFrame(
        {
            "ts": [start + timedelta(hours=h) for h in range(72)] * 2,
            "fuel": ["nuclear"] * 72 + ["wind"] * 72,
            "load": [50.0 + (h % 24) for h in range(72)] + [30.0 + (h % 24) for h in range(72)],
        }
    )


@pytest.fixture
def mc_df() -> pl.DataFrame:
    """24 hours x 5 MC realizations — for testing CI ribbons."""
    start = datetime(2025, 1, 1)
    rows = []
    for h in range(24):
        for mc in range(5):
            rows.append(
                {
                    "ts": start + timedelta(hours=h),
                    "mc_year": mc,
                    "load": 50.0 + h + mc * 2,  # MC adds spread
                }
            )
    return pl.DataFrame(rows)


# ─── construction & validation ─────────────────────────────────────────────


def test_constructs_with_minimum_args(ts_df: pl.DataFrame) -> None:
    ds = Dataset(ts_df.lazy())
    plot = TimeSeriesPlot(ds, y="load")
    assert plot.y == "load"
    assert plot.by is None
    assert plot.conf_int is None


def test_rejects_unknown_y_column(ts_df: pl.DataFrame) -> None:
    ds = Dataset(ts_df.lazy())
    with pytest.raises(ValueError, match="y='missing'"):
        TimeSeriesPlot(ds, y="missing")


def test_rejects_unknown_by_column(ts_df: pl.DataFrame) -> None:
    ds = Dataset(ts_df.lazy())
    with pytest.raises(ValueError, match="by='missing'"):
        TimeSeriesPlot(ds, y="load", by="missing")


def test_rejects_dataset_without_time_column() -> None:
    df = pl.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0]})
    ds = Dataset(df.lazy())
    with pytest.raises(ValueError, match="requires a time column"):
        TimeSeriesPlot(ds, y="y")


def test_rejects_invalid_conf_int(ts_df: pl.DataFrame) -> None:
    ds = Dataset(ts_df.lazy())
    for bad in (0.0, 1.0, -0.1, 1.5, 95):
        with pytest.raises(ValueError, match="conf_int"):
            TimeSeriesPlot(ds, y="load", conf_int=bad)


# ─── build: simple line ────────────────────────────────────────────────────


def test_build_simple_returns_one_trace(ts_df: pl.DataFrame) -> None:
    ds = Dataset(ts_df.lazy())
    fig = TimeSeriesPlot(ds, y="load").build()
    assert len(fig.data) == 1
    assert fig.data[0].mode == "lines"


def test_build_uses_dataset_name_in_title(ts_df: pl.DataFrame) -> None:
    ds = Dataset(ts_df.lazy(), name="europe-2025")
    fig = TimeSeriesPlot(ds, y="load").build()
    assert "europe-2025" in fig.layout.title.text
    assert "load" in fig.layout.title.text


def test_build_explicit_title_overrides_default(ts_df: pl.DataFrame) -> None:
    ds = Dataset(ts_df.lazy(), name="europe")
    fig = TimeSeriesPlot(ds, y="load", title="Custom Title").build()
    assert fig.layout.title.text == "Custom Title"


def test_build_y_axis_label_matches_column(ts_df: pl.DataFrame) -> None:
    ds = Dataset(ts_df.lazy())
    fig = TimeSeriesPlot(ds, y="load").build()
    assert fig.layout.yaxis.title.text == "load"


def test_build_applies_theme(ts_df: pl.DataFrame) -> None:
    """Figures get the active theme's bg color."""
    from antalens.theme import DARK

    ds = Dataset(ts_df.lazy())
    fig = TimeSeriesPlot(ds, y="load").build()
    # Plotly converts hex to lowercase but preserves the value
    assert fig.layout.paper_bgcolor.lower() == DARK.paper_bgcolor.lower()


# ─── build: grouped ────────────────────────────────────────────────────────


def test_build_grouped_one_trace_per_group(ts_df: pl.DataFrame) -> None:
    ds = Dataset(ts_df.lazy())
    fig = TimeSeriesPlot(ds, y="load", by="fuel").build()
    assert len(fig.data) == 2
    names = sorted(t.name for t in fig.data)
    assert names == ["nuclear", "wind"]


def test_build_grouped_uses_palette(ts_df: pl.DataFrame) -> None:
    """Each group gets a distinct color from the palette."""
    from antalens.theme import DARK

    ds = Dataset(ts_df.lazy())
    fig = TimeSeriesPlot(ds, y="load", by="fuel").build()
    colors = [t.line.color for t in fig.data]
    assert colors[0] == DARK.palette_categorical[0]
    assert colors[1] == DARK.palette_categorical[1]


def test_build_grouped_shows_legend(ts_df: pl.DataFrame) -> None:
    ds = Dataset(ts_df.lazy())
    fig = TimeSeriesPlot(ds, y="load", by="fuel").build()
    assert fig.layout.showlegend is True


def test_build_simple_hides_legend(ts_df: pl.DataFrame) -> None:
    ds = Dataset(ts_df.lazy())
    fig = TimeSeriesPlot(ds, y="load").build()
    assert fig.layout.showlegend is False


# ─── build: confidence interval ────────────────────────────────────────────


def test_ci_adds_ribbon_trace(mc_df: pl.DataFrame) -> None:
    ds = Dataset(mc_df.lazy())
    fig = TimeSeriesPlot(ds, y="load", conf_int=0.95).build()
    # Ribbon (fill=toself) + central line = 2 traces
    assert len(fig.data) == 2
    fills = [t.fill for t in fig.data]
    assert "toself" in fills


def test_ci_ribbon_has_translucent_fill(mc_df: pl.DataFrame) -> None:
    """The CI ribbon fill is rgba with alpha < 1."""
    ds = Dataset(mc_df.lazy())
    fig = TimeSeriesPlot(ds, y="load", conf_int=0.95).build()
    ribbon = next(t for t in fig.data if t.fill == "toself")
    assert ribbon.fillcolor.startswith("rgba(")
    # Alpha should be 0.18 (the constant in _add_ci_ribbon)
    assert "0.18" in ribbon.fillcolor


def test_ci_ribbon_does_not_show_in_legend(mc_df: pl.DataFrame) -> None:
    ds = Dataset(mc_df.lazy())
    fig = TimeSeriesPlot(ds, y="load", conf_int=0.95).build()
    ribbon = next(t for t in fig.data if t.fill == "toself")
    assert ribbon.showlegend is False


# ─── build: cumulative ─────────────────────────────────────────────────────


def test_cumulative_produces_monotonic_increasing(ts_df: pl.DataFrame) -> None:
    """Cumulative-mode y values never decrease."""
    ds = Dataset(ts_df.lazy()).filter(fuel="nuclear")
    fig = TimeSeriesPlot(ds, y="load", cumulative=True).build()
    y_values = list(fig.data[0].y)
    for prev, nxt in pairwise(y_values):
        assert nxt >= prev


# ─── reactive integration ──────────────────────────────────────────────────


def test_to_pane_static_has_no_watchers(ts_df: pl.DataFrame) -> None:
    """Non-reactive datasets produce a plain Plotly pane."""
    import panel as pn

    ds = Dataset(ts_df.lazy())
    pane = TimeSeriesPlot(ds, y="load").to_pane()
    # Plain pane wraps a Figure object directly
    assert isinstance(pane, pn.pane.Plotly)


def test_to_pane_reactive_uses_pn_bind(ts_df: pl.DataFrame) -> None:
    """Reactive datasets produce a pane bound via pn.bind."""
    import panel as pn

    ds = Dataset(ts_df.lazy())
    lens = Lens(variable="nuclear")
    # Wire a reactive filter on a column that exists. ``variable`` is a
    # canonical Lens parameter; we map it onto the ``fuel`` column.
    reactive = ds.filter(fuel=lens.param.variable)
    pane = TimeSeriesPlot(reactive, y="load").to_pane()
    assert isinstance(pane, pn.pane.Plotly)


def test_build_reflects_lens_state(ts_df: pl.DataFrame) -> None:
    """When the lens changes, build() returns a fresh figure with new data."""
    # Add an 'area' column for the lens-bound filter
    ts_df_with_area = ts_df.with_columns(
        pl.when(pl.col("fuel") == "nuclear")
        .then(pl.lit("FR"))
        .otherwise(pl.lit("DE"))
        .alias("area")
    )
    ds = Dataset(ts_df_with_area.lazy())
    lens = Lens(area="FR")
    reactive = ds.filter(area=lens)
    plot = TimeSeriesPlot(reactive, y="load")

    fig_fr = plot.build()
    n_points_fr = len(fig_fr.data[0].y)

    lens.area = "DE"
    fig_de = plot.build()
    n_points_de = len(fig_de.data[0].y)

    # Both have the same number of timestamps but different values.
    # FR is nuclear (50-73), DE is wind (30-53). Assert different.
    assert list(fig_fr.data[0].y) != list(fig_de.data[0].y)
    assert n_points_fr == n_points_de  # Same row count


# ─── ds.plot accessor ──────────────────────────────────────────────────────


def test_accessor_returns_pane(ts_df: pl.DataFrame) -> None:
    import panel as pn

    ds = Dataset(ts_df.lazy())
    pane = ds.plot.timeseries("load")
    assert isinstance(pane, pn.pane.Plotly)


def test_accessor_passes_kwargs(ts_df: pl.DataFrame) -> None:
    """conf_int, by, etc. all reach TimeSeriesPlot via the accessor."""
    ds = Dataset(ts_df.lazy())
    pane = ds.plot.timeseries("load", by="fuel")
    fig = pane.object
    assert len(fig.data) == 2  # one per fuel
