"""GEMS curated outputs — :class:`Views`.

A :class:`Views` is a :class:`Dataset` subclass specialized for GEMS curated
outputs in wide format. These are derived from raw ``SimulationTable`` data
and aggregate by component groupings or other semantic groupings defined
in the view configuration.

See Also:
    :mod:`antalens.data.simulation_table` — Raw long-format outputs
    :doc:`../gems` — GEMS data model reference
"""

from __future__ import annotations

import polars as pl

from antalens.catalog import Catalog
from antalens.data.dataset import Dataset, ReactiveBinding
from antalens.data.schema import Schema


class Views(Dataset):
    """Dataset subclass for GEMS curated outputs (wide-format parquet).

    Views are pre-computed aggregations of raw simulation data, organized
    by semantic groupings defined in the view configuration. They are
    lighter-weight than ``SimulationTable`` and suitable for dashboard
    exploration.

    Args:
        lf: The underlying polars LazyFrame.
        schema: The schema (should be a Views schema).
        name: Optional name for identification.
        catalog: Optional catalog for domain semantics.
        _reactive_bindings: Optional list of reactive bindings.

    Example:
        Load curated views::

            from antalens.io import load_views

            views = load_views("curated_views.parquet")
            views.columns  # Wide-format columns
    """

    __slots__ = ()

    def __init__(
        self,
        lf: pl.LazyFrame,
        *,
        schema: Schema | None = None,
        name: str | None = None,
        catalog: Catalog | None = None,
        _reactive_bindings: list[ReactiveBinding] | None = None,
    ) -> None:
        """Initialize a Views instance.

        Args:
            lf: The underlying polars LazyFrame.
            schema: The schema (should be a Views schema).
            name: Optional name for identification.
            catalog: Optional catalog for domain semantics.
            _reactive_bindings: Optional list of reactive bindings.
        """
        super().__init__(
            lf=lf,
            schema=schema,
            name=name,
            catalog=catalog,
            _reactive_bindings=_reactive_bindings,
        )


class ViewsSchema(Schema):
    """Schema for GEMS curated wide-format outputs.

    Views have a wide format with one column per component grouping.
    The schema tracks which columns are time, which are measures,
    and which are categorical identifiers.
    """

    __slots__ = ()

    def __init__(self) -> None:
        """Initialize the Views schema."""
        super().__init__(
            kind="wide",
            time_col=None,
            categorical_cols={},
            numeric_cols=[],
            geo_cols=None,
            ndim=2,
        )


__all__ = ["Views", "ViewsSchema"]
