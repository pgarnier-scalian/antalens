# AntaLens — phase tracker

Source of truth for what's shipped, what's in flight, what's queued. Updated
when a feature locks in. Lightweight by design — heavy detail lives in
`SPEC.md`, `IMPLEMENTATION_PLAN.md`, and the per-decision ADRs.

**Current version**: v0.2.0 (in development)

## Status legend

- `[x]` shipped and locked
- `[~]` in flight
- `[ ]` queued
- `[—]` deferred (with reason)

---

## Phase 0 — Foundations

- [x] `pyproject.toml` with optional extras: `[maps]` `[bigdata]` `[antares]` `[mcp]` `[dev]`
- [x] Pre-commit hooks: ruff (lint + format), mypy --strict
- [x] `Makefile` with check/test/lint/docs/smoke/format targets
- [x] Sphinx docs scaffold with MyST + furo theme
- [x] Test fixture pattern (synthetic DataFrames, real disk via `tmp_path`)
- [x] VS Code workspace config (auto-format on save, pytest discovery)
- [x] **Refactor Task 1**: Schema with kind discriminator (`wide`, `long_gems`, `xarray`)
- [x] **Refactor Task 1b**: Migrate `Lens.mc` → `scenario` with backwards-compat deprecation
- [—] CI on GitHub Actions — deferred until first external contributor
- [—] PyPI publishing — deferred until v0.1.0 release-ready

## Phase 1 — Data layer + plot builders

### Data layer

- [x] `Schema` dataclass with auto-inference (time/categorical/numeric/geo)
- [x] `Dataset` with fluent chain (`filter`, `resample`, `compare`, `pipe`)
- [x] `ComparedDataset` (with reactive-binding bake-in compromise)
- [x] Loaders: `load_parquet`, `load_csv`, `from_dataframe`
- [—] `load_hdf5`, `load_antares`, `from_sql` — deferred to Phase 3 (need real ANTARES data first)

### Reactive layer

- [x] **Refactor Task 1b**: `Lens` with `area`, `dates`, `variable`, `scenario` (replaces deprecated `mc`)
- [x] **Refactor Task 1b**: Backwards-compatible `mc` alias with deprecation warning
- [x] `Lens.with_extras()` for domain-specific subclasses
- [x] Reactive `Dataset.filter` with deferred binding resolution
- [x] `watched_parameters` API for downstream consumers

### Plot layer

- [x] **Refactor Task 10**: `BasePlot.apply_catalog()` stub (catalog metadata integration)
- [x] `BasePlot` ABC with `build` / `to_pane` / `apply_theme`
- [x] `TimeSeriesPlot` with grouping, conf-int ribbon, cumulative mode
- [x] `BarPlot` with sort, orientation, aggregation
- [x] `ProductionStack` with template-based palette + load overlay + negative layers
- [x] **Refactor Task 2**: `StackTemplateConfig` externalized to YAML (removed ANTARES-specific `ECO2MIX`/`BASE`)
- [x] **Refactor Task 2**: `PlotlyTheme` with DARK / LIGHT instances only
- [x] Plot accessor (`ds.plot.timeseries()` etc.)
- [x] **Refactor Task 6**: `pipe()` primitive exported from `antalens.plot`

### Tests

- [x] Schema (20 tests)
- [x] Dataset (29 tests)
- [x] Loaders (24 tests)
- [x] Lens (24 tests)
- [x] Reactive Dataset (16 tests)
- [x] Theme (7 tests)
- [x] TimeSeriesPlot (~28 tests)
- [x] BarPlot (~22 tests)
- [x] ProductionStack (~12 tests)

### MVP integration

- [x] `examples/data_explorer.py` — parquet/CSV → reactive plot → served
- [x] `examples/dashboard_demo.py` — multi-pane reactive dashboard with shared Lens
- [x] `examples/lp_explorer.py` — real LP solver data (210MB CSV) with stack/bar/timeseries

## Phase 2 — Reactivity + dashboard

### Data layer (GEMS-aware)

- [x] **Refactor Task 7**: `SimulationTable` stub (GEMS raw output Dataset subclass)
- [x] **Refactor Task 7**: `SimulationTableSchema` with long-format schema
- [x] **Refactor Task 7**: `Views` stub (GEMS curated output Dataset subclass)
- [x] **Refactor Task 7**: `ViewsSchema` for wide-format curated outputs

### Dashboard

- [x] `Dashboard` class with FlexBox layout, add/remove/move panes
- [x] `Dashboard` lens ownership + sharing
- [x] `Dashboard` status bar
- [x] `SectionTitle` for sidebar grouping
- [x] **Refactor Task 8**: `link()` for chart-to-chart events with `transform=` support
- [x] Per-plot `event_extractors()` registry
- [x] CSS theme injection (deliberately incomplete — no full polish)

### Controls (stubbed)

- [x] **Refactor Task 8**: `ScenarioSelector` stub
- [x] **Refactor Task 8**: `DateRangeSlider` stub
- [x] **Refactor Task 8**: `VariableToggle` stub

### Legacy adapter (stubbed)

- [x] **Refactor Task 8**: `AntaresLegacyStudy` wrapper stub
- [x] **Refactor Task 8**: `load_antares()` loader stub

- [ ] More controls (full implementation)
- [ ] Widget styling wrapper (currently `stylesheets=[...]` hack in examples)
- [ ] Dashboard JSON serialization (`to_json` / `from_json`)
- [ ] Heatmap chart type
- [—] Distribution / Duration / Scatter charts — deferred until needed

## Phase 3 — Maps + presets

### Maps (stubbed)

- [x] **Refactor Task 8**: `antalens.map` namespace (stub, deferred to Phase 3)

### Presets

- [ ] `MapLayout` dataclass with JSON round-trip
- [ ] `NetworkMap` (PyDeck ScatterplotLayer + ArcLayer)
- [ ] `ChoroplethMap`
- [ ] Layout editor (drag-and-drop in Panel)
- [ ] `dash.overview` preset (any Dataset)
- [ ] `dash.adequacy` preset (ANTARES)
- [ ] `dash.exchanges` preset (ANTARES)

## Phase 4 — Big data + MCP

### Catalog system

- [x] **Refactor Task 3**: `Catalog` dataclass skeleton
- [x] **Refactor Task 3**: `ComponentPattern` dataclass
- [x] **Refactor Task 3**: `OutputMetadata` dataclass
- [x] **Refactor Task 3**: `ColorPalette` dataclass
- [x] **Refactor Task 3**: `StackTemplateConfig` dataclass
- [x] **Refactor Task 3**: `load_catalog()` loader

### Big data + MCP

- [ ] Datashader auto-switching at 50k point threshold
- [ ] Dask integration for chunked xarray
- [ ] FastMCP server
- [ ] All 12 MCP tools from spec §5.1
- [ ] MCP integration tests

## Phase 5 — Polish + 1.0

- [ ] Architecture decision records (in flight — see `docs/adrs/`)
- [ ] Stability classification document
- [ ] Sphinx tutorials (getting started, migration, dashboards, MCP)
- [ ] Cookbook recipes
- [ ] Real CSS/component polish round
- [ ] Dockerfile + Helm chart
- [ ] PyPI 1.0 release

---

## What's "done enough" right now

The toolchain works end-to-end on real client data. A user can:

- Load parquet, CSV, or DataFrame
- Filter reactively via a `Lens`
- Render as timeseries / bar / production stack
- Compose multi-pane dashboards with shared state
- Wire chart events to lens parameters via `link()`
- Serve via Panel

### Refactored public API

Following the spec.md §3.1 alignment:

- `import antalens as al` exposes: `io`, `plot`, `map`, `dash`, `controls`, `catalog`, `theme`, `legacy`, `link`, `Dataset`, `SimulationTable`, `Views`, `Catalog`, `Lens`, `pipe`
- `SimulationTable` and `Views` are stubs awaiting full GEMS implementation
- `controls` and `legacy` modules are stubs awaiting full implementation
- `Catalog` system is skeleton (dataclasses + loader) awaiting domain semantics

### Stub placeholder status

The following modules are stubs (functional imports, no full implementation):

- `SimulationTable`, `Views` — GEMS data layer stubs
- `ScenarioSelector`, `DateRangeSlider`, `VariableToggle` — controls stubs
- `AntaresLegacyStudy`, `load_antares()` — legacy adapter stub
- `MapLayout`, `NetworkMap`, `ChoroplethMap` — maps stubs (moved to Phase 3)

Missing for a full v0.1 release: stub implementations, more controls, JSON dashboard serialization,
documentation, and a real CSS polish round.
