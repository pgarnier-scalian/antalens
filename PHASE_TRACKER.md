# AntaLens — phase tracker

Source of truth for what's shipped, what's in flight, what's queued. Updated
when a feature locks in. Lightweight by design — heavy detail lives in
`SPEC.md`, `IMPLEMENTATION_PLAN.md`, and the per-decision ADRs.

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

- [x] `Lens` (param.Parameterized subclass) with `area`, `dates`, `variable`, `mc`
- [x] `Lens.with_extras()` for domain-specific subclasses
- [x] Reactive `Dataset.filter` with deferred binding resolution
- [x] `watched_parameters` API for downstream consumers

### Plot layer

- [x] `BasePlot` ABC with `build` / `to_pane` / `apply_theme`
- [x] `TimeSeriesPlot` with grouping, conf-int ribbon, cumulative mode
- [x] `BarPlot` with sort, orientation, aggregation
- [x] `ProductionStack` with template-based palette + load overlay + negative layers
- [x] `PlotlyTheme` with DARK / LIGHT instances
- [x] `StackTemplate` with `ECO2MIX` / `BASE` built-ins, `register_template()`
- [x] Plot accessor (`ds.plot.timeseries()` etc.)

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

- [x] `Dashboard` class with FlexBox layout, add/remove/move panes
- [x] `Dashboard` lens ownership + sharing
- [x] `Dashboard` status bar
- [x] `SectionTitle` for sidebar grouping
- [x] `link()` for chart-to-chart events with `transform=` support
- [x] Per-plot `event_extractors()` registry
- [x] CSS theme injection (deliberately incomplete — no full polish)
- [ ] More controls (`AreaSelector`, `DateRangeSelector`)
- [ ] Widget styling wrapper (currently `stylesheets=[...]` hack in examples)
- [ ] Dashboard JSON serialization (`to_json` / `from_json`)
- [ ] Heatmap chart type
- [—] Distribution / Duration / Scatter charts — deferred until needed

## Phase 3 — Maps + presets

- [ ] `MapLayout` dataclass with JSON round-trip
- [ ] `NetworkMap` (PyDeck ScatterplotLayer + ArcLayer)
- [ ] `ChoroplethMap`
- [ ] Layout editor (drag-and-drop in Panel)
- [ ] `dash.overview` preset (any Dataset)
- [ ] `dash.adequacy` preset (ANTARES)
- [ ] `dash.exchanges` preset (ANTARES)

## Phase 4 — Big data + MCP

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

Missing for a full v0.1 release: more controls, JSON dashboard serialization,
documentation, and a real CSS polish round.
