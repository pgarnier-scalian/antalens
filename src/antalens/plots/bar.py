"""The :class:`BarPlot` — categorical aggregation of a numeric variable.

Used to compare a numeric measure across categories: average load by
fuel type, total emissions by area, peak demand by month. Supports
sorting (ascending, descending, or none) and orientation (vertical or
horizontal).

Example:
    Mean load by fuel::

        ds.plot.bar(x="fuel", y="load", agg="mean")

    Top-10 areas by total emissions, horizontal::

        ds.plot.bar(x="area", y="co2", agg="sum",
                    sort="desc", orientation="h")
"""

from __future__ import annotations

from typing import Literal

import plotly.graph_objects as go
import polars as pl

from antalens.data.dataset import Dataset
from antalens.plots._base import BasePlot, assert_column_exists
from antalens.theme import get_active_theme

# Aggregation function names. Subset of polars-supported operations.
BarAgg = Literal["mean", "sum", "min", "max", "median", "count"]
BarSort = Literal["asc", "desc"]
BarOrientation = Literal["v", "h"]


class BarPlot(BasePlot):
    """Build a categorical bar chart from a Dataset.

    Args:
        dataset: The :class:`~antalens.data.dataset.Dataset` to plot.
        x: Categorical column for the bar axis.
        y: Numeric column to aggregate.
        agg: Aggregation function. Default ``"mean"``.
        sort: Bar ordering. ``"asc"`` / ``"desc"`` to sort by the
            aggregated y-value; ``None`` keeps source order.
        orientation: ``"v"`` (default) for vertical bars, ``"h"`` for
            horizontal (useful for many categories or long labels).
        title: Optional figure title. Defaults to the dataset name +
            ``f"{agg}({y}) by {x}"``.

    Raises:
        ValueError: If ``x`` or ``y`` references a column not in the
            dataset.
    """

    __slots__ = ("agg", "orientation", "sort", "title", "x", "y")

    def __init__(
        self,
        dataset: Dataset,
        x: str,
        y: str,
        *,
        agg: BarAgg = "mean",
        sort: BarSort | None = None,
        orientation: BarOrientation = "v",
        title: str | None = None,
    ) -> None:
        """Build a categorical bar chart from a Dataset.

        Args:
            dataset: The :class:`~antalens.data.dataset.Dataset` to plot.
            x: Categorical column for the bar axis.
            y: Numeric column to aggregate.
            agg: Aggregation function. Default ``"mean"``.
            sort: Bar ordering. ``"asc"`` / ``"desc"`` to sort by the
                aggregated y-value; ``None`` keeps source order.
            orientation: ``"v"`` (default) for vertical bars, ``"h"`` for
                horizontal (useful for many categories or long labels).
            title: Optional figure title. Defaults to the dataset name +
                ``f"{agg}({y}) by {x}"``.

        Raises:
            ValueError: If ``x`` or ``y`` references a column not in the
                dataset.
        """
        super().__init__(dataset)
        assert_column_exists(dataset, x, role="x")
        assert_column_exists(dataset, y, role="y")
        if sort is not None and sort not in ("asc", "desc"):
            raise ValueError(f"sort must be 'asc', 'desc', or None; got {sort!r}")
        if orientation not in ("v", "h"):
            raise ValueError(f"orientation must be 'v' or 'h'; got {orientation!r}")
        self.x = x
        self.y = y
        self.agg = agg
        self.sort = sort
        self.orientation = orientation
        self.title = title

    def build(self) -> go.Figure:
        """Construct the Plotly figure."""
        df = self.dataset.to_dataframe()
        agg_df = self._aggregate(df)
        theme = get_active_theme()
        color = theme.palette_categorical[0]

        # In horizontal mode, x and y axes are swapped at the trace level.
        if self.orientation == "v":
            x_data, y_data = agg_df[self.x].to_list(), agg_df["__agg"].to_list()
            xaxis_title, yaxis_title = self.x, f"{self.agg}({self.y})"
        else:
            x_data, y_data = agg_df["__agg"].to_list(), agg_df[self.x].to_list()
            xaxis_title, yaxis_title = f"{self.agg}({self.y})", self.x

        fig = go.Figure(
            go.Bar(
                x=x_data,
                y=y_data,
                orientation=self.orientation,
                marker={"color": color},
                hovertemplate="%{label}: %{value:.2f}<extra></extra>",
            )
        )
        fig.update_layout(
            title={
                "text": self.title or self._default_title(),
                "x": 0.0,
                "xanchor": "left",
                "font": {"size": 13},
            },
            xaxis_title=xaxis_title,
            yaxis_title=yaxis_title,
            showlegend=False,
        )
        return self.apply_theme(fig)

    # ── internals ─────────────────────────────────────────────────────────

    def _aggregate(self, df: pl.DataFrame) -> pl.DataFrame:
        """Group by ``x``, apply ``agg`` to ``y``, optionally sort."""
        agg_expr = self._agg_expr().alias("__agg")
        result = df.group_by(self.x).agg(agg_expr)
        if self.sort == "asc":
            result = result.sort("__agg")
        elif self.sort == "desc":
            result = result.sort("__agg", descending=True)
        return result

    def _agg_expr(self) -> pl.Expr:
        col = pl.col(self.y)
        match self.agg:
            case "mean":
                return col.mean()
            case "sum":
                return col.sum()
            case "min":
                return col.min()
            case "max":
                return col.max()
            case "median":
                return col.median()
            case "count":
                return col.count()

    def _default_title(self) -> str:
        base = f"{self.agg}({self.y}) by {self.x}"
        if self.dataset.name:
            return f"{self.dataset.name} · {base}"
        return base
