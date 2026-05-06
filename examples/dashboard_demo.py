"""Multi-pane reactive dashboard. Run after Phase 1 demo data is in place.

Usage: uv run python examples/dashboard_demo.py data/demo.parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

import panel as pn

from antalens import io
from antalens.dash import Dashboard
from antalens.lens import Lens
from antalens.link import link


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python examples/dashboard_demo.py <path>")
        sys.exit(1)

    path = Path(sys.argv[1])
    loader = io.load_csv if path.suffix.lower() == ".csv" else io.load_parquet
    ds = loader(path, name=path.stem)

    if not ds.schema.numeric_cols or not ds.schema.categorical_cols:
        print(f"Need numeric + categorical cols. Schema: {ds.schema}")
        sys.exit(1)

    y = ds.schema.numeric_cols[0]
    filter_col = next(iter(ds.schema.categorical_cols))
    options = ds.schema.categorical_cols[filter_col]

    lens = Lens(variable=options[0])
    reactive_ds = ds.filter(**{filter_col: lens.param.variable})

    picker = pn.widgets.Select.from_param(
        lens.param.variable,
        options=options,
        name=filter_col,
    )

    dash = Dashboard(title=path.stem, subtitle=f"{filter_col} explorer", lens=lens)
    dash.add_control(picker)
    bar_pane = ds.plot.bar(
        x=filter_col, y=y, agg="mean", sort="desc", sizing_mode="stretch_width", height=300
    )
    ts_pane = reactive_ds.plot.timeseries(y, sizing_mode="stretch_width", height=320)

    # Click a bar in the bar pane → updates lens.variable → re-filters ts_pane
    link(bar_pane, on="bar_click", set=lens.param.variable)
    link(ts_pane, on="point_click", set=lens.param.variable, transform=lambda x: None)

    dash.add_pane(ts_pane, width_pct=100)
    dash.add_pane(bar_pane, width_pct=100)
    dash.serve(port=5006)


if __name__ == "__main__":
    main()
