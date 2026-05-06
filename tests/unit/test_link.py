"""Tests for :func:`antalens.link.link`."""

from __future__ import annotations

from datetime import datetime, timedelta

import panel as pn
import polars as pl
import pytest

from antalens.data.dataset import Dataset
from antalens.lens import Lens
from antalens.link import link


@pytest.fixture
def bar_df() -> pl.DataFrame:
    return pl.DataFrame({"fuel": ["nuclear", "wind", "gas"], "load": [50.0, 30.0, 80.0]})


@pytest.fixture
def ts_df() -> pl.DataFrame:
    start = datetime(2025, 1, 1)
    return pl.DataFrame(
        {
            "ts": [start + timedelta(hours=h) for h in range(24)],
            "load": [50.0 + h for h in range(24)],
        }
    )


# ─── argument validation ───────────────────────────────────────────────────


def test_set_must_be_param_parameter(bar_df: pl.DataFrame) -> None:
    ds = Dataset(bar_df.lazy())
    pane = ds.plot.bar(x="fuel", y="load")
    with pytest.raises(TypeError, match=r"param.Parameter"):
        link(pane, on="bar_click", set="not-a-param")  # type: ignore[arg-type]


def test_unknown_event_raises(bar_df: pl.DataFrame) -> None:
    ds = Dataset(bar_df.lazy())
    lens = Lens()
    pane = ds.plot.bar(x="fuel", y="load")
    with pytest.raises(ValueError, match="not exposed"):
        link(pane, on="not_a_real_event", set=lens.param.variable)


def test_pane_without_source_plot_raises() -> None:
    """A Panel pane not built by AntaLens has no event vocabulary."""
    raw_pane = pn.pane.Markdown("hello")  # type: ignore
    lens = Lens()
    with pytest.raises(TypeError, match="not built by an AntaLens plot"):
        link(raw_pane, on="bar_click", set=lens.param.variable)


# ─── event extractors ──────────────────────────────────────────────────────


def test_bar_click_extracts_x_for_vertical(bar_df: pl.DataFrame) -> None:
    """For vertical bars the category lives in points[0].x."""
    ds = Dataset(bar_df.lazy())
    plot_obj = ds.plot.bar(x="fuel", y="load")._antalens_plot
    extractor = plot_obj.event_extractors()["bar_click"]
    assert extractor({"points": [{"x": "nuclear", "y": 50.0}]}) == "nuclear"


def test_bar_click_extracts_y_for_horizontal(bar_df: pl.DataFrame) -> None:
    """For horizontal bars the category lives in points[0].y."""
    ds = Dataset(bar_df.lazy())
    plot_obj = ds.plot.bar(x="fuel", y="load", orientation="h")._antalens_plot
    extractor = plot_obj.event_extractors()["bar_click"]
    assert extractor({"points": [{"x": 50.0, "y": "nuclear"}]}) == "nuclear"


def test_bar_click_returns_none_on_empty(bar_df: pl.DataFrame) -> None:
    ds = Dataset(bar_df.lazy())
    plot_obj = ds.plot.bar(x="fuel", y="load")._antalens_plot
    extractor = plot_obj.event_extractors()["bar_click"]
    assert extractor(None) is None
    assert extractor({}) is None
    assert extractor({"points": []}) is None


def test_timeseries_point_click_extracts_x(ts_df: pl.DataFrame) -> None:
    ds = Dataset(ts_df.lazy())
    plot_obj = ds.plot.timeseries("load")._antalens_plot
    extractor = plot_obj.event_extractors()["point_click"]
    payload = {"points": [{"x": "2025-01-01T05:00", "y": 55.0}]}
    assert extractor(payload) == "2025-01-01T05:00"


def test_timeseries_xrange_select_extracts_range(ts_df: pl.DataFrame) -> None:
    ds = Dataset(ts_df.lazy())
    plot_obj = ds.plot.timeseries("load")._antalens_plot
    extractor = plot_obj.event_extractors()["xrange_select"]
    payload = {"range": {"x": ["2025-01-01T00:00", "2025-01-01T12:00"]}}
    assert extractor(payload) == ("2025-01-01T00:00", "2025-01-01T12:00")


def test_xrange_select_returns_none_on_unusable(ts_df: pl.DataFrame) -> None:
    ds = Dataset(ts_df.lazy())
    plot_obj = ds.plot.timeseries("load")._antalens_plot
    extractor = plot_obj.event_extractors()["xrange_select"]
    assert extractor(None) is None
    assert extractor({}) is None


# ─── end-to-end watcher firing ─────────────────────────────────────────────


def test_link_assigns_to_lens_on_event(bar_df: pl.DataFrame) -> None:
    """Simulate a Plotly click_data update; verify the lens picks it up."""
    ds = Dataset(bar_df.lazy())
    lens = Lens()
    pane = ds.plot.bar(x="fuel", y="load")
    link(pane, on="bar_click", set=lens.param.variable)

    # Trigger by setting click_data on the underlying Plotly pane —
    # this fires the param.watch we registered.
    pane.click_data = {"points": [{"x": "wind", "y": 30.0}]}
    assert lens.variable == "wind"


def test_link_with_transform(bar_df: pl.DataFrame) -> None:
    ds = Dataset(bar_df.lazy())
    lens = Lens()
    pane = ds.plot.bar(x="fuel", y="load")
    link(
        pane,
        on="bar_click",
        set=lens.param.variable,
        transform=lambda v: v.upper(),
    )
    pane.click_data = {"points": [{"x": "wind", "y": 30.0}]}
    assert lens.variable == "WIND"


def test_link_skips_when_extractor_returns_none(bar_df: pl.DataFrame) -> None:
    """No assignment if the extractor returns None."""
    ds = Dataset(bar_df.lazy())
    lens = Lens(variable="initial")
    pane = ds.plot.bar(x="fuel", y="load")
    link(pane, on="bar_click", set=lens.param.variable)

    pane.click_data = {"points": []}  # extractor returns None
    assert lens.variable == "initial"


def test_link_skips_when_transform_returns_none(bar_df: pl.DataFrame) -> None:
    ds = Dataset(bar_df.lazy())
    lens = Lens(variable="initial")
    pane = ds.plot.bar(x="fuel", y="load")
    link(pane, on="bar_click", set=lens.param.variable, transform=lambda v: None)

    pane.click_data = {"points": [{"x": "wind", "y": 30.0}]}
    assert lens.variable == "initial"
