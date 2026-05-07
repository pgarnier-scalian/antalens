"""Domain catalogs — YAML-driven metadata for GEMS data.

A Catalog holds domain semantics for GEMS data: component naming
patterns, output display metadata, color palettes, and stack templates.
"""

from __future__ import annotations

from antalens.catalog.catalog import (
    Catalog,
    ColorPalette,
    ComponentPattern,
    OutputMetadata,
    StackTemplateConfig,
)


def empty() -> Catalog:
    """Return an empty catalog.

    Returns a Catalog with no component patterns, outputs, palettes,
    or stack templates.

    Returns:
        An empty Catalog instance.
    """
    return Catalog()


__all__ = [
    "Catalog",
    "ColorPalette",
    "ComponentPattern",
    "OutputMetadata",
    "StackTemplateConfig",
    "empty",
    "load_catalog",
]


def load_catalog(path: str) -> Catalog:
    """Load a catalog from a YAML file.

    .. deprecated:: 0.2.0
        This function is a placeholder for Phase 2 implementation.
        Use :meth:`Catalog.from_yaml` directly instead.

    Args:
        path: Path to a YAML catalog file.

    Returns:
        A Catalog instance.

    Raises:
        NotImplementedError: Always raised as this is a Phase 2 placeholder.
    """
    raise NotImplementedError(
        "load_catalog is a Phase 2 placeholder. Use Catalog.from_yaml('path.yaml') instead."
    )
