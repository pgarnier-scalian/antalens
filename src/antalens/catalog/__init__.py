"""Domain catalogs — YAML-driven metadata for GEMS data.

A Catalog holds domain semantics for GEMS data: component naming
patterns, output display metadata, color palettes, and stack templates.
"""

from __future__ import annotations

from pathlib import Path

from antalens.catalog.catalog import (
    Catalog,
    ColorPalette,
    ComponentPattern,
    OutputMetadata,
    StackTemplateConfig,
)
from antalens.catalog.parser import load_catalog


def empty() -> Catalog:
    """Return an empty catalog.

    Returns a Catalog with no component patterns, outputs, palettes,
    or stack templates.

    Returns:
        An empty Catalog instance.
    """
    return Catalog()


EXAMPLES_DIR = Path(__file__).parent.parent.parent / "catalogs" / "examples"
"""Directory holding bundled example catalogs."""

__all__ = [
    "Catalog",
    "ColorPalette",
    "ComponentPattern",
    "OutputMetadata",
    "StackTemplateConfig",
    "empty",
    "load_catalog",
]
