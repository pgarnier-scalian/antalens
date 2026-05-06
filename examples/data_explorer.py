"""Minimal demo: load → reactive filter → plot → serve.

Run: python examples/data_explorer.py <path.parquet|.csv>
"""

from __future__ import annotations

import sys
from pathlib import Path

import panel as pn

from antalens import io
from antalens.lens import Lens


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python examples/data_explorer.py <path>")
        sys.exit(1)

    path = Path(sys.argv[1])
    loader = io.load_csv if path.suffix.lower() == ".csv" else io.load_parquet
    ds = loader(path, name=path.stem)

    if not ds.schema.numeric_cols or not ds.schema.categorical_cols:
        print(f"Need at least one numeric + one categorical column. Schema: {ds.schema}")
        sys.exit(1)

    y = ds.schema.numeric_cols[0]
    filter_col = next(iter(ds.schema.categorical_cols))
    options = ds.schema.categorical_cols[filter_col]

    lens = Lens(variable=options[0])
    reactive_ds = ds.filter(**{filter_col: lens.param.variable})
    pane = reactive_ds.plot.timeseries(y, sizing_mode="stretch_width", height=400)
    picker = pn.widgets.Select.from_param(
        lens.param.variable,
        options=options,
        name=filter_col,
    )

    layout = pn.Column(
        f"# {path.stem}",
        f"Filtering **{filter_col}**, plotting **{y}**",
        picker,
        pane,
        sizing_mode="stretch_width",
    )
    pn.serve(layout, port=5006, show=True)  # type: ignore


if __name__ == "__main__":
    main()
