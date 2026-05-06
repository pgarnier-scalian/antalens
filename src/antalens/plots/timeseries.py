"""The :class:`TimeSeriesPlot` — line chart of one or more variables over time.

Used for displaying any time-indexed numeric variable: load curves, prices,
emissions, sensor readings. Supports three optional features:

- **Grouping** via ``by=``: split into multiple lines colored by a
  categorical column (e.g. one line per fuel type).
- **Confidence interval** via ``conf_int=``: shade a percentile band
  around the central line (Monte Carlo ensembles, statistical forecasts).
- **Cumulative** via ``cumulative=True``: plot the running sum rather
  than the raw series.

Example:
    Basic usage::

        ds.plot.timeseries("LOAD")

    With grouping::

        ds.plot.timeseries("output_mw", by="fuel")

    With confidence interval (assumes ``ds`` has multiple MC realizations
    aggregated into a column with the variable name)::

        ds.plot.timeseries("LOAD", conf_int=0.95)
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import polars as pl

from antalens.data.dataset import Dataset
from antalens.plots._base import BasePlot, EventExtractor, assert_column_exists
from antalens.theme import get_active_theme


class TimeSeriesPlot(BasePlot):
    """Build a time-series line chart from a Dataset.

    Args:
        dataset: The :class:`~antalens.data.dataset.Dataset` to plot.
        y: The numeric column to plot on the y-axis.
        by: Optional categorical column. When set, splits the data into
            one line per distinct value, colored by the active theme's
            categorical palette.
        conf_int: Optional confidence-interval level in ``(0, 1)``.
            When set and the dataset has multiple observations per
            timestamp (e.g. one per MC year), draws a shaded band of
            the corresponding percentile range. ``0.95`` produces a
            band from the 2.5th to 97.5th percentile.
        cumulative: When ``True``, plot the running sum of ``y`` instead
            of the raw series.
        title: Optional figure title. Defaults to the dataset name + ``y``.

    Raises:
        ValueError: If ``y`` or ``by`` references a column not in the
            dataset, or if ``conf_int`` is not in ``(0, 1)``.
    """

    __slots__ = ("by", "conf_int", "cumulative", "title", "y")

    def __init__(
        self,
        dataset: Dataset,
        y: str,
        *,
        by: str | None = None,
        conf_int: float | None = None,
        cumulative: bool = False,
        title: str | None = None,
    ) -> None:
        """Build a time-series line chart from a Dataset.

        Args:
            dataset: The :class~antalens.data.dataset.Dataset to plot.
            y: The numeric column to plot on the y-axis.
            by: Optional categorical column. When set, splits the data into
                one line per distinct value, colored by the active theme's
                categorical palette.

            conf_int: Optional confidence-interval level in (0, 1).
                When set and the dataset has multiple observations per
                imestamp (e.g. one per MC year), draws a shaded band of
                the corresponding percentile range. 0.95 produces a
                band from the 2.5th to 97.5th percentile.
            cumulative: When True, plot the running sum of y instead
                of the raw series.
            title: Optional figure title. Defaults to the dataset name + y.

        Raises:
            ValueError: If y or by references a column not in the
                dataset, or if conf_int is not in (0, 1).
        """
        super().__init__(dataset)

        assert_column_exists(dataset, y, role="y")
        if by is not None:
            assert_column_exists(dataset, by, role="by")

        if conf_int is not None and not (0.0 < conf_int < 1.0):
            raise ValueError(
                f"conf_int must be a level in the open interval (0, 1), "
                f"got {conf_int!r}. For 95% interval, pass 0.95."
            )

        if dataset.schema.time_col is None:
            raise ValueError(
                "TimeSeriesPlot requires a time column on the dataset's "
                "schema. Pass time_col= when loading the data."
            )

        self.y = y
        self.by = by
        self.conf_int = conf_int
        self.cumulative = cumulative
        self.title = title

    def build(self) -> go.Figure:
        """Construct the Plotly figure."""
        df = self.dataset.to_dataframe()
        time_col = self.dataset.schema.time_col
        # mypy: time_col is not None — checked in __init__.
        assert time_col is not None
        theme = get_active_theme()

        fig = go.Figure()

        if self.by is not None:
            self._add_grouped_traces(fig, df, time_col, theme.palette_categorical)
        else:
            self._add_single_trace(fig, df, time_col, theme.palette_categorical[0])

        # Title falls back to dataset name + y column name.
        title = self.title or self._default_title()
        fig.update_layout(
            title={"text": title, "x": 0.0, "xanchor": "left", "font": {"size": 13}},
            xaxis_title=None,
            yaxis_title=self.y,
            hovermode="x unified",
            showlegend=self.by is not None,
        )
        return self.apply_theme(fig)

    def event_extractors(self) -> dict[str, EventExtractor]:
        """Expose ``point_click`` and ``xrange_select``.

        - ``point_click``: emits the clicked x value (a timestamp).
        - ``xrange_select``: emits a ``(start, end)`` tuple of timestamps.
        """
        return {
            "point_click": _extract_point_click_x,
            "xrange_select": _extract_xrange_select,
        }

    # ── trace construction ─────────────────────────────────────────────────

    def _add_single_trace(
        self,
        fig: go.Figure,
        df: pl.DataFrame,
        time_col: str,
        color: str,
    ) -> None:
        """Add one line (no grouping)."""
        x, y = self._series_xy(df, time_col)

        if self.conf_int is not None:
            self._add_ci_ribbon(fig, df, time_col, color)

        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines",
                line={"color": color, "width": 1.5},
                name=self.y,
                hovertemplate=f"%{{y:.2f}}<extra>{self.y}</extra>",
            )
        )

    def _add_grouped_traces(
        self,
        fig: go.Figure,
        df: pl.DataFrame,
        time_col: str,
        palette: tuple[str, ...],
    ) -> None:
        """Add one line per distinct value of ``self.by``."""
        # mypy: by is not None — caller checks.
        assert self.by is not None
        # Use polars to get distinct values in stable order
        groups = df[self.by].unique().sort().to_list()

        for i, group in enumerate(groups):
            color = palette[i % len(palette)]
            sub = df.filter(pl.col(self.by) == group).sort(time_col)
            x, y = self._series_xy(sub, time_col)
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode="lines",
                    line={"color": color, "width": 1.5},
                    name=str(group),
                    hovertemplate=f"%{{y:.2f}}<extra>{group}</extra>",
                )
            )

    def _add_ci_ribbon(
        self,
        fig: go.Figure,
        df: pl.DataFrame,
        time_col: str,
        color: str,
    ) -> None:
        """Add a shaded confidence interval band.

        Computes percentile bounds across rows sharing the same timestamp.
        For datasets without repeated timestamps (no MC ensemble), the
        upper and lower bounds collapse onto the central line and the
        ribbon is invisible — semantically correct, visually a no-op.
        """
        # mypy: conf_int is not None — caller checks.
        assert self.conf_int is not None
        alpha = (1 - self.conf_int) / 2  # e.g. 0.025 for 95% CI
        bounds = (
            df.group_by(time_col)
            .agg(
                pl.col(self.y).quantile(alpha).alias("__lower"),
                pl.col(self.y).quantile(1 - alpha).alias("__upper"),
            )
            .sort(time_col)
        )

        x_band = bounds[time_col].to_list() + bounds[time_col].reverse().to_list()
        y_band = bounds["__upper"].to_list() + bounds["__lower"].reverse().to_list()
        # Convert hex color to a translucent rgba for the fill.
        fill_color = _hex_to_rgba(color, alpha=0.18)

        fig.add_trace(
            go.Scatter(
                x=x_band,
                y=y_band,
                fill="toself",
                fillcolor=fill_color,
                line={"width": 0},
                mode="lines",
                hoverinfo="skip",
                showlegend=False,
                name=f"{int(self.conf_int * 100)}% CI",
            )
        )

    # ── helpers ────────────────────────────────────────────────────────────

    def _series_xy(self, df: pl.DataFrame, time_col: str) -> tuple[list[Any], list[Any]]:
        """Extract the x (time) and y (value) series, applying cumulative."""
        sub = df.sort(time_col)
        x = sub[time_col].to_list()
        y_series = sub[self.y]
        if self.cumulative:
            y_series = y_series.cum_sum()
        return x, y_series.to_list()

    def _default_title(self) -> str:
        """Construct a default title from dataset name and y column."""
        if self.dataset.name:
            return f"{self.dataset.name} · {self.y}"
        return self.y


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convert ``#rrggbb`` to ``rgba(r,g,b,a)`` for Plotly fill colors."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        # Fallback for theme entries that aren't 6-digit hex — return as-is
        # and let Plotly handle (it accepts named colors etc.)
        return hex_color
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _extract_point_click_x(event: Any) -> Any:
    """Extract the x coordinate from a Plotly point click event."""
    if not event or "points" not in event:
        return None
    points = event["points"]
    if not points:
        return None
    return points[0].get("x")


def _extract_xrange_select(event: Any) -> tuple[Any] | None:
    """Extract the (start, end) range from a Plotly box-select on x.

    Returns None if the event isn't a usable range select.
    """
    if not event:
        return None
    rng = event.get("range") or event.get("xaxis.range")
    if not rng:
        return None
    if isinstance(rng, dict):
        rng = rng.get("x") or rng.get("xaxis")
    if isinstance(rng, list | tuple) and len(rng) == 2:
        return tuple(rng)
    return None
