"""The :class:`Dashboard` — top-level composable layout for AntaLens.

Wraps Panel's :class:`~panel.layout.FlexBox` so panes can be added,
removed, or reordered at runtime. Every pane has a stable ID returned
by :meth:`Dashboard.add_pane`, usable later for :meth:`remove_pane`,
:meth:`move_pane`, or (in a future iteration) MCP tool calls.

Layout structure
----------------

A Dashboard has three fixed regions:

- **Header**: title and global controls (across the top).
- **Sidebar**: filters and widgets (left side).
- **Main**: a flex-wrapped grid of panes (the rest).

Panes in the main region wrap to fit. Each pane carries a width
percentage (default 50%) — change it with :meth:`set_pane_width` to
make a chart span the full row, or shrink it to fit alongside others.

Lens ownership
--------------

A Dashboard owns one :class:`~antalens.lens.Lens` shared across every
pane. By default a fresh Lens is created; pass an external one via the
``lens=`` kwarg if you've already built one (e.g. when composing
multiple dashboards that share state).

Example::

    from antalens import io
    from antalens.dash import Dashboard
    from antalens.lens import Lens

    ds = io.load_parquet("data.parquet")
    lens = Lens(variable="nuclear")
    reactive = ds.filter(fuel=lens.param.variable)

    dash = Dashboard("Energy 2030")
    dash.lens = lens                     # share the lens
    dash.add_control(picker_widget)
    plot_id = dash.add_pane(
        reactive.plot.timeseries("load"), width_pct=100,
    )
    dash.serve(port=5006)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import panel as pn

from antalens.lens import Lens
from antalens.theme.panel_css import build_dashboard_css

if TYPE_CHECKING:
    pass


@dataclass
class _PaneEntry:
    """Internal record of a pane registered with the dashboard."""

    pane_id: str
    viewable: pn.viewable.Viewable
    width_pct: int  # 25, 33, 50, 67, 75, 100 — flex-basis percentage


class Dashboard:
    """Composable top-level layout for AntaLens applications.

    Args:
        title: Title shown in the header.
        subtitle: Optional secondary line under the title.
        lens: Shared :class:`~antalens.lens.Lens` for all panes. Created
            fresh if not supplied.
    """

    __slots__ = (
        "_controls",
        "_header_extras",
        "_layout_cache",
        "_panes",
        "_status_items",
        "lens",
        "subtitle",
        "title",
    )

    def __init__(
        self,
        title: str,
        *,
        subtitle: str | None = None,
        lens: Lens | None = None,
    ) -> None:
        """Composable top-level layout for AntaLens applications.

        Args:
            title: Title shown in the header.
            subtitle: Optional secondary line under the title.
            lens: Shared :class:`~antalens.lens.Lens` for all panes. Created
                fresh if not supplied.
        """
        self.title = title
        self.subtitle = subtitle
        self.lens: Lens = lens if lens is not None else Lens()
        self._panes: list[_PaneEntry] = []
        self._controls: list[pn.viewable.Viewable] = []
        self._header_extras: list[pn.viewable.Viewable] = []
        self._status_items: list[str] = []
        self._layout_cache: pn.viewable.Viewable | None = None

    # ── pane management ───────────────────────────────────────────────────

    def add_pane(
        self,
        viewable: pn.viewable.Viewable,
        *,
        width_pct: int = 50,
        pane_id: str | None = None,
    ) -> str:
        """Append a pane to the main region.

        Args:
            viewable: Any Panel viewable — typically a plot pane returned
                by ``ds.plot.X(...)``.
            width_pct: Target width as a percentage of the main area.
                Default 50 (two panes per row). Use 100 for full-width.
            pane_id: Optional explicit ID. Auto-generated if omitted.

        Returns:
            The pane's stable ID, usable with :meth:`remove_pane` etc.
        """
        if not 10 <= width_pct <= 100:
            raise ValueError(f"width_pct must be in [10, 100], got {width_pct}")
        pid = pane_id or f"pane-{uuid.uuid4().hex[:8]}"
        if any(p.pane_id == pid for p in self._panes):
            raise ValueError(f"pane_id {pid!r} already exists")
        self._panes.append(_PaneEntry(pid, viewable, width_pct))
        self._invalidate_cache()
        return pid

    def remove_pane(self, pane_id: str) -> None:
        """Remove a pane by ID. Raises ``KeyError`` if not found."""
        for i, p in enumerate(self._panes):
            if p.pane_id == pane_id:
                del self._panes[i]
                self._invalidate_cache()
                return
        raise KeyError(f"no pane with id {pane_id!r}")

    def move_pane(self, pane_id: str, new_index: int) -> None:
        """Move a pane to a different position in the main region."""
        idx = self._index_of(pane_id)
        entry = self._panes.pop(idx)
        self._panes.insert(new_index, entry)
        self._invalidate_cache()

    def set_pane_width(self, pane_id: str, width_pct: int) -> None:
        """Resize a pane's flex-basis percentage."""
        if not 10 <= width_pct <= 100:
            raise ValueError("width_pct must be in [10, 100]")
        idx = self._index_of(pane_id)
        self._panes[idx].width_pct = width_pct
        self._invalidate_cache()

    @property
    def pane_ids(self) -> list[str]:
        """All registered pane IDs in display order."""
        return [p.pane_id for p in self._panes]

    # ── controls and header ───────────────────────────────────────────────

    def add_control(self, widget: pn.viewable.Viewable) -> None:
        """Append a widget to the sidebar."""
        self._controls.append(widget)
        self._invalidate_cache()

    def add_header_widget(self, widget: pn.viewable.Viewable) -> None:
        """Add a widget to the header bar (right side)."""
        self._header_extras.append(widget)
        self._invalidate_cache()

    def add_status_item(self, text: str) -> None:
        """Append a small text item to the bottom status bar.

        Useful for showing always-visible context: "MC YEARS: 30",
        "LIVE", or version strings. Items render in monospace.
        """
        self._status_items.append(text)
        self._invalidate_cache()

    def _build_status_bar(self) -> pn.viewable.Viewable | None:
        """Return the status bar viewable, or None if no items."""
        if not self._status_items:
            return None
        spans = " · ".join(self._status_items)
        return pn.pane.HTML(
            spans,
            css_classes=["antalens-statusbar"],
            sizing_mode="stretch_width",
        )  # type: ignore

    # ── serving and embedding ─────────────────────────────────────────────

    def assemble(self) -> pn.viewable.Viewable:
        """Build (and cache) the Panel layout.

        Called by :meth:`serve` and :meth:`servable`. Public so callers
        can embed the layout in a notebook or larger Panel app.
        """
        import panel as pn

        pn.config.theme = "dark"  # type: ignore
        if self._layout_cache is not None:
            return self._layout_cache

        # Inject theme CSS once per process. Idempotent — Panel
        # deduplicates raw_css strings.
        css = build_dashboard_css()
        if css not in pn.config.raw_css:
            pn.config.raw_css.append(css)

        header = self._build_header()
        sidebar = self._build_sidebar()
        main = self._build_main()

        body = pn.Row(
            sidebar,
            main,
            sizing_mode="stretch_width",
        )
        sections = [header, body]
        status_bar = self._build_status_bar()
        if status_bar is not None:
            sections.append(status_bar)
        layout = pn.Column(
            *sections,
            sizing_mode="stretch_width",
            min_height=800,
        )
        self._layout_cache = layout
        return layout

    def serve(self, *, port: int = 5006, show: bool = True) -> None:
        """Run a Panel server hosting this dashboard.

        Blocks the calling thread. Use :meth:`servable` for embedding
        scenarios where you don't want to block.
        """
        pn.serve(self.assemble(), port=port, show=show)  # type: ignore

    def servable(self) -> pn.viewable.Viewable:
        """Return the layout marked servable for ``panel serve`` CLI."""
        return self.assemble().servable()

    # ── future hooks (stubs) ──────────────────────────────────────────────

    def to_json(self) -> dict[str, Any]:
        """Serialize the dashboard to a JSON-safe dict.

        Not yet implemented — reserved for Phase 2 extension when the
        pane registry has enough metadata to reconstruct.
        """
        raise NotImplementedError("Dashboard.to_json is reserved for a future iteration.")

    # ── internals ─────────────────────────────────────────────────────────

    def _invalidate_cache(self) -> None:
        """Drop the cached layout so the next assemble() rebuilds."""
        self._layout_cache = None

    def _index_of(self, pane_id: str) -> int:
        for i, p in enumerate(self._panes):
            if p.pane_id == pane_id:
                return i
        raise KeyError(f"no pane with id {pane_id!r}")

    def _build_header(self) -> pn.viewable.Viewable:
        title_html = f"<h1>{self.title}</h1>"
        if self.subtitle:
            title_html += f"<span class='subtitle'>{self.subtitle}</span>"

        title_block = pn.pane.HTML(
            title_html,
            css_classes=["antalens-header-title"],
        )  # type: ignore
        extras_block = pn.Row(
            *self._header_extras,
            css_classes=["antalens-header-extras"],
        )
        return pn.Row(
            title_block,
            extras_block,
            css_classes=["antalens-header"],
            sizing_mode="stretch_width",
        )

    def _build_sidebar(self) -> pn.viewable.Viewable:
        return pn.Column(
            *self._controls,
            css_classes=["antalens-sidebar"],
            width=240,
            sizing_mode="stretch_height",
        )

    def _build_main(self) -> pn.viewable.Viewable:
        wrapped = [
            pn.Column(
                p.viewable,
                css_classes=["antalens-pane"],
                width_policy="max",
                sizing_mode="stretch_width",
                styles={"flex": f"1 1 calc({p.width_pct}% - 12px)"},
            )
            for p in self._panes
        ]
        return pn.FlexBox(
            *wrapped,
            css_classes=["antalens-main"],
            sizing_mode="stretch_both",
            flex_wrap="wrap",
        )  # type: ignore
