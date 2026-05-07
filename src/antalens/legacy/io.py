"""Legacy IO adapter (stub for Phase 2)."""

from __future__ import annotations


def load_simulation_table(*args: object, **kwargs: object) -> None:
    """Load a GEMS simulation table from parquet.

    .. deprecated:: 0.2.0
        This function is a placeholder for Phase 2 implementation.
        Use :func:`antalens.io.load_parquet` instead.

    Raises:
        NotImplementedError: Always raised.
    """
    raise NotImplementedError(
        "load_simulation_table is a Phase 2 placeholder. "
        "Use al.io.load_parquet('output.parquet') instead."
    )


__all__ = ["load_simulation_table"]
