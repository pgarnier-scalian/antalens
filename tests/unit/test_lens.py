"""Tests for :class:`antalens.lens.Lens` and binding helpers."""

from __future__ import annotations

from datetime import datetime

import param
import pytest

from antalens.lens import (
    Lens,
    is_reactive,
    normalize_lens_date_range,
    resolve_filter_value,
)

# ─── Lens basics ───────────────────────────────────────────────────────────


def test_lens_defaults() -> None:
    lens = Lens()
    assert lens.area is None
    assert lens.dates is None
    assert lens.variable is None
    assert lens.scenario is None


def test_lens_initial_values_via_kwargs() -> None:
    lens = Lens(area="FR", scenario=0)
    assert lens.area == "FR"
    assert lens.scenario == 0


def test_lens_mutation_works() -> None:
    lens = Lens()
    lens.area = "DE"
    assert lens.area == "DE"


def test_lens_watch_fires_on_change() -> None:
    """A param.watch() callback fires when a parameter changes."""
    lens = Lens()
    received: list[str] = []

    def on_area_change(event: param.parameterized.Event) -> None:
        received.append(event.new)

    lens.param.watch(on_area_change, "area")
    lens.area = "FR"
    lens.area = "DE"

    assert received == ["FR", "DE"]


# ─── with_extras ───────────────────────────────────────────────────────────


def test_with_extras_creates_subclass() -> None:
    HRLens = Lens.with_extras(
        department=param.String(default="engineering"),
        seniority_level=param.String(default=None),  # type: ignore[arg-type]
    )
    lens = HRLens()
    assert lens.department == "engineering"  # type: ignore[attr-defined]
    assert lens.seniority_level is None  # type: ignore[attr-defined]
    # Base parameters still present
    assert lens.area is None
    assert lens.scenario is None


def test_with_extras_subclass_is_lens() -> None:
    Custom = Lens.with_extras(extra=param.String(default="x"))
    lens = Custom()
    assert isinstance(lens, Lens)


def test_with_extras_extra_param_is_reactive() -> None:
    """Watch events fire on extra params too."""
    Custom = Lens.with_extras(extra=param.String(default=None))  # type: ignore[arg-type]
    lens = Custom()
    received: list[str] = []
    lens.param.watch(lambda e: received.append(e.new), "extra")
    lens.extra = "hello"  # type: ignore[attr-defined]
    assert received == ["hello"]


# ─── snapshot ──────────────────────────────────────────────────────────────


def test_snapshot_returns_current_values() -> None:
    lens = Lens(area="FR", scenario=12, variable="LOAD")
    snap = lens.snapshot()
    assert snap == {
        "area": "FR",
        "dates": None,
        "variable": "LOAD",
        "scenario": 12,
    }


def test_snapshot_excludes_param_internal_name() -> None:
    """The auto-added 'name' parameter is omitted from snapshot."""
    lens = Lens()
    assert "name" not in lens.snapshot()


def test_snapshot_includes_extras() -> None:
    Custom = Lens.with_extras(department=param.String(default="eng"))
    lens = Custom()
    assert lens.snapshot()["department"] == "eng"


# ─── resolve_filter_value ──────────────────────────────────────────────────


def test_resolve_static_value_passes_through() -> None:
    current, watched = resolve_filter_value("area", "FR")
    assert current == "FR"
    assert watched is None


def test_resolve_lens_picks_canonical_param() -> None:
    lens = Lens(area="FR")
    current, watched = resolve_filter_value("area", lens)
    assert current == "FR"
    assert watched is lens.param.area


def test_resolve_lens_for_date_range_uses_dates_param() -> None:
    """date_range kwarg binds to lens.dates parameter (rename)."""
    lens = Lens(dates=(datetime(2025, 1, 1), datetime(2025, 1, 7)))
    current, watched = resolve_filter_value("date_range", lens)
    assert current == (datetime(2025, 1, 1), datetime(2025, 1, 7))
    assert watched is lens.param.dates


def test_resolve_explicit_param_reference() -> None:
    lens = Lens(area="DE")
    current, watched = resolve_filter_value("anything", lens.param.area)
    assert current == "DE"
    assert watched is lens.param.area


def test_resolve_lens_unmapped_kwarg_raises() -> None:
    lens = Lens()
    with pytest.raises(ValueError, match="cannot be bound to a Lens directly"):
        resolve_filter_value("custom_col", lens)


# ─── is_reactive ───────────────────────────────────────────────────────────


def test_is_reactive_for_lens() -> None:
    assert is_reactive(Lens())


def test_is_reactive_for_param_reference() -> None:
    lens = Lens()
    assert is_reactive(lens.param.area)


def test_is_reactive_for_static_values() -> None:
    assert not is_reactive("FR")
    assert not is_reactive(["FR", "DE"])
    assert not is_reactive(None)
    assert not is_reactive(42)


# ─── normalize_lens_date_range ─────────────────────────────────────────────


def test_normalize_none_returns_none() -> None:
    assert normalize_lens_date_range(None) is None


def test_normalize_tuple_passes_through() -> None:
    pair = (datetime(2025, 1, 1), datetime(2025, 1, 7))
    assert normalize_lens_date_range(pair) == pair


def test_normalize_rejects_non_tuple() -> None:
    with pytest.raises(TypeError):
        normalize_lens_date_range("2025-01-01")


def test_normalize_rejects_wrong_arity() -> None:
    with pytest.raises(TypeError):
        normalize_lens_date_range((datetime(2025, 1, 1),))
