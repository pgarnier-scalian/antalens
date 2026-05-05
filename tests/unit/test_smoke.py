"""Smoke tests — basic import and version checks."""

from __future__ import annotations

import antalens


def test_version_is_string() -> None:
    """Version is exposed and is a string."""
    assert isinstance(antalens.__version__, str)
    assert antalens.__version__ == "0.0.1"


def test_version_in_all() -> None:
    """Version is exported in __all__."""
    assert "__version__" in antalens.__all__
