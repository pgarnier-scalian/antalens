# AntaLens — Technical Specification

> **Version**: 0.1.0-draft
> **Status**: pre-implementation
> **Audience**: implementing engineers, technical reviewers, downstream library authors

---

## 1. Purpose and scope

### 1.1 Goals

AntaLens is a Python visualization engine designed to:

1. Replace the R `antaresViz` package with full feature parity for ANTARES power-system simulation outputs.
2. Generalize beyond ANTARES to serve as the organization-wide standard for interactive scientific dashboards on tabular and multi-dimensional time-series data.
3. Expose a programmatic, composable API that enables MCP-driven dashboard generation by an LLM agent.
4. Handle Monte Carlo datasets at full scale (30 years × 8760 hours × 100+ entities) without browser-side rendering bottlenecks.

### 1.2 Non-goals

- AntaLens is not a general-purpose plotting grammar (no Vega/Altair-style declarative spec language). It is an opinionated, domain-aware engine.
- It does not replace dedicated GIS tooling (no full-feature spatial analysis — only network/choropleth visualization).
- It is not a real-time streaming framework. The reactivity model assumes datasets that change on user interaction, not at sub-second rates.
- It does not embed authentication, RBAC, or multi-tenancy. Those concerns live in the deployment layer (Panel server, reverse proxy, Anthropic-hosted services).

### 1.3 Audience

The library serves two distinct user groups whose needs the API must satisfy simultaneously:

- **ANTARES analysts** at RTE replacing existing R workflows. They expect production stacks, exchange stacks, and network maps with familiar semantics.
- **Data analysts and engineers in other organizational units** working with parquet files, CSV exports, SQL databases, or in-memory DataFrames. They have no power-systems context and need the API to feel natural for arbitrary tabular time series.

Both groups must be able to use AntaLens without special configuration. ANTARES-specific concepts (production aliases, MC year selection) must be available but never imposed.

---

## 2. Architecture overview

### 2.1 Layered design

AntaLens is structured into five layers. Each layer depends only on layers below it. There are no upward dependencies.

```
┌──────────────────────────────────────────────────────────┐
│  MCP layer       — FastMCP tool wrappers                 │
├──────────────────────────────────────────────────────────┤
│  Dashboard layer — Panel GridSpec, Lens, link(), pipe()  │
├──────────────────────────────────────────────────────────┤
│  Reactivity      — Param + pn.bind                       │
├──────────────────────────────────────────────────────────┤
│  Rendering       — Plotly · Datashader · PyDeck          │
├──────────────────────────────────────────────────────────┤
│  Data layer      — Dataset, AntaresStudy, polars/xarray  │
└──────────────────────────────────────────────────────────┘
```

### 2.2 Core abstractions

Five objects form the conceptual core. All other types in the library either produce, consume, or wrap one of these.

**`Dataset`** — the universal data container. Wraps a polars DataFrame (for 2D tabular data) and/or an xarray Dataset (for multi-dimensional MC time series). Exposes the fluent chain methods: `filter`, `resample`, `compare`, `pipe`, `to_dataframe`, `to_xarray`. All plot and map builders are accessible as namespaced attributes (`ds.plot.timeseries`, `ds.map.network`).

**`AntaresStudy`** — a `Dataset` subclass that adds ANTARES-specific knowledge: areas, links, clusters, MC metadata, output variable taxonomy. Returned by `antalens.io.load_antares()`. All methods of `Dataset` work identically on `AntaresStudy`; the subclass adds specialized accessors (`study.areas`, `study.links`, `study.mc_years`).

**`Lens`** — a `param.Parameterized` subclass holding mutable shared state for a connected dashboard. Plot builders consume a `Lens` via `ds.filter(lens)` and re-render when any watched parameter changes. The `Lens` is what turns isolated panes into a connected dashboard.

**`Pane`** — the rendered output of any plot or map builder. Wraps a Plotly `Figure`, a PyDeck `Deck`, or a Datashader `Image` in a `panel.pane.*` object. Panes are composable into `Dashboard` objects and serializable to HTML.

**`Dashboard`** — a Panel `GridSpec`-backed container that holds panes, controls, and a `Lens`. Owns the methods `add`, `remove`, `serve`, `save`, `to_html`, and the serialization round-trip via `to_json` / `from_json`.

### 2.3 Data flow

A typical request flows top-to-bottom and back:

```
User interaction (click, brush, widget change)
    ↓
Panel callback fires
    ↓
Lens parameter mutates (via param.watch)
    ↓
All panes bound via ds.filter(lens) re-execute
    ↓
Dataset transforms run (polars/xarray, lazy where possible)
    ↓
Plot builder constructs new Plotly Figure / PyDeck Deck
    ↓
Pane updates in-place (no full DOM rebuild)
    ↓
Browser receives diff, re-renders affected panes only
```

Datashader-backed panes follow the same flow but the rendering happens server-side: the `Dataset` transform produces a points DataFrame, Datashader rasterizes to a NumPy array, and only the resulting PNG bytes cross the wire.

---

## 3. Public API

### 3.1 Top-level namespace

The public surface of `import antalens as al` consists of exactly these symbols:

| Symbol | Type | Purpose |
|---|---|---|
| `al.io` | module | data loaders |
| `al.plot` | module | standalone plot builders (mirrors `Dataset.plot`) |
| `al.map` | module | map builders + layout editor |
| `al.dash` | module | `Dashboard` class and presets |
| `al.controls` | module | reactive widget primitives |
| `al.Lens` | class | shared reactive state container |
| `al.Dataset` | class | universal data container |
| `al.AntaresStudy` | class | ANTARES-aware `Dataset` subclass |
| `al.link` | function | wires a pane event to a `Lens` parameter |
| `al.pipe` | function | shared transform node for cross-dataset composition |
| `al.theme` | module | colors, layouts, alias dictionaries |

Anything else is considered internal and may change without notice.

### 3.2 `antalens.io` — loaders

All loaders return either a `Dataset` or an `AntaresStudy`. Loaders are pure functions; they never mutate filesystem state.

```python
io.load_parquet(path: str | Path | list[Path], **kw) -> Dataset
io.load_csv(path: str | Path, parse_dates: bool | list[str] = True, **kw) -> Dataset
io.load_hdf5(path: str | Path, key: str | None = None) -> Dataset
io.load_antares(path: str | Path, mc_years: list[int] | None = None) -> AntaresStudy
io.from_dataframe(df: pl.DataFrame | pd.DataFrame | xr.Dataset, time_col: str | None = None) -> Dataset
io.from_sql(query: str, con: Connection | str, **kw) -> Dataset
```

**Schema inference contract**: each loader inspects column types and infers:
- The time column (any `datetime`/`date` dtype, or columns named `time`, `timestamp`, `date`, `valid_time`).
- Categorical dimensions (any `string`/`categorical` dtype with cardinality < 200).
- Numeric variables (everything else with a numeric dtype).

The inferred schema is stored on the `Dataset` and exposed via `ds.schema()`. Users can override inference by passing explicit kwargs.

### 3.3 `Dataset` — fluent chain

`Dataset` exposes the following public methods. Every method that returns a `Dataset` returns a new instance — `Dataset` is immutable from the user's perspective.

```python
class Dataset:
    # ── chain methods ───────────────────────────────────────
    def filter(self, *,
               area: str | list[str] | None = None,
               variable: str | list[str] | None = None,
               date_range: tuple[date, date] | Lens | None = None,
               **kw) -> Dataset: ...

    def resample(self, freq: str, agg: str | dict[str, str] = "mean") -> Dataset: ...

    def compare(self, other: Dataset, *,
                label_a: str = "A", label_b: str = "B") -> ComparedDataset: ...

    def pipe(self, fn: Callable[[Dataset], Dataset]) -> Dataset: ...

    # ── escape hatches ──────────────────────────────────────
    def to_dataframe(self) -> pl.DataFrame: ...
    def to_pandas(self) -> pd.DataFrame: ...
    def to_xarray(self) -> xr.Dataset: ...
    def schema(self) -> Schema: ...

    # ── plot/map namespaces ─────────────────────────────────
    @property
    def plot(self) -> PlotAccessor: ...
    @property
    def map(self) -> MapAccessor: ...
```

**Filter semantics**: `filter()` arguments are AND-combined. Passing `None` for an argument means "no constraint on this dimension". Passing a `Lens` for `date_range` (or any other supported argument) makes the filter reactive — the resulting `Dataset` is bound to the lens and re-evaluates on parameter change.

**Resample frequencies**: `freq` accepts pandas/polars-compatible strings: `"1h"`, `"1d"`, `"1w"`, `"1mo"`, `"1y"`. The `agg` argument is either a single function name applied to all numeric columns, or a dict mapping column names to functions.

**Comparison contract**: `compare()` returns a `ComparedDataset` (subclass of `Dataset`) where every plot method automatically renders both series with consistent styling — solid for A, dashed for B, distinct color scales for each.

### 3.4 `Dataset.plot` — chart builders

All plot methods return a `Pane`. The pane is a Panel object that can be displayed in a notebook, added to a `Dashboard`, or exported.

```python
plot.timeseries(y: str | list[str], *,
                conf_int: float | None = None,
                by: str | None = None,
                cumulative: bool = False) -> Pane

plot.stack(template: str | dict[str, str] = "eco2mix", *,
           load: str | None = None,
           negative: list[str] | None = None) -> Pane

plot.bar(x: str, y: str, *,
         sort: Literal["asc", "desc"] | None = None,
         orientation: Literal["v", "h"] = "v") -> Pane

plot.duration(y: str, *,
              normalize: bool = False) -> Pane

plot.heatmap(x: str, y: str, z: str, *,
             colorscale: str = "antalens",
             aggfunc: str = "mean") -> Pane

plot.distribution(y: str, *,
                  kind: Literal["cdf", "kde", "box", "violin"] = "cdf",
                  by: str | None = None) -> Pane

plot.scatter(x: str, y: str, *,
             color: str | None = None,
             size: str | None = None,
             trendline: Literal["ols", "lowess"] | None = None) -> Pane
```

**Auto-detection**: when called on a `Dataset` with a clear schema, every parameter except the data variable is optional. `ds.plot.timeseries("LOAD")` works without specifying the time column — it's inferred from `ds.schema().time_col`.

**Big data handling**: when the underlying data exceeds 50,000 points after filtering, `plot.timeseries`, `plot.heatmap`, and `plot.scatter` automatically switch to Datashader-backed rendering. This is transparent to the caller. The threshold is configurable via `al.theme.config.datashader_threshold`.

### 3.5 `Dataset.map` — geo/network builders

```python
map.network(layout: MapLayout, *,
            node_color: str | None = None,
            node_size: str | None = None,
            link_width: str | None = None,
            link_color: str | None = None) -> Pane

map.choropleth(geojson: dict | Path, *,
               value_col: str,
               key_col: str = "id",
               colorscale: str = "antalens") -> Pane

map.flow(layout: MapLayout, *,
         flow_var: str,
         arc_height: float = 0.4) -> Pane
```

The `map` namespace is part of the optional `[maps]` install extra. Importing it without `pydeck` installed raises `ImportError` with installation guidance.

### 3.6 `Lens` — reactive shared state

```python
class Lens(param.Parameterized):
    """Shared mutable state for a connected dashboard."""

    area     = param.String(default=None, allow_None=True)
    dates    = param.DateRange(default=None, allow_None=True)
    variable = param.String(default=None, allow_None=True)
    mc       = param.String(default="mean")

    @classmethod
    def with_extras(cls, **extras) -> type[Lens]:
        """Create a Lens subclass with additional parameters."""
        ...
```

The base `Lens` covers the four most common dimensions in ANTARES and time-series workflows. For domain-specific extensions:

```python
HRLens = Lens.with_extras(
    department=param.String(default=None),
    seniority_level=param.String(default=None),
)
lens = HRLens()
```

### 3.7 `link()` and `pipe()`

```python
link(pane: Pane, *,
     on: str,
     set: param.Parameter,
     transform: Callable | None = None) -> None
```

Wires a pane event to a `Lens` parameter. Supported event names per pane type:

| Pane type | Events |
|---|---|
| timeseries | `xrange_select`, `point_click`, `legend_click` |
| stack | `xrange_select`, `legend_click` |
| heatmap | `cell_click`, `xrange_select`, `yrange_select` |
| bar | `bar_click` |
| scatter | `point_click`, `box_select`, `lasso_select` |
| network | `node_click`, `link_click` |
| choropleth | `region_click` |

```python
pipe(*datasets: Dataset, **named_datasets: Dataset) -> PipeNode
```

Creates a shared transform node. Downstream chains share the recomputation: filtering `pipe.filter(lens)` once causes both linked chains to re-render. Returns a `PipeNode` that supports `__getitem__` (for named access) and `.join_on(time_col)` for cross-dataset joins.

### 3.8 `Dashboard` — composition shell

```python
class Dashboard:
    def __init__(self, title: str, *,
                 theme: Literal["dark", "light"] = "dark",
                 lens: Lens | None = None): ...

    def add(self, pane: Pane, *,
            row: int, col: int,
            rowspan: int = 1, colspan: int = 1,
            id: str | None = None) -> str: ...

    def remove(self, id: str) -> None: ...

    def serve(self, *, port: int = 5006, address: str = "localhost",
              threaded: bool = False) -> None: ...

    def save(self, path: str | Path, *,
             embed_data: bool = True) -> None: ...

    def to_html(self) -> str: ...
    def to_notebook(self) -> "panel.viewable.Viewable": ...

    def to_json(self) -> dict: ...
    @classmethod
    def from_json(cls, spec: dict, *, datasets: dict[str, Dataset]) -> Dashboard: ...
```

Pane IDs returned by `add()` are stable identifiers usable by the MCP layer to subsequently modify or remove panes.

### 3.9 `antalens.dash` — presets

```python
dash.overview(ds: Dataset, *, lens: Lens | None = None) -> Dashboard
dash.adequacy(study: AntaresStudy, *, lens: Lens | None = None) -> Dashboard
dash.exchanges(study: AntaresStudy, *, lens: Lens | None = None) -> Dashboard
```

Each preset returns a fully-composed `Dashboard` ready to `.serve()`. Presets are the entry point for new users — `al.dash.overview(al.io.load_parquet("file.parquet")).serve()` should produce a useful dashboard with zero configuration.

---

## 4. Internal contracts

### 4.1 Plot builder protocol

Every plot builder implements the internal `BasePlot` ABC:

```python
class BasePlot(abc.ABC):
    def __init__(self, dataset: Dataset, **params: Any): ...

    @abc.abstractmethod
    def build(self) -> plotly.graph_objects.Figure | pydeck.Deck: ...

    def to_pane(self) -> panel.viewable.Viewable: ...
    def apply_theme(self, fig: Figure) -> Figure: ...
    def schema_check(self) -> None: ...
```

`to_pane()` is the only method called by external code. `build()` is called once per render and must be deterministic for a given dataset+params combination.

### 4.2 Theme contract

Every Plotly figure produced by AntaLens must pass through `apply_theme()` before being wrapped in a pane. The theme is a single dataclass:

```python
@dataclass
class PlotlyTheme:
    paper_bgcolor: str
    plot_bgcolor: str
    font_family: str
    font_color: str
    grid_color: str
    line_color: str
    palette_categorical: list[str]
    palette_continuous: list[tuple[float, str]]
    margin: dict[str, int]
```

Two themes ship with the library: `theme.DARK` and `theme.LIGHT`. Users override via `al.theme.set_active(my_theme)`.

### 4.3 Schema object

```python
@dataclass(frozen=True)
class Schema:
    time_col: str | None
    categorical_cols: dict[str, list[str]]   # {col: distinct_values}
    numeric_cols: list[str]
    geo_cols: list[str] | None               # cols holding lat/lon or area IDs
    ndim: int                                # 2 (table) or 3+ (xarray)

    def has(self, col: str) -> bool: ...
    def kind_of(self, col: str) -> Literal["time", "categorical", "numeric", "geo"]: ...
```

### 4.4 MapLayout

```python
@dataclass
class MapLayout:
    nodes: dict[str, NodePosition]      # {area_id: (lat, lon)}
    links: list[tuple[str, str]]        # [(area_a, area_b), …]
    metadata: dict[str, Any]            # arbitrary user fields

    def to_json(self) -> str: ...
    @classmethod
    def from_json(cls, s: str) -> MapLayout: ...
    @classmethod
    def auto(cls, study: AntaresStudy) -> MapLayout: ...   # geocode by area name
```

---

## 5. MCP integration

### 5.1 Tool surface

The MCP server (`antalens.mcp.server`) exposes exactly these tools to LLM agents:

| Tool name | Returns | Purpose |
|---|---|---|
| `load_study` | study_id (string) | register an AntaresStudy with the session |
| `load_dataset` | dataset_id (string) | register a generic Dataset |
| `add_timeseries` | pane_id | append a timeseries pane to the active dashboard |
| `add_stack` | pane_id | append a production stack pane |
| `add_map` | pane_id | append a network or choropleth map |
| `add_heatmap` | pane_id | append a heatmap |
| `add_distribution` | pane_id | append a CDF/KDE/box plot |
| `set_filter` | (success) | mutate the active Lens |
| `compare_studies` | pane_id | overlay two studies on a single pane |
| `remove_pane` | (success) | remove a pane by ID |
| `export_dashboard` | path | save the current dashboard to HTML or PNG |
| `describe_dashboard` | dict | introspect the current dashboard's structure |

### 5.2 Session model

The MCP server holds one `Session` per connected client. A `Session` contains:
- A registry of loaded datasets keyed by `dataset_id`.
- A single active `Dashboard` instance.
- A single active `Lens` shared across all panes in the dashboard.

The session is in-memory and not persisted between connections. For persistence, the LLM is expected to call `export_dashboard` and `Dashboard.from_json` on subsequent connections.

### 5.3 Tool-to-API mapping

Each MCP tool is a thin wrapper. Example:

```python
@mcp.tool()
async def add_timeseries(
    session: Session,
    dataset_id: str,
    y: str,
    conf_int: float | None = None,
) -> str:
    ds = session.datasets[dataset_id]
    pane = ds.filter(session.lens).plot.timeseries(y, conf_int=conf_int)
    return session.dashboard.add(pane, row=session.next_row(), col=0)
```

No business logic lives in the MCP layer. Every tool is ≤ 10 lines.

---

## 6. Performance requirements

### 6.1 Rendering tiers

| Data volume after filtering | Rendering path | Target latency |
|---|---|---|
| < 50 000 points | Plotly WebGL in browser | < 200 ms |
| 50 000 – 10 000 000 points | Datashader server-side rasterization | < 1 500 ms |
| > 10 000 000 points | Datashader + Dask out-of-core | < 5 000 ms |

The Datashader threshold is tuned for typical hardware (4 vCPU, 16 GB RAM). It is configurable.

### 6.2 Memory ceilings

- A single `Dataset` instance must not eagerly materialize more than 4 GB of data. Larger datasets are held as polars `LazyFrame` or xarray-backed Dask arrays.
- Loading an ANTARES study with default parameters (synthetic MC results only) must use ≤ 2 GB regardless of study size. Per-MC-year data is loaded on demand.

### 6.3 Reactivity latency

- A `Lens` parameter change must result in pane re-rendering within 500 ms for datasets in tier 1, and within 2 000 ms for tier 2.
- Linked event propagation (e.g. `link(map, on="node_click", set=lens.area)`) must complete in under 100 ms exclusive of pane re-render.

---

## 7. Compatibility and dependencies

### 7.1 Python version

AntaLens supports Python 3.11 and later. This is non-negotiable: the codebase relies on PEP 695 type aliases, `Self` types, and `dataclass(slots=True)` performance characteristics.

### 7.2 Hard dependencies

The base install pulls only:

```
polars>=0.20
pandas>=2.0
xarray>=2024.1
plotly>=5.18
panel>=1.4
param>=2.0
holoviews>=1.18
hvplot>=0.9
numpy>=1.24
```

### 7.3 Optional extras

```
[maps]        — pydeck>=0.9
[bigdata]     — datashader>=0.16, dask>=2024.1
[antares]     — h5py>=3.10, PyYAML>=6.0
[mcp]         — fastmcp>=0.2
[dev]         — pytest, pytest-cov, ruff, mypy, jupyterlab
[all]         — everything above
```

The base install must produce a working library for tabular CSV/parquet workflows without any optional extras.

### 7.4 Deployment targets

- Standalone Panel server (`dashboard.serve()`) — supported.
- Embedded in a Jupyter notebook (`dashboard.to_notebook()`) — supported.
- Static HTML export (`dashboard.save("out.html")`) — supported, with the caveat that linked interactivity requires a running Panel server.
- Docker container — Dockerfile shipped in `docker/` for reference deployments.

---

## 8. Testing requirements

### 8.1 Coverage targets

- Unit tests: ≥ 85% line coverage on `antalens/` excluding `mcp/` and `dash/presets.py`.
- Integration tests: every MCP tool exercised end-to-end with a mock study.
- Visual regression: `plot/*` builders compared against committed Plotly JSON snapshots (assertions on trace structure, not pixel comparison).

### 8.2 Mock study fixture

A pytest fixture `mock_study` in `tests/conftest.py` produces a deterministic `AntaresStudy` with:
- 5 areas (FR, DE, ES, IT, BE)
- 6 links (full mesh minus 4)
- 1 year of hourly data (8760 timesteps)
- 5 MC years
- All standard ANTARES output variables (LOAD, BALANCE, MRG. PRICE, NUCLEAR, WIND, SOLAR, GAS, etc.)

The fixture uses a fixed seed; output is byte-identical across runs.

### 8.3 Continuous integration

GitHub Actions workflow runs on every PR:
1. `ruff check` and `ruff format --check`
2. `mypy antalens/`
3. `pytest tests/ -v --cov=antalens --cov-fail-under=85`
4. `pytest tests/integration/ -v` (only on PRs labelled `integration`)
5. Build sphinx docs (warnings fail the build)

---

## 9. Versioning and stability

### 9.1 Semantic versioning

AntaLens follows SemVer. The public API as defined in section 3 is the contract. Anything imported via `import antalens as al; al.X` is public; anything else is internal.

### 9.2 Stability levels

| Level | Symbols | Stability commitment |
|---|---|---|
| Stable | All of section 3 except `al.controls` | No breaking changes within a major version |
| Provisional | `al.controls` | May change within minor versions, with deprecation warnings |
| Internal | Anything starting with `_` or under `antalens._internal` | No stability guarantee |

### 9.3 Deprecation policy

A symbol marked deprecated emits a `DeprecationWarning` for at least one minor version before removal. Deprecation notices include the recommended replacement and the version in which removal is scheduled.

---

## 10. Open questions and design decisions deferred

The following items are explicitly deferred to implementation and documented here for visibility:

1. **Datashader/Plotly handoff threshold** — the 50 000 point threshold is a reasoned default but should be benchmarked on real ANTARES datasets in Phase 1 and adjusted.
2. **`Lens` serialization format** — Param's built-in serialization is sufficient for v0.1; revisit if MCP demands richer schemas (e.g. parameter constraints, conditional dependencies).
3. **Multi-user dashboard sharing** — out of scope for v0.1. If demand emerges, evaluate Panel's session-level state vs. process-level shared state.
4. **WebAssembly export** — Panel supports PyScript-based static export. Not promised for v0.1; evaluate in Phase 3.
5. **Custom theme authoring UI** — `theme.PlotlyTheme` is editable in code; a GUI theme editor is a Phase 4 candidate.

---

## Appendix A — glossary

- **ANTARES**: open-source power-system simulator developed by RTE. Produces hourly time series for areas, links, and clusters across multiple Monte Carlo (MC) years.
- **Area**: a market zone in an ANTARES study (typically a country or sub-region).
- **Link**: a directional interconnection between two areas.
- **Cluster**: a thermal generation unit grouping within an area.
- **MC year**: one independent stochastic realization of a Monte Carlo simulation.
- **eco2mix**: a French TSO standard for production-stack visualization (specific fuel ordering and color mapping).
- **LOLD**: Loss Of Load Duration — number of hours per year where demand exceeds available generation.
- **ENS**: Energy Not Served — total unserved energy in MWh.
- **Pane**: a single rendered visual unit (chart, map, table) within a dashboard.
- **Lens**: AntaLens's reactive shared-state container; the bridge that turns isolated panes into a connected dashboard.
