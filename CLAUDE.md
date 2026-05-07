# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AntaLens is a Python visualization engine for tabular and time-series data, designed to serve as the visualization front-end for GEMS (Generic Energy Systems Modelling Scheme). It handles full-scale outputs (annual horizon × 100+ scenarios, ~35 GB parquet) without browser-side rendering bottlenecks.

**Current state**: Pre-implementation phase, actively being refactored. See `PHASE_TRACKER.md` for what's shipped vs. in-flight.

## Development Commands (via `just`)

The project uses a [`justfile`](justfile) for common commands. All commands run via `uv` for dependency management.

```bash
just install      # Install all deps including dev: uv sync --all-extras
just test         # Run tests with coverage: uv run pytest
just test-fast    # Skip slow tests: uv run pytest -m "not slow"
just lint         # Run linters: uv run ruff check + uv run ruff format --check
just format       # Auto-format code: uv run ruff check --fix + uv run ruff format
just type         # Type-check: uv run mypy src/antalens
just check        # Run everything: lint + type + test
just docs         # Build docs: uv run sphinx-build
just docs-serve   # Serve docs with live reload: uv run sphinx-autobuild
just smoke        # Quick import check: uv run python -c "import antalens"
just clean        # Remove build artifacts
```

### Test commands

- Run all tests: `just test` or `uv run pytest`
- Run single test file: `uv run pytest tests/unit/data/test_schema.py -v`
- Run single test: `uv run pytest tests/unit/data/test_schema.py::test_schema_inference -v`
- Skip slow tests: `just test-fast` or `uv run pytest -m "not slow"`
- Run with coverage: `uv run pytest --cov=antalens --cov-report=html` then open `htmlcov/index.html`

### Linting and type checking

```bash
just lint        # ruff check + ruff format --check
just format      # ruff check --fix + ruff format
just type        # mypy src/antalens
```

VS Code is configured for auto-format on save with ruff.

## Project Structure

```
antalens/
├── src/antalens/           # Core library code
│   ├── data/               # Data layer (Dataset, SimulationTable, Views, loaders)
│   ├── plots/              # Plot builders (timeseries, bar, stack, _base)
│   ├── dash/               # Dashboard composition (Dashboard, presets)
│   ├── maps/               # Geo/network visualizations (PyDeck)
│   ├── mcp/                # FastMCP server for LLM agent integration
│   ├── theme/              # Styling and stack templates
│   ├── lens.py             # Reactive shared state (param.Parameterized)
│   ├── link.py             # Chart-to-chart event wiring
│   ├── io.py               # Public loader API (re-exports from data.loaders)
│   └── __init__.py
├── tests/
│   ├── unit/               # Unit tests (schema, dataset, loaders, plots, lens)
│   ├── integration/        # End-to-end integration tests
│   ├── perf/               # Performance benchmarks
│   ├── snapshots/          # Visual regression snapshots
│   └── conftest.py         # Test fixtures (mock_simulation_table, mock_views)
├── docs/                   # Sphinx documentation
│   ├── api/                # API reference
│   ├── tutorials/          # Getting started guides
│   ├── cookbook/           # Recipe collection
│   ├── adrs/               # Architecture Decision Records
│   ├── spec.md             # Full architectural specification
│   ├── gems.md             # GEMS data model reference
│   ├── plan.md             # Implementation plan
│   └── refactor.md         # Refactoring notes
├── examples/               # Example scripts
├── catalogs/               # Example catalog YAML files
├── data/                   # Test fixture data
├── pyproject.toml          # Project config (dependencies, ruff, mypy, pytest)
├── justfile                # Command shortcuts
├── .pre-commit-config.yaml # Pre-commit hooks
└── PHASE_TRACKER.md        # Feature status (shipped/in-flight/queued/deferred)
```

## Key Architecture Concepts

### Layered design

```
MCP layer       — FastMCP tool wrappers
Dashboard layer — Panel GridSpec, Lens, link(), pipe()
Reactivity      — Param + pn.bind
Rendering       — Plotly · Datashader · PyDeck
Catalog         — YAML-driven domain semantics
Data layer      — Dataset, SimulationTable, Views (polars · DuckDB · xarray)
```

The **catalog layer** is what makes AntaLens domain-pluggable. It sits between data and rendering.

### Core abstractions

Six objects form the conceptual core:

1. **`Dataset`** — Universal data container wrapping polars DataFrame/LazyFrame, DuckDB connection, or xarray Dataset. Exposes fluent chain methods: `filter`, `resample`, `compare`, `pipe`, `to_dataframe`.

2. **`SimulationTable`** — `Dataset` subclass for GEMS raw outputs (long-format parquet). Adds GEMS-aware accessors (`.components`, `.outputs`, `.scenarios`, `.blocks`) and `filter()` overload.

3. **`Views`** — `Dataset` subclass for GEMS curated outputs (wide-format parquet). Lighter-weight than `SimulationTable`.

4. **`Catalog`** — Parsed YAML catalog holding domain semantics (component patterns, output metadata, palettes, stack templates). Attached to `Dataset` via `ds.with_catalog(cat)`.

5. **`Lens`** — `param.Parameterized` subclass holding mutable shared state for connected dashboards. Plot builders consume via `ds.filter(lens)`.

6. **`Pane`** — Rendered output of plot/map builders wrapped in Panel pane objects.

### Public API surface

```python
import antalens as al

al.io          # Loaders: load_parquet, load_csv, from_dataframe
al.plot        # Standalone plot builders (mirrors Dataset.plot)
al.dash        # Dashboard class and presets
al.Lens        # Shared reactive state container
al.Dataset     # Universal data container
al.SimulationTable  # GEMS raw-output Dataset subclass
al.Views       # GEMS curated-output Dataset subclass
al.link        # Wire pane events to Lens parameters
```

Everything else is internal and may change without notice.

## Important Files to Reference

- **`docs/spec.md`** — Full architectural specification with complete API docs
- **`docs/gems.md`** — GEMS data model reference (SimulationTable, Views, Catalog)
- **`PHASE_TRACKER.md`** — Feature status tracker (what's shipped, in-flight, queued)
- **`docs/plan.md`** — Detailed implementation plan with step-by-step instructions
- **`docs/refactor.md`** — Refactoring notes and decisions

## Code Quality Tools

- **ruff**: linting and formatting (configured in `pyproject.toml`)
- **mypy**: strict type checking (configured in `pyproject.toml`)
- **pytest**: testing with coverage (configured in `pyproject.toml`)
- **pre-commit**: runs ruff and mypy before commits

VS Code settings configured for auto-format on save with ruff.

## Testing Conventions

- Test fixtures defined in `tests/conftest.py`: `mock_simulation_table`, `mock_views`
- Markers: `@pytest.mark.slow`, `@pytest.mark.integration`, `@pytest.mark.perf`
- Coverage target: ≥85% line coverage on `antalens/` (excluding `mcp/`, `dash/presets.py`, `legacy/`)
- Visual regression: Plotly JSON snapshots compared in `tests/snapshots/`

## Development Workflow

1. Use `just check` to verify everything passes
2. For feature work, check `PHASE_TRACKER.md` to see what's in-flight
3. Consult `docs/spec.md` for API contracts
4. Run tests incrementally: `uv run pytest tests/unit/...`
5. Lint before commit: `just format` runs auto-fix, `just lint` checks

## Backend Strategy

| Data size on disk | Backend               | Use case                           |
|-------------------|-----------------------|------------------------------------|
| < 1 GB            | polars eager          | Fits in RAM                        |
| 1–50 GB           | polars LazyFrame      | Predicate pushdown, streaming agg  |
| > 50 GB           | DuckDB on parquet     | Out-of-core SQL, spills            |
| distributed       | Dask + xarray         | Multi-MC scientific workflows      |

Backend selection is automatic based on file size but can be overridden via `backend=` parameter. See `gems.md` section 6 for rationale.

## MCP Integration

The `antalens.mcp` module provides a FastMCP server exposing tools to LLM agents. See `docs/spec.md` section 5 for the complete tool surface. The MCP layer is thin wrappers around the core API—no business logic lives there.

## Cross-cutting Concerns

### Domain-vocabulary lint

The core `antalens/` package must remain **domain-agnostic**. Domain-specific terms (ANTARES, eco2mix, France, CCGT, etc.) are forbidden in core code and must live only in:
- `catalogs/` (YAML configuration)
- `examples/` (demonstration code)
- `docs/` (documentation)

Forbidden terms list (from refactor.md):
```
ANTARES, eco2mix, Adequacy, Reserve, Marginal Price, bidding zone,
CCGT, nuclear, wind load, France, RTE, Enel, production margin
```

Use grep or a ruff custom rule to check before committing.

### Security requirements

- Never hardcode secrets; use environment variables
- MCP tools must validate all inputs; treat external data as untrusted
- No network calls from core library (except optional MCP server)

### Performance requirements

- Load 35 GB parquet within 2 minutes (lazy evaluation)
- Filter 1M rows within 100ms
- Render timeseries with 100k points without browser lag (use datashader)
- Dashboard with 5 panes must respond to lens updates within 500ms

See `spec.md` section 6 for full performance budget.

## Architecture Decision Records (ADRs)

See `docs/adrs/` for detailed architectural decisions:

- **ADR-001: Generic core vs domain knowledge** — Why core code stays domain-agnostic and domain terms live in catalogs
- **ADR-002: LazyFrame-first data layer** — Trade-offs of polars LazyFrame as the default backend
- **ADR-003: Lens with_extras() pattern** — How domain-specific extensions are built without subclassing the base Lens
- **ADR-004: Catalog v1 design** — Why the catalog is YAML-based and user-supplied rather than hardcoded

## Risk register (highlights)

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GEMS SimulationTable schema evolves | Medium | High | Pin to documented schema version in gems.md |
| Catalog v1 too rigid for user needs | Medium | Medium | Design conservatively; mark as Provisional stability |
| DuckDB-Plotly event integration harder than expected | Medium | Low | Spike in Phase 4 week 1; have fallback plan |
| Large simulation tables (TB-scale) overwhelm Polars | Low | High | DuckDB tier + streaming aggregations |

See `plan.md` full risk register for details.

## 6-phase timeline (current status)

```
Phase 0  → Foundations                   (2 weeks)   [DONE]
Phase 1  → Generic library + plots       (4 weeks)   [IN FLIGHT, ~80% done]
Phase 2  → GEMS data layer + reactivity  (6 weeks)   [QUEUED]
Phase 3  → Maps, presets, legacy adapter (5 weeks)   [QUEUED]
Phase 4  → Big data + MCP                (5 weeks)   [QUEUED]
Phase 5  → Polish + 1.0 release          (3 weeks)   [QUEUED]
```

See `PHASE_TRACKER.md` for detailed per-feature status.

## Refactor tasks (11-task cleanup plan)

The `refactor.md` file documents an 11-task structural cleanup to align the codebase with the GEMS data model and domain-agnostic architecture:

1. **Schema rewrite** — Replace Schema with GEMS-aware variants (SimulationTableSchema, ViewsSchema)
2. **Dataset API alignment** — Public API surface matching spec §3.1
3. **Theme de-domainization** — Remove ANTARES-specific themes
4. **Catalog skeleton** — Add Catalog dataclass and loader
5. **Lens refactor** — Base Lens generic, domain specifics via with_extras()
6. **Plot builder cleanup** — Remove domain-specific plot types, keep generic primitives
7. **Dashboard API finalization** — Stabilize Dashboard, SectionTitle, link() API
8. **Tests refactor** — Update test fixtures, add GEMS-specific tests
9. **Examples cleanup** — Update all examples to use new API
10. **Docs updates** — Update docs/plan.md, docs/spec.md with final API surface
11. **Final verification** — Run lint/typecheck/tests, verify public API surface

See `refactor.md` for detailed acceptance criteria per task.

### Task 11 verification commands

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
