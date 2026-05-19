"""The :class:`SimulationTable` — GEMS raw-output Dataset subclass.

A SimulationTable wraps a long-format parquet/CSV with the canonical GEMS
schema (see ``gems.md`` §2):

    block, component, output, absolute_time_index, block_time_index,
    scenario_index, value, basis_status

It adds GEMS-aware accessors (``.components``, ``.outputs``, ``.scenarios``,
``.blocks``) and a :meth:`filter` overload accepting keyword arguments
mapped to those columns. All chain methods inherited from
:class:`~antalens.data.dataset.Dataset` continue to work — the subclass is
strictly additive.

The accessors are computed lazily and cached. On a 35GB SimulationTable,
calling ``.outputs`` reads only the distinct values of one column from
the parquet header, not the whole file.

Example::

    sim = al.io.load_simulation_table("output.parquet")
    print(sim.outputs)       # ['p', 'e', 'p_nom', ...]
    print(sim.scenarios)     # [0, 1, 2, ...]

    # GEMS-aware filtering
    nuclear = sim.filter(component="generator_FR_NUCLEAR_0", output="p")
    week2 = sim.filter(time_range=(168, 336))
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import polars as pl

from antalens.data.dataset import Dataset, ReactiveBinding
from antalens.data.schema import Schema

if TYPE_CHECKING:
    from antalens.catalog import Catalog


# Canonical GEMS column names. These are baked into the schema and used
# by the accessors and the filter overload.
_GEMS_COLUMNS = {
    "block": "block",
    "component": "component",
    "output": "output",
    "absolute_time_index": "absolute_time_index",
    "block_time_index": "block_time_index",
    "scenario_index": "scenario_index",
    "value": "value",
    "basis_status": "basis_status",
}


class SimulationTable(Dataset):
    """A GEMS SimulationTable backed by a polars LazyFrame.

    Constructed by :func:`antalens.io.load_simulation_table`. Users
    rarely instantiate directly.

    Args:
        lf: The polars LazyFrame backing this SimulationTable. Must
            contain at least the eight canonical GEMS columns.
        schema: Optional pre-computed Schema. If ``None``, a long-format
            schema with ``kind="long_gems"`` is constructed from the
            canonical GEMS column names.
        name: Optional human-readable name.
        catalog: Optional :class:`~antalens.catalog.Catalog` providing
            domain semantics. ``None`` means raw generic columns only.
        _reactive_bindings: Internal — reactive filter bindings
            propagated from chain methods.
    """

    __slots__ = ("_blocks_cache", "_components_cache", "_outputs_cache", "_scenarios_cache")

    def __init__(
        self,
        lf: pl.LazyFrame,
        *,
        schema: Schema | None = None,
        name: str | None = None,
        catalog: Catalog | None = None,
        _reactive_bindings: list[ReactiveBinding] | None = None,
    ) -> None:
        """A GEMS SimulationTable backed by a polars LazyFrame.

        Constructed by :func:`antalens.io.load_simulation_table`. Users
        rarely instantiate directly.

        Args:
            lf: The polars LazyFrame backing this SimulationTable. Must
                contain at least the eight canonical GEMS columns.
            schema: Optional pre-computed Schema. If ``None``, a long-format
                schema with ``kind="long_gems"`` is constructed from the
                canonical GEMS column names.
            name: Optional human-readable name.
            catalog: Optional :class:`~antalens.catalog.Catalog` providing
                domain semantics. ``None`` means raw generic columns only.
            _reactive_bindings: Internal — reactive filter bindings
                propagated from chain methods.
        """
        # Build a canonical long-format schema if one wasn't supplied.
        if schema is None:
            schema = _build_simulation_table_schema(lf)
        super().__init__(
            lf,
            schema=schema,
            name=name,
            catalog=catalog,
            _reactive_bindings=_reactive_bindings,
        )
        self._components_cache: list[str] | None = None
        self._outputs_cache: list[str] | None = None
        self._scenarios_cache: list[int] | None = None
        self._blocks_cache: list[int] | None = None

    # ── GEMS accessors (lazy + cached) ────────────────────────────────────

    @property
    def components(self) -> list[str]:
        """Distinct component names present in the table."""
        if self._components_cache is None:
            self._components_cache = self._distinct_values("component", str)
        return self._components_cache

    @property
    def outputs(self) -> list[str]:
        """Distinct output (variable) names present in the table."""
        if self._outputs_cache is None:
            self._outputs_cache = self._distinct_values("output", str)
        return self._outputs_cache

    @property
    def scenarios(self) -> list[int]:
        """Distinct scenario indices present in the table."""
        if self._scenarios_cache is None:
            self._scenarios_cache = self._distinct_values("scenario_index", int)
        return self._scenarios_cache

    @property
    def blocks(self) -> list[int]:
        """Distinct block indices present in the table."""
        if self._blocks_cache is None:
            self._blocks_cache = self._distinct_values("block", int)
        return self._blocks_cache

    def _distinct_values(self, column: str, dtype: type) -> list:  # type: ignore
        """Read distinct values of ``column`` and cast to ``dtype``."""
        values = (
            self._lf.select(pl.col(column).unique().drop_nulls()).collect().to_series().to_list()
        )
        return sorted([dtype(v) for v in values])

    # ── GEMS-aware filter ─────────────────────────────────────────────────

    def filter(  # type: ignore[override]
        self,
        *,
        component: str | list[str] | None = None,
        component_kind: str | None = None,
        output: str | list[str] | Any = None,
        scenario: int | list[int] | Any = None,
        time_range: tuple[int, int] | None = None,
        **extra: Any,
    ) -> SimulationTable:
        """Narrow the SimulationTable along GEMS-aware dimensions.

        All kwargs are AND-combined. Each may be a static value, a list,
        or a reactive binding (a Lens parameter or whole Lens — see
        :meth:`Dataset.filter`).

        Args:
            component: One or more component names. Filters the
                ``component`` column.
            component_kind: Filter by component kind (``"generator"``,
                ``"link"``, etc.). Requires an attached catalog with
                component patterns. Raises :class:`NotImplementedError`
                when no catalog is available.
            output: One or more output (variable) names. Filters the
                ``output`` column.
            scenario: One or more scenario indices. Filters the
                ``scenario_index`` column.
            time_range: An ``(start, end)`` tuple of
                ``absolute_time_index`` values, both inclusive.
            **extra: Additional column-name kwargs forwarded to
                :meth:`Dataset.filter`.

        Returns:
            A new :class:`SimulationTable` with the filter applied.

        Raises:
            NotImplementedError: If ``component_kind`` is provided but
                no catalog is attached.
        """
        if component_kind is not None:
            if self.catalog is None:
                raise NotImplementedError(
                    "filter(component_kind=...) requires a Catalog with "
                    "component patterns. Attach one via "
                    ".with_catalog(cat) and retry."
                )
            # When the catalog is available, resolve component_kind to a
            # list of component names that match the kind's pattern, then
            # AND with the explicit `component` filter.
            kind_components = self.catalog.components_of_kind(
                component_kind, candidates=self.components
            )
            if component is None:
                component = kind_components
            elif isinstance(component, str):
                component = [c for c in kind_components if c == component]
            else:
                component = [c for c in kind_components if c in component]

        # Build the filter kwargs to pass through to Dataset.filter via **extra.
        filter_kwargs: dict[str, Any] = dict(extra)
        if component is not None:
            filter_kwargs["component"] = component
        if output is not None:
            filter_kwargs["output"] = output
        if scenario is not None:
            filter_kwargs["scenario_index"] = scenario

        # The base Dataset.filter doesn't know about absolute_time_index
        # as a "time range" because the schema's time_col may or may not
        # be that column. Apply the range filter directly here, then hand
        # off the rest to the parent.
        if time_range is not None:
            start, end = time_range
            new_lf = self._lf.filter(
                pl.col("absolute_time_index").is_between(start, end, closed="both")
            )
            # Build an interim SimulationTable with the time range applied,
            # then run the rest of the filters through it.
            interim = type(self)(
                new_lf,
                schema=self.schema,
                name=self.name,
                catalog=self.catalog,
                _reactive_bindings=self._reactive_bindings,
            )
            return Dataset.filter(interim, **filter_kwargs)  # type: ignore[return-value]

        # No time range: forward straight to Dataset.filter. The base
        # method calls _with(...) which preserves our subclass via type(self).
        return Dataset.filter(self, **filter_kwargs)  # type: ignore[return-value]

    # ── pivot to wide format ──────────────────────────────────────────────

    def pivot(
        self,
        *,
        index: str = "absolute_time_index",
        columns: str = "output",
        values: str = "value",
    ) -> Dataset:
        """Pivot the long-format table to wide format.

        Useful for plotting workflows that want one column per
        ``output`` (or one per ``component``, or any other discriminator)
        rather than the long-format mix.

        Args:
            index: Column to use as the row index. Default
                ``"absolute_time_index"``.
            columns: Column to spread into multiple columns. Default
                ``"output"``.
            values: Column whose values populate the pivoted cells.
                Default ``"value"``.

        Returns:
            A plain :class:`Dataset` (not a SimulationTable — the result
            no longer has GEMS long-format shape).
        """
        # polars' pivot on LazyFrame requires a collect (it's not lazy),
        # so we materialize here. For very large SimulationTables this
        # may be expensive — pre-filter with `.filter()` first.
        wide = self._lf.collect().pivot(on=columns, index=index, values=values)
        return Dataset(wide.lazy(), name=self.name)

    # ── to_views (stubbed for ViewsBuilder integration) ───────────────────

    def to_views(self, view_config: str | dict) -> Any:  # type: ignore
        """Promote this SimulationTable to a Views file via a view-config.

        Not yet implemented — reserved for the future ViewsBuilder
        reference path. Use the GEMS ViewsBuilder externally for now.
        """
        raise NotImplementedError(
            "SimulationTable.to_views is reserved for the ViewsBuilder "
            "integration. Run the GEMS ViewsBuilder externally and load "
            "the resulting parquet via al.io.load_views() instead."
        )

    # ── catalog attachment ────────────────────────────────────────────────

    def with_catalog(self, catalog: Catalog) -> SimulationTable:
        """Return a new SimulationTable with a Catalog attached.

        The catalog enables semantic filtering (``component_kind=``),
        display-name resolution, and palette-driven plotting. Without a
        catalog, the table works on raw generic columns.
        """
        return type(self)(
            self._lf,
            schema=self.schema,
            name=self.name,
            catalog=catalog,
            _reactive_bindings=self._reactive_bindings,
        )


# ─── helpers ────────────────────────────────────────────────────────────────


def _build_simulation_table_schema(lf: pl.LazyFrame) -> Schema:
    """Construct the canonical long-format GEMS schema.

    Validates that the eight canonical columns are present and builds a
    :class:`Schema` with ``kind="long_gems"`` populating the long-format
    fields. Columns beyond the canonical eight are tolerated and
    classified by dtype.
    """
    columns = lf.collect_schema().names()
    missing = [c for c in _GEMS_COLUMNS.values() if c not in columns]
    if missing:
        raise ValueError(
            f"SimulationTable requires the GEMS canonical columns. "
            f"Missing: {missing!r}. Got: {columns!r}"
        )

    # Use the long-format schema kind. Time column is absolute_time_index
    # (integer-valued in GEMS, not a datetime).
    return Schema(
        kind="long_gems",
        time_col="absolute_time_index",
        categorical_cols={},  # GEMS uses 'component', 'output' as long-format keys
        numeric_cols=["value"],
        geo_cols=None,
        ndim=2,
        component_col="component",
        output_col="output",
        value_col="value",
        scenario_col="scenario_index",
        abs_time_col="absolute_time_index",
    )
