"""Backwards-compatibility adapter for legacy studies.

This module provides legacy adapters that are not part of the architectural
core; they exist for backwards compatibility with pre-GEMS studies.
"""

from __future__ import annotations

from pathlib import Path

from antalens.legacy.study import LegacyStudy

__all__ = ["LegacyStudy", "load_legacy"]


def load_legacy(path: str | Path, mc_years: list[int] | None = None) -> LegacyStudy:
    """Load a legacy study.

    Convenience function that returns an :class:`LegacyStudy` instance.

    Args:
        path: Path to the legacy study output folder.
        mc_years: Optional list of Monte Carlo years to include.

    Returns:
        An :class:`LegacyStudy` instance.

    Raises:
        NotImplementedError: Always raised as this is a Phase 2 placeholder.
    """
    return LegacyStudy(path, mc_years)
