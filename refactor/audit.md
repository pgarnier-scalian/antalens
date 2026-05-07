# Refactor Audit — Current State vs Target

This document captures the pre-flight audit findings from the 11-task refactor plan. Use this as a reference when executing each task.

---

## Task 1 — Schema Rewrite

### Current State

`src/antalens/data/schema.py`:

```python
@dataclass
class Schema:
    time_col: str | None
    categorical_cols: list[str]
    numeric_cols: list[str]
    geo_cols: list[str]
    ndim: int

def infer_schema(df, time_col=None) -> Schema
```

**Issues:**
- No `kind` discriminator for GEMS compatibility (wide vs long_gems vs xarray)
- No GEMS-specific fields (component_col, output_col, value_col, etc.)
- Uses hardcoded `_TIME_COLUMN_HINTS` and `_GEO_COLUMN_HINTS` (acceptable for inference but should be externalized eventually)

### Target State

```python
@dataclass
class Schema:
    kind: Literal["wide", "long_gems", "xarray"]
    time_col: str | None
    categorical_cols: list[str]
    numeric_cols: list[str]
    geo_cols: list[str]
    ndim: int
    # GEMS-specific fields (only used when kind == "long_gems")
    component_col: str | None = None
    output_col: str | None = None
    value_col: str | None = None
    scenario_col: str | None = None
    abs_time_col: str | None = None
    block_col: str | None = None
```

**Implementation approach:**
- Add `kind` field with default `"wide"` for backwards compatibility
- Add GEMS-specific fields with `None` defaults
- Create `infer_schema()` overload for `kind="long_gems"` that detects GEMS column names
- No breaking changes to existing `Dataset` code

### Status

**NOT STARTED**

---

## Task 1b — Lens mc → scenario Migration

### Current State

`src/antalens/lens.py`, lines 73–79:

```python
class Lens(param.Parameterized):
    area = param.String(default=None, doc="Filter by area")
    dates = param.DateRange(default=None, doc="Filter by date range")
    variable = param.String(default=None, doc="Filter by variable name")
    mc = param.Integer(default=None, doc="Monte Carlo year (legacy ANTARES term)")
```

**Issues:**
- `mc` is legacy ANTARES terminology for Monte Carlo scenario index
- GEMS uses `scenario` instead
- Codebase has mixed usage: some files use `mc`, some use `scenario`

### Target State

```python
class Lens(param.Parameterized):
    area = param.String(default=None, doc="Filter by area")
    dates = param.DateRange(default=None, doc="Filter by date range")
    variable = param.String(default=None, doc="Filter by variable name")
    scenario = param.Integer(default=None, doc="Monte Carlo scenario index")

    # Deprecated alias for backwards compatibility
    def __init__(self, *args, **kwargs):
        mc = kwargs.pop("mc", None)
        if mc is not None:
            warnings.warn(
                "Lens mc parameter is deprecated; use scenario instead",
                DeprecationWarning,
                stacklevel=2
            )
            kwargs["scenario"] = mc
        super().__init__(*args, **kwargs)

    @property
    def mc(self):
        warnings.warn(
            "Lens.mc is deprecated; use Lens.scenario instead",
            DeprecationWarning,
            stacklevel=2
        )
        return self.scenario

    @mc.setter
    def mc(self, value):
        warnings.warn(
            "Lens.mc is deprecated; use Lens.scenario instead",
            DeprecationWarning,
            stacklevel=2
        )
        self.scenario = value
```

**Implementation approach:**
- Add `scenario` parameter
- Add `__init__` to handle deprecated `mc` kwarg
- Add property getter/setter for backwards compatibility
- Update all internal references to use `scenario`
- Update `__init__.py` export to include `Lens`

### Status

**NOT STARTED**

---

## Task 2 — De-domainize Theme and Stack Templates

### Current State

`src/antalens/theme/stack_templates.py`, lines 105–121:

```python
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
```

**Issues:**
- Fuel names (`nuclear`, `gas`, `coal`, etc.) are domain-specific
- Template name `eco2mix` is French TSO-specific
- Hardcoded in Python instead of YAML catalog
- `src/antalens/theme/__init__.py` lines 37–42 exports these domain constants

```python
__all__ = [
    "BASE",
    "ECO2MIX",
    "StackLayer",
    ...
]
```

### Target State

**File: `catalogs/examples/eco2mix.yml`**

```yaml
name: eco2mix
description: French TSO standard production stack (GEMS-compatible)

layers:
  - category: nuclear
    color: "#6366f1"
    side: positive
  - category: hydro
    color: "#38bdf8"
    side: positive
  # ... rest of layers

palette_name: by_fuel
```

**File: `catalogs/examples/base.yml`**

```yaml
name: base
description: Generic four-tier template

layers:
  - category: baseload
    color: "#6366f1"
    side: positive
  # ... rest of layers
```

**File: `src/antalens/theme/stack_templates.py`**

```python
# Remove ECO2MIX and BASE constants
# Keep StackLayer, StackTemplate, register_template, get_template
# get_template() loads from YAML via catalog system

__all__ = [
    "StackLayer",
    "StackTemplate",
    "get_template",
    "register_template",
]
```

**File: `src/antalens/theme/__init__.py`**

```python
# Remove ECO2MIX, BASE from __all__
__all__ = [
    "PlotlyTheme",
    "DARK",
    "LIGHT",
    "get_active_theme",
    "set_active",
    # Re-export stack template primitives only
    "StackLayer",
    "StackTemplate",
    "get_template",
    "register_template",
]
```

**Migration path:**
1. Create YAML versions in `catalogs/examples/`
2. Update `get_template()` to load from YAML via `Catalog` system
3. Keep `ECO2MIX` and `BASE` as Python aliases that reference the YAML versions (for backwards compatibility)
4. Mark them as deprecated in docstrings

### Status

**NOT STARTED**

---

## Task 3 — Catalog Skeleton

### Current State

**No catalog module exists.** Domain-specific configuration (stack templates, palettes) is hardcoded in `src/antalens/theme/`.

### Target State

**File: `src/antalens/catalog.py`**

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class ComponentPattern:
    pattern: str  # regex
    kind: str  # generator, link, load, etc.
    display: str  # format string for display name

@dataclass
class OutputMetadata:
    display: str
    unit: str
    default_agg: Literal["sum", "mean", "max", "min"]

@dataclass
class Palette:
    name: str
    colors: dict[str, str]  # category -> color

@dataclass
class Catalog:
    """Domain semantics loaded from YAML catalog.

    Attributes:
        component_patterns: List of regex patterns to parse component names.
        output_metadata: Metadata for output/variable names.
        palettes: Named color palettes by category.
        stack_templates: Named stack templates (fuel orderings).
    """
    component_patterns: list[ComponentPattern] = field(default_factory=list)
    output_metadata: dict[str, OutputMetadata] = field(default_factory=dict)
    palettes: dict[str, Palette] = field(default_factory=dict)
    stack_templates: dict[str, StackTemplate] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path) -> Catalog
    def resolve_component(self, component_name: str) -> dict[str, str]
    def color_for(self, category: str, palette_name: str) -> str | None
    def stack_template(self, name: str) -> StackTemplate
```

**File: `src/antalens/catalogs/`**

- `examples/eco2mix.yml`
- `examples/base.yml`
- `examples/europe_geo.yml`

### Status

**NOT STARTED**

---

## Task 4 — Dataset Catalog Hooks

### Current State

`src/antalens/data/dataset.py`:

```python
@dataclass
class Dataset:
    _data: InMemoryData | LazyData | XArrayData
    _schema: Schema

    def filter(self, **kwargs) -> Dataset
    def resample(self, ...) -> Dataset
    ...
```

**Issues:**
- No way to attach a `Catalog` to a `Dataset`
- No domain-aware filtering or plotting

### Target State

```python
@dataclass
class Dataset:
    _data: InMemoryData | LazyData | XArrayData
    _schema: Schema
    _catalog: Catalog | None = None  # NEW

    def with_catalog(self, catalog: Catalog) -> Dataset:
        """Return a copy attached to a catalog."""
        return Dataset(self._data, self._schema, catalog)

    @property
    def catalog(self) -> Catalog | None:
        """Return attached catalog, or None."""
        return self._catalog

    def filter(self, **kwargs) -> Dataset:
        # If self._catalog exists, use it for domain-aware filtering
        ...
```

### Status

**NOT STARTED**

---

## Task 5 — BasePlot apply_catalog Stub

### Current State

`src/antalens/plots/_base.py`:

```python
class BasePlot(ABC):
    dataset: Dataset

    def build(self) -> go.Figure
    def to_pane(self) -> pn.pane.GRAF...
```

**Issues:**
- No hook to apply catalog palettes and templates
- Plot builders hard-code color selection logic

### Target State

```python
class BasePlot(ABC):
    dataset: Dataset
    _catalog: Catalog | None = None  # NEW

    def apply_catalog(self, catalog: Catalog | None = None) -> Self:
        """Attach catalog for palette/template lookup.

        Args:
            catalog: Optional catalog. If None, use self.dataset.catalog.

        Returns:
            Self for method chaining.
        """
        self._catalog = catalog or self.dataset.catalog
        return self

    def _color_for(self, category: str, palette_name: str) -> str:
        """Lookup color from catalog, fallback to categorical palette."""
        if self._catalog:
            color = self._catalog.color_for(category, palette_name)
            if color:
                return color
        # fallback to self._theme.palette_categorical
```

### Status

**NOT STARTED**

---

## Task 6 — Public API Surface Alignment

### Current State

`src/antalens/__init__.py`:

```python
from ._version import __version__

__all__ = ["__version__"]
```

**Issues:**
- No public API exposed
- Users must import submodules directly (e.g., `from antalens.data import Dataset`)

### Target State

```python
from ._version import __version__

# Core types
from .data.dataset import Dataset
from .lens import Lens

# Plot primitives (no domain-specific plot types)
from .plots.timeseries import TimeSeriesPlot
from .plots.bar import BarPlot
from .plots.stack import ProductionStack

# Dashboard
from .dash.dashboard import Dashboard

# Catalog (stub for now)
from .catalog import Catalog  # TBD

# Theme
from .theme import (
    PlotlyTheme,
    DARK,
    LIGHT,
    get_active_theme,
    set_active,
    StackLayer,
    StackTemplate,
    get_template,
    register_template,
)

# Loaders
from .data.loaders import load_parquet, load_csv, from_dataframe

# Link and pipe
from .link import link
from .data.dataset import pipe  # or separate function

__all__ = [
    # Version
    "__version__",
    # Core
    "Dataset",
    "Lens",
    # Plot primitives
    "TimeSeriesPlot",
    "BarPlot",
    "ProductionStack",
    # Dashboard
    "Dashboard",
    # Catalog
    "Catalog",
    # Theme
    "PlotlyTheme",
    "DARK",
    "LIGHT",
    "get_active_theme",
    "set_active",
    "StackLayer",
    "StackTemplate",
    "get_template",
    "register_template",
    # Loaders
    "load_parquet",
    "load_csv",
    "from_dataframe",
    # Utilities
    "link",
    "pipe",
]
```

**Implementation approach:**
- Create property-based API: `al.plot.timeseries()` → returns `TimeSeriesPlot`
- Create `al.map` namespace for map primitives
- Create `al.controls` namespace for Panel widgets
- Re-export from submodules in `__init__.py`

### Status

**NOT STARTED**

---

## Task 7 — SimulationTable and Views Stubs

### Current State

**No `SimulationTable` or `Views` classes exist.** These are defined in `docs/gems.md` but not implemented.

### Target State

**File: `src/antalens/data/simulation_table.py`**

```python
from .dataset import Dataset
from .schema import Schema

class SimulationTable(Dataset):
    """GEMS SimulationTable backed by parquet (lazy).

    A GEMS SimulationTable is a long-format table with columns:
    - block: int
    - component: str
    - output: str
    - absolute_time_index: int
    - block_time_index: int
    - scenario_index: int
    - value: float | None
    - basis_status: str

    See docs/gems.md section 2 for full schema.
    """

    @property
    def components(self) -> list[str]:
        """Return unique component names."""
        ...

    @property
    def outputs(self) -> list[str]:
        """Return unique output/variable names."""
        ...

    @property
    def scenarios(self) -> list[int]:
        """Return unique scenario indices."""
        ...

    @property
    def blocks(self) -> list[int]:
        """Return unique block indices."""
        ...

    def filter(
        self,
        *,
        component: str | list[str] | None = None,
        component_kind: str | None = None,
        output: str | list[str] | None = None,
        scenario: int | list[int] | None = None,
        time_range: tuple[int, int] | None = None,
        **kwargs,
    ) -> SimulationTable:
        ...
```

**File: `src/antalens/data/views.py`**

```python
from .dataset import Dataset
from .schema import Schema

class Views(Dataset):
    """GEMS Views file (curated, wide-format).

    Views are wide-format parquet files derived from a SimulationTable
    by the GEMS ViewsBuilder. They contain curated outputs configured
    by a view-config.yml and catalog.yml.
    """

    catalog: Catalog | None = None
    source: SimulationTable | Path | None = None  # lineage
    view_config: Path | None = None  # lineage
```

**File: `src/antalens/data/__init__.py`**

```python
from .dataset import Dataset
from .simulation_table import SimulationTable
from .views import Views
from .loaders import load_parquet, load_csv, from_dataframe

__all__ = [
    "Dataset",
    "SimulationTable",
    "Views",
    "load_parquet",
    "load_csv",
    "from_dataframe",
]
```

### Status

**NOT STARTED**

---

## Task 8 — Legacy Module Skeleton

### Current State

**No legacy module exists.** Legacy ANTARES outputs are handled by ad-hoc scripts.

### Target State

**File: `src/antalens/legacy/__init__.py`**

```python
"""Legacy ANTARES output adapter.

This module provides backwards-compatibility for organizations still
using legacy ANTARES outputs. It is NOT part of the core GEMS workflow
and will be deprecated when the organization fully migrates to GEMS.

DO NOT USE in new code unless maintaining legacy integrations.
"""

from .adapter import AntaresLegacyStudy

__all__ = ["AntaresLegacyStudy"]
```

**File: `src/antalens/legacy/adapter.py`**

```python
from pathlib import Path
import h5py
import pandas as pd

from antalens.data.dataset import Dataset
from antalens.data.schema import Schema


class AntaresLegacyStudy:
    """Adapter for legacy ANTARES h5 outputs.

    This is a backwards-compatibility layer. New studies should use
    GEMS SimulationTable/Views instead.

    Deprecated: Will be removed in v1.0.0.
    """

    def __init__(self, study_path: Path):
        self._path = study_path
        self._h5 = h5py.File(study_path / "output.h5", "r")

    @property
    def dataset(self) -> Dataset:
        """Convert legacy output to a Dataset for visualization."""
        # Load MC years, time indices, and variables
        # Pivot to wide format
        # Return Dataset with Schema
        ...

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._h5.close()
```

**File: `src/antalens/__init__.py`**

```python
# ... rest of exports

# Legacy (explicit opt-in)
from .legacy import AntaresLegacyStudy

__all__ += ["AntaresLegacyStudy"]
```

### Status

**NOT STARTED**

---

## Task 9 — Domain-Vocabulary Lint Test

### Current State

**No test exists for domain-vocabulary leakage.** Domain-specific terms sometimes leak into core code.

### Target State

**File: `tests/unit/test_domain_vocab.py`**

```python
"""Test that core code does not leak domain-specific vocabulary.

Forbidden terms that must not appear in src/antalens/ (except catalogs/,
docs/, examples/):
"""

from pathlib import Path
import re
import pytest

FORBIDDEN_TERMS = [
    r"\bANTARES\b",
    r"\beCO2mIX\b",
    r"\bNUCLEAR\b",  # uppercase variable names
    r"\bGAS_CCGT\b",
    r"\bTYNDP\b",
    r"\bLOLD\b",
    r"\bbidding zone\b",
    r"\bproduction margin\b",
]

CORE_PATH = Path(__file__).parent.parent.parent / "src" / "antalens"


def test_no_forbidden_terms_in_core():
    """Forbidden terms must not appear in core code."""
    violations = []

    for py_file in CORE_PATH.rglob("*.py"):
        # Skip legacy/ module (by design)
        if "legacy" in str(py_file):
            continue

        content = py_file.read_text(encoding="utf-8")

        for pattern in FORBIDDEN_TERMS:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                # Allow comments/docstrings in tests/
                if "test" not in str(py_file):
                    violations.append(
                        f"{py_file}:{match.start()}: "
                        f"forbidden term {match.group()}"
                    )

    if violations:
        pytest.fail(f"Forbidden terms found:\n" + "\n".join(violations))
```

**Integration with ruff:**

Add to `pyproject.toml`:

```toml
[tool.ruff.lint.extend-unsafe-fixes]
# Rule to detect forbidden terms (custom rule via ruff's `# noqa: domain-vocab`)
```

### Status

**NOT STARTED**

---

## Task 10 — Documentation Updates

### Current State

- `README.md`: Outdated API surface
- `CHANGELOG.md`: No v0.2.0 entries
- `PHASE_TRACKER.md`: Accurate (already updated)
- `docs/plan.md`: Accurate (already updated)
- `docs/spec.md`: Accurate (already updated)

### Target State

**File: `README.md`**

Update API examples to match v0.2.0 surface:

```python
import antalens as al

# Load data
ds = al.io.load_parquet("data.parquet")

# Attach catalog (optional)
cat = al.Catalog.from_yaml("catalogs/examples/eco2mix.yml")
ds = ds.with_catalog(cat)

# Create plot with catalog-aware styling
pane = (
    al.plot.stack(ds)
    .stack_by("fuel")
    .template("eco2mix")
    .apply_catalog(cat)
    .to_pane()
)
```

**File: `CHANGELOG.md`**

Add v0.2.0 section:

```markdown
## v0.2.0 (Unreleased)

### Breaking Changes

- `Lens.mc` renamed to `Lens.scenario` (deprecated alias maintained)
- Stack templates externalized to YAML catalogs
- Domain-specific plot types removed from core (`ProductionStack` stays as generic primitive)
- Public API surface expanded: `al.Dataset`, `al.Lens`, `al.Catalog`, etc.

### New Features

- GEMS-aware data layer: `SimulationTable`, `Views`
- Catalog system for domain semantics (YAML-based)
- Domain-vocabulary lint prevents leakage into core code

### Deprecated

- `Lens.mc` parameter (use `scenario` instead)
- `ECO2MIX` and `BASE` Python constants (use `get_template("eco2mix")` via catalog)
```

### Status

**NOT STARTED**

---

## Task 11 — Final Verification

### Commands

```bash
# 1. Lint and type-check
ruff check antalens/ tests/
ruff format --check antalens/ tests/
mypy --strict antalens/

# 2. Test suite
pytest tests/ -m "not slow"
pytest tests/integration/

# 3. Smoke test
python -c "import antalens as al; print(al.__version__)"

# 4. Public API surface check
python -c "
import antalens as al
expected = {'io','plot','map','dash','controls','catalog','theme','legacy',
            'Dataset','SimulationTable','Views','Catalog','Lens','link','pipe'}
actual = {x for x in dir(al) if not x.startswith('_')}
missing = expected - actual
assert not missing, f'Missing public symbols: {missing}'
"
```

### Status

**NOT STARTED** (pending completion of Tasks 1–10)

---

## Reconciliation with PHASE_TRACKER.md

| Refactor Task | PHASE_TRACKER Status | Alignment |
|--------------|----------------------|-----------|
| Task 1 (Schema) | Phase 1 complete, but lacks GEMS `kind` | Out of sync |
| Task 1b (Lens) | Phase 1 complete, uses `mc` | Out of sync |
| Task 2 (Theme) | Phase 1 complete, domain-specific | Out of sync |
| Task 3–6 | Phase 2 (GEMS layer) queued | In sync |
| Task 7 (ST/Views) | Phase 2 queued, not started | In sync |
| Task 8 (legacy) | Phase 3 queued | In sync |
| Task 9 (lint) | Not mentioned in tracker | Additional quality gate |
| Task 10 (docs) | Docs up to date | In sync |
| Task 11 (verify) | N/A | Quality gate |

**Conclusion:** Phase 1 shipped without full GEMS alignment. This refactor brings Phase 1 code in line with the GEMS data model described in Phase 2.

---

## Recommended Execution Order

1. **Task 1** (Schema) — foundational, no dependencies
2. **Task 1b** (Lens) — foundational, no dependencies
3. **Task 3** (Catalog skeleton) — needed by Tasks 4–6
4. **Task 4** (Dataset hooks) — depends on Task 3
5. **Task 5** (apply_catalog stub) — depends on Task 3
6. **Task 2** (Theme de-domainization) — independent, can run in parallel
7. **Task 6** (Public API) — depends on Tasks 1–5
8. **Task 7** (SimulationTable/Views) — depends on Tasks 3–4
9. **Task 8** (legacy) — independent
10. **Task 9** (lint test) — depends on completion of Tasks 1–8
11. **Task 10** (docs) — depends on completion of Tasks 1–9
12. **Task 11** (verification) — final gate

**Total estimated effort:** 3–4 weeks for a single developer (matching Phase 2 timeline in PHASE_TRACKER.md).
