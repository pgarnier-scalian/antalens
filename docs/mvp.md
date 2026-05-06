# AntaLens MVP — first vertical slice

> **Goal**: a single command takes a parquet file and serves a working dashboard in a browser.
> **Scope**: the thinnest possible slice through *every* layer of the architecture, end-to-end.
> **Out of scope**: more chart types, ANTARES-specific features, MCP, Datashader, polish.

The point of this phase is not to add features. It's to **prove the full toolchain works as one system**. We have data loading, reactive filtering, and one plot type. The MVP wires those into a served Panel dashboard with at least one interactive control. Once that loop closes, every future feature is a *delta* on a working baseline.

---

## What "MVP done" looks like

A user can run:

```bash
python -m antalens.examples.parquet_explorer path/to/data.parquet
```

…and a browser opens to `http://localhost:5006` showing:

- A **dashboard title** with the file name.
- One **time-series plot** of an auto-detected numeric column.
- One **interactive control** (a select widget for the y-axis variable).
- Changing the control updates the plot live, via the `Lens`/`watched_parameters` plumbing we already built.

That's it. No styling polish, no second chart, no presets. Just: file in → live, interactive plot out.

---

## Why this is the right next step

We have the foundation. Nothing in the foundation has been *exercised end-to-end yet*. Three things go wrong at integration time that local unit tests can't catch:

1. **Panel's `pn.bind()` on `to_pane()`** has only been tested on a static figure. We haven't actually watched a `Lens` change and confirmed the pane re-renders.
2. **Serving** is a separate code path from rendering. `pn.pane.Plotly` works in a notebook; `pn.serve(...)` runs a Bokeh server. Things break there that don't break in tests.
3. **The CLI / entry point** doesn't exist yet. Users need a way to invoke the toolchain that isn't "open a Python REPL." This is what makes it *real software* instead of a library.

Building all three now means every later feature lands on a known-good baseline. Adding `BarPlot` later is a one-file change instead of a one-file change *plus* discovering the dashboard layer was broken the whole time.

---

## What gets built

### 1. `Dashboard` class (minimum viable)

A thin wrapper around a Panel layout. **Not the full `Dashboard` from the spec** — no GridSpec, no JSON serialization, no preset registry. Just enough to hold a title, a controls column, a plot pane, and serve.

`src/antalens/dash/dashboard.py`:

- `class Dashboard` with `__init__(title, lens=None)`.
- `.add_control(widget)` — append a Panel widget to the controls sidebar.
- `.add_pane(pane)` — append a viewable to the main content area.
- `.serve(port=5006)` — call `pn.serve()` on the assembled layout.
- `.servable()` — return the layout as a Panel servable for `panel serve` CLI.

The full Dashboard with GridSpec, presets, and JSON round-trip is Phase 2. This MVP version is roughly 60 lines.

### 2. `controls` module (one widget for the MVP)

`src/antalens/controls.py`:

- `VariablePicker(lens, options)` — a `pn.widgets.Select` wired to `lens.variable`.
- That's it for the MVP. `AreaSelector`, `DateRangeSelector`, etc. land in Phase 2.

The widget pattern is what every future control follows: take a `Lens`, mutate one of its parameters, return a Panel widget. Locking this pattern down is the value of the MVP.

### 3. The example script (the actual MVP deliverable)

`src/antalens/examples/parquet_explorer.py`:

- Argparse for the file path.
- `io.load_parquet()` to load.
- Construct a `Lens` with `variable` initialized to the first numeric column.
- Build a `VariablePicker` bound to that lens.
- Build a `TimeSeriesPlot` whose dataset is filtered by `lens.variable` mapped to the y-axis.
- Wrap in a `Dashboard`.
- Call `dashboard.serve()`.

This is the script that proves the toolchain. Roughly 30-40 lines of mostly glue.

### 4. The "y-axis-from-lens" mechanism

This is the one piece of new design needed. The current `TimeSeriesPlot` takes `y` as a constructor argument — fixed at build time. For the MVP we need `y` to come from the `Lens` so the picker can change it.

Two options:
- **Option A (smaller change)**: `TimeSeriesPlot.y` accepts a `param.Parameter` reference; `build()` reads the current value at call time.
- **Option B (cleaner long-term)**: introduce a generic `LensBound[T]` type that any plot parameter can use, not just `y`.

For the MVP, **Option A**. It's a 5-line change to `TimeSeriesPlot.__init__` and `build()`. Option B is the right shape for Phase 3 when multiple plot parameters need to be lens-bound, but doing it now would invent abstraction without enough use cases to validate it.

### 5. CLI entry point

`pyproject.toml` gets a `[project.scripts]` entry:

```toml
[project.scripts]
antalens-explore = "antalens.examples.parquet_explorer:main"
```

After `pip install -e .`, the user gets `antalens-explore path/to/data.parquet` as a real command.

---

## What stays the same

- **Existing tests still pass.** The MVP doesn't change `Dataset`, `Schema`, `Lens`, `loaders`, `_base.py`, or `theme`. Only `TimeSeriesPlot` gets the `y=lens.param.X` accommodation.
- **No new dependencies.** Panel, Plotly, polars, param are already installed.
- **The architecture stays.** No shortcuts in the core. The MVP is a *thin slice through* the architecture, not a bypass of it.

---

## Big picture — where this sits

The implementation plan has 5 phases. This MVP isn't a phase — it's the **end of Phase 1**, the moment when we stop building components and start using them together.

```
Phase 0 — foundations (done)
Phase 1 — data layer + plots
  ├─ Schema           (done)
  ├─ Dataset          (done)
  ├─ Loaders          (done)
  ├─ Lens             (done)
  ├─ TimeSeriesPlot   (done)
  └─ MVP integration  ← we are here
Phase 2 — reactivity + dashboard (more chart types, full Dashboard, link/pipe)
Phase 3 — maps + presets
Phase 4 — big data + MCP
Phase 5 — polish + 1.0
```

The MVP is the first moment the project has a **product**, not a library. Everything after this — more chart types, ANTARES-specific code, maps, MCP — is iteration on a working artifact. That's a much faster development mode than building components in isolation and praying they integrate at the end.

---

## What does NOT belong in the MVP

- **More plot types**. Tempting, fast to add, wrong move. The point is to prove the toolchain. Adding `BarPlot` adds zero confidence in the Panel/serve integration.
- **Styling polish**. The default theme is dark and looks fine. The MVP can be ugly. Polish lands once we know what to polish.
- **ANTARES study loader**. Parquet first. The whole bet on the "generic engine" framing was that ANTARES support is a *subclass*, not the foundation. MVP proves that bet by working without it.
- **Multiple controls**. One picker is enough to prove reactivity. Adding `DateRangeSelector` doesn't teach us anything new at this stage.
- **JSON dashboard serialization**. Phase 2 territory.
- **MCP**. Phase 4 territory. Don't even sketch it now.

---

## The order of operations

Six small, testable steps. Each one ends in a working state.

1. **Add `LensBound` y to `TimeSeriesPlot`** (5 mins). Modify `__init__` to accept a `param.Parameter` reference for `y`; `build()` resolves it at call time. Existing tests still pass; one new test for the reactive y-axis.
2. **Build `controls.VariablePicker`** (15 mins). `pn.widgets.Select` wired to `lens.variable`. One unit test confirming widget value updates lens.
3. **Build minimal `Dashboard`** (20 mins). Title + sidebar + main content. `add_control`, `add_pane`, `servable`. No fancy layout.
4. **Wire the example script** (15 mins). `parquet_explorer.py` with argparse, instantiates everything, calls `dashboard.serve()`.
5. **Add the CLI entry point** to `pyproject.toml` (2 mins).
6. **Manual end-to-end test**: run `antalens-explore data.parquet`, click the picker, watch the plot update. Take a screenshot.

If step 6 works, the MVP is done.

---

## Acceptance criteria

- `antalens-explore <parquet-file>` starts a server and opens a browser.
- The page shows a title, a variable picker, and a time-series plot.
- Selecting a different variable in the picker updates the plot within ~500ms.
- The full existing test suite (139 passing) still passes.
- Two new tests pass: one for `LensBound` y, one for `VariablePicker` wiring.
- Total new code under 200 lines including tests.

---

## After the MVP, in priority order

1. **Second chart type** — likely `BarPlot` or `Heatmap`. First chart added to a *working* dashboard.
2. **Multi-pane dashboard with GridSpec layout** — multiple charts that share a `Lens`.
3. **`link()` for chart-to-chart events** — clicking a bar to filter the time-series.
4. **More controls** — `AreaSelector`, `DateRangeSelector`.
5. **Dashboard JSON serialization** — round-trip a dashboard to disk and back.
6. **First ANTARES preset** — `dash.adequacy(study)` returning a complete dashboard.

Each item builds on a system that's known to work end-to-end. That's the value of investing in the MVP before adding more breadth.
