"""LP solver output explorer — long-format CSV with output x component x time x scenario.

The data shape is::

    block,component,output,absolute_time_index,block_time_index,
    scenario_index,value,basis_status

where ``output`` discriminates *what kind of value* lives in the ``value``
column (``p`` for power, ``min_dispatch`` for constraints, ``p_nom`` for
capacities, etc.). Plotting raw is meaningless because mixed semantics
get aggregated together.

This script:

1. Loads the CSV (treating "None" strings as nulls).
2. Inspects which ``output`` types and scenarios are present.
3. Lets the user pick one of each via dropdowns.
4. Renders a per-component bar chart (mean over time) and a time-series
   grouped by component.

Usage::

    uv run python examples/lp_explorer.py path/to/big.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import panel as pn
import polars as pl

from antalens import io
from antalens.dash import Dashboard, SectionTitle
from antalens.lens import Lens


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python examples/lp_explorer.py <path.csv>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"No file at {path}")
        sys.exit(1)

    print(f"Loading {path} (this may take a moment for large files)...")
    ds = io.load_csv(
        path,
        name=path.stem,
        # 'absolute_time_index' is a numeric column we want as the time axis.
        # Without this override, schema inference would pick whatever it
        # thinks looks temporal, which on this schema is nothing.
        time_col="absolute_time_index",
    )

    # Discover the cardinality of the discriminator columns by collecting
    # just those two columns. Cheap on lazy frames — polars only reads
    # the relevant column data.
    print("Scanning output and scenario values...")
    discriminators = ds.to_lazy().select(["output", "scenario_index"]).unique().collect()
    output_options = sorted(discriminators["output"].drop_nulls().unique().to_list())
    scenario_options = sorted(discriminators["scenario_index"].drop_nulls().unique().to_list())
    print(f"  outputs:   {output_options}")
    print(f"  scenarios: {scenario_options}")

    if not output_options:
        print("No values in the 'output' column.")
        sys.exit(1)

    # Pick a default output that's most likely to be plottable.
    # 'p' is power dispatch — that's almost always the most useful slice.
    # Fall back to the first available output otherwise.
    default_output = "p" if "p" in output_options else output_options[0]
    default_scenario = scenario_options[0] if scenario_options else 0

    # The Lens parameters we'll wire to the dropdowns. We re-use the
    # generic 'variable' / 'mc' parameters from base Lens — the names
    # don't have to match the column names.
    lens = Lens(variable=default_output, mc=str(default_scenario))

    # Reactive filter chain:
    #   - filter output= lens.variable  (drives the 'output' column)
    #   - filter scenario_index= lens.mc (drives 'scenario_index', cast)
    # Both fire on dropdown change.
    def _scenario_int_transform(s: str) -> int:
        try:
            return int(s)
        except (TypeError, ValueError):
            return 0

    # Because lens.mc is a string param but scenario_index is int,
    # we filter manually inside a pn.bind callback for that column.
    # The output filter is reactive directly through the lens.
    reactive_ds = ds.filter(output=lens.param.variable)

    # The scenario filter needs a string→int conversion that filter()
    # doesn't currently do for us. Use a side filter via pn.bind.
    @pn.depends(lens.param.mc, watch=False)  # type: ignore
    def _scenario_filtered(mc_str: str) -> pl.DataFrame:
        mc_int = _scenario_int_transform(mc_str)
        return reactive_ds.to_lazy().filter(pl.col("scenario_index") == mc_int).collect()

    # ── Charts ──────────────────────────────────────────────────────────
    # Build a Dataset wrapper around the further-filtered LF for plotting.
    # We freshly build it inside the reactive function so it picks up
    # both lens parameters.
    def _build_charts(*_args):  # type: ignore
        from antalens.data.dataset import Dataset

        mc_int = _scenario_int_transform(lens.mc)
        # Apply both filters statically to a snapshot Dataset.
        snapshot_lf = (
            ds.to_lazy()
            .filter(pl.col("output") == lens.variable)
            .filter(pl.col("scenario_index") == mc_int)
        )
        snapshot = Dataset(
            snapshot_lf,
            name=f"{path.stem} · {lens.variable} · scenario {mc_int}",
        )

        # Diagnostic — print a summary so we can see what's actually
        # being plotted at each lens change.
        df = snapshot.to_dataframe()
        n_components = df["component"].n_unique() if df.height else 0
        print(
            f"  → output={lens.variable}, scenario={mc_int}: "
            f"{df.height:,} rows, {n_components} components"
        )

        if df.height == 0:
            return pn.pane.Markdown(f"_No rows for output={lens.variable}, scenario={mc_int}._")  # type: ignore

        # Bar: mean value per component (top 20 to keep readable)
        top_components = (
            df.group_by("component")
            .agg(pl.col("value").mean().alias("__mean"))
            .sort("__mean", descending=True)
            .head(20)["component"]
            .to_list()
        )
        df_top = df.filter(pl.col("component").is_in(top_components))
        snapshot_top = Dataset(df_top.lazy(), name=snapshot.name)

        bar = snapshot_top.plot.bar(
            x="component",
            y="value",
            agg="mean",
            sort="desc",
            sizing_mode="stretch_width",
            height=300,
        )
        ts = snapshot_top.plot.timeseries(
            "value",
            by="component",
            sizing_mode="stretch_width",
            height=320,
        )
        return pn.Column(bar, ts, sizing_mode="stretch_width")

    charts = pn.bind(_build_charts, lens.param.variable, lens.param.mc)

    # ── Controls ────────────────────────────────────────────────────────
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

    output_picker = pn.widgets.Select.from_param(
        lens.param.variable,
        options=output_options,
        name="Output",
        stylesheets=[WIDGET_CSS],
        sizing_mode="stretch_width",
    )
    scenario_picker = pn.widgets.Select.from_param(
        lens.param.mc,
        options=[str(s) for s in scenario_options],
        name="Scenario",
        stylesheets=[WIDGET_CSS],
        sizing_mode="stretch_width",
    )

    # ── Dashboard ───────────────────────────────────────────────────────
    dash = Dashboard(
        title=path.stem,
        subtitle=f"{len(output_options)} outputs · {len(scenario_options)} scenarios",
        lens=lens,
    )
    dash.add_control(SectionTitle("Slice"))
    dash.add_control(output_picker)
    dash.add_control(scenario_picker)
    dash.add_control(SectionTitle("Notes"))
    dash.add_control(
        pn.pane.Markdown(
            "Showing top-20 components by mean value. "
            "Bar = mean across time. Time series = value per component.",
            margin=(4, 0, 0, 0),
        )  # type: ignore
    )
    dash.add_pane(charts, width_pct=100)
    dash.add_status_item("LIVE")
    dash.add_status_item(f"FILE: {path.name}")
    dash.add_status_item("antalens v0.2-dev")

    print("Serving on http://localhost:5006 ...")
    dash.serve(port=5006)


if __name__ == "__main__":
    main()
