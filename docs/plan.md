# AntaLens — Implementation Plan

> **Companion to**: `SPEC.md`
> **Status**: pre-implementation
> **Format**: phase-based, with concrete deliverables, acceptance criteria, and explicit hand-offs

---

## Overview

The implementation is structured into five phases plus a phase 0 for foundational setup. Each phase is approximately 4–6 weeks and produces a tagged release that is deployable on its own.

```
Phase 0  →  Foundations             (2 weeks)
Phase 1  →  Data layer + plots      (5 weeks)
Phase 2  →  Reactivity + dashboard  (4 weeks)
Phase 3  →  Maps + presets          (4 weeks)
Phase 4  →  Big data + MCP          (5 weeks)
Phase 5  →  Polish + 1.0 release    (3 weeks)
```

Total: ~23 weeks (≈ 6 months) with one full-time engineer. Two engineers can compress this to ~14 weeks by parallelizing phase 1/2 and phase 3/4.

The plan is explicitly designed so that **Phase 1 alone delivers a usable library** for non-ANTARES tabular data. Each subsequent phase widens the surface; none of them gates the previous phase's usefulness.

---

## Phase 0 — Foundations

**Duration**: 2 weeks
**Tag**: `v0.0.1`
**Goal**: project skeleton, CI, no functional code.

### Deliverables

1. Repository structure matching the file tree in the project planning document.
2. `pyproject.toml` with dependency groups (`base`, `[maps]`, `[bigdata]`, `[antares]`, `[mcp]`, `[dev]`).
3. Pre-commit hooks: `ruff check`, `ruff format`, `mypy --strict`.
4. GitHub Actions CI: lint, type-check, test (will pass with zero tests at this stage).
5. Sphinx docs scaffold with autodoc configured against the empty module tree.
6. `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, license file (Apache-2.0 recommended).
7. Issue templates and PR template.
8. Branch protection on `main`: no direct pushes, required CI passing, ≥ 1 review.

### Acceptance criteria

- `pip install -e ".[dev]"` succeeds in a clean Python 3.11 environment on Linux, macOS, and Windows.
- `pytest` runs and reports zero tests (no errors).
- `mypy antalens/` exits cleanly.
- `make docs` produces a published HTML site (locally or on a preview deploy).
- A reviewer can clone the repo, run setup commands from `README.md`, and reach a working dev environment in under 10 minutes.

### Hand-off to Phase 1

The repository contains no logic but every guard rail is in place. New code added in Phase 1 is automatically linted, typed, tested, and documented.

---

## Phase 1 — Data layer and plot builders

**Duration**: 5 weeks
**Tag**: `v0.1.0`
**Goal**: a usable library for tabular time-series visualization. ANTARES support is partial; arbitrary parquet/CSV/SQL data works fully.

### Deliverables

#### 1.1 `Dataset` core (week 1–2)

- `antalens/data/dataset.py` — the `Dataset` class with `filter`, `resample`, `compare`, `pipe`, `to_dataframe`, `to_pandas`, `to_xarray`, `schema`.
- `antalens/data/schema.py` — the `Schema` dataclass and inference logic.
- `antalens/data/loaders.py` — `load_parquet`, `load_csv`, `load_hdf5`, `from_dataframe`, `from_sql`.
- `antalens/data/transforms.py` — internal polars/xarray helpers for resampling, joining, and pivoting.

#### 1.2 ANTARES study loader (week 2–3)

- `antalens/data/antares.py` — `AntaresStudy` class extending `Dataset` with `.areas`, `.links`, `.clusters`, `.mc_years`.
- `antalens/data/antares_io.py` — the actual filesystem reader for ANTARES output folders.
- Variable taxonomy: a hard-coded mapping of ANTARES variables to display names, units, and default aggregations.

#### 1.3 Theme system (week 2)

- `antalens/theme/plotly.py` — `PlotlyTheme` dataclass + `DARK` and `LIGHT` instances.
- `antalens/theme/aliases.py` — `ECO2MIX`, `BASE`, and a public `register_alias()` function.
- `antalens/theme/__init__.py` — `set_active()`, `get_active()`, and config singleton.

#### 1.4 Plot builders (week 3–5)

One file per plot family, each implementing the `BasePlot` ABC:

- `antalens/plots/_base.py` — `BasePlot` abstract class.
- `antalens/plots/timeseries.py` — `TimeSeriesPlot` with confidence intervals and grouping.
- `antalens/plots/stack.py` — `ProductionStack` with template support.
- `antalens/plots/bar.py` — `BarPlot` with sort and orientation.
- `antalens/plots/duration.py` — `DurationCurve` (monotone curve).
- `antalens/plots/heatmap.py` — `HeatmapPlot` with custom colorscales.
- `antalens/plots/distribution.py` — `DistributionPlot` (cdf/kde/box/violin).
- `antalens/plots/scatter.py` — `ScatterPlot` with optional trendline.

#### 1.5 Plot accessor (week 4)

- `antalens/data/accessors.py` — the `PlotAccessor` class wired to `Dataset.plot`.
- Auto-detection logic for inferring `time_col`, `categorical_cols`, etc. from the bound dataset's schema.

### Acceptance criteria

- A 5-line script loads a parquet file and produces a working timeseries plot:
  ```python
  import antalens as al
  ds = al.io.load_parquet("data.parquet")
  pane = ds.plot.timeseries("value")
  pane.show()  # opens in browser
  ```
- All 7 plot types render correctly with the mock dataset fixture.
- Snapshot tests pass for every plot type — committed Plotly JSON specs match generated output (modulo timestamps).
- An ANTARES study folder loads via `load_antares()` and `study.areas` returns the expected list.
- `study.plot.stack(template="eco2mix")` produces a chart visually equivalent to the antaresViz reference (manual review).
- Type coverage on the public API is 100% — `mypy --strict` clean on every method signature in section 3 of `SPEC.md`.

### Hand-off to Phase 2

Plot builders return Plotly figures wrapped in plain Panel panes. They do not yet react to external state changes. Phase 2 adds the reactive layer.

---

## Phase 2 — Reactivity and dashboard composition

**Duration**: 4 weeks
**Tag**: `v0.2.0`
**Goal**: connected dashboards via shared `Lens`, `link()`, and `pipe()`.

### Deliverables

#### 2.1 `Lens` (week 1)

- `antalens/lens.py` — `Lens` base class with `area`, `dates`, `variable`, `mc` parameters.
- `Lens.with_extras()` factory for domain-specific extensions.
- Serialization to/from JSON via Param's built-ins.

#### 2.2 Reactive `filter()` (week 1–2)

- Modify `Dataset.filter()` to accept `Lens` instances or individual `param.Parameter` references.
- Internal: when a `Lens` is bound, filter results are produced via `pn.bind()` so they re-evaluate on parameter change.
- Test: a `Dataset` filtered with a `Lens` and rendered as a pane updates within 500 ms when the lens mutates.

#### 2.3 `link()` (week 2)

- `antalens/link.py` — the `link()` function.
- Per-pane event registration: each plot builder declares which Plotly events it exposes (`xrange_select`, `point_click`, etc.).
- Implementation strategy: register a `clientData` callback on the Plotly pane, parse the event payload, and assign to the target `param.Parameter`.

#### 2.4 `pipe()` (week 2–3)

- `antalens/pipe.py` — `PipeNode` class + `pipe()` constructor.
- Shared transform memoization: a `PipeNode` caches its filtered result and exposes it to all downstream chains.
- `PipeNode.join_on(time_col)` for cross-dataset joins.

#### 2.5 `Dashboard` (week 3–4)

- `antalens/dash/dashboard.py` — `Dashboard` class with `add`, `remove`, `serve`, `save`, `to_html`, `to_notebook`, `to_json`, `from_json`.
- Internal use of Panel's `GridSpec` for layout.
- `to_json` / `from_json` round-trip — every pane is serialized to a `{type, params, position}` triple.

#### 2.6 Controls (week 3)

- `antalens/controls.py` — `AreaSelector`, `DateRangeSelector`, `VariablePicker`, `MCSelector`.
- Each control is a thin wrapper around a Panel widget that mutates a specific `Lens` parameter.

### Acceptance criteria

- The "click a node, all charts update" use case from the planning document runs end-to-end against the mock study.
- `Dashboard.to_json()` followed by `Dashboard.from_json()` produces a visually identical dashboard.
- Linked event propagation latency is under 100 ms (measured with a benchmark in `tests/perf/`).
- `Dashboard.save("out.html")` produces a self-contained HTML file that displays all panes (interactivity will be partial; full interactivity requires `serve()`).
- All four use-case examples from the planning document execute without modification.

### Hand-off to Phase 3

The library now supports connected dashboards on tabular data. Maps are not yet available; the `ds.map.*` namespace raises `NotImplementedError`.

---

## Phase 3 — Maps and presets

**Duration**: 4 weeks
**Tag**: `v0.3.0`
**Goal**: full geo/network map layer + ready-to-use dashboard presets.

### Deliverables

#### 3.1 `MapLayout` (week 1)

- `antalens/maps/layout.py` — `MapLayout` dataclass with `to_json`, `from_json`, `auto`.
- `MapLayout.auto(study)` uses a built-in country-name → centroid lookup table for ANTARES studies.

#### 3.2 PyDeck-backed map builders (week 1–2)

- `antalens/maps/network.py` — `NetworkMap` with ScatterplotLayer (nodes) + ArcLayer (links).
- `antalens/maps/choropleth.py` — `ChoroplethMap` with GeoJsonLayer.
- `antalens/maps/flow.py` — `FlowMap` for animated flow visualization.

#### 3.3 Layout editor (week 2–3)

- `antalens/maps/layout_editor.py` — Panel-based interactive editor.
- Drag-and-drop nodes onto a base map; save/load from JSON.
- Implementation: ipyleaflet for the editing surface (better drag UX than PyDeck), then convert the result to a `MapLayout` for use with PyDeck-backed visualization.

#### 3.4 Dashboard presets (week 3–4)

- `antalens/dash/presets/overview.py` — generic 4-panel dashboard for any `Dataset`.
- `antalens/dash/presets/adequacy.py` — ANTARES adequacy preset (LOLD heatmap, balance map, ENS distribution, prodstack).
- `antalens/dash/presets/exchanges.py` — ANTARES exchanges preset (exchange stack, flow map, hourly imports/exports).

### Acceptance criteria

- `study.map.network(layout, node_color="BALANCE")` produces a working PyDeck map with the correct color encoding.
- The layout editor opens in Jupyter, allows drag-and-drop, and persists to JSON.
- `al.dash.overview(al.io.load_parquet("any.parquet")).serve()` produces a useful dashboard with no further configuration.
- All three ANTARES presets visually match the antaresViz reference for the same study (manual review).
- The `[maps]` extra is correctly gated — `import antalens.maps` without pydeck installed raises a clear `ImportError`.

### Hand-off to Phase 4

The library now has full visualization parity with antaresViz. Phase 4 adds the scale (Datashader) and AI integration (MCP) layers.

---

## Phase 4 — Big data and MCP

**Duration**: 5 weeks
**Tag**: `v0.4.0`
**Goal**: handle full Monte Carlo datasets and expose the library to LLM agents via MCP.

### Deliverables

#### 4.1 Datashader integration (week 1–2)

- `antalens/plots/_datashader.py` — internal helpers for converting a points DataFrame to a Datashader-rasterized PNG.
- Auto-switching logic in `TimeSeriesPlot`, `HeatmapPlot`, `ScatterPlot`: when `len(data) > threshold`, route through Datashader.
- Datashader-rasterized panes still expose the same events (`xrange_select`, etc.) by tracking the data extent.

#### 4.2 Dask integration (week 2)

- xarray-backed `Dataset` instances support Dask-chunked data transparently.
- `load_antares()` with `mc_years="all"` produces a Dask-backed xarray where each MC year is a chunk.
- Bench: rendering a 30-MC × 8760h × 100-area scatter must complete in under 5 seconds on the reference hardware.

#### 4.3 FastMCP server (week 3)

- `antalens/mcp/server.py` — FastMCP application.
- `antalens/mcp/session.py` — `Session` class holding datasets, dashboard, and lens.
- `antalens/mcp/tools.py` — all 12 tool wrappers from `SPEC.md` section 5.1.
- `antalens/mcp/converters.py` — Panel pane → MCP-safe response conversion.

#### 4.4 MCP integration tests (week 4)

- `tests/integration/test_mcp.py` — end-to-end test for each tool.
- Mock LLM transcript: a sequence of tool calls that builds, modifies, and exports a dashboard.

#### 4.5 Performance benchmarks (week 4–5)

- `tests/perf/bench_render.py` — measures render latency at each data tier.
- `tests/perf/bench_mcp.py` — measures end-to-end latency from MCP call to dashboard update.
- Results published in `docs/performance.md` per release.

### Acceptance criteria

- A 26-billion-point Datashader-rendered timeseries displays in under 5 seconds.
- All 12 MCP tools pass integration tests.
- The natural-language-to-dashboard flow described in the proposal slide deck works end-to-end with a Claude agent.
- Memory usage during full-MC rendering stays under 8 GB on the reference hardware.
- `pip install antalens[mcp]` produces a working MCP server reachable via `python -m antalens.mcp.server`.

### Hand-off to Phase 5

The library is feature-complete. Phase 5 is hardening, documentation, and the 1.0 release.

---

## Phase 5 — Polish and 1.0 release

**Duration**: 3 weeks
**Tag**: `v1.0.0`
**Goal**: production-ready release with comprehensive documentation and tested deployment paths.

### Deliverables

#### 5.1 Documentation (week 1–2)

- Complete API reference (sphinx autodoc) for every public symbol.
- Tutorials in `docs/tutorials/`:
  - "Getting started with AntaLens" (5 min, parquet + overview preset)
  - "Migrating from antaresViz" (15 min, side-by-side R → Python translations)
  - "Building a connected dashboard" (20 min, full Lens/link/pipe walkthrough)
  - "Using AntaLens with an LLM" (10 min, MCP setup + example prompts)
- Cookbook with 10+ recipes addressing common questions.
- Architecture decision records (ADRs) for the five major design choices.

#### 5.2 Deployment guides (week 2)

- Reference Dockerfile and `docker-compose.yml` in `docker/`.
- Kubernetes manifest in `deploy/k8s/`.
- A working `helm` chart in `deploy/helm/`.
- Documentation for embedding AntaLens dashboards in existing web applications via iframes.

#### 5.3 Examples gallery (week 2–3)

- `examples/` directory with 8 fully working examples corresponding to the four use cases from the planning document plus four additional ones (workforce analytics, sensor monitoring, financial time series, IoT telemetry).

#### 5.4 Release engineering (week 3)

- PyPI release process documented and executed for `v1.0.0`.
- conda-forge package submitted.
- Release notes covering every phase.
- Migration guide from `v0.x` to `v1.0` (should be empty if SemVer was respected).
- Public announcement on internal communication channels and external blog post.

### Acceptance criteria

- A new user can go from "I have a parquet file" to "I have a deployed dashboard" using only the published documentation in under 30 minutes.
- All examples in the gallery run without modification.
- The Dockerfile builds and the resulting image serves a working dashboard.
- Public API matches `SPEC.md` section 3 exactly — no undocumented public symbols.
- `pip install antalens==1.0.0` succeeds from a fresh PyPI cache.

---

## Cross-cutting concerns

These items run in parallel to all phases and are owned by every contributor.

### Code quality

- Every PR must include tests. New public API requires a snapshot test, a unit test, and an integration test where applicable.
- `mypy --strict` clean is required for merge.
- Public API additions require a corresponding docs entry in the same PR.

### Security

- No telemetry is collected by default. If telemetry is added, it requires explicit opt-in.
- Loading an untrusted ANTARES study or parquet file must not allow arbitrary code execution. All loaders use safe parsing (no `pickle`, no `eval`, no shell-out).
- The MCP server validates every tool input against a Pydantic schema before dispatch.

### Performance

- Every PR that touches a hot path (loaders, plot builders, Datashader integration) must include a benchmark result delta in the description.
- Performance regressions > 10% against the previous release are blocking unless explicitly accepted.

### Backwards compatibility

- Once `v1.0.0` ships, breaking changes require a deprecation cycle of at least one minor version.
- Internal-only APIs (anything starting with `_`) may change at any time.

---

## Risk register

The following risks are tracked throughout implementation. Each has an owner, a mitigation, and a trigger condition that escalates to the project lead.

| Risk | Likelihood | Impact | Mitigation | Trigger |
|---|---|---|---|---|
| Datashader-Plotly event integration is harder than expected | Medium | High | Spike in Phase 4 week 1; fallback is a hybrid scatter (raster background + sparse interactive overlay) | Spike fails to wire `xrange_select` events to Datashader-backed pane after 5 days |
| ANTARES output format changes between versions | Low | Medium | Pin to a specific ANTARES version; document upgrade path | Upstream releases incompatible format |
| Panel performance regression in linked-pane scenarios | Medium | Medium | Benchmark suite catches early; have Bokeh-direct fallback for critical panes | Render latency > 1 s on tier 1 data |
| MCP protocol changes requiring rework | Medium | Low | Use FastMCP's stable interface; pin major version | FastMCP releases breaking changes |
| Adoption stalls in non-ANTARES teams | Medium | High | Phase 5 invests heavily in non-ANTARES examples and the `overview` preset | < 3 internal teams using AntaLens 3 months after 1.0 |

---

## Glossary of project terms

- **Phase**: a 3–5 week unit of work producing a tagged release.
- **Deliverable**: a concrete artifact (file, feature, document) committed during a phase.
- **Acceptance criterion**: a binary check that determines whether a phase is complete.
- **Hand-off**: the description of what the next phase inherits from the current one.
- **Tier 1/2/3 data**: rendering volume tiers as defined in `SPEC.md` section 6.1.
- **Reference hardware**: 4 vCPU, 16 GB RAM, no GPU. The default benchmark target.
