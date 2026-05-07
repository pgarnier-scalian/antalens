"""Plot builder classes for AntaLens.

Most users access plot builders via the fluent ``ds.plot.X(...)`` accessor
on a :class:`~antalens.data.dataset.Dataset`. The classes themselves are
available here for advanced use cases — subclassing, direct figure access
without Panel wrapping, or bypassing the accessor for clarity.

Example:
    Direct class usage::

        from antalens.plots import TimeSeriesPlot
        plot = TimeSeriesPlot(ds, y="LOAD", conf_int=0.95)
        fig = plot.build()  # raw Plotly figure
        fig.write_html("out.html")
"""

from __future__ import annotations

from collections.abc import Callable

import polars as pl

from antalens.plots._base import BasePlot
from antalens.plots.bar import BarPlot
from antalens.plots.stack import ProductionStack
from antalens.plots.timeseries import TimeSeriesPlot

__all__ = [
    "BarPlot",
    "BasePlot",
    "ProductionStack",
    "TimeSeriesPlot",
    "pipe",
]


def pipe(fn: Callable[[pl.LazyFrame], pl.LazyFrame]) -> Callable[[pl.LazyFrame], pl.LazyFrame]:
    """Apply a transformation function to a LazyFrame.

    This is a pipeline primitive for composing data transformations.
    It's equivalent to ``fn(lf)`` but enables fluent chaining.

    Args:
        fn: A callable taking a LazyFrame and returning a transformed LazyFrame.

    Returns:
        The same function for chaining.

    Example:
        >>> from antalens.plots import pipe
        >>> def filter_rows(lf):
        ...     return lf.filter(pl.col("value") > 0)
        >>> lf.pipe(filter_rows)  # doctest: +SKIP
    """
    return fn
