"""Loaders for constructing :class:`~antalens.data.dataset.Dataset` objects.

All loaders return a :class:`Dataset` (or one of its subclasses). They are
pure functions — no filesystem mutation, no global state.

The shape of a loader call is::

    al.io.load_parquet("data.parquet")
    al.io.load_csv("data.csv", time_col="timestamp")
    al.io.from_dataframe(my_df, name="experiment-A")

Every loader accepts:

- A source argument specific to its format (path, DataFrame, query, …).
- ``time_col`` to override schema inference.
- ``name`` to attach a human-readable label.
- Format-specific keyword arguments forwarded to the underlying reader.

Optional formats (HDF5, ANTARES studies, SQL) live in submodules gated
by install extras. Importing them without the extras installed raises a
helpful :class:`ImportError`.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

from antalens.data.dataset import Dataset
from antalens.data.schema import infer_schema

if TYPE_CHECKING:
    import pandas as pd
    import xarray as xr


# Acceptable inputs for path-like arguments.
PathLike = str | Path


# ─── parquet ────────────────────────────────────────────────────────────────


def load_parquet(
    source: PathLike | Iterable[PathLike],
    *,
    time_col: str | None = None,
    name: str | None = None,
    **read_kwargs: Any,
) -> Dataset:
    """Load one or more parquet files into a :class:`Dataset`.

    Uses polars' ``scan_parquet`` so the file is opened lazily — the data
    is not read into memory until a chain method or plot builder forces
    materialization.

    Args:
        source: Path to a single parquet file, a glob pattern (e.g.
            ``"data/*.parquet"``), or an iterable of paths to concatenate.
        time_col: Override automatic time column detection. Pass an empty
            string ``""`` to indicate "no time column".
        name: Optional display name surfaced in plot titles and legends.
        **read_kwargs: Additional keyword arguments forwarded to
            :func:`polars.scan_parquet`.

    Returns:
        A :class:`Dataset` wrapping the lazy scan.

    Raises:
        FileNotFoundError: If a single explicit path does not exist.
            (Glob patterns matching zero files are passed through to
            polars, which produces its own diagnostic.)
        ValueError: If ``source`` is an empty iterable.

    Examples:
        Single file::

            ds = al.io.load_parquet("data/year_2025.parquet")

        Multiple files concatenated vertically::

            ds = al.io.load_parquet([
                "data/year_2025.parquet",
                "data/year_2030.parquet",
            ])

        Glob pattern::

            ds = al.io.load_parquet("data/year_*.parquet")
    """
    paths = _normalize_paths(source)
    if isinstance(paths, list):
        if not paths:
            raise ValueError("load_parquet received an empty list of paths.")
        # Validate each explicit path. Globs are not validated up-front
        # because zero matches is a polars-level concern.
        for p in paths:
            _check_path_exists(p)
        lf = pl.scan_parquet(paths, **read_kwargs)
    else:
        # Single path or glob pattern (string).
        if isinstance(paths, Path):
            _check_path_exists(paths)
        lf = pl.scan_parquet(paths, **read_kwargs)

    schema = infer_schema(lf, time_col=time_col)
    return Dataset(lf, schema=schema, name=name)


# ─── csv ────────────────────────────────────────────────────────────────────


def load_csv(
    source: PathLike,
    *,
    time_col: str | None = None,
    name: str | None = None,
    parse_dates: bool = True,
    **read_kwargs: Any,
) -> Dataset:
    """Load a CSV file into a :class:`Dataset`.

    Uses polars' ``scan_csv`` for lazy loading. By default, columns whose
    names match common time hints are parsed as datetimes — this matches
    user expectations for typical time-series CSVs.

    Args:
        source: Path to a CSV file or glob pattern.
        time_col: Override automatic time column detection.
        name: Optional display name.
        parse_dates: Whether to attempt date parsing on string columns.
            When ``True``, polars' ``try_parse_dates`` is enabled.
        **read_kwargs: Additional keyword arguments forwarded to
            :func:`polars.scan_csv`. The ``try_parse_dates`` argument is
            controlled by ``parse_dates``; passing it directly raises
            ``TypeError``.

    Returns:
        A :class:`Dataset` wrapping the lazy scan.

    Raises:
        FileNotFoundError: If ``source`` is a single path that doesn't exist.
        TypeError: If ``try_parse_dates`` is passed in ``read_kwargs``.

    Examples:
        Standard time-series CSV with date parsing::

            ds = al.io.load_csv("measurements.csv")

        Disable date parsing for performance on large files::

            ds = al.io.load_csv("big.csv", parse_dates=False)
    """
    if "try_parse_dates" in read_kwargs:
        raise TypeError(
            "Pass parse_dates= instead of try_parse_dates= to load_csv. "
            "The parse_dates argument is the canonical AntaLens spelling."
        )

    path = Path(source) if isinstance(source, str) and "*" not in source else source
    if isinstance(path, Path):
        _check_path_exists(path)

    lf = pl.scan_csv(source, try_parse_dates=parse_dates, **read_kwargs)
    schema = infer_schema(lf, time_col=time_col)
    return Dataset(lf, schema=schema, name=name)


# ─── from_dataframe ─────────────────────────────────────────────────────────


def from_dataframe(
    df: pl.DataFrame | pl.LazyFrame | pd.DataFrame | xr.Dataset,
    *,
    time_col: str | None = None,
    name: str | None = None,
) -> Dataset:
    """Wrap an in-memory DataFrame as a :class:`Dataset`.

    The escape hatch for users whose data is already in memory. Accepts
    polars DataFrames and LazyFrames natively; pandas DataFrames are
    converted via :func:`polars.from_pandas`; xarray datasets are flattened
    via ``to_dataframe()``.

    Args:
        df: The data to wrap.
        time_col: Override automatic time column detection.
        name: Optional display name.

    Returns:
        A :class:`Dataset` wrapping the data.

    Raises:
        TypeError: If ``df`` is not one of the accepted types.

    Examples:
        From an existing polars DataFrame::

            df = pl.DataFrame({"ts": [...], "load": [...]})
            ds = al.io.from_dataframe(df)

        From a pandas DataFrame::

            ds = al.io.from_dataframe(my_pandas_df, time_col="timestamp")
    """
    lf = _coerce_to_lazyframe(df)
    schema = infer_schema(lf, time_col=time_col)
    return Dataset(lf, schema=schema, name=name)


# ─── internal helpers ───────────────────────────────────────────────────────


def _normalize_paths(
    source: PathLike | Iterable[PathLike],
) -> str | Path | list[Path]:
    """Coerce a path-or-iterable argument into a polars-friendly form.

    Returns:
        - A ``str`` if ``source`` is a string (preserved so glob patterns
          reach polars unchanged).
        - A ``Path`` if ``source`` is a single ``Path``.
        - A ``list[Path]`` if ``source`` is an iterable of paths.
    """
    if isinstance(source, str):
        return source
    if isinstance(source, Path):
        return source
    # Treat as iterable
    return [Path(p) for p in source]


def _check_path_exists(path: Path) -> None:
    """Raise FileNotFoundError with a helpful message if ``path`` is missing."""
    if not path.exists():
        raise FileNotFoundError(
            f"No file at {path!s}. Check the path is correct and the file is readable."
        )


def _coerce_to_lazyframe(
    df: pl.DataFrame | pl.LazyFrame | pd.DataFrame | xr.Dataset,
) -> pl.LazyFrame:
    """Convert any supported DataFrame type into a polars LazyFrame."""
    if isinstance(df, pl.LazyFrame):
        return df
    if isinstance(df, pl.DataFrame):
        return df.lazy()

    # pandas — only import on demand to keep the path light when not used.
    try:
        import pandas as pd
    except ImportError:
        pd = None  # type: ignore[assignment]

    if pd is not None and isinstance(df, pd.DataFrame):
        return pl.from_pandas(df).lazy()

    # xarray — same on-demand import.
    try:
        import xarray as xr
    except ImportError:
        xr = None  # type: ignore[assignment]

    if xr is not None and isinstance(df, xr.Dataset):
        # Flatten to a long-format DataFrame. Users with multi-dim data
        # who want xarray-native handling will get it in Phase 4 via
        # AntaresStudy; for now, flatten and let the schema infer.
        return pl.from_pandas(df.to_dataframe().reset_index()).lazy()

    raise TypeError(
        f"from_dataframe expected a polars/pandas DataFrame or xarray "
        f"Dataset, got {type(df).__name__}. If you have data in another "
        f"format, convert it to one of these first."
    )
