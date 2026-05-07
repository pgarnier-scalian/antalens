# AntaLens — Implementation Plan

> **Companion to**: `SPEC.md`, `gems.md`
> **Version**: 0.2.0-draft (post-GEMS reframe)
> **Status**: Phase 0 complete; Phase 1 in flight; Phase 2+ re-scoped for GEMS.

---

## Overview

The implementation is structured into five phases plus a phase 0 for foundational setup. Each phase produces a tagged release that is deployable on its own.

```
Phase 0  →  Foundations                   (2 weeks)   [DONE]
Phase 1  →  Generic library + plots       (4 weeks)   [IN FLIGHT, ~80% done]
Phase 2  →  GEMS data layer + reactivity  (6 weeks)
Phase 3  →  Maps, presets, legacy adapter (5 weeks)
Phase 4  →  Big data (DuckDB+Datashader) + MCP  (5 weeks)
Phase 5  →  Polish + 1.0 release          (3 weeks)
```

Total: ~25 weeks (≈ 6 months) with one full-time engineer. Two engineers can compress this to ~15 weeks by parallelizing Phase 2's data and reactivity tracks, and Phase 3/4.

The plan is explicitly designed so that **Phase 1 alone delivers a usable library** for non-GEMS tabular data. Phase 2 makes it the canonical GEMS visualization layer. Phase 3 adds the legacy-ANTARES adapter and the visual richness presets. Phase 4 makes it scale. Phase 5 ships it.

---

## Phase 0 — Foundations

**Status**: ✅ complete. **Tag**: `v0.0.1`.

Repository skeleton, CI, pre-commit, sphinx scaffold, license, contributing docs. No functional code. See the original Phase 0 in the v0.1 plan for full deliverables list — none of it changes.

---

## Phase 1 — Generic library and plots

**Duration**: 4 weeks (originally 5; trimmed because `AntaresStudy` is removed from this phase).
**Tag**: `v0.1.0`
**Goal**: a usable library for tabular time-series visualization on arbitrary parquet/CSV/SQL data. **No GEMS-specific features and no ANTARES-specific features in this phase.**

### Status (as of refactor)

Most of Phase 1 is already done. The MVP (`mvp.md`) is the closing milestone:

- ✅ `Schema`, `Dataset`, generic loaders, `Lens`, `TimeSeriesPlot`, theme system, plot accessor.
- 🚧 MVP integration: `Dashboard` (minimal), `VariablePicker` control, CLI entry point (`antalens-explore`).
- ❌ Remaining plot builders: `BarPlot`, `ProductionStack`, `DurationCurve`, `HeatmapPlot`, `DistributionPlot`, `ScatterPlot`, `TablePlot`.

### Deliverables (final form post-refactor)

#### 1.1 `Dataset` core ✅

- `antalens/data/dataset.py` — `Dataset` with `filter`, `resample`, `compare`, `pipe`, `with_catalog`, `to_dataframe`, `to_pandas`, `to_xarray`, `schema`, `catalog`.
- `antalens/data/schema.py` — extended `Schema` with `kind` discriminator (`"wide"`, `"long_gems"`, `"xarray"`) and the long-format fields populated only for the GEMS case. Long-format support lands here so Phase 2's `SimulationTable` is purely additive.
- `antalens/data/loaders.py` — `load_parquet`, `load_csv`, `load_hdf5`, `from_dataframe`, `from_sql`.

#### 1.2 Theme system ✅ *(needs externalization pass)*

- `antalens/theme/plotly.py` — `PlotlyTheme` dataclass + `DARK` and `LIGHT`. **`palette_categorical` removed** — categorical palettes belong in catalogs (Phase 2), not in themes.
- `antalens/theme/aliases.py` — **deleted in this phase**. The `ECO2MIX` and `BASE` alias dictionaries move to `catalogs/examples/eco2mix.yml` (Phase 2). Until catalogs land, plot builders use the theme's neutral fallback palette.

#### 1.3 Plot builders 🚧

One file per plot family, each implementing the `BasePlot` ABC. `apply_catalog()` is a no-op stub in this phase; it gets implemented in Phase 2.

- `antalens/plots/_base.py` — `BasePlot` with `apply_theme()` and stub `apply_catalog()`.
- `antalens/plots/timeseries.py` — `TimeSeriesPlot` ✅
- `antalens/plots/bar.py` — `BarPlot`
- `antalens/plots/stack.py` — `ProductionStack` (template defaults to `"auto"`; resolves from catalog when one is attached, otherwise neutral palette in column-name order)
- `antalens/plots/duration.py` — `DurationCurve`
- `antalens/plots/heatmap.py` — `HeatmapPlot`
- `antalens/plots/distribution.py` — `DistributionPlot`
- `antalens/plots/scatter.py` — `ScatterPlot`
- `antalens/plots/table.py` — `TablePlot` (TableMode, Tabulator-backed)

#### 1.4 Plot accessor ✅

- `antalens/data/accessors.py` — `PlotAccessor` wired to `Dataset.plot`. Now exposes `.table` alongside the seven chart builders.
- Auto-detection logic for inferring `time_col`, `categorical_cols` from the bound dataset's schema.

#### 1.5 MVP closure 🚧

The `mvp.md` deliverables: minimal `Dashboard`, `VariablePicker`, `LensBound` y-axis on `TimeSeriesPlot`, `parquet_explorer` example, `antalens-explore` CLI.

### Acceptance criteria

- The `mvp.md` acceptance criteria pass (5-line script → live, interactive timeseries plot served in browser).
- All eight plot types render correctly (seven charts + table) with the generic mock fixture.
- Snapshot tests pass for every plot type.
- Type coverage on the public API is 100% — `mypy --strict` clean.
- **No file in `antalens/` references ANTARES, GEMS, eco2mix, or any domain-specific term.** This is a structural check (grep-able in CI).

### Hand-off to Phase 2

The library has a generic, domain-free core. Plot builders return Plotly figures wrapped in panes. They expose `apply_catalog()` as a stub. Phase 2 fills in the GEMS data layer, the catalog system, and the reactivity that turns isolated panes into connected dashboards.

---

## Phase 2 — GEMS data layer and reactivity

**Duration**: 6 weeks
**Tag**: `v0.2.0`
**Goal**: AntaLens reads `SimulationTable` and `Views`, applies user-supplied catalogs, and supports connected dashboards via shared `Lens`, `link()`, and `pipe()`.

### Deliverables

#### 2.1 Catalog system (week 1)

- `antalens/catalog/__init__.py` — re-exports `Catalog`, `load`, `merge`, `empty`.
- `antalens/catalog/catalog.py` — `Catalog` dataclass with `component_patterns`, `outputs`, `palettes`, `stack_templates`, `geo`. Frozen and hashable.
- `antalens/catalog/parser.py` — YAML → `Catalog` parser with strict schema validation (Pydantic).
- `antalens/catalog/parse_component.py` — regex-based component-name parser.
- `catalogs/examples/eco2mix.yml` — French TSO production-stack template (replaces the old hardcoded `ECO2MIX` dictionary).
- `catalogs/examples/europe_geo.yml` — European area centroids (replaces the old hardcoded country lookup in `MapLayout.auto`).
- `catalogs/examples/gems_minimal.yml` — minimal patterns for the standard GEMS naming convention.

#### 2.2 `SimulationTable` (week 1–2)

- `antalens/data/simulation_table.py` — `SimulationTable(Dataset)` with `.components`, `.outputs`, `.scenarios`, `.blocks`, GEMS-aware `filter()`, `pivot()`, `to_views()`.
- `antalens/data/loaders.py` — `load_simulation_table()` with `backend="polars"` only in this phase. `backend="duckdb"` and `"auto"` land in Phase 4. The signature accepts the parameter now so the API contract is stable.
- Polars LazyFrame backend with predicate pushdown verified by tests.

#### 2.3 `Views` (week 2)

- `antalens/data/views.py` — `Views(Dataset)` with optional `source` and `view_config` lineage fields.
- `antalens/data/loaders.py` — `load_views()`.
- Reference implementation of `SimulationTable.to_views()` for simple group-by-and-aggregate view configs (full ViewsBuilder feature parity is *not* a goal — this is the convenience path).

#### 2.4 Catalog wiring through plot builders (week 2)

- `BasePlot.apply_catalog()` actually does work now: applies display names, units, palettes, stack orderings.
- `ProductionStack` resolves `template="auto"` from the attached catalog's `stack_templates.default`.
- `Dataset.with_catalog(cat)` propagates to all plot/map builders without re-loading data.

#### 2.5 `Lens` and reactive `filter()` (week 3)

- Confirm `Lens` (already built in Phase 1) supports the GEMS-relevant parameters: `component`, `output`, `scenario`. Add via `with_extras()` if not already present.
- `Dataset.filter()` accepts `Lens` instances or individual `param.Parameter` references; results re-evaluate via `pn.bind()` on parameter change.
- `SimulationTable.filter()` pushes Lens-bound predicates down to polars LazyFrame.
- Test: a `SimulationTable` filtered with a `Lens` and rendered as a pane updates within 500 ms when the lens mutates.

#### 2.6 `link()` (week 4)

- `antalens/link.py` — the `link()` function.
- Per-pane event registration: each plot builder declares which Plotly events it exposes (`xrange_select`, `point_click`, `row_click`, etc.).
- Implementation: register a `clientData` callback on the Plotly/Tabulator pane, parse the event payload, assign to the target `param.Parameter`.

#### 2.7 `pipe()` (week 4)

- `antalens/pipe.py` — `PipeNode` class + `pipe()` constructor.
- Shared transform memoization: a `PipeNode` caches its filtered result and exposes it to all downstream chains.
- `PipeNode.join_on(time_col)` for cross-dataset joins.

#### 2.8 `Dashboard` (week 5)

- `antalens/dash/dashboard.py` — promote the MVP `Dashboard` to the full spec: `GridSpec`-backed, with `add`, `remove`, `serve`, `save`, `to_html`, `to_notebook`, `to_json`, `from_json`.
- Pane IDs are stable identifiers usable later by MCP.

#### 2.9 Controls (week 5)

- `antalens/controls.py` — extends `VariablePicker` (from MVP) with `ComponentPicker`, `OutputPicker`, `ScenarioPicker`, `AreaSelector`, `DateRangeSelector`. Each is a thin wrapper around a Panel widget that mutates a specific `Lens` parameter.

#### 2.10 First GEMS preset (week 6)

- `antalens/dash/presets/simulation_explorer.py` — 4-pane dashboard for a `SimulationTable`: TableMode, ComponentPicker, per-output timeseries, per-scenario distribution. The recommended starting point for scientists exploring raw output.

### Acceptance criteria

- The end-to-end script runs:
  ```python
  import antalens as al
  cat = al.io.load_catalog("catalog.yml")
  ds = al.io.load_simulation_table("sim.parquet", catalog=cat)
  al.dash.simulation_explorer(ds).serve()
  ```
- Loading a 1 GB `SimulationTable` parquet uses < 200 MB RAM (verified by benchmark).
- A `Lens.component` change propagates to all bound panes in < 500 ms.
- `Dashboard.to_json()` followed by `Dashboard.from_json()` produces a visually identical dashboard.
- `ProductionStack` with the `eco2mix.yml` catalog produces a chart matching the legacy reference (manual review).
- 100% of public API symbols (per spec §3) implemented or stubbed with clear `NotImplementedError` for legacy/maps/MCP namespaces.

### Hand-off to Phase 3

GEMS data flows through the reactive layer end-to-end. Catalogs drive all domain semantics. Phase 3 adds the visual richness (maps, choropleth, flow), the additional presets, and the legacy ANTARES adapter that connects pre-GEMS studies to the same plot/dashboard infrastructure.

---

## Phase 3 — Maps, presets, and legacy adapter

**Duration**: 5 weeks
**Tag**: `v0.3.0`
**Goal**: full geo/network map layer + ready-to-use dashboard presets + working `antalens.legacy` adapter.

### Deliverables

#### 3.1 `MapLayout` (week 1)

- `antalens/maps/layout.py` — `MapLayout` dataclass with `to_json`, `from_json`, `auto`. **`auto` requires a catalog with a `geo` section** (reads `catalogs/examples/europe_geo.yml` for ANTARES studies).

#### 3.2 PyDeck-backed map builders (week 1–2)

- `antalens/maps/network.py` — `NetworkMap` with ScatterplotLayer (nodes) + ArcLayer (links).
- `antalens/maps/choropleth.py` — `ChoroplethMap` with GeoJsonLayer.
- `antalens/maps/flow.py` — `FlowMap` for animated flow visualization.

#### 3.3 Layout editor (week 2)

- `antalens/maps/layout_editor.py` — Panel-based interactive editor (ipyleaflet for editing UX, converts to `MapLayout`).

#### 3.4 Remaining presets (week 3)

- `antalens/dash/presets/overview.py` — generic 4-panel dashboard for any `Dataset`.
- `antalens/dash/presets/adequacy.py` — operates on `Views`. LOLD heatmap, balance map, ENS distribution, prodstack.
- `antalens/dash/presets/exchanges.py` — operates on `Views`. Exchange stack, flow map, hourly imports/exports.

#### 3.5 Legacy ANTARES adapter (week 4–5)

- `antalens/legacy/__init__.py` — public surface: `AntaresLegacyStudy`, `load_antares`.
- `antalens/legacy/study.py` — `AntaresLegacyStudy(Dataset)` with `.areas`, `.links`, `.clusters`, `.mc_years`.
- `antalens/legacy/io.py` — filesystem walker for legacy ANTARES output folders.
- `antalens/legacy/catalog.py` — a built-in catalog covering the legacy ANTARES variable taxonomy (LOAD, BALANCE, NUCLEAR, WIND, SOLAR, GAS, etc.) so existing studies plot correctly without users authoring a catalog.
- This module depends on the `[legacy]` extra (h5py).

### Acceptance criteria

- `views.map.network(layout, node_color="balance")` produces a working PyDeck map with catalog-driven coloring.
- The layout editor opens in Jupyter, allows drag-and-drop, persists to JSON.
- `al.dash.overview(al.io.load_parquet("any.parquet")).serve()` produces a useful dashboard with no further configuration.
- All three Views-based presets (`overview`, `adequacy`, `exchanges`) work end-to-end on `mock_views`.
- `al.legacy.load_antares("path/to/legacy_study/").plot.stack()` produces a chart visually equivalent to the antaresViz reference.
- `import antalens.maps` without `pydeck` raises a clear `ImportError`. Same for `antalens.legacy` without h5py.

### Hand-off to Phase 4

The library has full visual feature coverage. Everything works at desktop-data scale. Phase 4 adds the scale (DuckDB + Datashader + Dask) and the AI integration (MCP).

---

## Phase 4 — Big data and MCP

**Duration**: 5 weeks
**Tag**: `v0.4.0`
**Goal**: handle full-scale `SimulationTable` workloads (35+ GB parquet) and expose AntaLens to LLM agents via MCP.

### Deliverables

#### 4.1 DuckDB backend for `SimulationTable` (week 1–2)

- `antalens/data/_duckdb.py` — internal DuckDB connection wrapper, parquet attach, predicate-pushdown query builder.
- `load_simulation_table(backend="duckdb")` and `backend="auto"` (5 GB threshold by default).
- `SimulationTable.filter()` translates Lens-bound predicates to SQL `WHERE` clauses.
- `SimulationTable.pivot()` uses DuckDB's `PIVOT` syntax.
- Bench: filtering one component-output pair from a 35 GB parquet returns to a renderable DataFrame in < 2 s.

#### 4.2 Datashader integration (week 2–3)

- `antalens/plots/_datashader.py` — internal helpers for converting a points DataFrame to a Datashader-rasterized PNG.
- Auto-switching logic in `TimeSeriesPlot`, `HeatmapPlot`, `ScatterPlot`: when `len(data) > threshold`, route through Datashader.
- Datashader-rasterized panes still expose the same events (`xrange_select`, etc.) by tracking the data extent.

#### 4.3 Dask integration (week 3)

- xarray-backed `Dataset` instances support Dask-chunked data transparently.
- Multi-scenario `SimulationTable` operations that don't map cleanly to SQL fall back to Dask via the xarray escape hatch.

#### 4.4 FastMCP server (week 3–4)

- `antalens/mcp/server.py` — FastMCP application.
- `antalens/mcp/session.py` — `Session` class holding datasets, catalogs, dashboard, lens.
- `antalens/mcp/tools.py` — all 15 tool wrappers from `SPEC.md` §5.1.
- `antalens/mcp/converters.py` — Panel pane → MCP-safe response conversion.

#### 4.5 MCP integration tests (week 4)

- `tests/integration/test_mcp.py` — end-to-end test for each tool.
- Mock LLM transcript: a sequence of tool calls that loads a SimulationTable + catalog, builds a dashboard, exports.

#### 4.6 Performance benchmarks (week 5)

- `tests/perf/bench_render.py` — render latency at each data tier.
- `tests/perf/bench_storage.py` — polars vs DuckDB on small/medium/large `mock_simulation_table`.
- `tests/perf/bench_mcp.py` — end-to-end latency from MCP call to dashboard update.
- Results published in `docs/performance.md` per release.

### Acceptance criteria

- A 26-billion-point Datashader-rendered timeseries displays in under 5 seconds.
- A 35 GB `SimulationTable` loads via `backend="auto"` using ≤ 2 GB RAM.
- All 15 MCP tools pass integration tests.
- The natural-language-to-dashboard flow described in the GEMS deck works end-to-end with a Claude agent (loads a SimulationTable, attaches a catalog, builds a 3-pane dashboard, exports).
- `pip install antalens[mcp,bigdata]` produces a working server reachable via `python -m antalens.mcp.server`.

### Hand-off to Phase 5

Feature-complete. Phase 5 is hardening, documentation, and the 1.0 release.

---

## Phase 5 — Polish and 1.0 release

**Duration**: 3 weeks
**Tag**: `v1.0.0`
**Goal**: production-ready release with comprehensive documentation and tested deployment paths.

### Deliverables

#### 5.1 Documentation (week 1–2)

- Complete API reference (sphinx autodoc).
- Tutorials in `docs/tutorials/`:
  - "Getting started with AntaLens" (parquet + overview preset).
  - "Exploring a SimulationTable as a scientist" (the `simulation_explorer` preset, then ad-hoc charts).
  - "Authoring a catalog" (component patterns, outputs, palettes, stack templates).
  - "Migrating from antaresViz" (R → Python translations using `antalens.legacy`).
  - "Building a connected GEMS dashboard" (full Lens/link/pipe walkthrough on `Views`).
  - "Using AntaLens with an LLM" (MCP setup + example prompts).
- Cookbook with 10+ recipes.
- Architecture decision records (ADRs) for the major design choices: catalog externalization, DuckDB choice, legacy split, schema discriminator.

#### 5.2 Deployment guides (week 2)

- Reference Dockerfile and `docker-compose.yml` in `docker/`.
- Kubernetes manifest in `deploy/k8s/`.
- A working `helm` chart in `deploy/helm/`.
- Documentation for embedding AntaLens dashboards in existing web applications via iframes.

#### 5.3 Examples gallery (week 2–3)

- `examples/` directory with at least:
  - `simulation_explorer.py` — GEMS scientist workflow.
  - `views_dashboard.py` — Views + adequacy preset.
  - `legacy_antares.py` — using `antalens.legacy` on a pre-GEMS study.
  - `mcp_demo.py` — Claude-driven dashboard build transcript.
  - Four non-energy examples (workforce, sensors, financial, IoT) to validate the generic positioning.

#### 5.4 Release engineering (week 3)

- PyPI release process documented and executed for `v1.0.0`.
- conda-forge package submitted.
- Release notes covering every phase.
- Migration guide from `v0.x` to `v1.0`.
- Public announcement.

### Acceptance criteria

- A new GEMS scientist can go from "I have a SimulationTable parquet" to "I have a deployed dashboard" using only the published documentation in under 30 minutes.
- All examples in the gallery run without modification.
- The Dockerfile builds and the resulting image serves a working dashboard.
- Public API matches `SPEC.md` section 3 exactly — no undocumented public symbols.
- `pip install antalens==1.0.0` succeeds from a fresh PyPI cache.

---

## Cross-cutting concerns

These items run in parallel to all phases.

### Code quality

- Every PR must include tests. New public API requires a snapshot test, a unit test, and an integration test where applicable.
- `mypy --strict` clean is required for merge.
- Public API additions require a corresponding docs entry in the same PR.
- **Domain-vocabulary lint**: no file outside `antalens/legacy/`, `antalens/catalog/`, or `tests/legacy/` may reference ANTARES, eco2mix, or any electricity-specific term. Enforced by a `ruff` custom rule or a CI grep.

### Security

- No telemetry is collected by default.
- Loading an untrusted `SimulationTable`, `Views`, parquet, or catalog file must not allow arbitrary code execution. All loaders use safe parsing (no `pickle`, no `eval`, no shell-out).
- Catalog YAML loading uses `yaml.safe_load`. Component patterns are validated for catastrophic backtracking.
- The MCP server validates every tool input against a Pydantic schema before dispatch.

### Performance

- Every PR that touches a hot path (loaders, plot builders, DuckDB backend, Datashader integration) must include a benchmark result delta in the description.
- Performance regressions > 10% against the previous release are blocking unless explicitly accepted.

### Backwards compatibility

- Once `v1.0.0` ships, breaking changes require a deprecation cycle of at least one minor version.
- Internal-only APIs (anything starting with `_`) may change at any time.
- `antalens.legacy` is feature-frozen at 1.0; only security and compat fixes thereafter.

---

## Risk register

| Risk | Likelihood | Impact | Mitigation | Trigger |
|---|---|---|---|---|
| GEMS SimulationTable schema evolves before 1.0 | Medium | High | Pin to a documented schema version in `gems.md`; isolate parsing in one module; add a migration path note to release docs | Upstream simulator emits incompatible columns |
| Catalog v1 schema proves too rigid for second/third real catalog | Medium | Medium | Design v1 conservatively; treat catalog as Provisional stability until at least three real catalogs exist | Real-world catalog requires features outside the current schema |
| DuckDB-Plotly event integration is harder than expected (events on rasterized data) | Medium | High | Spike in Phase 4 week 1; fallback is a hybrid scatter (raster background + sparse interactive overlay) | Spike fails to wire `xrange_select` to DuckDB-backed pane after 5 days |
| Legacy ANTARES output format changes between simulator versions | Low | Medium | Pin to a specific ANTARES version in `antalens.legacy`; document upgrade path | Upstream releases incompatible format |
| Panel performance regression in linked-pane scenarios | Medium | Medium | Benchmark suite catches early; have Bokeh-direct fallback for critical panes | Render latency > 1 s on tier 1 data |
| MCP protocol changes requiring rework | Medium | Low | Use FastMCP's stable interface; pin major version | FastMCP releases breaking changes |
| Adoption stalls in non-GEMS teams | Medium | High | Phase 5 invests heavily in non-GEMS examples and the `overview` preset; the generic Phase 1 library remains usable on its own | < 3 internal teams using AntaLens 3 months after 1.0 |
| Polars LazyFrame insufficient for 5–10 GB SimulationTable before DuckDB lands | Medium | Medium | Phase 2 explicitly limits SimulationTable testing to ≤ 1 GB files; Phase 4 lands DuckDB before any production deployment is asked to handle full scale | Phase 2 user attempts to load > 5 GB |

---

## Glossary of project terms

- **Phase**: a 3–6 week unit of work producing a tagged release.
- **Deliverable**: a concrete artifact (file, feature, document) committed during a phase.
- **Acceptance criterion**: a binary check that determines whether a phase is complete.
- **Hand-off**: the description of what the next phase inherits from the current one.
- **Tier 1/2/3 data**: rendering volume tiers as defined in `SPEC.md` §6.1.
- **Storage tier**: SimulationTable file-size bucket as defined in `SPEC.md` §6.2.
- **Reference hardware**: 4 vCPU, 16 GB RAM, no GPU. The default benchmark target.
- **Domain-vocabulary lint**: the CI check that prevents domain-specific terms from leaking into the generic core.
