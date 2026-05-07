# AntaLens — Technical Specification

> **Version**: 0.2.0-draft
> **Status**: pre-implementation (post-GEMS reframe)
> **Audience**: implementing engineers, technical reviewers, downstream library authors
> **Companion**: `gems.md` for the GEMS data model AntaLens consumes.

---

## 1. Purpose and scope

### 1.1 Goals

AntaLens is a Python visualization engine designed to:

1. Serve as the visualization front-end for **GEMS** (Generic Energy Systems Modelling Scheme), reading both raw `SimulationTable` outputs and curated `Views` (see `gems.md`).
2. Generalize beyond GEMS to serve as the organization-wide standard for interactive scientific dashboards on tabular and multi-dimensional time-series data.
3. Expose a programmatic, composable API that enables MCP-driven dashboard generation by an LLM agent.
4. Handle full-scale outputs (annual horizon × 100+ scenarios, ~35 GB parquet) without browser-side rendering bottlenecks and without loading the full file into RAM.
5. Provide a backwards-compatibility path for legacy ANTARES studies through a separate `antalens.legacy` adapter (full feature parity with the R `antaresViz` package).

### 1.2 Non-goals

- AntaLens is not a general-purpose plotting grammar (no Vega/Altair-style declarative spec language). It is an opinionated, domain-aware engine.
- It does not invoke simulators. The GEMS interpreter, the ViewsBuilder, and any system/library editing GUIs are out of scope.
- It does not author catalogs. Catalogs are user-supplied YAML files; AntaLens consumes them.
- It does not replace dedicated GIS tooling (no full-feature spatial analysis — only network/choropleth visualization).
- It is not a real-time streaming framework. The reactivity model assumes datasets that change on user interaction, not at sub-second rates.
- It does not embed authentication, RBAC, or multi-tenancy. Those concerns live in the deployment layer.

### 1.3 Audience

Three distinct user groups whose needs the API must satisfy simultaneously:

- **GEMS scientists** exploring raw `SimulationTable` files at the per-component, per-output, per-scenario level. They need lazy filtering on multi-GB parquet, pivot tables, and the ability to add ad-hoc charts without writing dashboard scaffolding.
- **GEMS analysts and stakeholders** consuming `Views` files via dashboards and presets. They never see a `component` column; they see semantic labels (`NUCLEAR`, `LOAD`, `BALANCE`) supplied by their catalog.
- **Data analysts in non-GEMS contexts** working with parquet files, CSV exports, SQL databases, or in-memory DataFrames. They have no power-systems context and need the API to feel natural for arbitrary tabular time series.

All three groups must be served without special configuration. GEMS-specific concepts (catalogs, view configs, MC scenarios) must be available but never imposed.

---

## 2. Architecture overview

### 2.1 Layered design

AntaLens is structured into six layers. Each layer depends only on layers below it.

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
│  Catalog         — YAML-driven domain semantics          │
├──────────────────────────────────────────────────────────┤
│  Data layer      — Dataset, SimulationTable, Views       │
│                    (polars · DuckDB · xarray)            │
└──────────────────────────────────────────────────────────┘
```

The catalog layer is what makes AntaLens domain-pluggable. It sits between data and rendering: data carries generic GEMS columns, the catalog gives them display names and groupings, the renderer consumes both.

### 2.2 Core abstractions

Six objects form the conceptual core. Everything else either produces, consumes, or wraps one of these.

**`Dataset`** — the universal data container. Wraps a polars DataFrame / LazyFrame, a DuckDB connection, or an xarray Dataset. Exposes the fluent chain methods: `filter`, `resample`, `compare`, `pipe`, `to_dataframe`, `to_xarray`. All plot and map builders are accessible as namespaced attributes (`ds.plot.timeseries`, `ds.map.network`).

**`SimulationTable`** — a `Dataset` subclass for GEMS raw outputs (long-format, eight-column schema; see `gems.md` §2). Adds GEMS-aware accessors (`.components`, `.outputs`, `.scenarios`, `.blocks`), a GEMS-aware `filter()` overload, and `pivot()` for converting to wide-format. Returned by `antalens.io.load_simulation_table()`.

**`Views`** — a `Dataset` subclass for GEMS curated outputs (wide-format parquet; see `gems.md` §3). Lighter-weight than `SimulationTable` — most operations are inherited from `Dataset`. Returned by `antalens.io.load_views()`.

**`Catalog`** — a frozen dataclass holding parsed domain semantics (component-name patterns, output metadata, palettes, stack templates). Loaded via `antalens.io.load_catalog()` and attached to a `Dataset` via `ds.with_catalog(cat)`. Optional for generic tabular data; recommended for GEMS data.

**`Lens`** — a `param.Parameterized` subclass holding mutable shared state for a connected dashboard. Plot builders consume a `Lens` via `ds.filter(lens)` and re-render when any watched parameter changes. The `Lens` is what turns isolated panes into a connected dashboard.

**`Pane`** — the rendered output of any plot or map builder. Wraps a Plotly `Figure`, a PyDeck `Deck`, or a Datashader `Image` in a `panel.pane.*` object. Composable into `Dashboard` objects and serializable to HTML.

**`Dashboard`** — a Panel `GridSpec`-backed container that holds panes, controls, and a `Lens`. Owns the methods `add`, `remove`, `serve`, `save`, `to_html`, and the serialization round-trip via `to_json` / `from_json`.

`AntaresLegacyStudy` (in `antalens.legacy`) is a `Dataset` subclass that wraps legacy ANTARES output folders. It is *not* part of the architectural core; it exists for backwards compatibility with pre-GEMS studies.

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
Dataset transforms run (polars / DuckDB / xarray, lazy where possible)
    ↓
Catalog applies display names, units, palettes
    ↓
Plot builder constructs new Plotly Figure / PyDeck Deck
    ↓
Pane updates in-place (no full DOM rebuild)
    ↓
Browser receives diff, re-renders affected panes only
```

For `SimulationTable` workloads, filter predicates are pushed down to the parquet reader (polars LazyFrame) or to the SQL engine (DuckDB). Only the filtered slice ever materializes in memory.

Datashader-backed panes follow the same flow but the rendering happens server-side: the `Dataset` transform produces a points DataFrame, Datashader rasterizes to a NumPy array, and only the resulting PNG bytes cross the wire.

---

## 3. Public API

### 3.1 Top-level namespace

The public surface of `import antalens as al` consists of exactly these symbols:

| Symbol               | Type     | Purpose                                              |
|----------------------|----------|------------------------------------------------------|
| `al.io`              | module   | data and catalog loaders                             |
| `al.plot`            | module   | standalone plot builders (mirrors `Dataset.plot`)    |
| `al.map`             | module   | map builders + layout editor                         |
| `al.dash`            | module   | `Dashboard` class and presets                        |
| `al.controls`        | module   | reactive widget primitives                           |
| `al.catalog`         | module   | catalog parsing and helpers                          |
| `al.theme`           | module   | colors, layouts (no domain content)                  |
| `al.legacy`          | module   | backwards-compat adapter for legacy ANTARES studies  |
| `al.Lens`            | class    | shared reactive state container                      |
| `al.Dataset`         | class    | universal data container                             |
| `al.SimulationTable` | class    | GEMS raw-output `Dataset` subclass                   |
| `al.Views`           | class    | GEMS curated-output `Dataset` subclass               |
| `al.Catalog`         | class    | parsed YAML catalog                                  |
| `al.link`            | function | wires a pane event to a `Lens` parameter             |
| `al.pipe`            | function | shared transform node for cross-dataset composition  |

Anything else is internal and may change without notice. `AntaresLegacyStudy` is not at the top level — it is reached via `al.legacy.AntaresLegacyStudy` to make the migration boundary obvious in user code.

### 3.2 `antalens.io` — loaders

All loaders return either a `Dataset` (or subclass) or a `Catalog`. Loaders are pure functions; they never mutate filesystem state.

```python
# Generic data loaders
io.load_parquet(path: str | Path | list[Path], **kw) -> Dataset
io.load_csv(path: str | Path, parse_dates: bool | list[str] = True, **kw) -> Dataset
io.load_hdf5(path: str | Path, key: str | None = None) -> Dataset
io.from_dataframe(df: pl.DataFrame | pd.DataFrame | xr.Dataset,
                  time_col: str | None = None) -> Dataset
io.from_sql(query: str, con: Connection | str, **kw) -> Dataset

# GEMS loaders
io.load_simulation_table(path: str | Path, *,
                         catalog: Catalog | Path | None = None,
                         backend: Literal["polars", "duckdb", "auto"] = "auto",
                         scenarios: list[int] | None = None) -> SimulationTable
io.load_views(path: str | Path | list[Path], *,
              catalog: Catalog | Path | None = None) -> Views
io.load_catalog(path: str | Path) -> Catalog

# Legacy adapter (lives under al.legacy, not al.io, but listed here for reference)
legacy.load_antares(path: str | Path,
                    mc_years: list[int] | None = None) -> AntaresLegacyStudy
```

**Backend selection for `load_simulation_table`**: `auto` (the default) chooses polars LazyFrame for files under 5 GB and DuckDB above. Users can force a backend explicitly.

**Schema inference contract**: each generic loader inspects column types and infers:
- The time column (any `datetime`/`date` dtype, or columns named `time`, `timestamp`, `date`, `valid_time`, `absolute_time_index`).
- Categorical dimensions (any `string`/`categorical` dtype with cardinality < 200).
- Numeric variables (everything else with a numeric dtype).

`load_simulation_table` skips inference and applies the canonical GEMS schema directly.

The inferred or applied schema is stored on the `Dataset` and exposed via `ds.schema()`.

### 3.3 `Dataset` — fluent chain

`Dataset` exposes the following public methods. Every method that returns a `Dataset` returns a new instance — `Dataset` is immutable from the user's perspective.

```python
class Dataset:
    # ── chain methods ───────────────────────────────────────
    def filter(self, *,
               variable: str | list[str] | None = None,
               date_range: tuple[date, date] | Lens | None = None,
               where: str | None = None,           # SQL-like predicate (DuckDB)
               **kw) -> Dataset: ...

    def resample(self, freq: str, agg: str | dict[str, str] = "mean") -> Dataset: ...

    def compare(self, other: Dataset, *,
                label_a: str = "A", label_b: str = "B") -> ComparedDataset: ...

    def pipe(self, fn: Callable[[Dataset], Dataset]) -> Dataset: ...

    def with_catalog(self, catalog: Catalog) -> Dataset: ...

    # ── escape hatches ──────────────────────────────────────
    def to_dataframe(self) -> pl.DataFrame: ...
    def to_pandas(self) -> pd.DataFrame: ...
    def to_xarray(self) -> xr.Dataset: ...
    def schema(self) -> Schema: ...
    def catalog(self) -> Catalog | None: ...

    # ── plot/map namespaces ─────────────────────────────────
    @property
    def plot(self) -> PlotAccessor: ...
    @property
    def map(self) -> MapAccessor: ...
```

**Filter semantics**: arguments are AND-combined. Passing `None` for an argument means "no constraint on this dimension". Passing a `Lens` for `date_range` (or any other supported argument) makes the filter reactive — the resulting `Dataset` is bound to the lens and re-evaluates on parameter change.

`SimulationTable.filter()` adds GEMS-aware kwargs:

```python
class SimulationTable(Dataset):
    def filter(self, *,
               component: str | list[str] | None = None,
               component_kind: str | None = None,   # via catalog patterns
               output: str | list[str] | None = None,
               scenario: int | list[int] | None = None,
               time_range: tuple[int, int] | None = None,  # absolute_time_index
               **kw) -> SimulationTable: ...

    def pivot(self, *, index: str = "absolute_time_index",
              columns: str = "output", values: str = "value") -> Dataset: ...

    def to_views(self, view_config: Path | dict) -> Views: ...

    @property
    def components(self) -> list[str]: ...
    @property
    def outputs(self) -> list[str]: ...
    @property
    def scenarios(self) -> list[int]: ...
    @property
    def blocks(self) -> list[int]: ...
```

`SimulationTable` filters are pushed down to the storage layer wherever possible: polars LazyFrame predicate pushdown for parquet, `WHERE` clauses for DuckDB.

### 3.4 `Dataset.plot` — chart builders

All plot methods return a `Pane`. The pane is a Panel object that can be displayed in a notebook, added to a `Dashboard`, or exported.

```python
plot.timeseries(y: str | list[str], *,
                conf_int: float | None = None,
                by: str | None = None,
                cumulative: bool = False) -> Pane

plot.stack(template: str | dict[str, str] = "auto", *,
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

plot.table(*, columns: list[str] | None = None,
           pivot: dict[str, str] | None = None,
           page_size: int = 50) -> Pane
```

**`plot.table`** is the TableMode (per the GEMS deck slide 11): an interactive, paginated, optionally-pivoted table view. It is the natural first interaction for a scientist exploring a `SimulationTable`. Backed by Panel's `Tabulator`.

**Stack template resolution**: when `template="auto"`, the stack uses the catalog's `stack_templates.default` if present, otherwise infers from column names. The hardcoded `"eco2mix"` template no longer ships in code — it is provided as `catalogs/examples/eco2mix.yml`.

**Auto-detection**: when called on a `Dataset` with a clear schema, every parameter except the data variable is optional. `ds.plot.timeseries("LOAD")` works without specifying the time column — it's inferred from `ds.schema().time_col`.

**Big data handling**: when the underlying data exceeds 50 000 points after filtering, `plot.timeseries`, `plot.heatmap`, and `plot.scatter` automatically switch to Datashader-backed rendering. For `SimulationTable` with DuckDB backend, the threshold is reached after pushdown; the rendered pane only sees the filtered slice. The threshold is configurable via `al.theme.config.datashader_threshold`.

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

When a catalog is attached, `node_color` and `link_color` may reference catalog palettes (e.g. `node_color="by_fuel"`).

The `map` namespace is part of the optional `[maps]` install extra. Importing it without `pydeck` installed raises `ImportError` with installation guidance.

### 3.6 `Lens` — reactive shared state

```python
class Lens(param.Parameterized):
    """Shared mutable state for a connected dashboard."""

    # GEMS-relevant defaults
    component = param.String(default=None, allow_None=True)
    output    = param.String(default=None, allow_None=True)
    scenario  = param.Integer(default=None, allow_None=True)
    # Generic time/space defaults
    area      = param.String(default=None, allow_None=True)
    dates     = param.DateRange(default=None, allow_None=True)
    variable  = param.String(default=None, allow_None=True)

    @classmethod
    def with_extras(cls, **extras) -> type[Lens]:
        """Create a Lens subclass with additional parameters."""
        ...
```

The base `Lens` covers the most common dimensions across both GEMS and generic time-series workflows. Domain-specific extensions use `with_extras`:

```python
HRLens = Lens.with_extras(
    department=param.String(default=None),
    seniority_level=param.String(default=None),
)
```

### 3.7 `link()` and `pipe()`

```python
link(pane: Pane, *,
     on: str,
     set: param.Parameter,
     transform: Callable | None = None) -> None
```

Wires a pane event to a `Lens` parameter. Supported event names per pane type:

| Pane type   | Events                                                  |
|-------------|---------------------------------------------------------|
| timeseries  | `xrange_select`, `point_click`, `legend_click`          |
| stack       | `xrange_select`, `legend_click`                         |
| heatmap     | `cell_click`, `xrange_select`, `yrange_select`          |
| bar         | `bar_click`                                             |
| scatter     | `point_click`, `box_select`, `lasso_select`             |
| table       | `row_click`, `cell_click`                               |
| network     | `node_click`, `link_click`                              |
| choropleth  | `region_click`                                          |

```python
pipe(*datasets: Dataset, **named_datasets: Dataset) -> PipeNode
```

Creates a shared transform node. Downstream chains share the recomputation: filtering `pipe.filter(lens)` once causes all linked chains to re-render. Returns a `PipeNode` that supports `__getitem__` (for named access) and `.join_on(time_col)` for cross-dataset joins.

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
dash.simulation_explorer(table: SimulationTable, *,
                         lens: Lens | None = None) -> Dashboard
dash.adequacy(views: Views, *, lens: Lens | None = None) -> Dashboard
dash.exchanges(views: Views, *, lens: Lens | None = None) -> Dashboard
```

Each preset returns a fully-composed `Dashboard` ready to `.serve()`. Presets are the entry point for new users.

`simulation_explorer` is the new GEMS-specific preset: a 4-pane dashboard combining a TableMode pane, a component picker, a per-output timeseries, and a per-scenario distribution. It is the recommended starting point for scientists exploring a raw `SimulationTable`.

`adequacy` and `exchanges` operate on `Views` (not on raw `SimulationTable`), because the semantic columns (`LOAD`, `BALANCE`, etc.) they require live in the catalog-derived view.

### 3.10 `antalens.catalog` — domain semantics

```python
@dataclass(frozen=True)
class Catalog:
    component_patterns: list[ComponentPattern]
    outputs: dict[str, OutputMetadata]
    palettes: dict[str, dict[str, str]]
    stack_templates: dict[str, StackTemplate]
    geo: GeoCatalog | None  # area-name → centroid lookups for MapLayout.auto

    def parse_component(self, name: str) -> ComponentParsed | None: ...
    def display_name(self, output: str) -> str: ...
    def palette(self, name: str) -> dict[str, str]: ...

catalog.load(path: Path) -> Catalog
catalog.merge(*catalogs: Catalog) -> Catalog
catalog.empty() -> Catalog
```

A `Catalog` is the parsed form of one or more `catalog.yml` files (see `gems.md` §4). Catalogs are immutable. They can be merged (later wins on conflicts) to compose a base catalog with domain-specific overrides.

Example catalog files ship under `catalogs/examples/`:
- `eco2mix.yml` — French TSO production stack template.
- `europe_geo.yml` — European area centroids for `MapLayout.auto()`.
- `gems_minimal.yml` — minimal patterns for the standard GEMS component naming convention.

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
    def apply_catalog(self, fig: Figure) -> Figure: ...
    def schema_check(self) -> None: ...
```

`apply_catalog` is new: it applies display names, units, palettes, and stack orderings from the dataset's attached catalog. If no catalog is attached, it is a no-op.

`to_pane()` is the only method called by external code. `build()` is called once per render and must be deterministic for a given dataset+params combination.

### 4.2 Theme contract

`theme` controls layout and chrome, never domain content. Every Plotly figure produced by AntaLens passes through `apply_theme()` before being wrapped in a pane.

```python
@dataclass
class PlotlyTheme:
    paper_bgcolor: str
    plot_bgcolor: str
    font_family: str
    font_color: str
    grid_color: str
    line_color: str
    palette_neutral: list[str]      # neutral fallback palette only
    palette_continuous: list[tuple[float, str]]
    margin: dict[str, int]
```

Two themes ship with the library: `theme.DARK` and `theme.LIGHT`. Users override via `al.theme.set_active(my_theme)`. Note: `palette_categorical` from the previous spec is removed from the theme — categorical palettes belong in catalogs.

### 4.3 Schema object

Schema now models both wide-format and long-format (GEMS) tables.

```python
@dataclass(frozen=True)
class Schema:
    kind: Literal["wide", "long_gems", "xarray"]

    # wide-format and xarray fields
    time_col: str | None
    categorical_cols: dict[str, list[str]]
    numeric_cols: list[str]
    geo_cols: list[str] | None
    ndim: int

    # long_gems-specific fields (None for wide/xarray)
    component_col: str | None       # canonical "component"
    output_col: str | None          # canonical "output"
    value_col: str | None           # canonical "value"
    scenario_col: str | None        # canonical "scenario_index"
    abs_time_col: str | None        # canonical "absolute_time_index"

    def has(self, col: str) -> bool: ...
    def kind_of(self, col: str) -> Literal["time", "categorical", "numeric", "geo"]: ...
```

### 4.4 MapLayout

```python
@dataclass
class MapLayout:
    nodes: dict[str, NodePosition]      # {area_id: (lat, lon)}
    links: list[tuple[str, str]]
    metadata: dict[str, Any]

    def to_json(self) -> str: ...
    @classmethod
    def from_json(cls, s: str) -> MapLayout: ...
    @classmethod
    def auto(cls, ds: Dataset, *, catalog: Catalog | None = None) -> MapLayout: ...
```

`MapLayout.auto()` now requires a catalog with a `geo` section to resolve area names to centroids. The previous implementation's hardcoded country lookup is gone — that data ships as `catalogs/examples/europe_geo.yml`.

---

## 5. MCP integration

### 5.1 Tool surface

The MCP server (`antalens.mcp.server`) exposes exactly these tools to LLM agents:

| Tool name             | Returns               | Purpose                                                   |
|-----------------------|-----------------------|-----------------------------------------------------------|
| `load_simulation_table` | dataset_id          | register a SimulationTable with the session               |
| `load_views`          | dataset_id            | register a Views file                                     |
| `load_dataset`        | dataset_id            | register a generic Dataset                                |
| `load_catalog`        | catalog_id            | register a Catalog and optionally attach to a dataset     |
| `add_timeseries`      | pane_id               | append a timeseries pane                                  |
| `add_stack`           | pane_id               | append a production stack pane                            |
| `add_table`           | pane_id               | append a TableMode pane                                   |
| `add_map`             | pane_id               | append a network or choropleth map                        |
| `add_heatmap`         | pane_id               | append a heatmap                                          |
| `add_distribution`    | pane_id               | append a CDF/KDE/box plot                                 |
| `set_filter`          | (success)             | mutate the active Lens                                    |
| `compare_datasets`    | pane_id               | overlay two datasets on a single pane                     |
| `remove_pane`         | (success)             | remove a pane by ID                                       |
| `export_dashboard`    | path                  | save the current dashboard to HTML or PNG                 |
| `describe_dashboard`  | dict                  | introspect the current dashboard's structure              |

`load_simulation_table` and `add_table` are new vs. v0.1; `compare_studies` was renamed to `compare_datasets` to reflect that comparison applies to any `Dataset`.

### 5.2 Session model

The MCP server holds one `Session` per connected client. A `Session` contains:
- A registry of loaded datasets keyed by `dataset_id`.
- A registry of loaded catalogs keyed by `catalog_id`.
- A single active `Dashboard` instance.
- A single active `Lens` shared across all panes.

The session is in-memory and not persisted between connections. For persistence, the LLM is expected to call `export_dashboard` and `Dashboard.from_json` on subsequent connections.

### 5.3 Tool-to-API mapping

Each MCP tool is a thin wrapper. Example:

```python
@mcp.tool()
async def add_table(
    session: Session,
    dataset_id: str,
    columns: list[str] | None = None,
    pivot: dict[str, str] | None = None,
) -> str:
    ds = session.datasets[dataset_id]
    pane = ds.filter(session.lens).plot.table(columns=columns, pivot=pivot)
    return session.dashboard.add(pane, row=session.next_row(), col=0)
```

No business logic lives in the MCP layer. Every tool is ≤ 10 lines.

---

## 6. Performance requirements

### 6.1 Rendering tiers

| Data volume after filtering | Rendering path                          | Target latency |
|-----------------------------|-----------------------------------------|----------------|
| < 50 000 points             | Plotly WebGL in browser                 | < 200 ms       |
| 50 000 – 10 000 000 points  | Datashader server-side rasterization    | < 1 500 ms     |
| > 10 000 000 points         | Datashader + Dask out-of-core           | < 5 000 ms     |

### 6.2 Storage tiers (`SimulationTable`)

| File size on disk | Backend                       | Selection rule                    |
|-------------------|-------------------------------|-----------------------------------|
| < 1 GB            | polars eager                  | `auto` if file fits comfortably   |
| 1 – 5 GB          | polars LazyFrame on parquet   | `auto` default for medium files   |
| > 5 GB            | DuckDB on parquet             | `auto` switches at 5 GB threshold |

The 5 GB switch is a reasoned default. The threshold is configurable via `al.theme.config.duckdb_threshold` (yes, the name will move out of `theme` — see Open Questions).

### 6.3 Memory ceilings

- A single `Dataset` instance must not eagerly materialize more than 4 GB of data. Larger datasets are held as polars LazyFrame, DuckDB connections, or xarray-backed Dask arrays.
- Loading a `SimulationTable` of any size with the `auto` backend must use ≤ 2 GB regardless of file size. Per-scenario or per-component data is read on demand via predicate pushdown.

### 6.4 Reactivity latency

- A `Lens` parameter change must result in pane re-rendering within 500 ms for tier-1 data, and within 2 000 ms for tier 2.
- Linked event propagation must complete in under 100 ms exclusive of pane re-render.

---

## 7. Compatibility and dependencies

### 7.1 Python version

Python 3.11 and later. The codebase relies on PEP 695 type aliases, `Self` types, and `dataclass(slots=True)` performance characteristics.

### 7.2 Hard dependencies

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
PyYAML>=6.0           # catalog parsing
```

### 7.3 Optional extras

```
[maps]      — pydeck>=0.9
[bigdata]   — datashader>=0.16, dask>=2024.1, duckdb>=0.10
[legacy]    — h5py>=3.10  (legacy ANTARES studies)
[mcp]       — fastmcp>=0.2
[dev]       — pytest, pytest-cov, ruff, mypy, jupyterlab
[all]       — everything above
```

The base install must produce a working library for tabular CSV/parquet workflows and for in-memory `SimulationTable` files (< 1 GB) without any optional extras. DuckDB is recommended for production GEMS workloads and lives in `[bigdata]`.

### 7.4 Deployment targets

- Standalone Panel server (`dashboard.serve()`) — supported.
- Embedded in a Jupyter notebook (`dashboard.to_notebook()`) — supported.
- Static HTML export (`dashboard.save("out.html")`) — supported, with the caveat that linked interactivity requires a running Panel server.
- Docker container — Dockerfile shipped in `docker/` for reference deployments.

---

## 8. Testing requirements

### 8.1 Coverage targets

- Unit tests: ≥ 85% line coverage on `antalens/` excluding `mcp/`, `dash/presets.py`, and `legacy/`.
- Integration tests: every MCP tool exercised end-to-end with a mock SimulationTable.
- Visual regression: `plot/*` builders compared against committed Plotly JSON snapshots (assertions on trace structure, not pixel comparison).

### 8.2 Fixture data

Three pytest fixtures in `tests/conftest.py`:

- **`mock_simulation_table`** — a deterministic `SimulationTable` parquet with 5 areas × 3 generators per area × 5 outputs × 168 hours × 3 scenarios. Generated from a fixed seed; output is byte-identical across runs.
- **`mock_views`** — the canonical wide-format view derived from `mock_simulation_table`.
- **`mock_legacy_study`** (under `tests/legacy/`) — a deterministic legacy ANTARES output folder for regression-testing the legacy adapter.

The mock `SimulationTable` exists at three sizes (small / medium / large) by configurable scenario counts, so tests can exercise the polars↔DuckDB threshold without needing 35 GB of real data.

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

| Level       | Symbols                                                       | Stability commitment |
|-------------|---------------------------------------------------------------|----------------------|
| Stable      | All of section 3 except `al.controls` and `al.legacy`         | No breaking changes within a major version |
| Provisional | `al.controls`, `al.catalog` (until Catalog v2 lands)          | May change within minor versions, with deprecation warnings |
| Legacy      | `al.legacy`                                                   | Frozen feature set; security/compat fixes only |
| Internal    | Anything starting with `_` or under `antalens._internal`      | No stability guarantee |

### 9.3 Deprecation policy

A symbol marked deprecated emits a `DeprecationWarning` for at least one minor version before removal. Deprecation notices include the recommended replacement and the version in which removal is scheduled.

---

## 10. Open questions and design decisions deferred

1. **Catalog v1 vs Catalog v2.** The current schema (component patterns + outputs + palettes + stack templates) covers the immediate GEMS need. A v2 may add: derivation rules (collapsing the ViewsBuilder use case), validation (units consistency), inheritance (base catalog + delta). Decision deferred until at least three real catalogs exist.

2. **DuckDB ↔ polars threshold.** The 5 GB switch is a reasoned default but should be benchmarked on real `SimulationTable` files in the refactor's validation phase and tuned. We may also add a `[bigdata]`-free fallback path that uses polars LazyFrame even above 5 GB at the cost of latency, for users who can't or won't install DuckDB.

3. **`SimulationTable.to_views()` scope.** A reference implementation that handles simple `group_by + agg` view configs is sufficient for the library; complex view configs are the ViewsBuilder's job. The exact dividing line between "simple enough for AntaLens" and "use the ViewsBuilder" is TBD.

4. **`config` namespace location.** Several runtime knobs (`datashader_threshold`, `duckdb_threshold`, default catalog search path) are currently spec'd under `al.theme.config`. They should probably move to `al.config` since they aren't theme concerns. Pending a small naming pass before 1.0.

5. **`Lens` serialization format.** Param's built-in serialization is sufficient for v0.1; revisit if MCP demands richer schemas (e.g. parameter constraints, conditional dependencies).

6. **Multi-user dashboard sharing.** Out of scope for v0.1. If demand emerges, evaluate Panel's session-level state vs. process-level shared state.

7. **WebAssembly export.** Panel supports PyScript-based static export. Not promised for v0.1; evaluate in a later phase.

8. **Custom theme + catalog authoring UI.** Both are editable in code/YAML; GUI editors are a later-phase candidate.

---

## Appendix A — glossary

- **GEMS**: Generic Energy Systems Modelling Scheme. RTE's modelling framework that replaces the legacy ANTARES core. See `gems.md`.
- **SimulationTable**: GEMS raw simulation output — long-format, eight-column parquet. See `gems.md` §2.
- **Views**: GEMS curated output — wide-format, catalog-derived parquet. See `gems.md` §3.
- **Catalog**: user-supplied YAML mapping generic GEMS column values to domain semantics. See `gems.md` §4.
- **Component**: a named entity in a GEMS `system.yml` (generator, link, load, storage, bus).
- **Output (GEMS)**: a named variable on a component (e.g. `p`, `cost`, `flow`).
- **Scenario**: one Monte Carlo realization, indexed by `scenario_index` in the SimulationTable.
- **Block**: an optimization sub-problem in a rolling-horizon simulation.
- **basis_status**: solver-side flag on each variable indicating its basis state in the LP/MILP solution.
- **Pane**: a single rendered visual unit (chart, map, table) within a dashboard.
- **Lens**: AntaLens's reactive shared-state container; the bridge that turns isolated panes into a connected dashboard.
- **TableMode**: an interactive, paginated, optionally-pivoted table view (`plot.table`).
- **Legacy ANTARES**: pre-GEMS ANTARES studies, supported via the `antalens.legacy` adapter.
