"""The ``Dataset.plot`` accessor — fluent entry point for plot builders.

Users access plot builders via ``dataset.plot.timeseries(...)`` etc.
Each accessor method instantiates the corresponding plot builder class
and returns a Panel pane ready to display or embed.

The accessor pattern keeps the chain fluent: ``ds.filter(...).plot.timeseries(...)``
flows naturally and matches user expectation. The underlying classes
(:class:`~antalens.plots.timeseries.TimeSeriesPlot` etc.) remain
available for advanced subclassing.

A note on imports: this module is loaded lazily from
:class:`~antalens.data.dataset.Dataset` to avoid a circular import
(``Dataset → PlotAccessor → TimeSeriesPlot → BasePlot → Dataset``). The
:func:`get_plot_accessor` factory defers the import until first access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import panel as pn

    from antalens.data.dataset import Dataset


class PlotAccessor:
    """The ``ds.plot`` namespace — methods that build plots from a Dataset.

    Returned by :attr:`Dataset.plot`. Each method instantiates the
    corresponding plot builder class with the bound dataset plus the
    user's parameters, then returns the resulting Panel pane.

    Args:
        dataset: The :class:`~antalens.data.dataset.Dataset` this
            accessor is bound to. User code never instantiates this
            directly — it's created by :attr:`Dataset.plot`.
    """

    __slots__ = ("_dataset",)

    def __init__(self, dataset: Dataset) -> None:
        """The ds.plot namespace — methods that build plots from a Dataset.

        Returned by :attrDataset.plot. Each method instantiates the
        corresponding plot builder class with the bound dataset plus the
        user's parameters, then returns the resulting Panel pane.

        Args:
            dataset: The :class~antalens.data.dataset.Dataset this
                accessor is bound to. User code never instantiates this
                directly — it's created by :attrDataset.plot.
        """
        self._dataset = dataset

    def timeseries(
        self,
        y: str,
        *,
        by: str | None = None,
        conf_int: float | None = None,
        cumulative: bool = False,
        title: str | None = None,
        **pane_kwargs: Any,
    ) -> pn.viewable.Viewable:
        """Build a time-series line chart.

        Wraps :class:`~antalens.plots.timeseries.TimeSeriesPlot`. See
        that class for parameter semantics.

        Args:
            y: Numeric column to plot on the y-axis.
            by: Optional categorical column for grouping into multiple lines.
            conf_int: Optional confidence-interval level in ``(0, 1)``.
            cumulative: When ``True``, plot running sum.
            title: Optional figure title.
            **pane_kwargs: Forwarded to :class:`panel.pane.Plotly` (for
                ``sizing_mode``, ``height``, etc).

        Returns:
            A Panel pane. Reactive if the bound dataset has a Lens.
        """
        from antalens.plots.timeseries import TimeSeriesPlot

        plot = TimeSeriesPlot(
            self._dataset,
            y,
            by=by,
            conf_int=conf_int,
            cumulative=cumulative,
            title=title,
        )
        return plot.to_pane(**pane_kwargs)

    def bar(
        self,
        x: str,
        y: str,
        *,
        agg: str = "mean",
        sort: str | None = None,
        orientation: str = "v",
        title: str | None = None,
        **pane_kwargs: Any,
    ) -> pn.viewable.Viewable:
        """Build a categorical bar chart.

        Wraps :class:`~antalens.plots.bar.BarPlot`. See that class for
        parameter semantics.
        """
        from antalens.plots.bar import BarPlot

        plot = BarPlot(
            self._dataset,
            x,
            y,
            agg=agg,  # type: ignore[arg-type]
            sort=sort,  # type: ignore[arg-type]
            orientation=orientation,  # type: ignore[arg-type]
            title=title,
        )
        return plot.to_pane(**pane_kwargs)

    def stack(
        self,
        *,
        stack_by: str,
        y: str = "value",
        template: Any = "base",
        load: str | None = None,
        agg: str = "sum",
        title: str | None = None,
        **pane_kwargs: Any,
    ) -> pn.viewable.Viewable:
        """Build a stacked-area production chart.

        Wraps :class:`~antalens.plots.stack.ProductionStack`. See that
        class for parameter semantics.
        """
        from antalens.plots.stack import ProductionStack

        plot = ProductionStack(
            self._dataset,
            stack_by=stack_by,
            y=y,
            template=template,
            load=load,
            agg=agg,  # type: ignore[arg-type]
            title=title,
        )
        return plot.to_pane(**pane_kwargs)
