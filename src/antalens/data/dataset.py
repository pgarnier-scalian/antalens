"""The :class:`Dataset` — universal data container for AntaLens.

A :class:`Dataset` wraps a polars :class:`~polars.LazyFrame` together with
an inferred :class:`~antalens.data.schema.Schema`. All chain methods
(:meth:`Dataset.filter`, :meth:`Dataset.resample`, :meth:`Dataset.compare`,
:meth:`Dataset.pipe`) return new :class:`Dataset` instances — the type is
immutable from the user's perspective.

The underlying LazyFrame means operations are recorded but not executed
until materialization is forced via :meth:`Dataset.to_dataframe`,
:meth:`Dataset.to_pandas`, or by a downstream plot builder. This allows
the chain to compose without intermediate copies.

Example:
    Loading a parquet file and chaining transforms::

        import antalens as al
        ds = al.io.load_parquet("data.parquet")
        narrowed = (
            ds.filter(area="FR", date_range=("2025-01-01", "2025-02-01"))
              .resample("1d", agg="mean")
        )
        # No data is read yet — narrowed is a recipe.
        df = narrowed.to_dataframe()  # forces execution
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Literal, Self

import polars as pl

from antalens.data.schema import Schema, infer_schema

if TYPE_CHECKING:
    import pandas as pd


# Aggregation function names accepted by ``resample()``.
ResampleAgg = Literal["mean", "sum", "min", "max", "median", "count", "std"]

# Date-range argument shape: a 2-tuple of date/datetime/ISO-string.
DateBound = date | datetime | str
DateRange = tuple[DateBound, DateBound]


class Dataset:
    """A lazily-evaluated tabular dataset with schema-aware chain operations.

    Datasets are constructed via the :mod:`antalens.io` loaders, not
    directly. Every public chain method returns a new ``Dataset`` —
    instances are immutable from the user's perspective.

    Args:
        lf: The polars LazyFrame backing this dataset.
        schema: The :class:`Schema` describing column roles. If ``None``,
            schema is inferred from ``lf``.
        name: Optional human-readable name, surfaced in plot titles and
            legends when comparing multiple datasets. Defaults to ``None``.

    Attributes:
        schema: The :class:`Schema` for this dataset's columns.
        name: The dataset's display name.
    """

    __slots__ = ("_lf", "name", "schema")

    def __init__(
        self,
        lf: pl.LazyFrame,
        *,
        schema: Schema | None = None,
        name: str | None = None,
    ) -> None:
        """Construct a Dataset wrapping ``lf``.

        Args:
            lf: The polars LazyFrame backing this dataset.
            schema: Optional pre-computed Schema. If ``None``, schema is
                inferred from ``lf``. Pre-computing is useful when a chain
                method already knows the schema and wants to skip re-inference.
            name: Optional human-readable name, surfaced in plot titles and
                legends when comparing multiple datasets.
        """
        self._lf = lf
        self.schema = schema if schema is not None else infer_schema(lf)
        self.name = name

    # ── construction helpers ────────────────────────────────────────────────

    def _with(self, lf: pl.LazyFrame, *, schema: Schema | None = None) -> Dataset:
        """Return a new instance wrapping ``lf``, preserving subclass type.

        Used internally by chain methods. Schema is preserved by default
        because chain operations don't change column roles — a filter
        narrows rows, a resample changes time granularity, but neither
        turns a numeric column into a categorical one.
        """
        return type(self)(lf, schema=schema or self.schema, name=self.name)

    # ── chain methods ──────────────────────────────────────────────────────

    def filter(
        self,
        *,
        area: str | list[str] | None = None,
        variable: str | list[str] | None = None,
        date_range: DateRange | None = None,
        **extra: Any,
    ) -> Dataset:
        """Narrow the dataset along one or more dimensions.

        Filters are AND-combined: passing both ``area`` and ``date_range``
        keeps only rows matching both. Passing ``None`` for any argument
        leaves that dimension unconstrained.

        Args:
            area: One or more area identifiers. Filters the column
                named ``area`` (or whichever column is registered as the
                geo column in the schema).
            variable: One or more variable names. For datasets in long
                format with a ``variable`` column, this filters by that
                column.
            date_range: A ``(start, end)`` tuple of dates, datetimes, or
                ISO-format strings. Filters the schema's time column.
                Both bounds are inclusive.
            **extra: Additional column-name keyword arguments interpreted
                as equality or membership filters. ``ds.filter(fuel="nuclear")``
                keeps rows where ``fuel == "nuclear"``;
                ``ds.filter(fuel=["nuclear", "wind"])`` keeps either.

        Returns:
            A new :class:`Dataset` with the filter applied to its lazy plan.

        Raises:
            ValueError: If ``date_range`` is provided but the schema has
                no time column, or if a column referenced in ``extra``
                doesn't exist.

        Examples:
            >>> import polars as pl
            >>> from datetime import datetime
            >>> df = pl.DataFrame({
            ...     "ts": [datetime(2025, 1, 1), datetime(2025, 1, 2),
            ...            datetime(2025, 1, 3), datetime(2025, 1, 4)],
            ...     "area": ["FR", "DE", "FR", "DE"],
            ...     "load": [50.0, 60.0, 51.0, 61.0],
            ... })
            >>> ds = Dataset(df.lazy())
            >>> ds.filter(area="FR").to_dataframe().shape
            (2, 3)
        """
        lf = self._lf

        if area is not None:
            lf = self._apply_membership_filter(lf, "area", area)

        if variable is not None:
            lf = self._apply_membership_filter(lf, "variable", variable)

        if date_range is not None:
            if self.schema.time_col is None:
                raise ValueError(
                    "date_range filter requires a time column, but this "
                    "Dataset's schema has none. Pass time_col= when loading, "
                    "or use a column-keyword filter instead."
                )
            start, end = (_coerce_to_datetime(b) for b in date_range)
            lf = lf.filter(pl.col(self.schema.time_col).is_between(start, end, closed="both"))

        for col, value in extra.items():
            if not self.schema.has(col):
                raise ValueError(
                    f"filter argument {col!r} does not match any column in "
                    f"this Dataset's schema. Known columns: "
                    f"{self._all_known_columns()!r}"
                )
            lf = self._apply_membership_filter(lf, col, value)

        return self._with(lf)

    def resample(
        self,
        freq: str,
        agg: ResampleAgg | dict[str, ResampleAgg] = "mean",
    ) -> Dataset:
        """Resample to a coarser time frequency.

        Wraps polars' :meth:`group_by_dynamic` to aggregate the dataset
        to a regular time grid. All numeric columns are aggregated; non-numeric
        columns (categoricals, strings) are dropped from the result unless
        used as group keys.

        Args:
            freq: Target frequency string, polars-compatible.
                Examples: ``"1h"``, ``"1d"``, ``"1w"``, ``"1mo"``, ``"1y"``.
            agg: Aggregation to apply. Either a single function name applied
                to every numeric column, or a dict mapping column names to
                function names.

        Returns:
            A new :class:`Dataset` with the resampled data.

        Raises:
            ValueError: If the schema has no time column to resample on.

        Examples:
            >>> import polars as pl
            >>> from datetime import datetime
            >>> df = pl.DataFrame({
            ...     "ts": [datetime(2025, 1, 1, h) for h in range(0, 24)],
            ...     "load": list(range(50, 74)),
            ... })
            >>> ds = Dataset(df.lazy())
            >>> ds.resample("6h", agg="mean").to_dataframe().shape
            (4, 2)
        """
        if self.schema.time_col is None:
            raise ValueError(
                "resample requires a time column, but this Dataset's schema "
                "has none. Pass time_col= when loading."
            )

        # Build the per-column aggregation expressions.
        if isinstance(agg, str):
            agg_exprs = [_agg_expr(col, agg) for col in self.schema.numeric_cols]
        else:
            agg_exprs = [_agg_expr(col, fn) for col, fn in agg.items()]

        # Group keys: time column + any categorical column (so we keep
        # per-area, per-fuel breakdowns). This matches what users intuitively
        # expect — resampling preserves group structure.
        group_keys = list(self.schema.categorical_cols.keys())

        lf = (
            self._lf.sort(self.schema.time_col)
            .group_by_dynamic(
                self.schema.time_col,
                every=freq,
                group_by=group_keys if group_keys else None,
            )
            .agg(agg_exprs)
        )
        return self._with(lf)

    def compare(
        self,
        other: Dataset,
        *,
        label_a: str = "A",
        label_b: str = "B",
    ) -> ComparedDataset:
        """Pair this dataset with another for side-by-side comparison.

        The returned :class:`ComparedDataset` is itself a :class:`Dataset`,
        so all chain methods continue to work. Plot builders called on the
        comparison automatically render both series with consistent styling
        (solid vs. dashed, distinct color scales).

        Args:
            other: The dataset to compare against. Should have a compatible
                schema (same time column, same numeric columns of interest).
            label_a: Label for ``self`` in legends.
            label_b: Label for ``other`` in legends.

        Returns:
            A :class:`ComparedDataset` paired with ``other``.

        Examples:
            >>> ds_2025 = al.io.load_parquet("year_2025.parquet")  # doctest: +SKIP
            >>> ds_2030 = al.io.load_parquet("year_2030.parquet")  # doctest: +SKIP
            >>> compared = ds_2025.compare(ds_2030, label_a="2025", label_b="2030")
            >>> compared.plot.timeseries("load")  # doctest: +SKIP
        """
        return ComparedDataset(self, other, label_a=label_a, label_b=label_b)

    def pipe(self, fn: Callable[[Self], Self]) -> Self:
        """Apply an arbitrary function to this dataset.

        Useful for inserting custom transforms into a chain without breaking
        method chaining.

        Args:
            fn: A callable taking this dataset and returning a new one.

        Returns:
            The result of ``fn(self)``.

        Examples:
            >>> def select_summer(ds):  # doctest: +SKIP
            ...     return ds.filter(date_range=("2025-06-01", "2025-09-01"))
            >>> ds.pipe(select_summer).plot.timeseries("load")  # doctest: +SKIP
        """
        return fn(self)

    # ── escape hatches ─────────────────────────────────────────────────────

    def to_dataframe(self) -> pl.DataFrame:
        """Materialize the lazy plan and return a polars DataFrame.

        This is the primary way to extract data from a Dataset for use
        outside the AntaLens chain.

        Returns:
            A polars :class:`~polars.DataFrame` with all transforms applied.
        """
        return self._lf.collect()

    def to_pandas(self) -> pd.DataFrame:
        """Materialize and return as a pandas DataFrame.

        Provided for interop with libraries that don't speak polars yet.
        Prefer :meth:`to_dataframe` for performance.

        Returns:
            A pandas :class:`~pandas.DataFrame`.
        """
        return self._lf.collect().to_pandas()

    def to_lazy(self) -> pl.LazyFrame:
        """Return the underlying polars LazyFrame.

        Use when you need to interleave polars-specific operations with
        AntaLens chain methods. The returned LazyFrame is the same object
        backing this Dataset — do not mutate it.

        Returns:
            The backing :class:`~polars.LazyFrame`.
        """
        return self._lf

    # ── introspection ──────────────────────────────────────────────────────

    @property
    def columns(self) -> list[str]:
        """All column names in this dataset, in order."""
        return self._lf.collect_schema().names()

    def __repr__(self) -> str:
        """Return a concise summary showing schema roles."""
        time_part = f"time={self.schema.time_col!r}, " if self.schema.time_col else ""
        return (
            f"{type(self).__name__}("
            f"{time_part}"
            f"numeric={self.schema.numeric_cols!r}, "
            f"categorical={list(self.schema.categorical_cols)!r}"
            f")"
        )

    # ── internal helpers ───────────────────────────────────────────────────

    def _apply_membership_filter(
        self, lf: pl.LazyFrame, column: str, value: str | list[str]
    ) -> pl.LazyFrame:
        """Apply a single-value or list-of-values filter to ``column``."""
        if isinstance(value, list):
            return lf.filter(pl.col(column).is_in(value))
        return lf.filter(pl.col(column) == value)

    def _all_known_columns(self) -> list[str]:
        """Return every column name the schema knows about."""
        cols: list[str] = []
        if self.schema.time_col:
            cols.append(self.schema.time_col)
        cols.extend(self.schema.numeric_cols)
        cols.extend(self.schema.categorical_cols.keys())
        if self.schema.geo_cols:
            cols.extend(self.schema.geo_cols)
        return cols


class ComparedDataset(Dataset):
    """Two paired datasets ready for side-by-side plotting.

    Constructed by :meth:`Dataset.compare`. All Dataset methods work
    on the merged data; the comparison structure is preserved so plot
    builders can render the two series distinctly.

    Note:
        Chain methods (``filter``, ``resample``, ``pipe``) return plain
        :class:`Dataset` instances, not :class:`ComparedDataset`. The
        comparison metadata (``label_a``, ``label_b``) only exists on
        the immediate result of :meth:`Dataset.compare`. The merged data
        retains the ``__series__`` discriminator column so plot builders
        can still split the series.
    """

    __slots__ = ("dataset_a", "dataset_b", "label_a", "label_b")

    def __init__(
        self,
        a: Dataset,
        b: Dataset,
        *,
        label_a: str = "A",
        label_b: str = "B",
    ) -> None:
        """Pair two Datasets into a single comparison-aware Dataset.

        Concatenates ``a`` and ``b`` vertically with a ``__series__``
        discriminator column so plot builders can split them back apart.

        Args:
            a: The first dataset.
            b: The second dataset. Should be schema-compatible with ``a``.
            label_a: Display label for ``a`` in legends and series.
            label_b: Display label for ``b`` in legends and series.
        """
        # Concatenate with a discriminator column so plot builders can
        # split the two back apart. The discriminator is ``__series__``,
        # double-underscored to avoid collision with user columns.
        merged = pl.concat(
            [
                a.to_lazy().with_columns(pl.lit(label_a).alias("__series__")),
                b.to_lazy().with_columns(pl.lit(label_b).alias("__series__")),
            ],
            how="vertical_relaxed",
        )
        # Inherit schema from `a`; the __series__ column is implicit.
        super().__init__(merged, schema=a.schema, name=a.name)
        self.dataset_a = a
        self.dataset_b = b
        self.label_a = label_a
        self.label_b = label_b

    def _with(self, lf: pl.LazyFrame, *, schema: Schema | None = None) -> Dataset:
        """Return a plain Dataset; comparison metadata doesn't propagate.

        Override of :meth:`Dataset._with`. Once a ``ComparedDataset`` is
        chained through ``filter()`` etc., the result is a plain
        ``Dataset`` whose underlying data still carries the ``__series__``
        column. Rebuilding a ``ComparedDataset`` would require splitting
        and re-concatenating, which adds no value over the discriminator
        column already present.
        """
        return Dataset(lf, schema=schema or self.schema, name=self.name)


# ─── module-level helpers ───────────────────────────────────────────────────


def _coerce_to_datetime(value: DateBound) -> datetime:
    """Convert a date/datetime/ISO string to a datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        # polars's permissive datetime parsing handles ISO formats and
        # date-only strings like "2025-01-01".
        try:
            return datetime.fromisoformat(value)
        except ValueError as e:
            raise ValueError(
                f"could not parse {value!r} as a datetime. Expected ISO "
                f"format like '2025-01-01' or '2025-01-01T12:00:00'."
            ) from e
    raise TypeError(
        f"date_range bounds must be date, datetime, or ISO string; got {type(value).__name__}"
    )


def _agg_expr(col: str, fn: ResampleAgg) -> pl.Expr:
    """Build a polars aggregation expression for ``col`` using ``fn``."""
    expr = pl.col(col)
    match fn:
        case "mean":
            return expr.mean().alias(col)
        case "sum":
            return expr.sum().alias(col)
        case "min":
            return expr.min().alias(col)
        case "max":
            return expr.max().alias(col)
        case "median":
            return expr.median().alias(col)
        case "count":
            return expr.count().alias(col)
        case "std":
            return expr.std().alias(col)
