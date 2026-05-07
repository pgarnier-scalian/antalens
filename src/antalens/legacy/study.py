"""Legacy study adapter (stub for Phase 2)."""

from __future__ import annotations


class LegacyStudy:
    """Legacy study adapter.

    .. deprecated:: 0.2.0
        This module is a placeholder for Phase 2 implementation.
        Use :mod:`antalens.data.loaders` with GEMS parquet files instead.

    Raises:
        NotImplementedError: Always raised when instantiated.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Initialize LegacyStudy.

        Raises:
            NotImplementedError: This class is a stub for Phase 2.
        """
        raise NotImplementedError(
            "LegacyStudy is a Phase 2 placeholder. "
            "Use al.io.load_parquet() with GEMS parquet files instead."
        )


__all__ = ["LegacyStudy"]
