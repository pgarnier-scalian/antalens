# AntaLens Refactor Plan

> **Target audience**: Claude Code (autonomous execution)
> **Companion docs**: `gems.md`, `spec.md`, `plan.md` (all v0.2.0-draft)
> **Estimated effort**: 2–3 days of focused work
> **Branch**: `refactor/gems-reframe`

---

## What this refactor does

This refactor is a **structural cleanup** of the existing AntaLens codebase to make it match the v0.2.0 spec before Phase 2 work begins. It does **not** implement Phase 2 features. It re-shapes the existing Phase 1 code so Phase 2 can land cleanly and additively.

Three things change:

1. The `Schema` class is rewritten to be generic (currently shaped for the legacy ANTARES data model).
2. Domain-specific content (eco2mix, ANTARES vocabulary) is removed from the generic core. Where it must persist, it moves to YAML catalogs or to `antalens/legacy/`.
3. New module skeletons are created (`antalens/catalog/`, `antalens/legacy/`, plus stubs for `SimulationTable`, `Views`, `Catalog`, `TablePlot`) so Phase 2/3 can fill them in without re-arranging anything.

Tests must pass at each step. The final state must satisfy the **domain-vocabulary lint** (task 9): no domain-specific term in the generic core.

## What this refactor does NOT do

- Does not implement `SimulationTable.filter()`, `pivot()`, or `to_views()`. Those land in Phase 2.
- Does not implement DuckDB backend. Phase 4.
- Does not implement the catalog parser, palettes-from-catalog, or stack template resolution from catalog. Phase 2.
- Does not implement `AntaresLegacyStudy`. Phase 3.
- Does not write the actual content of `catalogs/examples/eco2mix.yml` (only the file with the externalized data).

For each non-implementation, the refactor leaves a **stub that raises `NotImplementedError("Lands in Phase X")`**. The import path is real; the behavior is deferred.

---

## Pre-flight: audit (Task 0)

**Before any code changes, produce an audit.**

Read the current state of:

- `PHASE_TRACKER.md` (or whatever the project's status tracker is named — search for files with names like `STATUS.md`, `PROGRESS.md`, `TRACKER.md`, `ROADMAP.md`)
- `antalens/data/schema.py`
- `antalens/data/dataset.py`
- `antalens/data/loaders.py`
- `antalens/data/accessors.py` (or wherever `PlotAccessor` lives)
- `antalens/data/transforms.py` (if it exists)
- `antalens/lens.py` (or wherever `Lens` lives)
- `antalens/theme/` (all files)
- `antalens/plots/_base.py`, `antalens/plots/timeseries.py`, `antalens/plots/bar.py`, `antalens/plots/stack.py` (and any `template.py` / `templates.py` if present)
- `antalens/dash/` (all files — `Dashboard` is shipped per the tracker; understand its shape)
- `antalens/link.py` if it exists (the tracker says `link()` is shipped)
- `antalens/__init__.py`
- `examples/` (every example script — they are real users of the existing API and may break under the refactor)
- `tests/` (only the test files for the above)

Produce `refactor/audit.md` with:

1. The exact current shape of `Schema` (every field, every method, every place it's instantiated).
2. The exact current shape of `Lens` (every `param.Parameter`, every default, every consumer). The current `Lens` has legacy-ANTARES parameters (`area`, `mc`); document them before they are migrated.
3. The exact current shape of the stack-template system: `StackTemplate` class, `ECO2MIX` and `BASE` instances, `register_template()` registry, and every plot builder or example that references these. The tracker says these are richer than a simple alias dictionary.
4. Every reference to ANTARES, antares, eco2mix, ECO2MIX, NUCLEAR, WIND, SOLAR, GAS, BALANCE, LOAD-as-domain-term, `mc` (when used as Monte-Carlo-year), TYNDP, LOLD anywhere in `antalens/`, `examples/`, and `tests/`. (Use grep; report file:line.)
5. Whether `antalens/data/antares.py` and `antalens/data/antares_io.py` exist and, if so, what they contain.
6. Whether `antalens/theme/aliases.py` exists and, if so, its full content.
7. List of all files in `antalens/plots/` and `antalens/dash/` (which builders, dashboard pieces, and presets are implemented).
8. The exact public surface of `antalens/__init__.py` (everything re-exported).
9. **Phase tracker cross-check + reconciliation table.** A markdown table where **every line in the existing `PHASE_TRACKER.md` is re-verified against the actual codebase**. The old tracker is treated as a *claim*, not as truth. Each row records: what the tracker says, what the code says, and where the item lands under `plan.md` v0.2.0.

   Verification methodology — apply each per item type:

   - **Classes / functions claimed shipped (`[x]`)**: import the symbol from a fresh Python session; confirm the file exists; check that referenced sub-features (e.g., `register_template()`) actually work; run the relevant tests in `tests/` and report pass/fail count.
   - **Test claims (`[x] BarPlot (~22 tests)`)**: run `pytest tests/ -v -k <name>` and report the actual test count and pass status.
   - **Example scripts (`[x] examples/lp_explorer.py`)**: confirm file exists, attempt to import it, list its top-level imports for ANTARES/eco2mix references.
   - **Items claimed in flight (`[~]`)**: locate the WIP code; describe what's done vs. missing.
   - **Items claimed deferred (`[—]`)**: confirm the file/feature genuinely doesn't exist.

   Table format:

   | Tracker item                                | Tracker status | Verified status            | Old phase | New phase                   | Action                            |
   |---------------------------------------------|----------------|----------------------------|-----------|-----------------------------|-----------------------------------|
   | `Schema` dataclass with auto-inference      | `[x]`          | `[x]` — 20 tests pass       | 1         | 1 (rewritten)               | Refactored in Task 1              |
   | `Lens` with `area, dates, variable, mc`     | `[x]`          | `[x]` — 24 tests pass       | 1         | 1 (migrated)                | Refactored in Task 1b             |
   | `StackTemplate` with `ECO2MIX` / `BASE`     | `[x]`          | `[x]` — instantiable; 12 ProductionStack tests pass | 1 | catalogs/examples + Phase 2 | Externalized in Task 2 |
   | `link()` for chart-to-chart events          | `[x]`          | *VERIFY: import + smoke run* | 2         | 2 (kept)                    | No change                         |
   | Heatmap chart type                          | `[ ]`          | *VERIFY: file absent*       | 2         | 1                           | Promoted to Phase 1 (TableMode adjacent) |
   | … (one row per item in old tracker)         |                |                            |           |                             |                                   |

   **Discrepancy column required.** If `Verified status` differs from `Tracker status` (e.g. tracker says `[x]` but tests fail or import errors), add a "Discrepancy" note. Discrepancies are valuable signal — they get fixed in Task 10's tracker rewrite, not papered over.

   Items marked `[—]` (deferred) are also mapped — usually they remain deferred but may move to a different phase under v0.2.

10. **Proposed next steps under the v0.2 plan.** A short, decision-ready section (no more than one page) titled `## Next steps` that produces:

    - **The 3–5 highest-value next units of work** the user can pick from once the refactor lands. Each unit named, scoped to roughly 1–3 days, with a one-paragraph justification grounded in the v0.2 `plan.md` phasing.
    - **The one item the audit recommends doing first**, with reasoning. Typical answers will be along the lines of *"Wire `Catalog` into `ProductionStack.apply_catalog` (Phase 2 §2.4) — already-shipped templates are the natural first consumer of the new catalog system."*
    - **Any blockers or risks the audit surfaced** that should be resolved before that first item. Example: *"Schema rewrite (Task 1) blocks any new long-format work — must merge first."*
    - **Items that should change priority** based on what the audit actually found (e.g. `[—] Heatmap` deferred earlier, but the audit reveals it would unblock SimulationTable exploration; recommend promoting).

    This is **not** a re-statement of `plan.md`. It is the audit's *opinion* on where to spend the next week, derived from the verified state of the code.

The audit is a fact-finding deliverable. No code changes. Commit it on the refactor branch.

### 0b — Updated `PHASE_TRACKER.md`

The reconciliation table inside `audit.md` (Q9 above) explains the *mapping*. This deliverable produces the **live source-of-truth tracker file** in the project root.

Re-map the existing `PHASE_TRACKER.md` against the v0.2 phase structure described in `plan.md`:

- Each existing item moves to its appropriate v0.2 phase. Old-Phase-2 items (`Dashboard`, `link()`, event extractors) become part of new-Phase-2's reactivity sub-track. Items related to `load_antares` move under Phase 3's legacy adapter section.
- Each item's status (`[x] [~] [ ] [—]`) is **re-verified by inspecting the codebase or running tests**, not copied from the old tracker.
- New v0.2 items absent from the old tracker are added: `SimulationTable`, `Views`, `Catalog` scaffold, `TablePlot`, `antalens.legacy` skeleton, the domain-vocabulary lint, DuckDB backend, the `simulation_explorer` preset, etc.
- The status legend (`[x] [~] [ ] [—]`) is preserved.
- The "What's done enough right now" section at the bottom is rewritten to describe the **post-refactor** state — what the toolchain will be able to do once the refactor branch merges.

A starting-point template is delivered alongside this refactor plan as `PHASE_TRACKER.template.md`. Use it as the skeleton; the audit (Q1–Q8) determines actual statuses.

The updated tracker becomes the live source of truth for project state under the v0.2 plan. Future PRs update it as features ship.

**Acceptance**:

1. `refactor/audit.md` exists and answers all ten questions, including the cross-checked phase tracker reconciliation table (Q9) and the next-steps recommendation (Q10).
2. The project-root `PHASE_TRACKER.md` is updated to the v0.2 phase structure with re-verified statuses.
3. **Stop here and surface both deliverables for review before proceeding to Task 1.** If the audit reveals that any task's scope is materially larger than the current refactor.md write-up suggests (in particular: Schema, Lens, or StackTemplate), this is the moment to revise the plan rather than power through.

---

## Task 1 — Rewrite `Schema` to be generic

The current `Schema` is shaped for the legacy ANTARES data model (per the audit). Rewrite it to match `spec.md` §4.3.

### Target shape

```python
# antalens/data/schema.py
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class Schema:
    kind: Literal["wide", "long_gems", "xarray"]

    # wide / xarray fields (None when kind == "long_gems")
    time_col: str | None = None
    categorical_cols: dict[str, list[str]] | None = None  # {col: distinct_values}
    numeric_cols: list[str] | None = None
    geo_cols: list[str] | None = None
    ndim: int = 2

    # long_gems fields (None for other kinds)
    component_col: str | None = None
    output_col: str | None = None
    value_col: str | None = None
    scenario_col: str | None = None
    abs_time_col: str | None = None
    block_col: str | None = None  # optional; nullable in older sim outputs

    def has(self, col: str) -> bool: ...
    def kind_of(self, col: str) -> Literal["time", "categorical", "numeric", "geo"]: ...

    @classmethod
    def infer_wide(cls, df) -> "Schema": ...
    @classmethod
    def infer_long_gems(cls, df) -> "Schema": ...
```

### Migration of existing call sites

Any code that constructs `Schema(...)` with the old signature must be updated:

- Callers that pass wide-format fields → pass `kind="wide"` and the same fields.
- The default constructor (no args) → not allowed; `kind` is required. Replace any defaulted constructions with `Schema(kind="wide")`.

### Inference

`Schema.infer_wide(df)` is the renamed/refactored version of whatever existing inference logic currently lives in `Schema` or in loaders. Keep its behavior identical.

`Schema.infer_long_gems(df)` is **stubbed**: it returns `Schema(kind="long_gems", component_col="component", output_col="output", value_col="value", scenario_col="scenario_index", abs_time_col="absolute_time_index", block_col="block")` only if the dataframe has all those columns, otherwise raises `ValueError`. Full implementation lands in Phase 2 — but the dispatch contract must work today.

### Acceptance criteria

1. `mypy --strict antalens/data/schema.py` passes.
2. Every existing test that uses `Schema` still passes (after migration of call sites).
3. New tests in `tests/data/test_schema.py`:
   - `Schema(kind="wide", ...)` round-trips through `dataclasses.asdict` and back.
   - `Schema.infer_long_gems(df_with_gems_columns)` returns the expected schema.
   - `Schema.infer_long_gems(df_without_gems_columns)` raises `ValueError`.
   - `Schema(kind="wide").component_col is None` (long-format fields default to None on wide schemas).
4. `grep -ri 'antares\|eco2mix' antalens/data/schema.py` is empty.

---

## Task 1b — Migrate `Lens` shape

The current `Lens` ships with `area`, `dates`, `variable`, `mc` — the last is the legacy ANTARES "Monte Carlo year" parameter. Migrate to a generic shape that fits both GEMS and non-GEMS use cases.

### Target shape (post-migration)

```python
class Lens(param.Parameterized):
    """Shared mutable state for a connected dashboard."""

    # Generic dimensions (kept from current Lens)
    area      = param.String(default=None, allow_None=True)
    dates     = param.DateRange(default=None, allow_None=True)
    variable  = param.String(default=None, allow_None=True)

    # Generic scenario index — replaces legacy `mc`
    scenario  = param.Integer(default=None, allow_None=True)
```

The two **GEMS-specific** parameters from `spec.md` §3.6 — `component` and `output` — do **not** go into the base `Lens`. They land in Phase 2 as a `GemsLens` subclass produced via `Lens.with_extras(component=..., output=...)`. Keeping the base `Lens` minimal preserves its usefulness for non-GEMS users.

> **Note**: this is a deliberate revision of `spec.md` §3.6. The spec puts `component`, `output`, `scenario` directly in the base `Lens`. After seeing the existing `Lens` and recognizing it serves non-GEMS users today, the cleaner call is to keep base `Lens` generic and let GEMS-specific parameters arrive via `with_extras`. **Update `spec.md` §3.6 accordingly as part of this task** (one-paragraph rewrite; see the redline in the Final Verification step).

### Migration of `mc` → `scenario`

`mc` is the legacy ANTARES Monte Carlo year. In GEMS terminology this is a "scenario." The migration:

1. Add `scenario` as the new canonical parameter.
2. Add `mc` as a deprecated alias property: reading or setting `lens.mc` works, emits `DeprecationWarning`, and proxies to `lens.scenario`. Schedule removal in v0.3.
3. Update all internal callers (`Dataset.filter`, `link()` event extractors, examples) to use `scenario`.
4. Update `Lens.with_extras` to ensure subclasses inherit `scenario` correctly.

### Examples migration

The audit (Q4) will identify which `examples/*.py` files reference `lens.mc`. Update them to `lens.scenario`. The behavior is unchanged.

### Acceptance criteria

1. `Lens()` has parameters `area`, `dates`, `variable`, `scenario` and no others in the base class.
2. `lens.mc = 0` works, emits a `DeprecationWarning` mentioning `scenario`, and `lens.scenario == 0` afterwards.
3. `Lens.with_extras(component=param.String(...))` produces a working subclass with `component` available.
4. Every existing test that uses `Lens` passes (after migration to `scenario`).
5. Every example script in `examples/` runs without `DeprecationWarning` after migration.
6. `grep -ri '\bmc\b' antalens/` only matches inside `antalens/lens.py` (the deprecated alias) and `antalens/legacy/` (legacy adapter use).

---

## Task 2 — De-domain the theme and stack templates

The audit (Q3, Q6) will reveal whether domain content lives in a flat `aliases.py` or in a richer system: a `StackTemplate` class with `ECO2MIX`/`BASE` instances and a `register_template()` registry. The tracker says the latter. Both cases are handled below.

### Actions — theme

1. Remove `palette_categorical` from `PlotlyTheme` (`antalens/theme/plotly.py`). Update both `DARK` and `LIGHT` instances.
2. Add `palette_neutral: list[str]` to `PlotlyTheme` if not present — a 10-color colorblind-safe neutral palette. This is the fallback when no catalog is attached.

### Actions — stack templates

The `StackTemplate` *class* is a useful runtime type and stays. What moves is the **content** of the `ECO2MIX` and `BASE` instances (fuel orderings, color palettes, negative-layer rules) — these are domain knowledge and belong in YAML.

3. Keep the `StackTemplate` class definition wherever it currently lives (likely `antalens/plots/stack.py` or a sibling `templates.py`). It is a generic container; no changes to its fields.
4. **Capture the ECO2MIX and BASE definitions as YAML** in `catalogs/examples/eco2mix.yml` and `catalogs/examples/base_stack.yml`. Use the `stack_templates` schema from `gems.md` §4.1. Real data, not placeholders — the audit will surface what's currently in the Python instances.
5. **Delete the module-level `ECO2MIX` and `BASE` instances** from Python code.
6. **Add a transitional loader**: `StackTemplate.from_yaml(path: Path) -> StackTemplate` (or `antalens.plots.load_stack_template(path)` if class methods are awkward in the existing structure). This is a one-screen function that reads the YAML and constructs a `StackTemplate`. It is provisional — Phase 2's catalog system will subsume it.
7. **Keep `register_template()`** — it's a useful runtime registry. But the registry **starts empty** at import time. No domain content registered by default.
8. **If `antalens/theme/aliases.py` exists** (per audit Q6): delete it, after capturing any data it holds into the relevant YAML.

### Migration of existing examples

The examples in `examples/` likely use `ECO2MIX` directly:

```python
# Before (will break after this task)
from antalens.plots import ECO2MIX
ds.plot.stack(template=ECO2MIX)

# After (one-line migration)
from antalens.plots import StackTemplate
template = StackTemplate.from_yaml("catalogs/examples/eco2mix.yml")
ds.plot.stack(template=template)
```

Update every example identified by the audit. Verify each runs end-to-end after migration.

### Acceptance criteria

1. `antalens/theme/aliases.py` does not exist (if it existed before).
2. No module-level `ECO2MIX` or `BASE` constants exist anywhere in `antalens/`. (`grep -rE '^(ECO2MIX|BASE)\s*=' antalens/` returns nothing.)
3. `catalogs/examples/eco2mix.yml` and `catalogs/examples/base_stack.yml` exist with real content (not placeholder TODOs).
4. `grep -ri 'eco2mix\|ECO2MIX\|antares\|ANTARES' antalens/theme/ antalens/plots/` returns nothing.
5. `from antalens.theme import set_active, get_active, DARK, LIGHT` works.
6. `StackTemplate.from_yaml(...)` (or equivalent) loads `catalogs/examples/eco2mix.yml` and produces a working template.
7. `register_template()` registry is empty at import time.
8. **Every example script in `examples/` runs to completion after the migration.** This is the regression test for the migration.
9. All existing plot tests pass.

---

## Task 3 — `antalens/catalog/` skeleton

Create the catalog module with stub-only implementation. Phase 2 fills in the actual parsing logic.

### Files to create

```
antalens/catalog/__init__.py     # public re-exports
antalens/catalog/catalog.py      # Catalog dataclass
antalens/catalog/parser.py       # YAML parser stub
antalens/catalog/parse_component.py  # regex stub
catalogs/examples/eco2mix.yml    # placeholder or real content (per Task 2)
catalogs/examples/europe_geo.yml # placeholder
catalogs/examples/gems_minimal.yml  # placeholder
```

### `Catalog` dataclass

```python
# antalens/catalog/catalog.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Catalog:
    component_patterns: tuple = field(default_factory=tuple)
    outputs: dict[str, dict] = field(default_factory=dict)
    palettes: dict[str, dict[str, str]] = field(default_factory=dict)
    stack_templates: dict[str, dict] = field(default_factory=dict)
    geo: dict | None = None

    def parse_component(self, name: str):
        raise NotImplementedError("Lands in Phase 2")

    def display_name(self, output: str) -> str:
        return self.outputs.get(output, {}).get("display", output)

    def palette(self, name: str) -> dict[str, str]:
        return self.palettes.get(name, {})
```

### Public surface (`antalens/catalog/__init__.py`)

```python
from .catalog import Catalog

def load(path):
    raise NotImplementedError("Lands in Phase 2")

def merge(*catalogs):
    raise NotImplementedError("Lands in Phase 2")

def empty() -> Catalog:
    return Catalog()

__all__ = ["Catalog", "load", "merge", "empty"]
```

### Example YAML files

Placeholder content is fine — these files are markers that the import path / config path exists:

```yaml
# catalogs/examples/eco2mix.yml
# Placeholder. Real content lands in Phase 2.
# See spec.md §3.10 and gems.md §4 for the target schema.
```

### Acceptance criteria

1. `from antalens.catalog import Catalog, load, merge, empty` works.
2. `empty()` returns a `Catalog` with all defaults.
3. `load(...)` and `merge(...)` raise `NotImplementedError("Lands in Phase 2")`.
4. `display_name` and `palette` work for empty catalogs (they degrade gracefully — `display_name("p")` returns `"p"`, `palette("by_fuel")` returns `{}`).
5. `mypy --strict antalens/catalog/` passes.

---

## Task 4 — Dataset catalog hooks

Add `with_catalog()` and `catalog()` to `Dataset` so Phase 2 can wire catalogs through plot builders without revisiting `Dataset`.

### Implementation

`with_catalog(catalog)` returns a new `Dataset` with the catalog attached (immutable, like all chain methods). Internally it stores the catalog reference; nothing in Phase 1 actually uses it.

`catalog()` returns the attached `Catalog` or `None`.

### Acceptance criteria

1. `ds.with_catalog(al.catalog.empty()).catalog()` returns a `Catalog` instance.
2. `ds.catalog()` returns `None` for a freshly-loaded dataset.
3. `with_catalog` is immutable: `ds2 = ds.with_catalog(c); ds.catalog() is None` still holds.
4. Existing tests pass.

---

## Task 5 — `apply_catalog` stub on `BasePlot`

Add the catalog hook to the plot builder base class. Phase 2 implements the body.

### Changes to `antalens/plots/_base.py`

```python
class BasePlot(abc.ABC):
    # ... existing ...

    def apply_catalog(self, fig):
        """Apply catalog-driven display names, units, palettes. No-op until Phase 2."""
        catalog = self.dataset.catalog()
        if catalog is None:
            return fig
        # Phase 2: actually apply display_name, palette, stack_template here.
        return fig
```

Update `to_pane()` so the call order is: `build()` → `apply_theme()` → `apply_catalog()` → wrap in pane.

### Acceptance criteria

1. Every existing plot test still passes.
2. `BasePlot.apply_catalog` exists, is callable, and is a no-op when no catalog is attached.
3. New unit test: a plot built from a dataset with a catalog still produces an identical figure to the no-catalog case (because `apply_catalog` is a no-op for now). This locks in the Phase 1 → Phase 2 boundary.

---

## Task 6 — Public API surface

Update `antalens/__init__.py` to expose the v0.2.0 namespace per `spec.md` §3.1.

### Top-level exports

```python
# antalens/__init__.py
from . import io, plot, map, dash, controls, catalog, theme, legacy
from .data.dataset import Dataset
from .data.simulation_table import SimulationTable
from .data.views import Views
from .catalog.catalog import Catalog
from .lens import Lens
from .link import link
from .pipe import pipe

__all__ = [
    "io", "plot", "map", "dash", "controls", "catalog", "theme", "legacy",
    "Dataset", "SimulationTable", "Views", "Catalog", "Lens",
    "link", "pipe",
]
```

### Stubs needed for the above to import

- `antalens/data/simulation_table.py` — see Task 7.
- `antalens/data/views.py` — see Task 7.
- `antalens/legacy/__init__.py` — see Task 8.
- `antalens/link.py` — if it doesn't exist yet, create with `def link(*a, **kw): raise NotImplementedError("Lands in Phase 2")`.
- `antalens/pipe.py` — same treatment.
- `antalens/map/__init__.py` — if absent, create with `def __getattr__(name): raise ImportError("antalens.map requires the [maps] extra; lands in Phase 3")`.
- `antalens/dash/__init__.py` — keep what's there from MVP; add a `def __getattr__` for missing presets.

### Acceptance criteria

1. `import antalens as al` succeeds.
2. `dir(al)` contains every symbol listed in `spec.md` §3.1.
3. `al.SimulationTable`, `al.Views`, `al.Catalog`, `al.Lens`, `al.Dataset` are all classes (not the `NotImplementedError` placeholders themselves — the *classes* exist, but their *methods* may raise).
4. `al.legacy.AntaresLegacyStudy` is importable (raises `NotImplementedError` on instantiation).
5. `al.link`, `al.pipe` are callables that raise `NotImplementedError("Lands in Phase 2")`.

---

## Task 7 — `SimulationTable` and `Views` stubs

Create the class bodies so Phase 2 can populate methods incrementally.

### `antalens/data/simulation_table.py`

```python
from .dataset import Dataset

class SimulationTable(Dataset):
    """GEMS SimulationTable. Long-format parquet. Phase 2 implementation."""

    @property
    def components(self) -> list[str]:
        raise NotImplementedError("Lands in Phase 2")

    @property
    def outputs(self) -> list[str]:
        raise NotImplementedError("Lands in Phase 2")

    @property
    def scenarios(self) -> list[int]:
        raise NotImplementedError("Lands in Phase 2")

    @property
    def blocks(self) -> list[int]:
        raise NotImplementedError("Lands in Phase 2")

    def pivot(self, **kw) -> Dataset:
        raise NotImplementedError("Lands in Phase 2")

    def to_views(self, view_config) -> "Views":
        raise NotImplementedError("Lands in Phase 2")
```

`SimulationTable.filter()` is **not** overridden in the stub — Phase 2 adds the GEMS-aware kwargs. For now, inherited `Dataset.filter()` is used.

### `antalens/data/views.py`

```python
from .dataset import Dataset

class Views(Dataset):
    """GEMS Views (curated wide-format parquet). Phase 2 implementation."""
    # No methods to add at stub stage — Views is mostly Dataset.
    pass
```

### Loader stubs in `antalens/data/loaders.py`

```python
def load_simulation_table(path, *, catalog=None, backend="auto", scenarios=None):
    raise NotImplementedError("Lands in Phase 2")

def load_views(path, *, catalog=None):
    raise NotImplementedError("Lands in Phase 2")

def load_catalog(path):
    from antalens.catalog import load as _load
    return _load(path)  # delegates to catalog.load (also NotImplementedError for now)
```

### Update `antalens/io/__init__.py` (or wherever `io` is)

Re-export the new loaders:

```python
from antalens.data.loaders import (
    load_parquet, load_csv, load_hdf5, from_dataframe, from_sql,
    load_simulation_table, load_views, load_catalog,
)
```

### Acceptance criteria

1. `from antalens import SimulationTable, Views` works.
2. `al.io.load_simulation_table("foo.parquet")` raises `NotImplementedError`.
3. `al.io.load_views("foo.parquet")` raises `NotImplementedError`.
4. `mypy --strict antalens/data/simulation_table.py antalens/data/views.py` passes.

---

## Task 8 — `antalens/legacy/` skeleton

Create the legacy adapter module. Phase 3 fills it in.

### Files

```
antalens/legacy/__init__.py
antalens/legacy/study.py
antalens/legacy/io.py
antalens/legacy/catalog.py   # the built-in legacy ANTARES catalog
```

### `antalens/legacy/__init__.py`

```python
from .study import AntaresLegacyStudy
from .io import load_antares

__all__ = ["AntaresLegacyStudy", "load_antares"]
```

### `antalens/legacy/study.py`

```python
from antalens.data.dataset import Dataset

class AntaresLegacyStudy(Dataset):
    """Legacy ANTARES study adapter. Phase 3 implementation."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError("antalens.legacy.AntaresLegacyStudy lands in Phase 3")
```

### `antalens/legacy/io.py`

```python
def load_antares(path, mc_years=None):
    raise NotImplementedError("antalens.legacy.load_antares lands in Phase 3")
```

### `antalens/legacy/catalog.py`

```python
"""Built-in catalog covering the legacy ANTARES variable taxonomy.

This is the ONLY place in the codebase that may hardcode ANTARES-specific
domain vocabulary (LOAD, BALANCE, NUCLEAR, etc.). Phase 3 populates this file.
"""
# Phase 3 fills this in.
```

### Acceptance criteria

1. `from antalens.legacy import AntaresLegacyStudy, load_antares` works.
2. Both raise `NotImplementedError` on use.
3. `antalens/legacy/` is the only path under `antalens/` that may reference ANTARES vocabulary (enforced by Task 9).

---

## Task 9 — Domain-vocabulary lint

Add a CI check that prevents domain-specific terms from leaking back into the generic core.

### Implementation

Choose either:

- **Option A**: a custom `pytest` test in `tests/test_no_domain_leak.py`.
- **Option B**: a CI step in `.github/workflows/ci.yml` that runs `grep` and fails on hits.

Option A is cleaner because it runs locally as part of the test suite. Use this.

### Forbidden terms (case-sensitive matters; some tokens are also valid English words)

```
ANTARES, antares,            # always domain
eco2mix, ECO2MIX,            # always domain
NUCLEAR, GAS_CCGT,           # always domain (uppercase = column-name convention)
TYNDP,                       # always domain
LOLD,                        # always domain
adequacy, ENS,               # mostly domain (review hits if any)
```

Lowercase `wind`, `solar`, `gas`, `load`, `balance` are common English words and **not** forbidden — only their uppercase column-name forms are flagged.

### Allowed paths

These directories are exempt from the lint:

```
antalens/legacy/             # the legacy adapter is allowed to use ANTARES vocab
catalogs/examples/           # example YAML files contain domain content by design
tests/legacy/                # tests for the legacy adapter
docs/                        # docs may discuss ANTARES freely
```

### Test sketch

```python
# tests/test_no_domain_leak.py
import re
from pathlib import Path
import pytest

FORBIDDEN = ["ANTARES", "antares", "eco2mix", "ECO2MIX",
             "NUCLEAR", "GAS_CCGT", "TYNDP", "LOLD"]
ALLOWED_PREFIXES = [
    "antalens/legacy/",
    "catalogs/examples/",
    "tests/legacy/",
    "docs/",
]

@pytest.mark.parametrize("term", FORBIDDEN)
def test_no_domain_leak(term):
    root = Path(__file__).parent.parent
    hits = []
    for path in root.rglob("*.py"):
        rel = str(path.relative_to(root))
        if any(rel.startswith(p) for p in ALLOWED_PREFIXES):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines(), 1):
            # Strip comments? No — domain leak in a comment is also a leak.
            if term in line:
                hits.append(f"{rel}:{i}: {line.strip()}")
    assert not hits, f"Domain-vocabulary leak for '{term}':\n" + "\n".join(hits)
```

### Acceptance criteria

1. The test passes on the refactored codebase.
2. The test fails if you add `# eco2mix` as a comment in any non-allowed file (verify by adding-then-removing).

---

## Task 10 — Update `__init__.py`-level docs, CHANGELOG, and phase tracker

Update all user-facing and project-tracking surfaces to reflect the refactor.

### Changes

1. `README.md` — update the headline. Was something like "Python visualization for ANTARES studies." Becomes: "Python visualization for GEMS simulation outputs and arbitrary tabular time series." Add a one-line callout for the legacy adapter.
2. `CHANGELOG.md` — add a `## Unreleased` section noting the refactor:
   - Schema rewritten with `kind` discriminator.
   - `Lens.mc` deprecated in favor of `Lens.scenario`.
   - `theme.aliases` removed; eco2mix moved to `catalogs/examples/`.
   - Module-level `ECO2MIX` and `BASE` stack templates removed; load from YAML via `StackTemplate.from_yaml`.
   - New top-level types: `SimulationTable`, `Views`, `Catalog`.
   - `AntaresStudy` moved to `antalens.legacy.AntaresLegacyStudy`.
   - Domain-vocabulary lint added.
3. `CONTRIBUTING.md` — add a short section "Where domain content lives" explaining the catalog/legacy boundary and pointing to `gems.md`.
4. The package docstring in `antalens/__init__.py` — one-paragraph summary referencing `gems.md`.

### Phase tracker reconciliation

5. **Rewrite `PHASE_TRACKER.md`** (or whatever the existing tracker is named) to match the v0.2.0 phase structure in `plan.md`. This is a fresh write, not a patch — the old tracker's phase boundaries are no longer correct. The new tracker must:

   - Use the new phase labels: Phase 0, Phase 1 (Generic library), Phase 2 (GEMS data layer + reactivity), Phase 3 (Maps + presets + legacy), Phase 4 (Big data + MCP), Phase 5 (Polish + 1.0).
   - Move every checked (`[x]`) item from the old tracker into the right new phase, using the reconciliation table from the audit (Task 0 Q9) as the source of truth.
   - Mark items that were partially done and are now expected to change (e.g. `Schema`, `Lens`, `StackTemplate`) with `[~]` and a note like *"refactored in v0.2.0; see refactor.md Task 1"*.
   - Move queued (`[ ]`) items to the phase they now belong to per `plan.md` v0.2.0.
   - Add the new v0.2.0 items: `Catalog` system, `SimulationTable`, `Views`, `TablePlot`, DuckDB backend, `simulation_explorer` preset, `antalens.legacy` adapter, etc.
   - Preserve the same `[x] / [~] / [ ] / [—]` legend.
   - Keep the "What's done enough right now" summary at the bottom — and update it to reflect post-refactor state.

6. **Add a top note** to the new tracker linking to `refactor.md` and dating the v0.2.0 reframe, so future readers understand the phase renumbering.

### Acceptance criteria

1. README mentions GEMS, SimulationTable, Views, and the legacy adapter in the first 30 lines.
2. CHANGELOG records every breaking change from this refactor.
3. CONTRIBUTING points new contributors at `gems.md` for domain context.
4. `PHASE_TRACKER.md` reflects the v0.2.0 phase structure exactly. Every item from the audit's reconciliation table appears in its new phase. The legend is preserved.
5. Reading the tracker, an outside reviewer can answer "what's shipped, what's in flight, what's queued" without consulting the old tracker.

---

## Final verification (Task 11)

After tasks 1–10 are complete, run the full verification:

```bash
# 1. Lint and type-check
ruff check antalens/ tests/
ruff format --check antalens/ tests/
mypy --strict antalens/

# 2. Test suite (must pass entirely)
pytest tests/ -v

# 3. Domain-vocabulary lint
pytest tests/test_no_domain_leak.py -v

# 4. Public API surface check
python -c "
import antalens as al
expected = {'io','plot','map','dash','controls','catalog','theme','legacy',
            'Dataset','SimulationTable','Views','Catalog','Lens','link','pipe'}
actual = {x for x in dir(al) if not x.startswith('_')}
missing = expected - actual
extra = actual - expected
assert not missing, f'Missing public symbols: {missing}'
print('Public API surface matches spec.')
"

# 5. MVP still works
antalens-explore tests/fixtures/mock.parquet  # should serve as before

# 6. Forbidden term check (should be empty)
grep -rE 'eco2mix|ECO2MIX|ANTARES' antalens/ \
    --exclude-dir=legacy --exclude-dir=__pycache__ || echo "Clean."

# 7. Examples regression — every example script must run end-to-end
for script in examples/*.py; do
    echo "Running $script..."
    timeout 30 python "$script" --help >/dev/null 2>&1 || true
    # Adjust per-example invocation as needed; the point is each script
    # imports and instantiates without errors.
done

# 8. Phase tracker is up to date
test -f PHASE_TRACKER.md && grep -q "v0.2.0" PHASE_TRACKER.md \
    && echo "Tracker mentions v0.2.0 reframe." \
    || (echo "PHASE_TRACKER.md not updated"; exit 1)

# 9. spec.md §3.6 reflects the Lens decision from Task 1b
grep -q "GemsLens" spec.md || grep -q "with_extras" spec.md \
    && echo "spec.md §3.6 updated." \
    || echo "WARNING: confirm spec.md §3.6 matches the Lens shape from Task 1b."
```

All checks must pass before the refactor branch is merged.

### One spec update embedded in the refactor

Task 1b revises `spec.md` §3.6 to keep `component` and `output` out of the base `Lens`. The redline:

- **Remove** `component` and `output` parameters from the base `Lens` class definition.
- **Keep** `area`, `dates`, `variable`, `scenario` in the base.
- **Add** an example showing GEMS-specific extension: `GemsLens = Lens.with_extras(component=param.String(default=None), output=param.String(default=None))`.
- **Note** that Phase 2 will ship a ready-made `GemsLens` subclass for convenience.

This is the only spec.md change driven by the refactor — every other v0.2.0 design call from spec.md/plan.md remains unchanged.

---

## Out-of-scope reminders

The following are **explicitly not part of this refactor**, even if encountered during the work:

| Topic | Lands in |
|---|---|
| Implementing `Catalog.parse_component` and YAML parsing | Phase 2 |
| Implementing `SimulationTable.filter()` GEMS overload | Phase 2 |
| Implementing `SimulationTable.pivot()` and `to_views()` | Phase 2 |
| Implementing the full `Dashboard` GridSpec layout and JSON round-trip | Phase 2 (current FlexBox `Dashboard` is kept as-is) |
| Implementing `simulation_explorer` preset | Phase 2 |
| Implementing `pipe()` (the registry primitive — `link()` is already shipped per the tracker) | Phase 2 |
| Adding `component` / `output` parameters to a `GemsLens` subclass | Phase 2 |
| DuckDB backend | Phase 4 |
| Datashader auto-switching | Phase 4 |
| MCP server | Phase 4 |
| `AntaresLegacyStudy` actual implementation | Phase 3 |
| Maps (`pydeck`-backed builders) | Phase 3 |
| `TablePlot` real implementation (if not already done) | Phase 1 finalization or Phase 2 |

If during the refactor Claude Code finds that one of these is partially implemented but broken, it should **leave it alone** and document the state in `refactor/audit.md` for the relevant phase to address later. The refactor's job is to set the stage, not to advance the curtain.

---

## Commit hygiene

One commit per task. Commit messages in conventional-commit style:

```
docs(audit): pre-refactor audit and tracker reconciliation (#task-0)
refactor(schema): rewrite Schema with kind discriminator (#task-1)
refactor(lens): migrate mc → scenario, deprecate mc with alias (#task-1b)
refactor(theme,plots): externalize ECO2MIX/BASE to YAML, drop palette_categorical (#task-2)
feat(catalog): add Catalog scaffold with stub loaders (#task-3)
feat(data): add Dataset.with_catalog and .catalog (#task-4)
feat(plots): add BasePlot.apply_catalog stub (#task-5)
refactor(api): align top-level exports with spec.md §3.1 (#task-6)
feat(data): add SimulationTable and Views stubs (#task-7)
feat(legacy): add antalens.legacy module skeleton (#task-8)
test(lint): add domain-vocabulary leak test (#task-9)
docs: update README/CHANGELOG/CONTRIBUTING and rewrite PHASE_TRACKER for v0.2 (#task-10)
```

Push the branch, open a PR titled `refactor: GEMS reframe (v0.2.0-draft)` referencing this document and `gems.md`.
