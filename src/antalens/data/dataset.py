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
from antalens.lens import (
    normalize_lens_date_range,
    resolve_filter_value,
)

if TYPE_CHECKING:
    import pandas as pd
    import param

    from antalens.catalog import Catalog
    from antalens.data.accessors import PlotAccessor

# Aggregation function names accepted by ``resample()``.
ResampleAgg = Literal["mean", "sum", "min", "max", "median", "count", "std"]

# Date-range argument shape: a 2-tuple of date/datetime/ISO-string.
DateBound = date | datetime | str
DateRange = tuple[DateBound, DateBound]

# A pending reactive filter on a Dataset. ``apply`` is a closure that takes
# a LazyFrame and returns a new LazyFrame with the current value of the
# bound parameter applied. ``watched`` is the param.Parameter the binding
# is following — exposed so dashboard layers can register watch handlers.
ReactiveBinding = tuple[Callable[[pl.LazyFrame], pl.LazyFrame], "param.Parameter"]


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
        _reactive_bindings: Internal. List of pending reactive filter
            bindings carried forward from prior chain steps. Users should
            not pass this directly; it is propagated by chain methods.

    Attributes:
        schema: The :class:`Schema` for this dataset's columns.
        name: The dataset's display name.
    """

    __slots__ = ("_catalog", "_lf", "_reactive_bindings", "name", "schema")

    def __init__(
        self,
        lf: pl.LazyFrame,
        *,
        schema: Schema | None = None,
        name: str | None = None,
        catalog: Catalog | None = None,
        _reactive_bindings: list[ReactiveBinding] | None = None,
    ) -> None:
        """Construct a Dataset wrapping ``lf``.

        Args:
            lf: The polars LazyFrame backing this dataset.
            schema: Optional pre-computed Schema. If ``None``, schema is
                inferred from ``lf``. Pre-computing is useful when a chain
                method already knows the schema and wants to skip re-inference.
            name: Optional human-readable name, surfaced in plot titles and
                legends when comparing multiple datasets.
            catalog: Optional :class:`~antalens.catalog.Catalog` for domain
                metadata (component patterns, output display names, palettes).
                Defaults to ``None``.
            _reactive_bindings: Internal. List of pending reactive filter
                bindings to carry forward. Defaults to an empty list when
                ``None``. Not part of the public API.
        """
        self._lf = lf
        self.schema = schema if schema is not None else infer_schema(lf)
        self.name = name
        self._catalog = catalog
        self._reactive_bindings = list(_reactive_bindings) if _reactive_bindings else []

    # ── construction helpers ────────────────────────────────────────────────

    def _with(
        self,
        lf: pl.LazyFrame,
        *,
        schema: Schema | None = None,
        extra_bindings: list[ReactiveBinding] | None = None,
        catalog: Catalog | None = None,
    ) -> Dataset:
        """Return a new Dataset wrapping ``lf``.

        Used internally by chain methods. Schema is preserved by default
        because chain operations don't change column roles — a filter
        narrows rows, a resample changes time granularity, but neither
        turns a numeric column into a categorical one.

        Reactive bindings propagate forward: a Dataset created by chaining
        from a reactive source remains reactive. New bindings introduced
        by the current chain step are appended via ``extra_bindings``.

        The return type is a plain :class:`Dataset` rather than ``Self``:
        :class:`ComparedDataset` overrides this method to also return a
        plain :class:`Dataset`, since comparison metadata (``label_a``,
        ``label_b``) is only meaningful immediately after :meth:`compare`.

        Args:
            lf: The polars LazyFrame backing the new Dataset.
            schema: Optional Schema. If ``None``, ``self.schema`` is reused.
            extra_bindings: Optional list of reactive bindings introduced
                by the current chain step. Appended after any bindings
                already present on ``self``.
            catalog: Optional Catalog override. If provided, replaces the
                current catalog; otherwise ``self._catalog`` is propagated.
                Defaults to ``None``.

        Returns:
            A new :class:`Dataset` (never a subclass instance).
        """
        merged_bindings = list(self._reactive_bindings)
        if extra_bindings:
            merged_bindings.extend(extra_bindings)
        return type(self)(
            lf,
            schema=schema or self.schema,
            name=self.name,
            catalog=catalog if catalog is not None else self._catalog,
            _reactive_bindings=merged_bindings,
        )

    # ── chain methods ──────────────────────────────────────────────────────

    def filter(
        self,
        *,
        area: str | list[str] | Any = None,
        variable: str | list[str] | Any = None,
        date_range: DateRange | Any = None,
        **extra: Any,
    ) -> Dataset:
        """Narrow the dataset along one or more dimensions.

        Filters are AND-combined: passing both ``area`` and ``date_range``
        keeps only rows matching both. Passing ``None`` for any argument
        leaves that dimension unconstrained.

        Reactive filtering: any argument can be a :class:`~antalens.lens.Lens`
        or a ``param.Parameter`` reference. When used, the filter is bound
        to the parameter's current value at call time, and the binding is
        recorded so dashboard layers can re-evaluate the filter when the
        parameter changes.

        Args:
            area: One or more area identifiers, a Lens, or
                ``lens.param.area``. Filters the ``area`` column.
            variable: One or more variable names, or a reactive binding.
                Filters the ``variable`` column.
            date_range: A ``(start, end)`` tuple of dates/datetimes/ISO
                strings, or a Lens (binds to ``lens.dates``), or a
                specific param.Parameter. Both bounds are inclusive.
            **extra: Additional column-name keyword arguments. Can also
                accept reactive bindings.

        Returns:
            A new :class:`Dataset` with the filter applied to its lazy plan.

        Raises:
            ValueError: If ``date_range`` is provided but the schema has
                no time column, or if a column referenced in ``extra``
                doesn't exist.

        Examples:
            Static filtering::

                >>> ds.filter(area="FR").to_dataframe().shape  # doctest: +SKIP

            Reactive filtering with a Lens::

                >>> from antalens.lens import Lens  # doctest: +SKIP
                >>> lens = Lens(area="FR")  # doctest: +SKIP
                >>> reactive = ds.filter(area=lens)  # doctest: +SKIP
                >>> reactive.to_dataframe()  # uses lens.area="FR"  # doctest: +SKIP
                >>> lens.area = "DE"  # doctest: +SKIP
                >>> reactive.to_dataframe()  # now uses lens.area="DE"  # doctest: +SKIP
        """
        lf = self._lf
        new_bindings: list[ReactiveBinding] = []
        all_columns = self.columns

        # ── area ───────────────────────────────────────────────────────────
        if area is not None:
            if "area" not in all_columns:
                raise ValueError(
                    "filter(area=...) requires a column named 'area' on "
                    "the dataset. Available columns: "
                    f"{all_columns!r}"
                )
            current, watched = resolve_filter_value("area", area)
            if watched is not None:
                # Reactive: defer the filter to materialization time.
                new_bindings.append(self._make_membership_binding("area", watched))
            elif current is not None:
                lf = self._apply_membership_filter(lf, "area", current)

        # ── variable ───────────────────────────────────────────────────────
        if variable is not None:
            if "variable" not in all_columns:
                raise ValueError(
                    "filter(variable=...) requires a column named 'variable' "
                    "on the dataset. Available columns: "
                    f"{all_columns!r}"
                )
            current, watched = resolve_filter_value("variable", variable)
            if watched is not None:
                new_bindings.append(self._make_membership_binding("variable", watched))
            elif current is not None:
                lf = self._apply_membership_filter(lf, "variable", current)

        # ── date_range ─────────────────────────────────────────────────────
        if date_range is not None:
            current, watched = resolve_filter_value("date_range", date_range)
            if self.schema.time_col is None and (current is not None or watched is not None):
                raise ValueError(
                    "date_range filter requires a time column, but this "
                    "Dataset's schema has none. Pass time_col= when loading, "
                    "or use a column-keyword filter instead."
                )
            if watched is not None:
                new_bindings.append(self._make_date_range_binding(watched))
            elif current is not None:
                lf = self._apply_date_range_filter(lf, current)

        # ── extra keyword filters ──────────────────────────────────────────
        for col, value in extra.items():
            if not self.schema.has(col):
                raise ValueError(
                    f"filter argument {col!r} does not match any column in "
                    f"this Dataset's schema. Known columns: "
                    f"{self._all_known_columns()!r}"
                )
            current, watched = resolve_filter_value(col, value)
            if watched is not None:
                new_bindings.append(self._make_membership_binding(col, watched))
            elif current is not None:
                lf = self._apply_membership_filter(lf, col, current)

        return self._with(lf, extra_bindings=new_bindings)

    def resample(
        self,
        freq: str,
        agg: ResampleAgg | dict[str, ResampleAgg] = "mean",
    ) -> Self:
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
                function names. Defaults to ``"mean"``.

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

        # Reactive bindings can't compose cleanly with resample because
        # resample changes the column set. We resolve them eagerly here,
        # which means subsequent lens changes don't update past the
        # resample point. Warn so users know.
        if self._reactive_bindings:
            import warnings

            warnings.warn(
                "resample() applied to a Dataset with reactive filters. "
                "Current lens values are baked in; later lens mutations "
                "will not propagate through the resample. Apply resample "
                "before reactive filters if reactivity is needed.",
                stacklevel=2,
            )
            base_lf = self._resolved_lazy()
        else:
            base_lf = self._lf

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
            base_lf.sort(self.schema.time_col)
            .group_by_dynamic(
                self.schema.time_col,
                every=freq,
                group_by=group_keys if group_keys else None,
            )
            .agg(agg_exprs)
        )

        # Drop bindings — they've been resolved into base_lf already.
        return type(self)(
            lf,
            schema=self.schema,
            name=self.name,
            _reactive_bindings=None,
        )

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
            label_a: Label for ``self`` in legends. Defaults to ``"A"``.
            label_b: Label for ``other`` in legends. Defaults to ``"B"``.

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

    def _resolved_lazy(self) -> pl.LazyFrame:
        """Return the LazyFrame with all pending reactive bindings applied.

        Internal — called by every materialization path. Walks the
        ``_reactive_bindings`` list and re-applies each one against the
        current value of its watched parameter, producing a LazyFrame that
        reflects the lens state at this exact moment.

        Returns:
            A :class:`~polars.LazyFrame` with every pending reactive
            binding evaluated and applied at the current parameter values.
        """
        lf = self._lf
        for apply, _watched in self._reactive_bindings:
            lf = apply(lf)
        return lf

    def to_dataframe(self) -> pl.DataFrame:
        """Materialize the lazy plan and return a polars DataFrame.

        This is the primary way to extract data from a Dataset for use
        outside the AntaLens chain. If the Dataset has reactive bindings,
        they are evaluated against the current parameter values before
        collection — calling ``to_dataframe()`` again after a lens change
        produces fresh results.

        Returns:
            A polars :class:`~polars.DataFrame` with all transforms applied.
        """
        return self._resolved_lazy().collect()

    def to_pandas(self) -> pd.DataFrame:
        """Materialize and return as a pandas DataFrame.

        Provided for interop with libraries that don't speak polars yet.
        Prefer :meth:`to_dataframe` for performance.

        Returns:
            A pandas :class:`~pandas.DataFrame`.
        """
        return self._resolved_lazy().collect().to_pandas()

    def to_lazy(self) -> pl.LazyFrame:
        """Return the underlying polars LazyFrame.

        Use when you need to interleave polars-specific operations with
        AntaLens chain methods. The returned LazyFrame includes all pending
        reactive bindings applied at the current parameter values — do not
        mutate it.

        Returns:
            A :class:`~polars.LazyFrame` reflecting the current state.
        """
        return self._resolved_lazy()

    @property
    def watched_parameters(self) -> list[param.Parameter]:
        """The :mod:`param` parameters this Dataset reacts to.

        Dashboard layers use this to set up watch handlers that trigger
        re-rendering when any bound parameter changes. Returns an empty
        list for non-reactive Datasets.
        """
        return [watched for _apply, watched in self._reactive_bindings]

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

    @property
    def plot(self) -> PlotAccessor:
        """Fluent accessor for plot builders.

        Returns a :class:`~antalens.data.accessors.PlotAccessor` bound to
        this dataset. Use as ``ds.plot.timeseries(...)``,
        ``ds.plot.heatmap(...)``, etc.
        """
        from antalens.data.accessors import PlotAccessor

        return PlotAccessor(self)

    @property
    def catalog(self) -> Catalog | None:
        """The :class:`~antalens.catalog.Catalog` attached to this dataset.

        Returns ``None`` if no catalog was provided during construction.
        Use :meth:`with_catalog` to attach a catalog to an existing
        dataset.

        Example::

            from antalens import Catalog, load_parquet

            cat = Catalog.from_yaml("catalogs/examples/gems.yml")
            ds = load_parquet("output.parquet").with_catalog(cat)
            ds.catalog.outputs["p"].display
            'Production'
        """
        return self._catalog

    def with_catalog(self, catalog: Catalog) -> Self:
        """Attach a catalog to this dataset.

        Returns a new :class:`Dataset` with the catalog bound. Chain
        methods propagate the catalog forward automatically.

        Args:
            catalog: The :class:`~antalens.catalog.Catalog` to attach.

        Returns:
            A new :class:`Dataset` with ``catalog`` set.

        Example::

            from antalens import Catalog, load_parquet

            cat = Catalog.from_yaml("catalogs/examples/gems.yml")
            ds = load_parquet("output.parquet").with_catalog(cat)
            ds.catalog.outputs["p"].display
            'Production'
        """
        return self._with(self._lf, catalog=catalog)  # type: ignore

    # ── internal helpers ───────────────────────────────────────────────────

    def _apply_membership_filter(
        self, lf: pl.LazyFrame, column: str, value: str | list[str]
    ) -> pl.LazyFrame:
        """Apply a single-value or list-of-values filter to ``column``.

        Args:
            lf: The LazyFrame to filter.
            column: The column name to filter on.
            value: Either a single value (equality filter) or a list of
                values (membership filter via ``is_in``).

        Returns:
            A new :class:`~polars.LazyFrame` with the filter appended.
        """
        if isinstance(value, list):
            return lf.filter(pl.col(column).is_in(value))
        return lf.filter(pl.col(column) == value)

    def _apply_date_range_filter(self, lf: pl.LazyFrame, date_range: Any) -> pl.LazyFrame:
        """Apply a date-range filter to the schema's time column.

        Accepts a 2-tuple of date/datetime/ISO-string values, or a
        Lens-shaped ``(datetime, datetime)`` tuple. The bounds are coerced
        to :class:`~datetime.datetime` and applied as inclusive limits.

        Args:
            lf: The LazyFrame to filter.
            date_range: A ``(start, end)`` 2-tuple. Each bound may be a
                :class:`~datetime.date`, :class:`~datetime.datetime`, or
                ISO-format string. Both bounds are inclusive.

        Returns:
            A new :class:`~polars.LazyFrame` filtered to the given range.

        Raises:
            TypeError: If ``date_range`` is not a 2-tuple, or if a bound
                cannot be coerced to a datetime.
        """
        if not (isinstance(date_range, tuple) and len(date_range) == 2):
            raise TypeError(
                f"date_range must be a (start, end) tuple, got "
                f"{type(date_range).__name__}: {date_range!r}"
            )
        start, end = (_coerce_to_datetime(b) for b in date_range)
        # mypy: time_col not None here — the caller guards it.
        time_col = self.schema.time_col
        assert time_col is not None
        return lf.filter(pl.col(time_col).is_between(start, end, closed="both"))

    def _make_membership_binding(self, column: str, watched: param.Parameter) -> ReactiveBinding:
        """Create a reactive binding that re-applies a membership filter.

        The returned closure reads the watched parameter's current value
        and applies it to whatever LazyFrame it receives. Stored on the
        Dataset so that materialization (or dashboard re-renders) can
        rebuild the lazy plan against the latest parameter value.

        Args:
            column: The dataset column the filter targets.
            watched: The :class:`param.Parameter` whose value drives the
                filter. Must have an ``owner`` and ``name`` for the
                binding to do anything; if either is missing at apply
                time, the binding is a no-op.

        Returns:
            A :data:`ReactiveBinding` — a ``(apply, watched)`` tuple.
        """

        def apply(lf: pl.LazyFrame) -> pl.LazyFrame:
            owner = watched.owner
            name = watched.name
            if owner is None or name is None:
                return lf
            current = getattr(owner, name)
            if current is None:
                return lf
            return self._apply_membership_filter(lf, column, current)

        return apply, watched

    def _make_date_range_binding(self, watched: param.Parameter) -> ReactiveBinding:
        """Create a reactive binding that re-applies a date-range filter.

        Args:
            watched: The :class:`param.Parameter` whose value drives the
                filter. Its current value is normalized via
                :func:`normalize_lens_date_range` before being applied.
                If the parameter has no ``owner``/``name`` or yields
                ``None`` after normalization, the binding is a no-op.

        Returns:
            A :data:`ReactiveBinding` — a ``(apply, watched)`` tuple.
        """

        def apply(lf: pl.LazyFrame) -> pl.LazyFrame:
            owner = watched.owner
            name = watched.name
            if owner is None or name is None:
                return lf
            current = normalize_lens_date_range(getattr(owner, name))
            if current is None:
                return lf
            return self._apply_date_range_filter(lf, current)

        return apply, watched

    def _all_known_columns(self) -> list[str]:
        """Return every column name the schema knows about.

        Returns:
            A list of column names assembled from the schema's time,
            numeric, categorical, and (optional) geo column groups, in
            that order.
        """
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

    Args:
        a: The first dataset.
        b: The second dataset. Should be schema-compatible with ``a``.
        label_a: Display label for ``a`` in legends and series.
            Defaults to ``"A"``.
        label_b: Display label for ``b`` in legends and series.
            Defaults to ``"B"``.

    Attributes:
        dataset_a: The first source :class:`Dataset` passed to the constructor.
        dataset_b: The second source :class:`Dataset` passed to the constructor.
        label_a: Display label for ``dataset_a``.
        label_b: Display label for ``dataset_b``.
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

        Note:
            If either source has reactive bindings, this constructor
            evaluates them once at construction time and bakes the result
            in. Reactive comparisons (where both sides re-react to a
            shared :class:`Lens`) will be handled in a future iteration
            once the dashboard layer exists to drive them.

        Args:
            a: The first dataset.
            b: The second dataset. Should be schema-compatible with ``a``.
            label_a: Display label for ``a`` in legends and series.
                Defaults to ``"A"``.
            label_b: Display label for ``b`` in legends and series.
                Defaults to ``"B"``.
        """
        if a._reactive_bindings or b._reactive_bindings:
            import warnings

            warnings.warn(
                "ComparedDataset does not yet propagate reactive bindings "
                "from its sources. Lens changes will not update this "
                "comparison; current values are baked in.",
                stacklevel=2,
            )
        # `to_lazy()` returns the resolved LF (any bindings applied at the
        # current parameter values).
        merged = pl.concat(
            [
                a.to_lazy().with_columns(pl.lit(label_a).alias("__series__")),
                b.to_lazy().with_columns(pl.lit(label_b).alias("__series__")),
            ],
            how="vertical_relaxed",
        )
        super().__init__(merged, schema=a.schema, name=a.name)
        self.dataset_a = a
        self.dataset_b = b
        self.label_a = label_a
        self.label_b = label_b

    def _with(
        self,
        lf: pl.LazyFrame,
        *,
        schema: Schema | None = None,
        extra_bindings: list[ReactiveBinding] | None = None,
        catalog: Catalog | None = None,
    ) -> Dataset:
        """Return a plain Dataset; comparison metadata doesn't propagate.

        Override of :meth:`Dataset._with`. Once a ``ComparedDataset`` is
        chained through ``filter()`` etc., the result is a plain
        ``Dataset`` whose underlying data still carries the ``__series__``
        column. Rebuilding a ``ComparedDataset`` would require splitting
        and re-concatenating, which adds no value over the discriminator
        column already present.

        Args:
            lf: The polars LazyFrame backing the new Dataset.
            schema: Optional Schema. If ``None``, ``self.schema`` is reused.
            extra_bindings: Optional list of reactive bindings introduced
                by the current chain step. Appended after any bindings
                already present on ``self``.
            catalog: Unused in ComparedDataset; passed through for
                compatibility with base class signature.

        Returns:
            A plain :class:`Dataset` (never a :class:`ComparedDataset`).
        """
        merged_bindings = list(self._reactive_bindings)
        if extra_bindings:
            merged_bindings.extend(extra_bindings)
        return Dataset(
            lf,
            schema=schema or self.schema,
            name=self.name,
            _reactive_bindings=merged_bindings,
        )


# ─── module-level helpers ───────────────────────────────────────────────────


def _coerce_to_datetime(value: DateBound) -> datetime:
    """Convert a date/datetime/ISO string to a datetime.

    Args:
        value: A :class:`~datetime.date`, :class:`~datetime.datetime`,
            or ISO-format string (e.g. ``"2025-01-01"`` or
            ``"2025-01-01T12:00:00"``).

    Returns:
        A :class:`~datetime.datetime`. ``date`` inputs are widened to
        midnight; ``datetime`` inputs are returned as-is.

    Raises:
        ValueError: If ``value`` is a string that cannot be parsed as
            an ISO datetime.
        TypeError: If ``value`` is not a date, datetime, or string.
    """
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
    """Build a polars aggregation expression for ``col`` using ``fn``.

    Args:
        col: The column name to aggregate. The output expression aliases
            back to this same name.
        fn: The aggregation function name. One of the values allowed by
            :data:`ResampleAgg`.

    Returns:
        A :class:`polars.Expr` computing ``fn(col)`` and aliased to ``col``.
    """
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
