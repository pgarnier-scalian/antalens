"""Catalog YAML parser (stub for Phase 2)."""

from __future__ import annotations


def parse_catalog_yaml(*args: object, **kwargs: object) -> None:
    """Parse a catalog YAML file.

    .. deprecated:: 0.2.0
        This function is a placeholder for Phase 2 implementation.
        Use :meth:`Catalog.from_yaml` directly instead.

    Raises:
        NotImplementedError: Always raised.
    """
    raise NotImplementedError(
        "parse_catalog_yaml is a Phase 2 placeholder. Use Catalog.from_yaml('path.yaml') instead."
    )


__all__ = ["parse_catalog_yaml"]
