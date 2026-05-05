"""Sphinx configuration for AntaLens documentation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

project = "AntaLens"
author = "AntaLens contributors"
copyright = "2026, AntaLens contributors"
release = "0.0.1"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",  # Google-style docstrings
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "myst_parser",  # Markdown support
]

# Build fails on broken cross-references
nitpicky = True
nitpick_ignore: list[tuple[str, str]] = []

# MyST settings
myst_enable_extensions = ["colon_fence", "deflist", "tasklist"]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}

# Autodoc
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
    "member-order": "bysource",
}
autodoc_typehints = "description"
autosummary_generate = True

# Intersphinx — link to other libraries' docs
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "polars": ("https://docs.pola.rs/api/python/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "panel": ("https://panel.holoviz.org/", None),
}

# Theme
html_theme = "furo"
html_title = "AntaLens"
html_theme_options = {
    "sidebar_hide_name": False,
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
