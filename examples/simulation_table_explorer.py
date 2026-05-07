"""GEMS SimulationTable explorer — the GEMS-shaped successor to lp_explorer.py.

Loads a long-format LP solver output (now properly framed as a GEMS
``SimulationTable``: 8-column schema with ``block``, ``component``,
``output``, ``absolute_time_index``, ``block_time_index``,
``scenario_index``, ``value``, ``basis_status``).

Lets the user filter by ``output`` and ``scenario`` via dropdowns, and
renders a stack / bar / timeseries view of the top-N components.

Usage::

    uv run python examples/simulation_table_explorer.py path/to/sim.csv
    uv run python examples/simulation_table_explorer.py path/to/sim.parquet

This script is a probe: it tries the GEMS-aware ``SimulationTable`` API
first, and falls back to the generic ``Dataset`` API where the stub
isn't yet fleshed out. Tells us which corners need work.
"""

from __future__ import annotations

import sys
from pathlib import Path

import panel as pn
import polars as pl

from antalens import io
from antalens.dash import Dashboard, SectionTitle
from antalens.lens import Lens

# ─── widget styling shim — to be replaced by controls.py wrappers ───────────

WIDGET_CSS = """
select, .bk-input {
    background: #111418 !important;
    color: #9dafc0 !important;
    border: 1px solid #2a3240 !important;
    border-radius: 4px;
    padding: 5px 8px;
    font-family: inherit;
    width: 100%;
    box-sizing: border-box;
}
"""


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python examples/simulation_table_explorer.py <path>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"No file at {path}")
        sys.exit(1)

    print(f"Loading {path} via io.load_simulation_table ...")

    # Try the GEMS-aware loader first. If the stub doesn't implement it
    # yet, fall back to load_csv/load_parquet with explicit GEMS schema.
    try:
        ds = io.load_simulation_table(path, name=path.stem)
        print(f"  Loaded as SimulationTable: {type(ds).__name__}")
    except (AttributeError, NotImplementedError) as e:
        print(f"  load_simulation_table not yet available ({e}); falling back to generic loader")
        loader = io.load_csv if path.suffix.lower() == ".csv" else io.load_parquet
        ds = loader(
            path,
            name=path.stem,
            time_col="absolute_time_index",
        )

    # ── Discover available outputs and scenarios ──────────────────────────
    # Prefer GEMS accessors if the stub provides them; fall back to a
    # column scan if it doesn't.
    print("Scanning output and scenario values ...")
    output_options: list[str]
    scenario_options: list[int]
    try:
        output_options = sorted(ds.outputs)
        scenario_options = sorted(ds.scenarios)
    except (AttributeError, NotImplementedError):
        # Generic fallback: scan the columns directly.
        scan = ds.to_lazy().select(["output", "scenario_index"]).unique().collect()
        output_options = sorted(scan["output"].drop_nulls().unique().to_list())
        scenario_options = sorted(scan["scenario_index"].drop_nulls().unique().to_list())

    print(f"  outputs:   {output_options}")
    print(f"  scenarios: {scenario_options}")

    if not output_options:
        print("No values in the 'output' column.")
        sys.exit(1)

    default_output = "p" if "p" in output_options else output_options[0]
    default_scenario = scenario_options[0] if scenario_options else 0

    # ── Lens setup ────────────────────────────────────────────────────────
    # NOTE the renamed parameter: scenario (was mc).
    lens = Lens(variable=default_output, scenario=default_scenario)

    def _build_charts(*_args):  # type: ignore
        from antalens.data.dataset import Dataset

        # Apply both filters statically. We don't use ds.filter(scenario=...)
        # reactively because:
        # 1. SimulationTable.filter may or may not support scenario= depending
        #    on the stub's completeness.
        # 2. We're rebuilding the charts on every lens change anyway via
        #    pn.bind, so static is fine here.
        snapshot_lf = (
            ds.to_lazy()  # type: ignore
            .filter(pl.col("output") == lens.variable)
            .filter(pl.col("scenario_index") == lens.scenario)
        )
        snapshot = Dataset(
            snapshot_lf,
            name=f"{path.stem} · {lens.variable} · scenario {lens.scenario}",
        )

        df = snapshot.to_dataframe()
        n_components = df["component"].n_unique() if df.height else 0
        print(
            f"  → output={lens.variable}, scenario={lens.scenario}: "
            f"{df.height:,} rows, {n_components} components"
        )

        if df.height == 0:
            return pn.pane.Markdown(
                f"_No rows for output={lens.variable}, scenario={lens.scenario}._"
            )  # type: ignore

        # Top-20 components by mean value to keep the legend readable.
        top_components = (
            df.group_by("component")
            .agg(pl.col("value").mean().alias("__mean"))
            .sort("__mean", descending=True)
            .head(20)["component"]
            .to_list()
        )
        df_top = df.filter(pl.col("component").is_in(top_components))
        snapshot_top = Dataset(df_top.lazy(), name=snapshot.name)

        # Stack chart: build a per-component template inline since the
        # ECO2MIX/BASE built-ins moved to YAML catalogs (Phase 2 work,
        # not yet wired). When the catalog system lands, this becomes:
        #     ds.with_catalog(cat).plot.stack(...)
        from antalens.theme import get_active_theme

        # The StackTemplate import path may have shifted post-refactor.
        # Try both locations to be resilient.
        try:
            from antalens.catalog import StackLayer  # type: ignore[attr-defined]
            from antalens.catalog import StackTemplateConfig as StackTemplate
        except ImportError:
            from antalens.theme.stack_templates import (  # type: ignore[no-redef]
                StackLayer,
                StackTemplate,
            )  # type: ignore

        palette = get_active_theme().palette_categorical
        custom_template = StackTemplate(
            name="components",
            layers=tuple(
                StackLayer(c, palette[i % len(palette)]) for i, c in enumerate(top_components)
            ),
        )  # type: ignore

        try:
            stack = snapshot.plot.stack(
                stack_by="component",
                y="value",
                template=custom_template,
                agg="sum",
                sizing_mode="stretch_width",
                height=320,
            )
        except (AttributeError, NotImplementedError, TypeError) as e:
            stack = pn.pane.Markdown(f"_Stack chart unavailable: {e}_")  # type: ignore

        bar = snapshot_top.plot.bar(
            x="component",
            y="value",
            agg="mean",
            sort="desc",
            sizing_mode="stretch_width",
            height=280,
        )
        ts = snapshot_top.plot.timeseries(
            "value",
            by="component",
            sizing_mode="stretch_width",
            height=300,
        )
        return pn.Column(stack, bar, ts, sizing_mode="stretch_width")

    charts = pn.bind(_build_charts, lens.param.variable, lens.param.scenario)

    # ── Controls ──────────────────────────────────────────────────────────
    output_picker = pn.widgets.Select.from_param(
        lens.param.variable,
        options=output_options,
        name="Output",
        stylesheets=[WIDGET_CSS],
        sizing_mode="stretch_width",
    )
    scenario_picker = pn.widgets.Select.from_param(
        lens.param.scenario,
        options=scenario_options,
        name="Scenario",
        stylesheets=[WIDGET_CSS],
        sizing_mode="stretch_width",
    )

    # ── Dashboard ─────────────────────────────────────────────────────────
    dash = Dashboard(
        title=path.stem,
        subtitle=(
            f"GEMS SimulationTable · {len(output_options)} outputs · "
            f"{len(scenario_options)} scenarios"
        ),
        lens=lens,
    )
    dash.add_control(SectionTitle("Slice"))
    dash.add_control(output_picker)
    dash.add_control(scenario_picker)
    dash.add_control(SectionTitle("Notes"))
    dash.add_control(
        pn.pane.Markdown(
            "Showing top-20 components by mean value. Stack/bar/timeseries all driven by the lens.",
            margin=(4, 0, 0, 0),
        )  # type: ignore
    )
    dash.add_pane(charts, width_pct=100)
    dash.add_status_item("LIVE")
    dash.add_status_item(f"FILE: {path.name}")
    dash.add_status_item("antalens v0.2-dev · GEMS")

    print("Serving on http://localhost:5006 ...")
    dash.serve(port=5006)


if __name__ == "__main__":
    main()
