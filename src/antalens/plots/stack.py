"""The :class:`ProductionStack` — stacked-area chart with template-based palette.

The marquee chart of AntaLens. Used to display generation mix, dispatch
profiles, and any composition that decomposes a total over time by an
ordered set of categories.

Three features distinguish this from a generic stacked-area chart:

1. **Template-based palette** — categories pick up canonical colors and
   ordering from a :class:`~antalens.theme.stack_templates.StackTemplate`,
   keeping every chart visually consistent.
2. **Negative layers** — categories marked ``side="negative"`` (battery
   charging, exports, pumped storage) render below the zero line.
3. **Optional load overlay** — a separate line plotted on top of the
   stack, for the classic "demand vs. generation" view.

Example::

    ds.plot.stack(stack_by="fuel", y="output_mw", template="eco2mix",
                  load="load_mw")

    # Custom template
    ds.plot.stack(
        stack_by="component",
        y="value",
        template={"unit_a": "#6366f1", "unit_b": "#34d399"},
    )
"""

from __future__ import annotations

import warnings
from typing import Any, Literal

import plotly.graph_objects as go
import polars as pl

from antalens.data.dataset import Dataset
from antalens.plots._base import BasePlot, EventExtractor, assert_column_exists
from antalens.theme import get_active_theme
from antalens.theme.stack_templates import StackTemplate, get_template

StackAgg = Literal["sum", "mean"]
"""How to collapse multiple rows per ``(time, category)`` before stacking."""


class ProductionStack(BasePlot):
    """Build a stacked-area production chart.

    Args:
        dataset: The :class:`~antalens.data.dataset.Dataset` to plot.
        stack_by: Column whose distinct values become stacked layers
            (typically ``"fuel"`` or ``"component"``).
        y: Numeric column whose values are stacked. Defaults to
            ``"value"`` to match LP solver output conventions.
        template: A :class:`StackTemplate`, a registered template name,
            or a ``{category: color}`` dict. Defaults to ``"eco2mix"``.
        load: Optional column name to overlay as a line on top of the
            stack. Common pattern: stack generation by fuel, overlay
            total demand.
        agg: How to aggregate multiple rows sharing the same
            ``(time, category)``. ``"sum"`` (default) for production
            ("total nuclear" = sum across reactors). ``"mean"`` for
            ensemble averages.
        title: Optional figure title.

    Raises:
        ValueError: If columns are missing, the dataset has no time
            column, or the template is unresolvable.
    """

    __slots__ = ("agg", "load", "stack_by", "template", "title", "y")

    def __init__(
        self,
        dataset: Dataset,
        *,
        stack_by: str,
        y: str = "value",
        template: StackTemplate | dict[str, str] | str = "eco2mix",
        load: str | None = None,
        agg: StackAgg = "sum",
        title: str | None = None,
    ) -> None:
        """Build a stacked-area production chart.

        Args:
            dataset: The :class:`~antalens.data.dataset.Dataset` to plot.
            stack_by: Column whose distinct values become stacked layers
                (typically ``"fuel"`` or ``"component"``).
            y: Numeric column whose values are stacked. Defaults to
                ``"value"`` to match LP solver output conventions.
            template: A :class:`StackTemplate`, a registered template name,
                or a ``{category: color}`` dict. Defaults to ``"eco2mix"``.
            load: Optional column name to overlay as a line on top of the
                stack. Common pattern: stack generation by fuel, overlay
                total demand.
            agg: How to aggregate multiple rows sharing the same
                ``(time, category)``. ``"sum"`` (default) for production
                ("total nuclear" = sum across reactors). ``"mean"`` for
                ensemble averages.
            title: Optional figure title.

        Raises:
            ValueError: If columns are missing, the dataset has no time
                column, or the template is unresolvable.
        """
        super().__init__(dataset)
        assert_column_exists(dataset, stack_by, role="stack_by")
        assert_column_exists(dataset, y, role="y")
        if load is not None:
            assert_column_exists(dataset, load, role="load")
        if dataset.schema.time_col is None:
            raise ValueError(
                "ProductionStack requires a time column. Pass time_col= when loading the dataset."
            )

        self.stack_by = stack_by
        self.y = y
        self.template = get_template(template)
        self.load = load
        self.agg = agg
        self.title = title

    def build(self) -> go.Figure:
        """Builds the stack and returns it."""
        df = self.dataset.to_dataframe()
        time_col = self.dataset.schema.time_col
        assert time_col is not None  # checked in __init__

        # Pivot to wide format: one column per category, indexed by time.
        # We aggregate (time, category) → single value before stacking.
        pivoted = self._aggregate_and_pivot(df, time_col)

        fig = go.Figure()
        self._add_stack_traces(fig, pivoted, time_col)
        if self.load is not None:
            self._add_load_overlay(fig, df, time_col)

        fig.update_layout(
            title={
                "text": self.title or self._default_title(),
                "x": 0.0,
                "xanchor": "left",
                "font": {"size": 13},
            },
            xaxis_title=None,
            yaxis_title=self.y,
            hovermode="x unified",
            showlegend=True,
            legend={"orientation": "h", "y": -0.15, "x": 0},
        )
        return self.apply_theme(fig)

    def event_extractors(self) -> dict[str, EventExtractor]:
        """Expose ``xrange_select`` and ``legend_click``."""
        return {
            "xrange_select": _extract_xrange_select,
            "legend_click": _extract_legend_click,
        }

    # ── internals ─────────────────────────────────────────────────────────

    def _aggregate_and_pivot(self, df: pl.DataFrame, time_col: str) -> pl.DataFrame:
        """Aggregate ``(time, stack_by) → y`` and pivot to wide format.

        Returns a DataFrame with ``time_col`` as index plus one column
        per category present in the data. Categories not in the template
        are dropped (with a warning).
        """
        present_categories = set(df[self.stack_by].unique().to_list())
        template_categories = set(self.template.categories())
        unknown = present_categories - template_categories
        if unknown:
            warnings.warn(
                f"ProductionStack: dropped {len(unknown)} categories not in "
                f"template {self.template.name!r}: {sorted(unknown)!r}. "
                f"Add them to the template or use a custom one.",
                stacklevel=3,
            )

        agg_expr = pl.col(self.y).sum() if self.agg == "sum" else pl.col(self.y).mean()
        long = (
            df.filter(pl.col(self.stack_by).is_in(list(template_categories)))
            .group_by([time_col, self.stack_by])
            .agg(agg_expr.alias("__y"))
        )
        wide = long.pivot(on=self.stack_by, index=time_col, values="__y").sort(time_col)
        return wide.fill_null(0.0)

    def _add_stack_traces(self, fig: go.Figure, pivoted: pl.DataFrame, time_col: str) -> None:
        """Add one stacked-area trace per template layer present in data."""
        x = pivoted[time_col].to_list()
        # Iterate template order — bottom-to-top stacking.
        for layer in self.template.layers:
            if layer.category not in pivoted.columns:
                continue  # category absent from data, skip
            y_values = pivoted[layer.category].to_list()
            # Negative layers get negated values so they render below zero.
            if layer.side == "negative":
                y_values = [-v for v in y_values]

            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y_values,
                    name=layer.category,
                    mode="lines",
                    line={"width": 0},
                    fill="tonexty",
                    fillcolor=_hex_with_alpha(layer.color, 0.7),
                    stackgroup=layer.side,  # separates positive/negative stacks
                    hovertemplate=f"%{{y:.1f}}<extra>{layer.category}</extra>",
                )
            )

    def _add_load_overlay(self, fig: go.Figure, df: pl.DataFrame, time_col: str) -> None:
        """Overlay a line plot of ``self.load`` on top of the stack."""
        load_df = (
            df.group_by(time_col).agg(pl.col(self.load).first().alias("__load")).sort(time_col)  # type: ignore
        )
        theme = get_active_theme()
        fig.add_trace(
            go.Scatter(
                x=load_df[time_col].to_list(),
                y=load_df["__load"].to_list(),
                name=self.load,
                mode="lines",
                line={"color": theme.font_color, "width": 1.5},
                hovertemplate=f"%{{y:.1f}}<extra>{self.load}</extra>",
            )
        )

    def _default_title(self) -> str:
        base = f"production stack · {self.template.name}"
        if self.dataset.name:
            return f"{self.dataset.name} · {base}"
        return base


# ─── helpers ────────────────────────────────────────────────────────────────


def _hex_with_alpha(hex_color: str, alpha: float) -> str:
    """Convert a hex color to ``rgba(...)`` for Plotly fill colors."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return hex_color
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _extract_xrange_select(event: Any) -> tuple[Any] | None:
    """Extract the (start, end) range from a Plotly box-select on x."""
    if not event:
        return None
    rng = event.get("range") or event.get("xaxis.range")
    if isinstance(rng, dict):
        rng = rng.get("x") or rng.get("xaxis")
    if isinstance(rng, list | tuple) and len(rng) == 2:
        return tuple(rng)
    return None


def _extract_legend_click(event: Any) -> str | None:
    """Extract the trace name from a Plotly legend click event."""
    if not event or "points" not in event:
        return None
    points = event.get("points", [])
    if not points:
        return None
    return points[0].get("name") or points[0].get("legendgroup")  # type: ignore
