"""Schema inference for Datasets.

Every :class:`~antalens.data.dataset.Dataset` carries a :class:`Schema`
describing the role of each column. Plot builders use the schema to pick
sensible defaults (which column is time, which is categorical, etc.)
without forcing the user to specify everything.

Schema is computed once at Dataset construction and propagates unchanged
through chain operations. This is intentional — recomputing schema after
each ``filter()`` would produce surprising behavior (a categorical column
might appear "non-categorical" after filtering reduced its cardinality).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import polars as pl

ColumnKind = Literal["time", "categorical", "numeric", "geo", "unknown"]
"""The role a column plays in a Dataset."""


# Column names that are treated as time even without a datetime dtype.
# Order matters — first match wins.
_TIME_COLUMN_HINTS: tuple[str, ...] = (
    "time",
    "timestamp",
    "datetime",
    "date",
    "valid_time",
    "ts",
    "absolute_time_index",
    "block_time_index",
)

# Column names that are treated as geo coordinates or area identifiers.
_GEO_COLUMN_HINTS: tuple[str, ...] = (
    "lat",
    "latitude",
    "lon",
    "lng",
    "longitude",
    "area",
    "area_id",
    "region",
    "country",
    "geometry",
)

# Categorical columns with more distinct values than this are treated as
# free-form strings rather than categories. 200 is a reasoned default —
# enough to cover countries, departments, fuel types; small enough to
# exclude things like user IDs or transaction IDs.
DEFAULT_CATEGORICAL_CARDINALITY_LIMIT = 200


@dataclass(frozen=True, slots=True)
class Schema:
    """Describes the structure of a Dataset's columns.

    Attributes:
        kind: Data model kind — ``"wide"`` for tabular wide-format,
            ``"long_gems"`` for GEMS SimulationTable long-format,
            ``"xarray"`` for multi-dimensional data.
        time_col: Name of the column to treat as the time axis, or ``None``
            if the dataset has no time dimension.
        categorical_cols: Mapping of categorical column names to their
            distinct values. Only includes columns with cardinality below
            :data:`DEFAULT_CATEGORICAL_CARDINALITY_LIMIT`.
        numeric_cols: Names of numeric columns suitable for plotting on
            a quantitative axis.
        geo_cols: Names of columns holding geographic information
            (lat/lon coordinates or area identifiers), or ``None`` if
            no geo columns are detected.
        ndim: Dimensionality of the underlying data. ``2`` for tabular,
            ``3+`` for xarray-backed multi-dimensional data.
        GEMS-specific fields (only used when kind == "long_gems"):
        component_col: Column name for component identifiers.
        output_col: Column name for output/variable names.
        value_col: Column name for the measured value.
        scenario_col: Column name for Monte Carlo scenario index.
        abs_time_col: Column name for absolute time index.
        block_col: Column name for optimization block index.
    """

    kind: Literal["wide", "long_gems", "xarray"] = "wide"
    time_col: str | None = None
    categorical_cols: dict[str, list[str]] = field(default_factory=dict)
    numeric_cols: list[str] = field(default_factory=list)
    geo_cols: list[str] | None = None
    ndim: int = 2
    # GEMS-specific fields
    component_col: str | None = None
    output_col: str | None = None
    value_col: str | None = None
    scenario_col: str | None = None
    abs_time_col: str | None = None
    block_col: str | None = None

    def has(self, col: str) -> bool:
        """Return whether ``col`` is known to this schema."""
        return (
            col == self.time_col
            or col in self.categorical_cols
            or col in self.numeric_cols
            or (self.geo_cols is not None and col in self.geo_cols)
            or (
                self.kind == "long_gems"
                and col
                in (
                    self.component_col,
                    self.output_col,
                    self.value_col,
                    self.scenario_col,
                    self.abs_time_col,
                    self.block_col,
                )
            )
        )

    def kind_of(self, col: str) -> ColumnKind:
        """Return the role of ``col`` in this schema.

        Args:
            col: Column name to look up.

        Returns:
            The column's role, or ``"unknown"`` if not in the schema.

        Examples:
            >>> import polars as pl
            >>> df = pl.DataFrame({"time": [1, 2], "load": [10.0, 11.0]})
            >>> schema = infer_schema(df.lazy())
            >>> schema.kind_of("time")
            'time'
            >>> schema.kind_of("load")
            'numeric'
            >>> schema.kind_of("missing")
            'unknown'
        """
        if col == self.time_col:
            return "time"
        if col in self.categorical_cols:
            return "categorical"
        if col in self.numeric_cols:
            return "numeric"
        if self.geo_cols is not None and col in self.geo_cols:
            return "geo"
        # GEMS-specific columns (long_gems kind only)
        if self.kind == "long_gems":
            if col == self.component_col:
                return "categorical"  # component names are categorical
            if col == self.output_col:
                return "categorical"  # output names are categorical
            if col == self.value_col:
                return "numeric"
            if col == self.scenario_col:
                return "categorical"  # scenario indices are categorical
            if col == self.abs_time_col:
                return "time"
            if col == self.block_col:
                return "categorical"  # block indices are categorical
        return "unknown"


def infer_schema(
    lf: pl.LazyFrame,
    *,
    kind: Literal["wide", "long_gems", "xarray"] = "wide",
    time_col: str | None = None,
    cardinality_limit: int = DEFAULT_CATEGORICAL_CARDINALITY_LIMIT,
    # GEMS-specific arguments
    component_col: str | None = None,
    output_col: str | None = None,
    value_col: str | None = None,
    scenario_col: str | None = None,
    abs_time_col: str | None = None,
    block_col: str | None = None,
) -> Schema:
    """Infer a :class:`Schema` from a polars LazyFrame.

    The inference rules are:

    1. **Time column**: the first column with a temporal dtype, or if none,
       the first column whose name matches a known time hint (``time``,
       ``timestamp``, ``date``, etc.). Overridden by an explicit ``time_col``
       argument.
    2. **Geo columns**: any columns whose names match known geo hints
       (``lat``, ``lon``, ``area``, etc.).
    3. **Categorical columns**: string and categorical columns with fewer
       than ``cardinality_limit`` distinct values. Their distinct values
       are materialized and stored.
    4. **Numeric columns**: everything else with a numeric dtype.

    Args:
        lf: The LazyFrame to inspect. Schema inference is cheap — only the
            schema (column names and dtypes) is read, not the data.
            Categorical value enumeration does materialize the relevant
            columns, which forces a partial collect.
        kind: Data model kind. ``"wide"`` for tabular data, ``"long_gems"``
            for GEMS SimulationTable format, ``"xarray"`` for multi-
            dimensional data.
        time_col: Override automatic time column detection. If provided,
            this column is treated as the time axis regardless of dtype.
            Pass an empty string to indicate "no time column".
        cardinality_limit: Maximum distinct values for a string column to
            be treated as categorical. Higher means more columns get the
            categorical treatment.
        GEMS-specific arguments (only used when kind == "long_gems"):
        component_col: Column name for component identifiers.
        output_col: Column name for output/variable names.
        value_col: Column name for measured values.
        scenario_col: Column name for Monte Carlo scenario index.
        abs_time_col: Column name for absolute time index.
        block_col: Column name for optimization block index.

    Returns:
        A populated :class:`Schema`.

    Raises:
        ValueError: If ``time_col`` is specified but doesn't exist in the
            LazyFrame.

    Examples:
        >>> import polars as pl
        >>> df = pl.DataFrame({
        ...     "timestamp": pl.datetime_range(
        ...         pl.datetime(2025, 1, 1), pl.datetime(2025, 1, 2),
        ...         interval="1h", eager=True,
        ...     ),
        ...     "area": ["FR"] * 13 + ["DE"] * 12,
        ...     "load": [50.0] * 25,
        ... })
        >>> schema = infer_schema(df.lazy())
        >>> schema.time_col
        'timestamp'
        >>> sorted(schema.categorical_cols["area"])
        ['DE', 'FR']
        >>> schema.numeric_cols
        ['load']

        For GEMS SimulationTable format:

        >>> gems_df = pl.DataFrame({
        ...     "block": [1] * 10,
        ...     "component": ["gen1"] * 10,
        ...     "output": ["p"] * 10,
        ...     "absolute_time_index": range(1, 11),
        ...     "scenario_index": [0] * 10,
        ...     "value": [10.0, 11.0, 12.0] + [10.0] * 7,
        ...     "basis_status": ["Free"] * 10,
        ... })
        >>> gems_schema = infer_schema(
        ...     gems_df.lazy(),
        ...     kind="long_gems",
        ...     component_col="component",
        ...     output_col="output",
        ...     value_col="value",
        ...     scenario_col="scenario_index",
        ...     abs_time_col="absolute_time_index",
        ...     block_col="block",
        ... )
        >>> gems_schema.kind
        'long_gems'
        >>> gems_schema.component_col
        'component'
    """
    polars_schema = lf.collect_schema()
    columns = polars_schema.names()

    # ── time column ────────────────────────────────────────────────────────
    resolved_time_col: str | None
    if time_col is not None:
        if time_col == "":
            resolved_time_col = None
        elif time_col not in columns:
            raise ValueError(
                f"time_col={time_col!r} does not exist in the dataset. "
                f"Available columns: {columns!r}"
            )
        else:
            resolved_time_col = time_col
    else:
        resolved_time_col = _detect_time_col(polars_schema)

    # ── geo columns ────────────────────────────────────────────────────────
    geo_cols = [c for c in columns if c.lower() in _GEO_COLUMN_HINTS]

    # ── categorical and numeric columns ────────────────────────────────────
    categorical_cols: dict[str, list[str]] = {}
    numeric_cols: list[str] = []

    # Skip GEMS-specific columns if kind == "long_gems"
    gems_cols = set()
    if kind == "long_gems":
        gems_cols = {
            component_col,
            output_col,
            value_col,
            scenario_col,
            abs_time_col,
            block_col,
        } - {None}

    for col in columns:
        if col == resolved_time_col or col in geo_cols:
            continue
        if col in gems_cols:
            continue

        dtype = polars_schema[col]
        if dtype.is_numeric():
            numeric_cols.append(col)
        elif dtype in (pl.String, pl.Categorical, pl.Enum):
            distinct_values = _distinct_values_or_none(lf, col, cardinality_limit)
            if distinct_values is not None:
                categorical_cols[col] = distinct_values

    # For GEMS format, determine which remaining columns are numeric vs categorical
    if kind == "long_gems" and "basis_status" in columns and "basis_status" not in gems_cols:
        # basis_status is categorical
        dtype = polars_schema["basis_status"]
        if dtype in (pl.String, pl.Categorical, pl.Enum):
            distinct_values = _distinct_values_or_none(lf, "basis_status", cardinality_limit)
            if distinct_values is not None:
                categorical_cols["basis_status"] = distinct_values

    return Schema(
        kind=kind,
        time_col=resolved_time_col,
        categorical_cols=categorical_cols,
        numeric_cols=numeric_cols,
        geo_cols=geo_cols if geo_cols else None,
        ndim=2,
        # GEMS-specific fields
        component_col=component_col,
        output_col=output_col,
        value_col=value_col,
        scenario_col=scenario_col,
        abs_time_col=abs_time_col,
        block_col=block_col,
    )


def _detect_time_col(polars_schema: pl.Schema) -> str | None:
    """Find a likely time column by dtype, then by name hint."""
    # First pass — any temporal dtype
    for col, dtype in polars_schema.items():
        if dtype.is_temporal():
            return col

    # Second pass — name hint
    lowered = {col.lower(): col for col in polars_schema.names()}
    for hint in _TIME_COLUMN_HINTS:
        if hint in lowered:
            return lowered[hint]

    return None


def _distinct_values_or_none(lf: pl.LazyFrame, col: str, limit: int) -> list[str] | None:
    """Return the distinct values of ``col`` if cardinality is within ``limit``.

    Returns ``None`` if the column has too many distinct values to be
    considered categorical. We cap the collected result at ``limit + 1`` so
    we can detect "more than limit" without materializing the full distinct
    set on a high-cardinality column.
    """
    distinct = (
        lf.select(pl.col(col).unique().drop_nulls()).head(limit + 1).collect().to_series().to_list()
    )
    if len(distinct) > limit:
        return None
    return [str(v) for v in distinct]
