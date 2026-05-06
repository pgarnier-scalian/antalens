"""CSS rules injected into Panel's <head> so the dashboard chrome matches
the active :class:`~antalens.theme.PlotlyTheme`.

The plot canvases are themed by Plotly directly. This module covers
everything *around* the plots: the header bar, the sidebar, the page
background, fonts, and the pane card chrome.

Usage::

    from antalens.theme.panel_css import build_dashboard_css
    pn.config.raw_css.append(build_dashboard_css())
"""  # noqa: D205

from __future__ import annotations

from antalens.theme import get_active_theme


def build_dashboard_css() -> str:
    """Return a CSS string matching the currently active theme."""
    t = get_active_theme()
    accent = t.palette_categorical[0]

    return f"""
    body, .bk-root {{
        background: {t.paper_bgcolor};
        color: {t.font_color};
        font-family: {t.font_family};
    }}

    .antalens-header {{
        background: {t.plot_bgcolor};
        border-bottom: 1px solid {t.line_color};
        padding: 12px 20px;
        display: flex;
        align-items: center;
        gap: 16px;
    }}

    .antalens-header h1, .antalens-header h2 {{
        margin: 0;
        font-size: 16px;
        font-weight: 600;
        color: {accent};
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }}

    .antalens-header .subtitle {{
        color: {t.font_color};
        font-size: 12px;
        opacity: 0.7;
    }}

    .antalens-sidebar {{
        background: {t.plot_bgcolor};
        border-right: 1px solid {t.line_color};
        padding: 16px;
        min-width: 220px;
    }}

    .antalens-sidebar .bk-input,
    .antalens-sidebar select {{
        background: {t.paper_bgcolor};
        color: {t.font_color};
        border: 1px solid {t.line_color};
        border-radius: 4px;
    }}

    .antalens-main {{
        padding: 12px;
        background: {t.paper_bgcolor};
    }}

    .antalens-pane {{
        background: {t.plot_bgcolor};
        border: 1px solid {t.line_color};
        border-radius: 6px;
        padding: 8px;
        margin: 6px;
        box-sizing: border-box;
    }}
    """
