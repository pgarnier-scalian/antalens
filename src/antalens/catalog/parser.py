"""Public ``load_catalog`` function.

A thin wrapper over :meth:`Catalog.from_yaml`. Exists so users can write
``al.catalog.load_catalog(path)`` matching the spec's public API, while
the actual parsing logic lives on the :class:`Catalog` class itself.
"""

from __future__ import annotations

from pathlib import Path

from antalens.catalog import Catalog

PathLike = str | Path


def load_catalog(path: PathLike) -> Catalog:
    """Load a catalog from a YAML file.

    Thin delegate to :meth:`Catalog.from_yaml`. Provided for API
    symmetry with :func:`antalens.io.load_parquet`,
    :func:`antalens.io.load_simulation_table`, etc.

    Args:
        path: Path to a YAML catalog file.

    Returns:
        A :class:`Catalog` instance.

    Raises:
        FileNotFoundError: If the YAML file doesn't exist.
        yaml.YAMLError: If the file is malformed.
    """
    return Catalog.from_yaml(path)
