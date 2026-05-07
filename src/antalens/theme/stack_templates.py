"""Stack templates — ordered fuel/category palettes for production stacks.

A :class:`StackTemplate` defines the visual identity of a stacked-area
chart: which categories appear, in what order, with what color, and on
which side of the zero line. Users can register their own via
:func:`register_template`.

The template is decoupled from any specific dataset — a template defines
"what a category should look like in any chart"; the chart code matches
the template's categories against actual data column values.

Example::

    from antalens.theme import StackTemplate, StackLayer

    # Build a custom template
    my_template = StackTemplate(
        name="my-mix",
        layers=(
            StackLayer("solar", "#fbbf24"),
            StackLayer("wind", "#34d399"),
            StackLayer("battery", "#fb7185", side="negative"),
        ),
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

StackSide = Literal["positive", "negative"]
"""Which side of the zero line a layer sits on."""


@dataclass(frozen=True, slots=True)
class StackLayer:
    """One ordered category in a stack template.

    Attributes:
        category: The value to match against the ``stack_by`` column of
            the dataset (e.g. ``"solar"``, ``"gas"``, ``"battery"``).
        color: The fill color, as a CSS hex string ``"#rrggbb"``.
        side: ``"positive"`` (default) for generation stacked above zero;
            ``"negative"`` for storage charging, exports, or other
            consumption-type series rendered below the zero line.
    """

    category: str
    color: str
    side: StackSide = "positive"


@dataclass(frozen=True, slots=True)
class StackTemplate:
    """A named, ordered template defining a stacked-area chart's layers.

    Layers are bottom-to-top — ``layers[0]`` renders against the zero
    line, subsequent layers stack on top. This is what controls visual
    ordering: base generation at the bottom, peaking generation at the top.

    Attributes:
        name: A human-readable identifier.
        layers: The ordered tuple of :class:`StackLayer` instances.
        display_name: Optional human-readable display name for UI contexts.
        description: Optional free-text description of the template's intent.
        _yaml_path: Optional path to the source YAML file, if loaded from YAML.
    """

    name: str
    layers: tuple[StackLayer, ...]
    display_name: str | None = None
    description: str | None = None
    _yaml_path: Path | None = field(default=None, compare=False, repr=False)

    def color_of(self, category: str) -> str | None:
        """Return the color for a category, or ``None`` if not in template."""
        for layer in self.layers:
            if layer.category == category:
                return layer.color
        return None

    def categories(self, side: StackSide | None = None) -> list[str]:
        """Return category names, optionally filtered by side."""
        return [layer.category for layer in self.layers if side is None or layer.side == side]

    @classmethod
    def from_dict(
        cls,
        mapping: dict[str, str],
        *,
        name: str = "custom",
    ) -> StackTemplate:
        """Build a template from a ``{category: color}`` dict.

        Convenience for users who don't need negative layers — every
        layer is positive, in dict-insertion order.
        """
        layers = tuple(StackLayer(cat, color) for cat, color in mapping.items())
        return cls(name=name, layers=layers)

    @classmethod
    def from_yaml(cls, path: str | Path) -> StackTemplate:
        """Load a template from a YAML file.

        Args:
            path: Path to a YAML file containing a stack template.

        Returns:
            A :class:`StackTemplate` instance with ``_yaml_path`` set.

        Raises:
            FileNotFoundError: If the YAML file doesn't exist.
            yaml.YAMLError: If the file is malformed.

        Examples:
            >>> template = StackTemplate.from_yaml("catalogs/examples/gems.yml")
            >>> template.name
            'gems'
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"stack template not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        layers = tuple(
            StackLayer(
                category=layer["name"],
                color=layer["color"],
                side=layer.get("side", "positive"),
            )
            for layer in data["layers"]
        )

        return cls(
            name=data["name"],
            layers=layers,
            display_name=data.get("display_name"),
            description=data.get("description"),
            _yaml_path=path,
        )

    def to_dict(self) -> dict[str, Any]:
        """Export the template to a dictionary suitable for YAML serialization.

        Returns:
            A dict mapping category names to colors, suitable for passing to
            :meth:`from_dict`.
        """
        return {layer.category: layer.color for layer in self.layers}


# ─── deprecated built-in templates ───────────────────────────────────────────


"""DEPRECATED module constants.

These built-in constants are deprecated and will be removed in a future
release. Load from YAML instead::

    from antalens.theme import StackTemplate
    tmpl = StackTemplate.from_yaml("catalogs/examples/gems.yml")
"""


# ─── registry ────────────────────────────────────────────────────────────────


_REGISTRY: dict[str, StackTemplate] = {}


def register_template(template: StackTemplate) -> None:
    """Register a custom template so it can be looked up by name.

    After registering, callers can pass the template's name as a string
    to :class:`~antalens.plots.stack.ProductionStack`'s ``template=``
    argument instead of the instance.

    Args:
        template: The template to register. Its ``name`` is used as the
            registry key, overwriting any existing entry with the same
            name.
    """
    _REGISTRY[template.name] = template


def get_template(name_or_obj: str | StackTemplate | dict[str, str]) -> StackTemplate:
    """Resolve a template by name, instance, or dict.

    Args:
        name_or_obj: A registered template name,
            a :class:`StackTemplate` instance (returned as-is), or a
            ``{category: color}`` dict (auto-wrapped via
            :meth:`StackTemplate.from_dict`).

    Returns:
        The resolved :class:`StackTemplate`.

    Raises:
        KeyError: If a string name doesn't match any registered template.
        TypeError: If the argument is none of the supported types.
    """
    if isinstance(name_or_obj, StackTemplate):
        return name_or_obj
    if isinstance(name_or_obj, dict):
        return StackTemplate.from_dict(name_or_obj)
    if isinstance(name_or_obj, str):
        if name_or_obj not in _REGISTRY:
            raise KeyError(
                f"unknown stack template {name_or_obj!r}. "
                f"Registered: {sorted(_REGISTRY)!r}. Use "
                f"register_template() to add custom ones."
            )
        return _REGISTRY[name_or_obj]
    raise TypeError(
        f"template must be a name, StackTemplate, or dict; got {type(name_or_obj).__name__}"
    )
