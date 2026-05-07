"""GEMS raw output data — :class:`SimulationTable`.

A :class:`SimulationTable` is a :class:`Dataset` subclass specialized for
GEMS raw simulation outputs. It exposes GEMS-specific accessors and methods
that make it easy to work with the long-format parquet files produced by
the GEMS solver.

See Also:
    :mod:`antalens.data.views` — Curated wide-format outputs
    :doc:`../gems` — GEMS data model reference
"""

from __future__ import annotations

import polars as pl

from antalens.catalog import Catalog
from antalens.data.dataset import Dataset, ReactiveBinding
from antalens.data.schema import Schema


class SimulationTable(Dataset):
    """Dataset subclass for GEMS raw outputs (long-format parquet).

    GEMS simulation outputs have a canonical long format with eight columns:
    ``component``, ``output``, ``scenario``, ``block``, ``time``, ``value``.
    This class provides accessors for those GEMS-specific dimensions.

    Args:
        lf: The underlying polars LazyFrame.
        schema: The schema (should be a GEMS schema).
        name: Optional name for identification.
        catalog: Optional catalog for domain semantics.
        _reactive_bindings: Optional list of reactive bindings.

    Example:
        Load a GEMS simulation table::

            from antalens.io import load_simulation_table

            st = load_simulation_table("output.parquet")
            st.components  # List of all components
            st.outputs     # List of all outputs
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
        """Initialize a SimulationTable.

        Args:
            lf: The underlying polars LazyFrame.
            schema: The schema (should be a GEMS schema).
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

    @property
    def components(self) -> list[str]:
        """List of all component names in this simulation table."""
        if "component" not in self.columns:
            return []
        return self._lf.unique(["component"]).sort("component").collect().item()  # type: ignore[no-any-return]

    @property
    def outputs(self) -> list[str]:
        """List of all output names in this simulation table."""
        if "output" not in self.columns:
            return []
        return self._lf.unique(["output"]).sort("output").collect().item()  # type: ignore[no-any-return]

    @property
    def scenarios(self) -> list[int]:
        """List of all scenario IDs in this simulation table."""
        if "scenario" not in self.columns:
            return []
        return self._lf.unique(["scenario"]).sort("scenario").collect().item()  # type: ignore[no-any-return]

    @property
    def blocks(self) -> list[str]:
        """List of all block names in this simulation table."""
        if "block" not in self.columns:
            return []
        return self._lf.unique(["block"]).sort("block").collect().item()  # type: ignore[no-any-return]

    def filter(  # type: ignore[override]
        self,
        *,
        components: str | list[str] | None = None,
        outputs: str | list[str] | None = None,
        scenarios: int | list[int] | None = None,
        blocks: str | list[str] | None = None,
    ) -> SimulationTable:
        """Filter by GEMS-specific dimensions.

        Args:
            components: Component name(s) to include.
            outputs: Output name(s) to include.
            scenarios: Scenario ID(s) to include.
            blocks: Block name(s) to include.

        Returns:
            A new SimulationTable with the specified filters applied.
        """
        lf = self._lf

        if components is not None:
            if isinstance(components, str):
                components = [components]
            lf = lf.filter(pl.col("component").is_in(components))

        if outputs is not None:
            if isinstance(outputs, str):
                outputs = [outputs]
            lf = lf.filter(pl.col("output").is_in(outputs))

        if scenarios is not None:
            if isinstance(scenarios, int):
                scenarios = [scenarios]
            lf = lf.filter(pl.col("scenario").is_in(scenarios))

        if blocks is not None:
            if isinstance(blocks, str):
                blocks = [blocks]
            lf = lf.filter(pl.col("block").is_in(blocks))

        return type(self)(
            lf,
            schema=self.schema,
            name=self.name,
            catalog=self.catalog,
            _reactive_bindings=list(self._reactive_bindings),
        )

    def pivot(self, value_col: str = "value") -> pl.DataFrame:
        """Pivot to wide format with components as columns.

        Args:
            value_col: The value column to pivot. Defaults to "value".

        Returns:
            A wide-format polars DataFrame.
        """
        return self._lf.pivot(
            "component",
            on_columns=["component"],
            values=value_col,
            index=["time", "scenario", "block"],
        ).collect()


class SimulationTableSchema(Schema):
    """Schema for GEMS raw simulation outputs.

    The canonical GEMS schema has these columns:
    - ``component``: Component identifier (string)
    - ``output``: Output variable name (string)
    - ``scenario``: Scenario ID (integer)
    - ``block``: Block identifier (string)
    - ``time``: Timestamp (datetime)
    - ``value``: Numeric value (float)
    """

    __slots__ = ()

    def __init__(self) -> None:
        """Initialize the GEMS schema."""
        super().__init__(
            kind="long_gems",
            time_col="time",
            categorical_cols={
                "component": [],
                "block": [],
                "scenario": [],
            },
            numeric_cols=["value"],
            geo_cols=None,
            ndim=3,
            component_col="component",
            output_col="output",
            value_col="value",
            scenario_col="scenario",
            abs_time_col="time",
            block_col="block",
        )


# Re-export from this module
__all__ = [
    "SimulationTable",
    "SimulationTableSchema",
]
