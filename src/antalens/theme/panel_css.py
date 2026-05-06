"""CSS rules injected into Panel's <head> so the dashboard chrome matches
the active :class:`~antalens.theme.PlotlyTheme`.

The plot canvases are themed by Plotly directly. This module covers
everything *around* the plots: header, sidebar, pane card chrome,
widgets (Select/Button/Slider), scrollbars, and the optional status bar.

Usage::

    from antalens.theme.panel_css import build_dashboard_css
    pn.config.raw_css.append(build_dashboard_css())

Most users don't call this directly — it's invoked automatically by
:meth:`antalens.dash.Dashboard.assemble`.
"""  # noqa: D205

from __future__ import annotations

from antalens.theme import get_active_theme


def build_dashboard_css() -> str:
    """Return a CSS string matching the currently active theme."""
    t = get_active_theme()
    accent = t.palette_categorical[0]
    accent_dim = _hex_with_alpha(accent, 0.15)
    border_strong = _shift(t.line_color, 30)

    return f"""
    /* ─── Reset & typography ─────────────────────────────────────── */
    body, .bk-root {{
        background: {t.paper_bgcolor};
        color: {t.font_color};
        font-family: {t.font_family};
        font-size: 13px;
        margin: 0;
    }}

    /* ─── Header ─────────────────────────────────────────────────── */
    .antalens-header {{
        background: {t.plot_bgcolor};
        border-bottom: 1px solid {t.line_color};
        height: 48px;
        padding: 0 20px;
        display: flex;
        align-items: center;
        gap: 16px;
        flex-shrink: 0;
    }}

    .antalens-header-title {{
        display: flex;
        align-items: center;
        gap: 14px;
    }}

    .antalens-header h1 {{
        margin: 0;
        font-size: 13px;
        font-weight: 500;
        color: {accent};
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }}

    .antalens-header .subtitle {{
        color: {t.font_color};
        font-size: 12px;
        opacity: 0.7;
        padding-left: 14px;
        border-left: 1px solid {t.line_color};
    }}

    .antalens-header-extras {{
        margin-left: auto;
        display: flex;
        align-items: center;
        gap: 8px;
    }}

    /* ─── Sidebar ────────────────────────────────────────────────── */
    .antalens-sidebar {{
        background: {t.plot_bgcolor};
        border-right: 1px solid {t.line_color};
        padding: 16px 14px;
        min-width: 240px;
        max-width: 240px;
    }}

    .antalens-sidebar h3,
    .antalens-sidebar .section-title {{
        font-size: 10px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: {t.font_color};
        opacity: 0.5;
        margin: 14px 0 8px;
    }}

    .antalens-sidebar h3:first-child {{ margin-top: 0; }}

    /* ─── Main area ──────────────────────────────────────────────── */
    .antalens-main {{
        padding: 8px;
        background: {t.paper_bgcolor};
    }}

    /* ─── Pane cards ─────────────────────────────────────────────── */
    .antalens-pane {{
        background: {t.plot_bgcolor};
        border: 1px solid {t.line_color};
        border-radius: 6px;
        padding: 10px 12px;
        margin: 6px;
        box-sizing: border-box;
        transition: border-color 0.15s ease;
    }}

    .antalens-pane:hover {{
        border-color: {border_strong};
    }}

    /* ─── Widgets (Select, Button, etc.) ─────────────────────────── */
    .antalens-sidebar select,
    .antalens-sidebar .bk-input,
    .bk-input.bk-Select select {{
        background: {t.paper_bgcolor};
        color: {t.font_color};
        border: 1px solid {t.line_color};
        border-radius: 4px;
        font-family: {t.font_family};
        font-size: 12px;
        padding: 5px 8px;
    }}

    .antalens-sidebar select:focus,
    .antalens-sidebar .bk-input:focus {{
        outline: none;
        border-color: {accent};
        box-shadow: 0 0 0 2px {accent_dim};
    }}

    .bk-btn-default {{
        background: {t.paper_bgcolor};
        color: {t.font_color};
        border: 1px solid {t.line_color};
        border-radius: 4px;
        font-family: {t.font_family};
        font-size: 11px;
        padding: 5px 12px;
        letter-spacing: 0.04em;
        transition: border-color 0.15s, background 0.15s;
    }}

    .bk-btn-default:hover {{
        border-color: {border_strong};
        background: {t.plot_bgcolor};
    }}

    .bk-btn-primary {{
        background: {accent_dim};
        color: {accent};
        border: 1px solid {accent};
    }}

    /* ─── Status bar ─────────────────────────────────────────────── */
    .antalens-statusbar {{
        background: {t.plot_bgcolor};
        border-top: 1px solid {t.line_color};
        height: 26px;
        padding: 0 16px;
        display: flex;
        align-items: center;
        gap: 18px;
        flex-shrink: 0;
        font-size: 10px;
        color: {t.font_color};
        opacity: 0.6;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        letter-spacing: 0.05em;
    }}

    /* ─── Scrollbars (WebKit) ────────────────────────────────────── */
    ::-webkit-scrollbar {{
        width: 6px;
        height: 6px;
    }}
    ::-webkit-scrollbar-track {{
        background: {t.paper_bgcolor};
    }}
    ::-webkit-scrollbar-thumb {{
        background: {t.line_color};
        border-radius: 3px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: {border_strong};
    }}
    """


# ─── color helpers ──────────────────────────────────────────────────────────


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert ``#rrggbb`` to ``(r, g, b)`` integers."""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex_with_alpha(hex_color: str, alpha: float) -> str:
    """Return an ``rgba(r, g, b, alpha)`` string from a hex color."""
    if not hex_color.startswith("#") or len(hex_color) != 7:
        return hex_color
    r, g, b = _hex_to_rgb(hex_color)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _shift(hex_color: str, amount: int) -> str:
    """Lighten a hex color by ``amount`` (-255..255). Negative darkens."""
    if not hex_color.startswith("#") or len(hex_color) != 7:
        return hex_color
    r, g, b = _hex_to_rgb(hex_color)
    r = max(0, min(255, r + amount))
    g = max(0, min(255, g + amount))
    b = max(0, min(255, b + amount))
    return f"#{r:02x}{g:02x}{b:02x}"
