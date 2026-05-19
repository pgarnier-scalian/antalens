"""Tests for :func:`antalens.catalog.load_catalog`.

The function is a thin delegate to :meth:`Catalog.from_yaml`. These
tests validate the end-to-end YAML → Catalog round-trip, not the
delegate plumbing itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from antalens.catalog import Catalog, load_catalog

# ─── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def minimal_yaml(tmp_path: Path) -> Path:
    """A minimal but complete catalog covering every section."""
    path = tmp_path / "catalog.yml"
    path.write_text("""
component_patterns:
  - pattern: '^gen_(?P<area>\\w+)$'
    kind: generator
    display: 'Gen {area}'
outputs:
  p:
    display: 'Power'
    unit: 'MW'
    default_agg: 'sum'
palette:
  default:
    nuclear: '#6366f1'
    wind: '#34d399'
stack_templates:
  default:
    order: [nuclear, wind]
    palette: default
""")
    return path


# ─── basic loading ────────────────────────────────────────────────────────


def test_load_minimal_catalog_returns_catalog(minimal_yaml: Path) -> None:
    cat = load_catalog(minimal_yaml)
    assert isinstance(cat, Catalog)


def test_load_records_yaml_path(minimal_yaml: Path) -> None:
    cat = load_catalog(minimal_yaml)
    assert cat._yaml_path == minimal_yaml


def test_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_catalog("/tmp/nonexistent_catalog_xyz.yml")


def test_accepts_string_path(minimal_yaml: Path) -> None:
    cat = load_catalog(str(minimal_yaml))
    assert isinstance(cat, Catalog)


# ─── component_patterns ───────────────────────────────────────────────────


def test_component_patterns_parsed(minimal_yaml: Path) -> None:
    cat = load_catalog(minimal_yaml)
    assert len(cat.component_patterns) == 1
    p = cat.component_patterns[0]
    assert p.kind == "generator"
    assert p.pattern == r"^gen_(?P<area>\w+)$"
    assert p.display == "Gen {area}"


def test_empty_component_patterns(tmp_path: Path) -> None:
    """A catalog without the section gets an empty list, not an error."""
    path = tmp_path / "min.yml"
    path.write_text("outputs:\n  p: {display: Power}\n")
    cat = load_catalog(path)
    assert cat.component_patterns == []


# ─── outputs ───────────────────────────────────────────────────────────────


def test_outputs_parsed(minimal_yaml: Path) -> None:
    cat = load_catalog(minimal_yaml)
    assert "p" in cat.outputs
    assert cat.outputs["p"].display == "Power"
    assert cat.outputs["p"].unit == "MW"
    assert cat.outputs["p"].default_agg == "sum"


def test_outputs_defaults_apply(tmp_path: Path) -> None:
    """Missing optional fields fall back to dataclass defaults."""
    path = tmp_path / "min.yml"
    path.write_text("""
outputs:
  p: {}
""")
    cat = load_catalog(path)
    assert cat.outputs["p"].display == "p"
    assert cat.outputs["p"].unit is None
    assert cat.outputs["p"].default_agg == "mean"


# ─── palette (note: 'palette' not 'palettes' per Catalog._from_dict) ──────


def test_palette_parsed(minimal_yaml: Path) -> None:
    cat = load_catalog(minimal_yaml)
    assert "default" in cat.palettes
    pal = cat.palettes["default"]
    assert pal.name == "default"
    assert pal.colors["nuclear"] == "#6366f1"
    assert pal.colors["wind"] == "#34d399"


# ─── stack_templates ──────────────────────────────────────────────────────


def test_stack_templates_parsed(minimal_yaml: Path) -> None:
    cat = load_catalog(minimal_yaml)
    tpl = cat.stack_templates["default"]
    assert tpl.order == ["nuclear", "wind"]
    assert tpl.palette == "default"
    assert tpl.negative == []


# ─── from_string ──────────────────────────────────────────────────────────


def test_catalog_from_string_works() -> None:
    """Sanity-check the alternative entrypoint also works."""
    yaml_str = """
outputs:
  p:
    display: 'Production'
    unit: 'MW'
"""
    cat = Catalog.from_string(yaml_str)
    assert cat.outputs["p"].display == "Production"
    assert cat._yaml_path is None  # set only by from_yaml


# ─── bundled example ─────────────────────────────────────────────────────


def test_bundled_gems_minimal_loads() -> None:
    """The shipped example catalog parses without errors."""
    examples_dir = Path(__file__).resolve().parent.parent.parent / "catalogs" / "examples"
    print(examples_dir)
    path = examples_dir / "gems_minimal.yaml"
    if not path.exists():
        pytest.skip(f"Example catalog not found at {path}")
    cat = load_catalog(path)
    assert len(cat.component_patterns) >= 3
    assert "p" in cat.outputs


def test_components_of_kind_filters_candidates(minimal_yaml: Path) -> None:
    cat = load_catalog(minimal_yaml)
    candidates = ["gen_FR", "gen_DE", "load_FR", "link_FR_DE"]
    # The minimal_yaml fixture has one pattern for kind 'generator'
    result = cat.components_of_kind("generator", candidates)
    assert set(result) == {"gen_FR", "gen_DE"}


def test_components_of_kind_unknown_kind_returns_empty(
    minimal_yaml: Path,
) -> None:
    cat = load_catalog(minimal_yaml)
    assert cat.components_of_kind("nonexistent_kind", ["gen_FR"]) == []


def test_components_of_kind_no_candidates_returns_empty(
    minimal_yaml: Path,
) -> None:
    cat = load_catalog(minimal_yaml)
    assert cat.components_of_kind("generator") == []
