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

from antalens.plots._base import BasePlot
from antalens.plots.bar import BarPlot
from antalens.plots.timeseries import TimeSeriesPlot

__all__ = ["BarPlot", "BasePlot", "TimeSeriesPlot"]
