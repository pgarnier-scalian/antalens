"""Catalog dataclasses — domain semantics for GEMS data."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class ComponentPattern:
    """A regex pattern for parsing component names.

    Attributes:
        pattern: Python regex pattern with named groups.
        kind: The component kind the pattern matches (e.g. "generator", "link").
        display: Format string for display names, e.g. "{fuel} unit {unit} ({area})".
    """

    pattern: str
    kind: str
    display: str


@dataclass(frozen=True, slots=True)
class OutputMetadata:
    """Display metadata for an output/variable.

    Attributes:
        display: Human-readable display name (e.g. "Production").
        unit: Unit of measurement (e.g. "MW", "€/MWh").
        default_agg: Default aggregation function for this output.
    """

    display: str
    unit: str | None = None
    default_agg: str = "mean"


@dataclass(frozen=True, slots=True)
class ColorPalette:
    """A named color palette.

    Attributes:
        name: The palette name.
        colors: Mapping from category to hex color.
    """

    name: str
    colors: dict[str, str]


@dataclass(frozen=True, slots=True)
class StackTemplateConfig:
    """A stack template defined in the catalog.

    Attributes:
        order: List of category names in stack order (bottom to top).
        negative: Category names that should render as negative (below zero).
        palette: Reference to a named palette for colors.
    """

    order: list[str]
    negative: list[str] = field(default_factory=list)
    palette: str | None = None


@dataclass(frozen=True, slots=True)
class Catalog:
    """A domain catalog for GEMS data.

    This is a read-only view of a YAML catalog file. It maps generic GEMS
    column names to domain semantics: component naming conventions, output
    display metadata, color palettes, and stack template definitions.

    Attributes:
        component_patterns: Ordered list of regex patterns for parsing
            component names. Applied in order — first match wins.
        outputs: Mapping of output names to their display metadata.
        palettes: Named color palettes defined in the catalog.
        stack_templates: Stack template configurations.
        _yaml_path: Optional path to the source YAML file.

    Examples:
        Load a catalog from YAML::

            from antalens.catalog import Catalog
            cat = Catalog.from_yaml("catalogs/examples/gems.yml")
            len(cat.outputs)
            3

        Access output metadata::

            cat.outputs["p"].display
            'Production'
    """

    component_patterns: list[ComponentPattern] = field(default_factory=list)
    outputs: dict[str, OutputMetadata] = field(default_factory=dict)
    palettes: dict[str, ColorPalette] = field(default_factory=dict)
    stack_templates: dict[str, StackTemplateConfig] = field(default_factory=dict)
    _yaml_path: Path | None = field(default=None, compare=False, repr=False)

    @classmethod
    def from_yaml(cls, path: str | Path) -> Catalog:
        """Load a catalog from a YAML file.

        Args:
            path: Path to a YAML catalog file.

        Returns:
            A :class:`Catalog` instance.

        Raises:
            FileNotFoundError: If the YAML file doesn't exist.
            yaml.YAMLError: If the file is malformed.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"catalog not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls._from_dict(data, yaml_path=path)

    @classmethod
    def from_string(cls, yaml_content: str) -> Catalog:
        """Load a catalog from a YAML string.

        Args:
            yaml_content: YAML-formatted catalog definition.

        Returns:
            A :class:`Catalog` instance.
        """
        data = yaml.safe_load(yaml_content)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any], *, yaml_path: Path | None = None) -> Catalog:
        """Build a Catalog from a parsed YAML dict."""
        component_patterns = []
        if "component_patterns" in data:
            for cp in data["component_patterns"]:
                component_patterns.append(
                    ComponentPattern(
                        pattern=cp["pattern"],
                        kind=cp["kind"],
                        display=cp["display"],
                    )
                )

        outputs = {}
        if "outputs" in data:
            for name, meta in data["outputs"].items():
                outputs[name] = OutputMetadata(
                    display=meta.get("display", name),
                    unit=meta.get("unit"),
                    default_agg=meta.get("default_agg", "mean"),
                )

        palettes = {}
        if "palette" in data:
            for palette_name, colors in data["palette"].items():
                palettes[palette_name] = ColorPalette(name=palette_name, colors=colors)

        stack_templates = {}
        if "stack_templates" in data:
            for name, config in data["stack_templates"].items():
                stack_templates[name] = StackTemplateConfig(
                    order=config.get("order", []),
                    negative=config.get("negative", []),
                    palette=config.get("palette"),
                )

        return cls(
            component_patterns=component_patterns,
            outputs=outputs,
            palettes=palettes,
            stack_templates=stack_templates,
            _yaml_path=yaml_path,
        )

    def components_of_kind(self, kind: str, candidates: list[str] | None = None) -> list[str]:
        """Return component names matching a given kind via the catalog's patterns.

        Walks ``component_patterns`` in order, finds those matching ``kind``,
        and tests each candidate component name against the corresponding
        regex. A candidate matches the kind if it matches at least one
        pattern of that kind.

        Args:
            kind: The component kind to match (e.g. ``"generator"``,
                ``"link"``).
            candidates: List of component names to test. Typically the
                ``.components`` of a :class:`SimulationTable`. If ``None``,
                returns an empty list (the catalog alone can't enumerate
                what components exist — it only knows the parsing rules).

        Returns:
            The subset of ``candidates`` whose names match a pattern
            registered for the given kind. Order matches ``candidates``.

        Examples:
            >>> cat = Catalog.from_yaml("catalog.yml")  # doctest: +SKIP
            >>> sim = al.io.load_simulation_table("sim.parquet")  # doctest: +SKIP
            >>> generators = cat.components_of_kind("generator", sim.components)  # doctest: +SKIP
        """
        import re

        if candidates is None:
            return []

        # Pre-compile all patterns for the requested kind, once.
        kind_patterns = [re.compile(p.pattern) for p in self.component_patterns if p.kind == kind]
        if not kind_patterns:
            return []

        return [name for name in candidates if any(rx.match(name) for rx in kind_patterns)]
