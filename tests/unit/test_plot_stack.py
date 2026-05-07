"""Tests for :class:`antalens.plots.stack.ProductionStack`."""

from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl
import pytest

from antalens.data.dataset import Dataset
from antalens.plots.stack import ProductionStack
from antalens.theme.stack_templates import (
    StackLayer,
    StackTemplate,
    get_template,
)

BASE_TEMPLATE = StackTemplate.from_dict({"solar": "#64748b", "wind": "#0ea5e9", "gas": "#f59e0b"})

PARTIAL_TEMPLATE = StackTemplate.from_dict({"solar": "#64748b"})


@pytest.fixture
def fuel_df() -> pl.DataFrame:
    """3 days x 3 fuels — minimal stack input."""
    start = datetime(2025, 1, 1)
    rows = []
    for h in range(72):
        ts = start + timedelta(hours=h)
        rows.append({"ts": ts, "fuel": "solar", "value": 50.0})
        rows.append({"ts": ts, "fuel": "wind", "value": 20.0 + (h % 5)})
        rows.append({"ts": ts, "fuel": "gas", "value": 30.0 - (h % 7)})
    return pl.DataFrame(rows)


# ─── template resolution ──────────────────────────────────────────────────


def test_get_template_by_name() -> None:
    # Test dict-based creation produces generic template
    t = get_template({"solar": "#64748b", "wind": "#0ea5e9", "gas": "#f59e0b"})
    assert t.name == "custom"
    assert len(t.layers) == 3


def test_get_template_by_instance() -> None:
    t = get_template(BASE_TEMPLATE)
    assert t is BASE_TEMPLATE


def test_get_template_from_dict() -> None:
    t = get_template({"a": "#ff0000", "b": "#00ff00"})
    assert t.name == "custom"
    assert len(t.layers) == 2
    assert t.color_of("a") == "#ff0000"


def test_get_template_unknown_name_raises() -> None:
    with pytest.raises(KeyError, match="unknown stack template"):
        get_template("not_a_real_template")


def test_template_categories_filter_by_side() -> None:
    t = StackTemplate(
        name="t",
        layers=(
            StackLayer("a", "#fff", side="positive"),
            StackLayer("b", "#000", side="negative"),
        ),
    )
    assert t.categories() == ["a", "b"]
    assert t.categories(side="positive") == ["a"]
    assert t.categories(side="negative") == ["b"]


# ─── construction ─────────────────────────────────────────────────────────


def test_constructs_with_minimum_args(fuel_df: pl.DataFrame) -> None:
    ds = Dataset(fuel_df.lazy())
    plot = ProductionStack(ds, stack_by="fuel", y="value")
    # Default is an empty dict template
    assert plot.template.name == "custom"
    assert len(plot.template.layers) == 0


def test_rejects_missing_stack_by(fuel_df: pl.DataFrame) -> None:
    ds = Dataset(fuel_df.lazy())
    with pytest.raises(ValueError, match="stack_by"):
        ProductionStack(ds, stack_by="missing", y="value")


def test_rejects_missing_y(fuel_df: pl.DataFrame) -> None:
    ds = Dataset(fuel_df.lazy())
    with pytest.raises(ValueError, match="y='missing'"):
        ProductionStack(ds, stack_by="fuel", y="missing")


def test_rejects_dataset_without_time_col() -> None:
    df = pl.DataFrame({"fuel": ["a", "b"], "value": [1.0, 2.0]})
    ds = Dataset(df.lazy())
    with pytest.raises(ValueError, match="requires a time column"):
        ProductionStack(ds, stack_by="fuel", y="value")


# ─── build: traces ────────────────────────────────────────────────────────


def test_build_one_trace_per_template_category_present(
    fuel_df: pl.DataFrame,
) -> None:
    ds = Dataset(fuel_df.lazy())
    fig = ProductionStack(ds, stack_by="fuel", y="value").build()
    # Three fuels in data with default template → 3 traces.
    trace_names = [t.name for t in fig.data]
    assert set(trace_names) == {"solar", "wind", "gas"}


def test_build_respects_template_order(fuel_df: pl.DataFrame) -> None:
    """Traces are emitted in template order, not data order."""
    ds = Dataset(fuel_df.lazy())
    fig = ProductionStack(ds, stack_by="fuel", y="value", template=BASE_TEMPLATE).build()
    trace_names = [t.name for t in fig.data]
    # Template order: solar, wind, gas (as defined in BASE_TEMPLATE)
    assert trace_names == ["solar", "wind", "gas"]


def test_unknown_categories_emit_warning() -> None:
    """Warning is emitted when using a partial template."""
    df = pl.DataFrame(
        {
            "ts": [datetime(2025, 1, 1, h) for h in range(3)],
            "fuel": ["solar", "fictional_fuel", "solar"],
            "value": [10.0, 20.0, 30.0],
        }
    )
    ds = Dataset(df.lazy())
    # Use partial template that only includes "solar"
    with pytest.warns(UserWarning, match="dropped 1 categories"):
        ProductionStack(ds, stack_by="fuel", y="value", template=PARTIAL_TEMPLATE).build()


def test_negative_layers_use_negative_stackgroup() -> None:
    """Storage (negative side) should be in a different stackgroup."""
    df = pl.DataFrame(
        {
            "ts": [datetime(2025, 1, 1, h) for h in range(3)],
            "fuel": ["solar", "storage", "solar"],
            "value": [50.0, 10.0, 50.0],
        }
    )
    ds = Dataset(df.lazy())
    # Use a template with negative side defined
    neg_template = StackTemplate(
        name="neg-test",
        layers=(
            StackLayer("solar", "#64748b", side="positive"),
            StackLayer("storage", "#000000", side="negative"),
        ),
    )
    fig = ProductionStack(ds, stack_by="fuel", y="value", template=neg_template).build()
    solar_trace = next(t for t in fig.data if t.name == "solar")
    storage_trace = next(t for t in fig.data if t.name == "storage")
    assert solar_trace.stackgroup == "positive"
    assert storage_trace.stackgroup == "negative"


def test_load_overlay_adds_extra_trace(fuel_df: pl.DataFrame) -> None:
    """Specifying load= adds an extra non-stacked line trace."""
    df = fuel_df.with_columns(pl.lit(120.0).alias("demand"))
    ds = Dataset(df.lazy())
    fig = ProductionStack(ds, stack_by="fuel", y="value", load="demand").build()
    load_trace = next(t for t in fig.data if t.name == "demand")
    assert load_trace.stackgroup is None  # not part of the stack
    assert load_trace.fill is None or load_trace.fill == "none"


# ─── accessor wiring ──────────────────────────────────────────────────────


def test_accessor_returns_pane(fuel_df: pl.DataFrame) -> None:
    import panel as pn

    ds = Dataset(fuel_df.lazy())
    # Use explicit template to avoid any template resolution issues
    pane = ds.plot.stack(stack_by="fuel", y="value", template=BASE_TEMPLATE)
    assert isinstance(pane, pn.pane.Plotly)
