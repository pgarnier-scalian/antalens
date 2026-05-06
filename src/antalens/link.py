"""The :func:`link` function — wire pane events to :class:`Lens` parameters.

Click a bar, brush a timeseries, click a map node — any of those events
can mutate a parameter on a shared :class:`~antalens.lens.Lens`, which
in turn re-renders every other pane bound to that parameter.

The mechanics: each :class:`~antalens.plots._base.BasePlot` subclass
declares its event vocabulary via :meth:`event_extractors`. :func:`link`
looks up the extractor for the requested event, registers a Panel
watcher on the pane's corresponding ``param.Parameter``, parses each
event with the extractor, and assigns the result to the target lens
parameter.

Example::

    from antalens.link import link
    from antalens.lens import Lens

    lens = Lens()
    bar_pane = ds.plot.bar(x="fuel", y="load")
    ts_pane = ds.filter(fuel=lens.param.variable).plot.timeseries("load")

    link(bar_pane, on="bar_click", set=lens.param.variable)
    # Clicking a bar now updates lens.variable, which updates ts_pane.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import param

if TYPE_CHECKING:
    import panel as pn

    from antalens.plots._base import BasePlot


# Map AntaLens event names to the Panel pane attributes that fire them.
# Each plot subclass declares which events it exposes via
# event_extractors(); we map those declarations to the underlying Panel
# parameter so we know what to watch.
_EVENT_TO_PANEL_PARAM: dict[str, str] = {
    "point_click": "click_data",
    "bar_click": "click_data",
    "xrange_select": "selected_data",
    "yrange_select": "selected_data",
    "box_select": "selected_data",
    "lasso_select": "selected_data",
    "cell_click": "click_data",
    "legend_click": "click_data",
    "node_click": "click_data",
    "link_click": "click_data",
    "region_click": "click_data",
}


def link(
    pane: pn.viewable.Viewable,
    *,
    on: str,
    set: param.Parameter,
    transform: Callable[[Any], Any] | None = None,
) -> None:
    """Wire a pane event to a :class:`Lens` parameter.

    Args:
        pane: The Panel pane returned by a plot builder. Must have been
            built from an AntaLens plot class so its source plot's event
            vocabulary is discoverable.
        on: Event name. Must be one declared by the plot's
            :meth:`~antalens.plots._base.BasePlot.event_extractors`.
        set: The :mod:`param` parameter to assign to. Typically
            ``lens.param.area`` or similar. Use ``Lens.param.X``, never
            a bare value.
        transform: Optional function applied to the extracted value
            before assignment. Useful for rounding, type conversion, or
            ignoring certain event payloads (return ``None`` to skip).

    Raises:
        ValueError: If ``on`` is not a known event name, or if the
            source plot doesn't expose it.
        TypeError: If ``pane`` wasn't built by an AntaLens plot class
            (no source plot reference), or ``set`` isn't a
            :class:`param.Parameter`.

    Examples:
        Click a bar to filter a timeseries::

            link(bar_pane, on="bar_click", set=lens.param.variable)

        Brush a timeseries to drive a date range::

            link(ts_pane, on="xrange_select", set=lens.param.dates)

        With a transform — round timestamps to whole days::

            link(ts_pane, on="xrange_select", set=lens.param.dates,
                 transform=lambda r: (r[0].date(), r[1].date()))
    """
    if not isinstance(set, param.parameterized.Parameter):
        raise TypeError(
            f"set= must be a param.Parameter (e.g. lens.param.area); got {type(set).__name__}"
        )

    plot = _source_plot(pane)
    extractors = plot.event_extractors()
    if on not in extractors:
        raise ValueError(
            f"event {on!r} not exposed by {type(plot).__name__}. Available: {sorted(extractors)!r}"
        )
    extractor = extractors[on]

    panel_param = _EVENT_TO_PANEL_PARAM.get(on)
    if panel_param is None:
        raise ValueError(
            f"no Panel parameter mapping for event {on!r}. This is an "
            f"internal AntaLens registration gap — file a bug."
        )

    plotly_pane = _underlying_plotly_pane(pane)

    def _on_event(event: param.parameterized.Event) -> None:
        value = extractor(event.new)
        if value is None:
            return
        if transform is not None:
            value = transform(value)
            if value is None:
                return
        owner = set.owner
        if owner is None:
            return
        setattr(owner, set.name, value)

    plotly_pane.param.watch(_on_event, panel_param)


def _source_plot(pane: pn.viewable.Viewable) -> BasePlot:
    """Recover the AntaLens plot that built ``pane``.

    Plot panes carry a ``_antalens_plot`` attribute pointing back to the
    builder. Set during :meth:`BasePlot.to_pane`.
    """
    plot = getattr(pane, "_antalens_plot", None)
    if plot is None:
        raise TypeError(
            "pane was not built by an AntaLens plot — no event vocabulary "
            "available. Pass a pane returned by ds.plot.X(...)."
        )
    return plot  # type: ignore


def _underlying_plotly_pane(pane: pn.viewable.Viewable) -> pn.pane.Plotly:
    """Return the actual :class:`panel.pane.Plotly` carrying the events.

    For static plots the pane *is* the Plotly pane. For reactive plots
    (built via ``pn.bind``), the same is true — pn.bind on a Figure
    returns a Plotly pane whose figure refreshes; events fire on it.
    """
    import panel as pn

    if isinstance(pane, pn.pane.Plotly):
        return pane
    raise TypeError(
        f"expected a panel.pane.Plotly, got {type(pane).__name__}. "
        f"AntaLens plot builders should always produce one."
    )
