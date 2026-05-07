"""The :class:`Lens` — shared reactive state for connected dashboards.

A :class:`Lens` is the single source of truth for "what is the dashboard
currently showing?". It carries the user's selections (area, date range,
variable, scenario) as :mod:`param` parameters, which means every change
fires a watch event that downstream consumers can listen to.

The base :class:`Lens` covers the four dimensions most common in time-series
dashboards. For domain-specific extensions — say, an HR dashboard that
needs ``department`` and ``seniority_level`` — use :meth:`Lens.with_extras`::

    HRLens = Lens.with_extras(
        department=param.String(default=None),
        seniority_level=param.String(default=None),
    )
    lens = HRLens()

Plot builders (and :meth:`Dataset.filter`) accept a :class:`Lens` or a
specific :class:`~param.Parameter` reference as a filter argument, and
re-render automatically when the lens mutates.
"""

from __future__ import annotations

import warnings
from datetime import datetime
from typing import Any

import param


class Lens(param.Parameterized):  # type: ignore[misc]
    """Mutable shared state for a connected AntaLens dashboard.

    Every parameter on a :class:`Lens` is reactive: changing it fires
    watch events that bound consumers (filtered Datasets, plot builders,
    widgets) react to.

    Args:
        **params: Initial parameter values, forwarded to
            :class:`param.Parameterized`.

    Examples:
        Basic usage::

            lens = Lens(area="FR", scenario="mean")
            lens.area = "DE"  # fires watch events on all bound consumers

        Subscribing to changes::

            @param.depends(lens.param.area, watch=True)
            def on_area_change(new_area):
                print(f"area changed to {new_area}")
    """

    area = param.String(
        default=None,
        allow_None=True,
        doc="Selected area or region identifier (e.g. 'FR', 'DE').",
    )

    dates = param.DateRange(
        default=None,
        allow_None=True,
        doc="Selected date range as a (start, end) tuple of datetimes.",
    )

    variable = param.String(
        default=None,
        allow_None=True,
        doc="Selected variable / measurement to display (e.g. 'LOAD').",
    )

    scenario = param.Integer(
        default=None,
        allow_None=True,
        doc="Selected Monte Carlo scenario index, 0-based.",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize Lens with deprecated `mc` alias support.

        Args:
            *args: Positional arguments (unused).
            **kwargs: Initial parameter values. If ``mc`` is provided,
                it is converted to ``scenario`` with a deprecation warning.
        """
        # Handle deprecated mc -> scenario migration
        mc = kwargs.pop("mc", None)
        if mc is not None:
            warnings.warn(
                "Lens.mc is deprecated; use Lens.scenario instead. "
                "Pass scenario=<value> instead of mc=<value>.",
                DeprecationWarning,
                stacklevel=2,
            )
            kwargs["scenario"] = mc
        super().__init__(*args, **kwargs)

    @property
    def mc(self) -> str:
        """Deprecated: Use scenario instead.

        Returns:
            The current value of the scenario parameter.

        Raises:
            DeprecationWarning: This property is deprecated.
        """
        warnings.warn(
            "Lens.mc is deprecated; use Lens.scenario instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return object.__getattribute__(self, "scenario")

    @mc.setter
    def mc(self, value: str) -> None:
        """Deprecated: Use scenario instead.

        Args:
            value: The scenario value to set.
        """
        warnings.warn(
            "Lens.mc is deprecated; use Lens.scenario instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.scenario = value

    @classmethod
    def with_extras(cls, **extra_params: param.Parameter) -> type[Lens]:
        """Create a :class:`Lens` subclass with additional parameters.

        Useful for domain-specific dashboards that need parameters beyond
        the four built-in ones. The returned class can be instantiated and
        used like the base :class:`Lens`.

        Args:
            **extra_params: Additional :mod:`param` parameters to add.
                Each value must be a :class:`param.Parameter` instance.

        Returns:
            A new :class:`Lens` subclass with the extra parameters merged in.

        Examples:
            >>> import param
            >>> HRLens = Lens.with_extras(
            ...     department=param.String(default=None),
            ... )
            >>> lens = HRLens(department="engineering")
            >>> lens.department
            'engineering'
            >>> lens.area is None  # base params still present
            True
        """
        # param.Parameterized subclasses are built by the metaclass walking
        # the class body for Parameter instances. We mirror that by setting
        # the new parameters as class-level attributes on a fresh subclass.
        return type(f"{cls.__name__}_Extended", (cls,), extra_params)

    def snapshot(self) -> dict[str, Any]:
        """Return the current parameter values as a plain dict.

        Useful for logging, persistence, or constructing serialisable
        dashboard specs. The dict contains every param defined on this
        class (including inherited ones), but excludes :mod:`param`'s
        internal attributes like ``name``.

        Returns:
            A dict mapping parameter names to their current values.

        Examples:
            >>> lens = Lens(area="FR", scenario="mean")
            >>> snap = lens.snapshot()
            >>> snap["area"]
            'FR'
            >>> snap["scenario"]
            'mean'
        """
        return {
            p: getattr(self, p)
            for p in self.param
            if p not in ("name", "mc")  # exclude param internal 'name' and deprecated 'mc' alias
        }


# ─── filter binding helpers ─────────────────────────────────────────────────


# Maps the keyword used in `Dataset.filter()` to the corresponding parameter
# name on `Lens`. Used when a user passes a whole `Lens` to a filter kwarg
# rather than picking a specific parameter — we need to know which lens
# parameter to bind.
_FILTER_KWARG_TO_LENS_PARAM: dict[str, str] = {
    "area": "area",
    "variable": "variable",
    "date_range": "dates",
}


def resolve_filter_value(
    kwarg_name: str,
    value: Any,
) -> tuple[Any, param.Parameter | None]:
    """Resolve a filter argument to (current_value, watched_parameter).

    Used internally by :meth:`Dataset.filter` to handle the three forms
    a filter argument can take:

    1. **Static value** — return it unchanged, no watch.
    2. **A :mod:`param.Parameter` reference** — read its current value
       and return the parameter for watching.
    3. **A whole :class:`Lens`** — pick the parameter matching the
       ``kwarg_name`` (via :data:`_FILTER_KWARG_TO_LENS_PARAM`), read its
       current value, return it for watching.

    Args:
        kwarg_name: The name of the kwarg being filtered on. Used to
            disambiguate when ``value`` is a whole :class:`Lens`.
        value: The argument value — static, parameter, or lens.

    Returns:
        A tuple ``(current_value, watched_param_or_None)``. The first
        element is what to use for filtering right now; the second is the
        :mod:`param` parameter to watch for future updates, or ``None``
        if the binding is static.

    Raises:
        ValueError: If ``value`` is a :class:`Lens` but ``kwarg_name``
            doesn't have a known mapping to a lens parameter.

    Examples:
        Static value::

            >>> resolve_filter_value("area", "FR")
            ('FR', None)

        Lens-bound value::

            >>> lens = Lens(area="DE")
            >>> current, watched = resolve_filter_value("area", lens)
            >>> current
            'DE'
            >>> watched is lens.param.area
            True
    """
    if isinstance(value, Lens):
        if kwarg_name not in _FILTER_KWARG_TO_LENS_PARAM:
            raise ValueError(
                f"filter kwarg {kwarg_name!r} cannot be bound to a Lens "
                f"directly because there's no canonical Lens parameter for "
                f"it. Use lens.param.{kwarg_name} explicitly, or pass a "
                f"static value."
            )
        param_name = _FILTER_KWARG_TO_LENS_PARAM[kwarg_name]
        watched = getattr(value.param, param_name)
        current = getattr(value, param_name)
        return current, watched

    if isinstance(value, param.parameterized.Parameter):
        owner = value.owner
        name = value.name

        if owner is not None and name is not None:  # noqa
            current = getattr(owner, name)
        else:
            current = value.default

        return current, value

    # Static value — no watch needed.
    return value, None


def is_reactive(value: Any) -> bool:
    """Return whether ``value`` is a reactive binding (Lens or Parameter)."""
    return isinstance(value, Lens | param.parameterized.Parameter)


# ─── datetime range helper ──────────────────────────────────────────────────


def normalize_lens_date_range(
    date_range: Any,
) -> tuple[datetime, datetime] | None:
    """Coerce a ``Lens.dates``-shaped value into a 2-tuple of datetimes.

    Param's ``DateRange`` parameter holds a ``(start, end)`` tuple of
    datetimes when set, or ``None`` when unset. This helper exists so
    callers don't repeat the None-check.

    Args:
        date_range: Either ``None`` or a ``(datetime, datetime)`` tuple.

    Returns:
        ``None`` if input is ``None``, otherwise the input tuple unchanged.
    """
    if date_range is None:
        return None
    if isinstance(date_range, tuple) and len(date_range) == 2:
        return date_range
    raise TypeError(
        f"Lens.dates must be None or a (start, end) tuple of datetimes, "
        f"got {type(date_range).__name__}: {date_range!r}"
    )
