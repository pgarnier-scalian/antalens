# GEMS — data model reference for AntaLens

> **Companion to**: `SPEC.md`, `PLAN.md`
> **Status**: pre-implementation
> **Audience**: AntaLens implementers; anyone integrating against GEMS outputs.

This document pins down the **data contract between GEMS and AntaLens**. It is not a GEMS tutorial — for that, see `gems-energy.readthedocs.io`. It is the source of truth for how AntaLens models GEMS outputs and what stays *outside* AntaLens.

---

## 1. Context

GEMS (Generic Energy Systems Modelling Scheme) is the architectural successor to legacy ANTARES. The key shift relevant to AntaLens is that **simulation outputs are no longer per-area, per-MC-year folders with hard-coded variable names**. Instead, a single **SimulationTable** is emitted with generic, use-case-independent column names, and downstream **Views** give it semantic meaning via user-supplied catalogs.

```
inputs                   raw output             curated output
─────────                ──────────             ──────────────
library.yml      ┐                              Views
system.yml       ├─→ GEMS interpreter ─→ SimulationTable ─→ ViewsBuilder ─→ (parquet)
timeseries.csv   ┘    (Antares Sim or          (CSV / Parquet)        ↑
                       GemsPy)                                        │
                                                              catalog.yml
                                                              view-config.yml
```

**AntaLens position in this pipeline**: AntaLens is a *consumer*. It reads SimulationTable and/or Views. It never produces them. The GEMS interpreter and the ViewsBuilder are out of scope.

---

## 2. SimulationTable

### 2.1 Schema

SimulationTable is a **long-format** table with eight generic columns, identical for every use case:

| Column                 | Type            | Meaning                                                                 |
|------------------------|-----------------|-------------------------------------------------------------------------|
| `block`                | int             | Index of the optimization sub-problem (rolling-horizon block).          |
| `component`            | string          | Unique name of a component in `system.yml` (e.g. `generator_AT0_0_CCGT`). |
| `output`               | string          | Name of an output variable on that component (e.g. `p`, `min_dispatch`). |
| `absolute_time_index`  | int             | Global timestep, 1-indexed, across the full simulation horizon.         |
| `block_time_index`     | int             | Timestep within the block; resets per block.                            |
| `scenario_index`       | int             | Monte Carlo scenario index, 0-indexed.                                  |
| `value`                | float \| null   | The variable's value, or `null` for unbounded / not-applicable.         |
| `basis_status`         | string          | Solver basis: `Free`, `Basic`, `AtLowerBound`, `AtUpperBound`, `AtFixedValue`. |

Example rows:

```
block, component,                output,        absolute_time_index, block_time_index, scenario_index, value,            basis_status
1,     generator_AT0_0_CCGT,     p,             166,                 166,              0,              371,              Free
1,     generator_AT0_0_CCGT,     p,             167,                 167,              0,              371,              Free
1,     generator_AT0_0_CCGT,     min_dispatch,  1,                   1,                0,              null,             Free
```

### 2.2 Notable properties

- **Generic**: column names never change. AntaLens code that consumes SimulationTable does *not* need to know whether the simulation is electrical, gas, telecom, or industrial.
- **Long-format**: one row per (component, output, time, scenario) observation. Wide-format pivoting happens at plot time, not at storage time.
- **Component names encode structure by convention**, not by schema. The example `generator_AT0_0_CCGT` parses (under one possible convention) as `<type>_<area>_<unit>_<fuel>`. Conventions are user-defined and live in the catalog (section 4), never in AntaLens code.
- **`output` names are component-type-specific**. A generator exposes `p`, `cost`, etc.; a link exposes `flow`, `available`. The vocabulary is defined in `library.yml` per component model.
- **Nullable values**: `value = null` means the variable is unbounded or not yet computed. Plotters must handle this gracefully (drop, mask, or warn).
- **`basis_status`** is solver-side metadata. Useful for marginal-price analysis and debugging; ignored by most plot builders.

### 2.3 Volume

Indicative sizes for one realistic study (RTE adequacy-class, ~500 components, ~10 outputs each):

| Horizon         | Scenarios | CSV size  | Parquet size (snappy) |
|-----------------|-----------|-----------|------------------------|
| 168h (1 week)   | 1         | ~200 MB   | ~7–8 MB                |
| 8760h (1 year)  | 1         | ~10 GB    | ~350 MB                |
| 8760h (1 year)  | 100       | ~1 TB     | ~35 GB                 |

A full-horizon, multi-scenario SimulationTable does **not** fit in RAM. The data layer must support out-of-core access.

---

## 3. Views

Views are **curated, wide-format parquet files** derived from a SimulationTable by the GEMS ViewsBuilder. Each view is configured by a `view-config.yml` and a `catalog.yml` (the catalog is shared across views; the view-config is per-view).

A typical Views file looks like:

| timestamp           | scenario | area  | NUCLEAR | GAS_CCGT | WIND  | LOAD   |
|---------------------|----------|-------|---------|----------|-------|--------|
| 2030-01-01 00:00:00 | 0        | FR    | 45000   | 8000     | 12000 | 65000  |
| 2030-01-01 01:00:00 | 0        | FR    | 45000   | 7500     | 12500 | 64000  |

This is what a non-scientist user wants. It's roughly the shape of a legacy ANTARES output, but produced by user-controlled configuration rather than hardcoded simulator behavior.

Properties:

- **Wide-format**: one column per semantic variable.
- **Smaller than SimulationTable**: typically 10×–100× smaller, because aggregations (sum-over-units, sum-over-fuels-per-area) are applied during view derivation.
- **Fits in memory** for most studies, even at full horizon × 100 scenarios.
- **Catalog-defined semantics**: the column names (`NUCLEAR`, `WIND`, `LOAD`) and groupings come from the catalog, not from AntaLens.

AntaLens treats Views as the canonical input for **dashboards and presets**, and SimulationTable as the canonical input for **scientist-driven exploration**.

---

## 4. Catalog system

The catalog is the bridge from generic GEMS column names to domain semantics. It lives in YAML files supplied by the user (or by a study template). AntaLens **consumes** catalogs; it never authors or modifies them.

### 4.1 `catalog.yml` (sketch)

```yaml
# Component-name parsing rules. AntaLens applies the first matching pattern.
component_patterns:
  - pattern: "^generator_(?P<area>\\w+?)_(?P<unit>\\d+)_(?P<fuel>\\w+)$"
    kind: generator
    display: "{fuel} unit {unit} ({area})"
  - pattern: "^link_(?P<from>\\w+?)_(?P<to>\\w+?)$"
    kind: link
    display: "{from} → {to}"
  - pattern: "^load_(?P<area>\\w+)$"
    kind: load
    display: "Load {area}"

# Output (variable) display metadata.
outputs:
  p:        { display: "Production",  unit: "MW",  default_agg: "sum"  }
  cost:     { display: "Cost",        unit: "€",   default_agg: "sum"  }
  flow:     { display: "Flow",        unit: "MW",  default_agg: "mean" }
  marginal: { display: "Marginal",    unit: "€/MWh", default_agg: "mean" }

# Color palette by fuel (or by any catalog-defined dimension).
palette:
  by_fuel:
    NUCLEAR: "#ffd23f"
    GAS_CCGT: "#d62828"
    WIND: "#06a77d"
    SOLAR: "#f4a261"
    LOAD: "#264653"

# Templated stack orderings — replaces the hardcoded eco2mix template.
stack_templates:
  eco2mix:
    order: [NUCLEAR, GAS_CCGT, WIND, SOLAR]
    negative: [PUMP, EXPORT]
    palette: by_fuel
```

### 4.2 `view-config.yml` (sketch)

```yaml
# Production by area: sum p over all generators in each area, broken down by fuel.
view: production_by_area
group_by: [area, fuel, scenario_index, absolute_time_index]
filter:
  component_kind: generator
  output: p
aggregation: sum
output_columns:
  area: from_pattern   # extract from component name via catalog
  fuel: from_pattern
  scenario: from scenario_index
  timestamp: from absolute_time_index  # mapped to wall-clock via study start date
  value: aggregated
```

### 4.3 Externalization principle

Anything domain-specific lives in catalogs:

- Fuel orderings and color palettes (no more hardcoded `eco2mix` in Python).
- Country-name → centroid lookups for `MapLayout.auto()`.
- Variable display names and units.
- Component-name parsing conventions.

The library ships **example catalogs** (`catalogs/examples/eco2mix.yml`, `catalogs/examples/europe_geo.yml`) but no hardcoded domain knowledge in code paths.

---

## 5. Mapping to AntaLens types

| GEMS concept            | AntaLens type                  | Backend                            |
|-------------------------|--------------------------------|------------------------------------|
| SimulationTable         | `SimulationTable(Dataset)`     | polars LazyFrame or DuckDB on parquet |
| Views                   | `Views(Dataset)`               | polars DataFrame or LazyFrame      |
| Catalog                 | `Catalog` (frozen dataclass)   | parsed from YAML at load time      |
| Generic tabular file    | `Dataset`                      | polars / xarray                    |
| Legacy ANTARES study    | `AntaresLegacyStudy(Dataset)`  | h5py + filesystem walker           |

`SimulationTable` and `Views` are first-class. `AntaresLegacyStudy` is a backwards-compatibility adapter for organizations not yet migrated to GEMS; it lives in `antalens.legacy` and is not part of the architectural core.

### 5.1 `SimulationTable` — public interface (informative)

```python
class SimulationTable(Dataset):
    """A GEMS SimulationTable backed by parquet (lazy)."""

    catalog: Catalog | None

    # GEMS-aware accessors (lazy, predicate-pushdown where possible)
    @property
    def components(self) -> list[str]: ...
    @property
    def outputs(self) -> list[str]: ...
    @property
    def scenarios(self) -> list[int]: ...
    @property
    def blocks(self) -> list[int]: ...

    # GEMS-aware filtering — extends Dataset.filter
    def filter(self, *,
               component: str | list[str] | None = None,
               component_kind: str | None = None,   # via catalog
               output: str | list[str] | None = None,
               scenario: int | list[int] | None = None,
               time_range: tuple[int, int] | None = None,  # absolute_time_index
               **kw) -> SimulationTable: ...

    # Wide-format pivot for plotting
    def pivot(self, *, index: str = "absolute_time_index",
              columns: str = "output",
              values: str = "value") -> Dataset: ...

    # Promote to a Views file via a view-config
    def to_views(self, view_config: Path | dict) -> Views: ...
```

### 5.2 `Views` — public interface (informative)

```python
class Views(Dataset):
    """A GEMS Views file (curated, wide-format)."""

    catalog: Catalog | None
    source: SimulationTable | Path | None  # lineage, optional
    view_config: Path | None               # lineage, optional
```

`Views` adds little beyond `Dataset` because the wide format already fits the chain API. The lineage fields exist for introspection and reproducibility.

---

## 6. Backend strategy

| Tier | Data size on disk | Backend                       | Why |
|------|-------------------|-------------------------------|-----|
| 1    | < 1 GB            | polars eager / pandas         | Fits in RAM; simplest path. |
| 2    | 1–50 GB           | polars LazyFrame on parquet   | Predicate pushdown + streaming aggregations. |
| 3    | > 50 GB           | DuckDB on parquet             | Vectorized SQL engine, zero-copy with Arrow, handles spills. |
| 4    | distributed       | Dask + xarray (out-of-core)   | Multi-MC scientific workflows that need broadcasting. |

Tier selection is automatic based on file size at load time, but can be overridden:

```python
ds = al.io.load_simulation_table("sim.parquet", backend="duckdb")
```

DuckDB lives in the `[bigdata]` extra. It is **the recommended backend for GEMS workloads at scale** because most user-facing operations (filter by component, pivot, aggregate per scenario) are SQL-shaped and benefit from predicate pushdown to parquet.

---

## 7. What stays out of AntaLens

These belong to GEMS or to the user, not to AntaLens:

- **The GEMS interpreter** (Antares Simulator, GemsPy). AntaLens never invokes a simulator.
- **The ViewsBuilder.** AntaLens reads its outputs but does not implement view derivation. (`SimulationTable.to_views()` is a thin convenience that delegates to a small reference implementation; large-scale view derivation is the ViewsBuilder's job.)
- **Catalog authoring.** AntaLens consumes catalogs. A future Catalog Editor GUI is a separate product.
- **System editing.** AntaLens visualizes outputs; the `system.yml` / `library.yml` editors are GEMS-side tools.

This boundary keeps AntaLens focused on visualization and prevents it from becoming a second simulator.

---

## 8. Glossary

- **Block**: an optimization sub-problem in a rolling-horizon simulation. A weekly block of 168h is typical.
- **Component**: a named entity in `system.yml` (a generator, a link, a load, a storage, a bus).
- **Output**: a named variable on a component, defined by its component model in `library.yml`.
- **Catalog**: user-supplied YAML mapping generic GEMS names to domain semantics.
- **View**: a curated, wide-format parquet derived from a SimulationTable by the ViewsBuilder.
- **SimulationTable**: the long-format, generic-schema raw output of a GEMS run.
- **basis_status**: solver-side flag indicating the basis state of a variable in the LP/MILP solution.
