"""Data layer — Dataset, SimulationTable, Views.

This package contains the data abstractions that power AntaLens:

- :class:`~antalens.data.dataset.Dataset` — Universal data container
- :class:`~antalens.data.simulation_table.SimulationTable` — GEMS raw outputs
- :class:`~antalens.data.views.Views` — GEMS curated outputs
- :class:`~antalens.data.schema.Schema` — Schema inference
"""

from __future__ import annotations

from antalens.data.dataset import Dataset
from antalens.data.simulation_table import SimulationTable
from antalens.data.views import Views, ViewsSchema

__all__ = [
    "Dataset",
    "SimulationTable",
    "Views",
    "ViewsSchema",
    "schema",
]
