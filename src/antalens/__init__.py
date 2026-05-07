"""AntaLens — interactive scientific visualization engine.

AntaLens provides domain-agnostic visualization primitives for tabular
and time-series data, with a YAML-driven catalog layer for domain semantics.

Public API:
    Data loaders:    :mod:`antalens.io`
    Plot builders:   :mod:`antalens.plot`
    Dashboard:       :mod:`antalens.dash`
    Catalogs:        :mod:`antalens.catalog`
    Themes:          :mod:`antalens.theme`
    Maps:            :mod:`antalens.maps`
    Links:           :func:`antalens.link`

Core classes:
    :class:`Dataset` — Universal data container
    :class:`Catalog` — YAML domain metadata

Examples:
    Load data and create a plot::

        import antalens as al

        ds = al.io.load_parquet("output.parquet")
        fig = ds.plot.timeseries("production").build()
"""

from __future__ import annotations

from typing import Any

__version__ = "0.0.1"

__all__ = [
    # Core classes
    "Catalog",
    "ColorPalette",
    "ComponentPattern",
    "Dataset",
    "Lens",
    "OutputMetadata",
    "SimulationTable",
    "StackTemplateConfig",
    "Views",
    "__version__",
    "catalog",
    "controls",
    "dash",
    # Module namespaces
    "io",
    "legacy",
    "link",
    # Catalog loading
    "load_catalog",
    "map",
    "plot",
    "theme",
]

# Import catalog symbols for convenience
from antalens.catalog import (
    Catalog,
    ColorPalette,
    ComponentPattern,
    OutputMetadata,
    StackTemplateConfig,
    load_catalog,
)

# Import core class symbols
from antalens.data.dataset import Dataset
from antalens.data.simulation_table import SimulationTable
from antalens.data.views import Views
from antalens.lens import Lens


# Lazy import for submodules
def __getattr__(name: str) -> Any:
    if name == "io":
        import antalens.io

        return antalens.io
    elif name == "plot":
        import antalens.plots

        return antalens.plots
    elif name == "map":
        import antalens.maps

        return antalens.maps
    elif name == "dash":
        import antalens.dash

        return antalens.dash
    elif name == "controls":
        import antalens.controls

        return antalens.controls
    elif name == "catalog":
        import antalens.catalog

        return antalens.catalog
    elif name == "theme":
        import antalens.theme

        return antalens.theme
    elif name == "legacy":
        import antalens.legacy

        return antalens.legacy
    elif name == "link":
        import antalens.link
        from antalens.link import link

        return link
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
