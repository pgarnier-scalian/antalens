"""Lightweight UI helpers for building deliberate-looking dashboards.

These aren't widgets — they're visual primitives. Use them to mark
sidebar sections, label control groups, or add small bits of structure
that make a dashboard feel like a product instead of a wireframe.

Example::

    from antalens.dash.components import SectionTitle

    dash.add_control(SectionTitle("Filters"))
    dash.add_control(area_picker)
    dash.add_control(SectionTitle("Aggregation"))
    dash.add_control(timestep_picker)
"""

from __future__ import annotations

import panel as pn


def SectionTitle(text: str) -> pn.viewable.Viewable:
    """Render a small uppercase section title for sidebar grouping.

    Styled via the ``antalens-section-title`` CSS class declared in
    :mod:`antalens.theme.panel_css`.

    Args:
        text: The title text. Typically 1-4 words.
    """
    return pn.pane.HTML(
        f"<div class='antalens-section-title'>{text}</div>",
        margin=(8, 0, 4, 0),
    )  # type: ignore
