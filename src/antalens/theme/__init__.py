"""Visual theming for AntaLens plots.

A :class:`PlotlyTheme` holds the palette and layout defaults applied
to every Plotly figure built by AntaLens. Two themes ship out of the
box: :data:`DARK` (the default — dark industrial aesthetic suited to
operational dashboards) and :data:`LIGHT` (white background, suited to
publications and exports).

The currently active theme is a process-wide singleton accessed via
:func:`get_active_theme` and changed via :func:`set_active`. Users who
want a custom theme construct a :class:`PlotlyTheme` and pass it to
:func:`set_active`.

Example:
    Switch to the light theme for a publication export::

        import antalens as al
        al.theme.set_active(al.theme.LIGHT)
        fig = study.plot.timeseries("LOAD").build()
        fig.write_image("report.png")
"""

from __future__ import annotations

from dataclasses import dataclass, field

from antalens.theme.stack_templates import (
    BASE,
    ECO2MIX,
    StackLayer,
    StackTemplate,
    get_template,
    register_template,
)

__all__ = [
    "BASE",
    "ECO2MIX",
    "StackLayer",
    "StackTemplate",
    "get_template",
    "register_template",
]


@dataclass(frozen=True, slots=True)
class PlotlyTheme:
    """Plotly figure layout defaults applied by every AntaLens plot.

    Frozen so themes can't be mutated by accident. To customize, build
    a new instance and pass it to :func:`set_active`.

    Attributes:
        paper_bgcolor: Background color of the figure as a whole.
        plot_bgcolor: Background color of the plotting area inside axes.
        font_family: Font family for all text.
        font_color: Default text color.
        grid_color: Color of axis grid lines.
        line_color: Color of axis lines and zero lines.
        palette_categorical: Default colors for discrete series. Used in
            order for legend items, fuel types, etc.
        palette_continuous: List of ``(stop, color)`` tuples for
            continuous color scales (heatmaps, choropleths).
        margin: Plotly margin dict ``{"l", "r", "t", "b"}``.
    """

    paper_bgcolor: str
    plot_bgcolor: str
    font_family: str
    font_color: str
    grid_color: str
    line_color: str
    palette_categorical: tuple[str, ...]
    palette_continuous: tuple[tuple[float, str], ...]
    margin: dict[str, int] = field(default_factory=lambda: {"l": 48, "r": 14, "t": 32, "b": 36})


# ─── built-in themes ────────────────────────────────────────────────────────


DARK = PlotlyTheme(
    paper_bgcolor="#0b0d0f",
    plot_bgcolor="#111418",
    font_family="IBM Plex Sans, -apple-system, sans-serif",
    font_color="#9dafc0",
    grid_color="#1f252c",
    line_color="#2a3240",
    palette_categorical=(
        "#00c9a7",  # teal
        "#0091ff",  # blue
        "#f59e0b",  # amber
        "#6366f1",  # indigo
        "#34d399",  # green
        "#fb7185",  # rose
        "#a855f7",  # purple
        "#fbbf24",  # yellow
    ),
    palette_continuous=(
        (0.0, "#0b1929"),
        (0.3, "#0c3460"),
        (0.6, "#0091ff"),
        (0.8, "#00c9a7"),
        (1.0, "#fbbf24"),
    ),
)


LIGHT = PlotlyTheme(
    paper_bgcolor="#ffffff",
    plot_bgcolor="#fafafa",
    font_family="IBM Plex Sans, -apple-system, sans-serif",
    font_color="#1f2937",
    grid_color="#e5e7eb",
    line_color="#9ca3af",
    palette_categorical=(
        "#0d9488",
        "#2563eb",
        "#d97706",
        "#4f46e5",
        "#059669",
        "#dc2626",
        "#9333ea",
        "#ca8a04",
    ),
    palette_continuous=(
        (0.0, "#f1f5f9"),
        (0.3, "#bae6fd"),
        (0.6, "#0091ff"),
        (0.8, "#0d9488"),
        (1.0, "#dc2626"),
    ),
)


# ─── active theme ──────────────────────────────────────────────────────────


_active: PlotlyTheme = DARK


def get_active_theme() -> PlotlyTheme:
    """Return the currently active :class:`PlotlyTheme`."""
    return _active


def set_active(theme: PlotlyTheme) -> None:
    """Set the process-wide active theme.

    Args:
        theme: The theme to activate. Subsequent calls to
            :meth:`~antalens.plots._base.BasePlot.apply_theme` use this.

    Examples:
        >>> import antalens.theme as t
        >>> t.set_active(t.LIGHT)
        >>> t.get_active_theme() is t.LIGHT
        True
        >>> t.set_active(t.DARK)
    """
    global _active
    _active = theme
