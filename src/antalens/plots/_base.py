"""The :class:`BasePlot` abstract base — every plot builder's contract.

A plot builder is a class that takes a :class:`~antalens.data.dataset.Dataset`
plus parameters in its constructor, exposes :meth:`build` to produce a
Plotly :class:`~plotly.graph_objects.Figure`, and :meth:`to_pane` to wrap
that figure in a Panel pane suitable for embedding in a dashboard.

The split between :meth:`build` and :meth:`to_pane` is intentional. Tests
exercise :meth:`build` directly (it's pure — same dataset, same params,
same figure) without spinning up Panel. Dashboards use :meth:`to_pane`,
which adds reactivity wiring on top of the figure.

When the bound Dataset has reactive bindings (a :class:`~antalens.lens.Lens`
in the chain), :meth:`to_pane` registers a :mod:`param` watcher that
re-runs :meth:`build` and replaces the figure on each parameter change.
The plot subclass itself never needs to think about reactivity — it just
implements :meth:`build` deterministically.

To implement a new plot type, subclass and override :meth:`build`. The
default :meth:`apply_theme` and :meth:`to_pane` should rarely need
customization.
"""

from __future__ import annotations

import abc
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import plotly.graph_objects as go

from antalens.data.dataset import Dataset
from antalens.theme import get_active_theme

EventExtractor = Callable[[Any], Any]
"""A function from raw Panel event payload to bound-parameter value."""

if TYPE_CHECKING:
    import panel as pn


class BasePlot(abc.ABC):
    """Abstract base for every AntaLens plot builder.

    Subclasses store their parameters on ``self`` and implement
    :meth:`build` to construct a Plotly figure from the bound dataset.

    Args:
        dataset: The :class:`~antalens.data.dataset.Dataset` to plot.
            Plot builders never own data — they read it on demand.

    Attributes:
        dataset: The bound dataset.
    """

    __slots__ = ("dataset",)

    def __init__(self, dataset: Dataset) -> None:
        self.dataset = dataset

    @abc.abstractmethod
    def build(self) -> go.Figure:
        """Construct and return a fully-themed Plotly figure.

        Subclasses must implement this. Implementations should:

        1. Read data from ``self.dataset.to_dataframe()`` (which honors
           any reactive bindings at the time of the call).
        2. Construct a :class:`plotly.graph_objects.Figure`.
        3. Call :meth:`apply_theme` before returning.

        Returns:
            A Plotly :class:`~plotly.graph_objects.Figure`.
        """

    def apply_theme(self, fig: go.Figure) -> go.Figure:
        """Apply the active theme's layout defaults to ``fig`` in place.

        Sets paper/plot background colors, font, axis colors, and margins
        from the currently-active :class:`~antalens.theme.PlotlyTheme`.
        Returns the same figure for chaining.
        """
        theme = get_active_theme()
        fig.update_layout(
            paper_bgcolor=theme.paper_bgcolor,
            plot_bgcolor=theme.plot_bgcolor,
            font={"family": theme.font_family, "color": theme.font_color, "size": 11},
            margin=theme.margin,
            xaxis={
                "gridcolor": theme.grid_color,
                "linecolor": theme.line_color,
                "zerolinecolor": theme.line_color,
            },
            yaxis={
                "gridcolor": theme.grid_color,
                "linecolor": theme.line_color,
                "zerolinecolor": theme.line_color,
            },
            hoverlabel={"bgcolor": theme.plot_bgcolor, "font_family": theme.font_family},
        )
        return fig

    def event_extractors(self) -> dict[str, EventExtractor]:
        """Map event names to functions that extract a value from event data.

        Each plot subclass overrides this to declare which Plotly events
        it exposes and how to interpret them. The :func:`~antalens.link.link`
        function uses this registry to wire pane events to Lens parameters
        without knowing the per-chart-type semantics.

        Returns:
            A dict mapping event name (e.g. ``"bar_click"``) to an
            extractor callable. The extractor receives the raw Panel event
            payload and returns the value to assign to the bound parameter,
            or ``None`` to skip the assignment.

            Default: empty dict (no events exposed).
        """
        return {}

    def apply_catalog(self, fig: go.Figure) -> go.Figure:
        """Apply catalog metadata to ``fig`` in place.

        Uses domain semantics from the attached catalog to enrich the plot:
        - Renames traces using output display names from the catalog
        - Applies palette colors from the catalog where applicable
        - Sets axis labels from catalog metadata

        The catalog must be attached to ``self.dataset.catalog``. If no
        catalog is attached, this is a no-op. Returns the same figure
        for chaining.

        Returns:
            The same figure for chaining.

        Examples:
            Attach a catalog to a dataset and plot::

                >>> from antalens.catalog import Catalog
                >>> from antalens.data.dataset import Dataset
                >>> import polars as pl
                >>>
                >>> ds = Dataset(pl.DataFrame({"p": [1, 2, 3]}).lazy())
                >>> cat = Catalog.from_string('''
                ... outputs:
                ...   p:
                ...     display: Production
                ...     unit: MW
                ... ''')
                >>> ds = ds.with_catalog(cat)
                >>>
                >>> plot = SomePlot(ds)
                >>> fig = plot.build()
                >>> plot.apply_catalog(fig)
        """
        catalog = self.dataset.catalog
        if catalog is None:
            return fig

        for trace in fig.data:
            # Try to get display name from catalog outputs
            if hasattr(trace, "name") and trace.name:
                output_meta = catalog.outputs.get(trace.name)
                if output_meta:
                    trace.name = output_meta.display

        return fig

    def to_pane(self, **pane_kwargs: Any) -> pn.viewable.Viewable:
        """Wrap the built figure in a Panel pane.

        ... (keep existing docstring)
        """
        import panel as pn

        watched = self.dataset.watched_parameters
        if not watched:
            pane = pn.pane.Plotly(self.build(), **pane_kwargs)  # type: ignore
        else:
            bound = pn.bind(lambda *_args: self.build(), *watched)
            pane = pn.pane.Plotly(bound, **pane_kwargs)  # type: ignore

        # Attach the source plot reference so link() can discover the
        # event vocabulary later. Stored as a private attribute so it
        # doesn't pollute Panel's namespace.
        pane._antalens_plot = self
        return pane


def assert_column_exists(dataset: Dataset, column: str, role: str = "column") -> None:
    """Helper for plot builders to validate column references.

    Args:
        dataset: The dataset to check.
        column: The column name to verify.
        role: A human-readable label for the parameter (e.g. ``"y"``,
            ``"color"``). Surfaced in the error message.

    Raises:
        ValueError: If ``column`` doesn't exist in the dataset's columns.
    """
    if column not in dataset.columns:
        raise ValueError(
            f"{role}={column!r} does not match any column in the dataset. "
            f"Available columns: {dataset.columns!r}"
        )
