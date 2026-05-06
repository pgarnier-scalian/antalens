"""Stack templates — ordered fuel/category palettes for production stacks.

A :class:`StackTemplate` defines the visual identity of a stacked-area
chart: which categories appear, in what order, with what color, and on
which side of the zero line. Built-in templates cover common power-system
conventions (eco2mix); users can register their own via
:func:`register_template`.

The template is decoupled from any specific dataset — a template defines
"what nuclear should look like in any chart"; the chart code matches
the template's categories against actual data column values.

Example::

    from antalens.theme import ECO2MIX, StackTemplate, StackLayer

    # Inspect a built-in template
    print(ECO2MIX.layers[0])
    # StackLayer(category='nuclear', color='#6366f1', side='positive')

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

from dataclasses import dataclass
from typing import Literal

StackSide = Literal["positive", "negative"]
"""Which side of the zero line a layer sits on."""


@dataclass(frozen=True, slots=True)
class StackLayer:
    """One ordered category in a stack template.

    Attributes:
        category: The value to match against the ``stack_by`` column of
            the dataset (e.g. ``"nuclear"``, ``"gas"``, ``"battery"``).
        color: The fill color, as a CSS hex string ``"#rrggbb"``.
        side: ``"positive"`` (default) for generation stacked above zero;
            ``"negative"`` for storage charging, exports, or other
            consumption-type series rendered below zero.
    """

    category: str
    color: str
    side: StackSide = "positive"


@dataclass(frozen=True, slots=True)
class StackTemplate:
    """A named, ordered template defining a stacked-area chart's layers.

    Layers are bottom-to-top — ``layers[0]`` renders against the zero
    line, subsequent layers stack on top. This is what controls visual
    ordering: nuclear at the bottom, peaking generation at the top.

    Attributes:
        name: A human-readable identifier.
        layers: The ordered tuple of :class:`StackLayer` instances.
    """

    name: str
    layers: tuple[StackLayer, ...]

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


# ─── built-in templates ────────────────────────────────────────────────────


ECO2MIX = StackTemplate(
    name="eco2mix",
    layers=(
        StackLayer("nuclear", "#6366f1"),
        StackLayer("hydro", "#38bdf8"),
        StackLayer("wind", "#34d399"),
        StackLayer("solar", "#fbbf24"),
        StackLayer("bioenergy", "#84cc16"),
        StackLayer("gas", "#f97316"),
        StackLayer("coal", "#78716c"),
        StackLayer("oil", "#525252"),
        StackLayer("imports", "#a855f7"),
        StackLayer("battery", "#fb7185", side="negative"),
        StackLayer("pumped_hydro", "#0ea5e9", side="negative"),
        StackLayer("exports", "#94a3b8", side="negative"),
    ),
)
"""French TSO standard production-stack ordering and colors.

Suitable for ANTARES outputs and any dataset using the canonical
fuel-type names: ``nuclear``, ``hydro``, ``wind``, ``solar``, etc.
"""


BASE = StackTemplate(
    name="base",
    layers=(
        StackLayer("baseload", "#6366f1"),
        StackLayer("intermittent", "#34d399"),
        StackLayer("dispatchable", "#f97316"),
        StackLayer("peaker", "#ef4444"),
    ),
)
"""Generic four-tier template for non-fuel-specific data.

Suitable for aggregated datasets where unit-level detail is collapsed
into broad categories.
"""


# ─── registry ──────────────────────────────────────────────────────────────


_REGISTRY: dict[str, StackTemplate] = {
    "eco2mix": ECO2MIX,
    "base": BASE,
}


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
        name_or_obj: A registered template name (e.g. ``"eco2mix"``),
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
