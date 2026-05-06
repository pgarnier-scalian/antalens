"""Tests for :class:`antalens.dash.dashboard.Dashboard`."""

from __future__ import annotations

import panel as pn
import pytest

from antalens.dash import Dashboard
from antalens.lens import Lens


@pytest.fixture
def empty_dash() -> Dashboard:
    return Dashboard(title="Test")


@pytest.fixture
def sample_pane() -> pn.viewable.Viewable:
    return pn.pane.Markdown("hello")  # type: ignore


# ─── construction ──────────────────────────────────────────────────────────


def test_default_lens_is_created() -> None:
    dash = Dashboard(title="X")
    assert isinstance(dash.lens, Lens)


def test_external_lens_is_used() -> None:
    lens = Lens(variable="foo")
    dash = Dashboard(title="X", lens=lens)
    assert dash.lens is lens


def test_subtitle_optional() -> None:
    assert Dashboard(title="X").subtitle is None
    assert Dashboard(title="X", subtitle="Y").subtitle == "Y"


# ─── add / remove / move panes ─────────────────────────────────────────────


def test_add_pane_returns_id(empty_dash: Dashboard, sample_pane: pn.viewable.Viewable) -> None:
    pid = empty_dash.add_pane(sample_pane)
    assert isinstance(pid, str)
    assert pid in empty_dash.pane_ids


def test_add_pane_with_explicit_id(
    empty_dash: Dashboard, sample_pane: pn.viewable.Viewable
) -> None:
    pid = empty_dash.add_pane(sample_pane, pane_id="my-pane")
    assert pid == "my-pane"


def test_duplicate_id_raises(empty_dash: Dashboard, sample_pane: pn.viewable.Viewable) -> None:
    empty_dash.add_pane(sample_pane, pane_id="x")
    with pytest.raises(ValueError, match="already exists"):
        empty_dash.add_pane(sample_pane, pane_id="x")


def test_invalid_width_raises(empty_dash: Dashboard, sample_pane: pn.viewable.Viewable) -> None:
    with pytest.raises(ValueError, match="width_pct"):
        empty_dash.add_pane(sample_pane, width_pct=5)
    with pytest.raises(ValueError, match="width_pct"):
        empty_dash.add_pane(sample_pane, width_pct=200)


def test_remove_pane(empty_dash: Dashboard, sample_pane: pn.viewable.Viewable) -> None:
    pid = empty_dash.add_pane(sample_pane)
    empty_dash.remove_pane(pid)
    assert pid not in empty_dash.pane_ids


def test_remove_unknown_id_raises(empty_dash: Dashboard) -> None:
    with pytest.raises(KeyError):
        empty_dash.remove_pane("nope")


def test_move_pane_reorders(empty_dash: Dashboard, sample_pane: pn.viewable.Viewable) -> None:
    a = empty_dash.add_pane(pn.pane.Markdown("a"), pane_id="a")  # type: ignore
    b = empty_dash.add_pane(pn.pane.Markdown("b"), pane_id="b")  # type: ignore
    c = empty_dash.add_pane(pn.pane.Markdown("c"), pane_id="c")  # type: ignore
    assert empty_dash.pane_ids == [a, b, c]
    empty_dash.move_pane("c", 0)
    assert empty_dash.pane_ids == [c, a, b]


def test_set_pane_width_updates(empty_dash: Dashboard, sample_pane: pn.viewable.Viewable) -> None:
    pid = empty_dash.add_pane(sample_pane, width_pct=50)
    empty_dash.set_pane_width(pid, 100)
    # Width is internal state — we just need to confirm it didn't error
    # and the pane is still registered.
    assert pid in empty_dash.pane_ids


def test_set_pane_width_invalid_raises(
    empty_dash: Dashboard, sample_pane: pn.viewable.Viewable
) -> None:
    pid = empty_dash.add_pane(sample_pane)
    with pytest.raises(ValueError):
        empty_dash.set_pane_width(pid, 5)


# ─── controls and header ───────────────────────────────────────────────────


def test_add_control_appends(empty_dash: Dashboard) -> None:
    widget = pn.widgets.Select(options=["a", "b"])  # type: ignore
    empty_dash.add_control(widget)
    assert widget in empty_dash._controls


def test_add_header_widget_appends(empty_dash: Dashboard) -> None:
    widget = pn.widgets.Button(name="export")  # type: ignore
    empty_dash.add_header_widget(widget)
    assert widget in empty_dash._header_extras


# ─── assemble / cache ──────────────────────────────────────────────────────


def test_assemble_returns_viewable(
    empty_dash: Dashboard, sample_pane: pn.viewable.Viewable
) -> None:
    empty_dash.add_pane(sample_pane)
    layout = empty_dash.assemble()
    assert isinstance(layout, pn.viewable.Viewable)


def test_assemble_is_cached(empty_dash: Dashboard, sample_pane: pn.viewable.Viewable) -> None:
    empty_dash.add_pane(sample_pane)
    layout1 = empty_dash.assemble()
    layout2 = empty_dash.assemble()
    assert layout1 is layout2


def test_cache_invalidated_after_add(
    empty_dash: Dashboard, sample_pane: pn.viewable.Viewable
) -> None:
    empty_dash.add_pane(sample_pane)
    layout1 = empty_dash.assemble()
    empty_dash.add_pane(pn.pane.Markdown("new"))  # type: ignore
    layout2 = empty_dash.assemble()
    assert layout1 is not layout2


def test_servable_returns_viewable(
    empty_dash: Dashboard, sample_pane: pn.viewable.Viewable
) -> None:
    empty_dash.add_pane(sample_pane)
    assert isinstance(empty_dash.servable(), pn.viewable.Viewable)


def test_to_json_not_implemented(empty_dash: Dashboard) -> None:
    with pytest.raises(NotImplementedError):
        empty_dash.to_json()
