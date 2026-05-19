"""Tests for :class:`antalens.data.simulation_table.SimulationTable`."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from antalens.data.dataset import Dataset
from antalens.data.simulation_table import SimulationTable

# ─── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def sim_df() -> pl.DataFrame:
    """A minimal valid GEMS SimulationTable in DataFrame form."""
    rows = []
    for component in ["gen_FR", "gen_DE"]:
        for output in ["p", "p_nom"]:
            for scenario in [0, 1]:
                for t in range(1, 25):  # 24 hours
                    rows.append(
                        {
                            "block": 1,
                            "component": component,
                            "output": output,
                            "absolute_time_index": t,
                            "block_time_index": t,
                            "scenario_index": scenario,
                            "value": 50.0 + t,
                            "basis_status": "Free",
                        }
                    )
    return pl.DataFrame(rows)


@pytest.fixture
def sim_table(sim_df: pl.DataFrame) -> SimulationTable:
    return SimulationTable(sim_df.lazy(), name="test")


# ─── construction ─────────────────────────────────────────────────────────


def test_constructs_from_lazyframe(sim_df: pl.DataFrame) -> None:
    sim = SimulationTable(sim_df.lazy())
    assert isinstance(sim, Dataset)
    assert isinstance(sim, SimulationTable)


def test_rejects_missing_canonical_columns() -> None:
    bad = pl.DataFrame({"block": [1], "value": [1.0]})  # missing 6 columns
    with pytest.raises(ValueError, match="GEMS canonical columns"):
        SimulationTable(bad.lazy())


# ─── accessors ────────────────────────────────────────────────────────────


def test_components_returns_distinct(sim_table: SimulationTable) -> None:
    assert sim_table.components == ["gen_DE", "gen_FR"]


def test_outputs_returns_distinct(sim_table: SimulationTable) -> None:
    assert sim_table.outputs == ["p", "p_nom"]


def test_scenarios_returns_distinct_ints(sim_table: SimulationTable) -> None:
    assert sim_table.scenarios == [0, 1]
    assert all(isinstance(s, int) for s in sim_table.scenarios)


def test_blocks_returns_distinct_ints(sim_table: SimulationTable) -> None:
    assert sim_table.blocks == [1]
    assert all(isinstance(b, int) for b in sim_table.blocks)


def test_accessors_are_cached(sim_table: SimulationTable) -> None:
    """Second call returns the same list object — no re-collection."""
    first = sim_table.components
    second = sim_table.components
    assert first is second


# ─── filter overload ──────────────────────────────────────────────────────


def test_filter_by_component(sim_table: SimulationTable) -> None:
    out = sim_table.filter(component="gen_FR").to_dataframe()
    assert set(out["component"].to_list()) == {"gen_FR"}


def test_filter_by_output(sim_table: SimulationTable) -> None:
    out = sim_table.filter(output="p").to_dataframe()
    assert set(out["output"].to_list()) == {"p"}


def test_filter_by_scenario(sim_table: SimulationTable) -> None:
    out = sim_table.filter(scenario=1).to_dataframe()
    assert set(out["scenario_index"].to_list()) == {1}


def test_filter_by_time_range_inclusive(sim_table: SimulationTable) -> None:
    out = sim_table.filter(time_range=(5, 10)).to_dataframe()
    times = out["absolute_time_index"].to_list()
    assert min(times) == 5
    assert max(times) == 10


def test_filter_combines_args(sim_table: SimulationTable) -> None:
    out = sim_table.filter(
        component="gen_FR", output="p", scenario=0, time_range=(1, 3)
    ).to_dataframe()
    assert out.height == 3
    assert set(out["component"].to_list()) == {"gen_FR"}
    assert set(out["output"].to_list()) == {"p"}


def test_filter_returns_simulation_table(sim_table: SimulationTable) -> None:
    """Subclass type is preserved through filter."""
    result = sim_table.filter(output="p")
    assert isinstance(result, SimulationTable)


def test_component_kind_without_catalog_raises(
    sim_table: SimulationTable,
) -> None:
    with pytest.raises(NotImplementedError, match="requires a Catalog"):
        sim_table.filter(component_kind="generator")


# ─── pivot ────────────────────────────────────────────────────────────────


def test_pivot_returns_wide_dataset(sim_table: SimulationTable) -> None:
    """Default pivot produces one column per output."""
    wide = sim_table.filter(component="gen_FR", scenario=0).pivot()
    assert isinstance(wide, Dataset)
    assert not isinstance(wide, SimulationTable)  # pivot drops shape
    df = wide.to_dataframe()
    assert "p" in df.columns
    assert "p_nom" in df.columns


# ─── to_views (stubbed) ───────────────────────────────────────────────────


def test_to_views_raises_not_implemented(sim_table: SimulationTable) -> None:
    with pytest.raises(NotImplementedError, match="ViewsBuilder"):
        sim_table.to_views({})


# ─── load_simulation_table (round-trip) ───────────────────────────────────


def test_load_from_parquet_roundtrip(tmp_path: Path, sim_df: pl.DataFrame) -> None:
    from antalens.io import load_simulation_table

    path = tmp_path / "sim.parquet"
    sim_df.write_parquet(path)

    sim = load_simulation_table(path)
    assert isinstance(sim, SimulationTable)
    assert sim.outputs == ["p", "p_nom"]


def test_load_from_csv_roundtrip(tmp_path: Path, sim_df: pl.DataFrame) -> None:
    from antalens.io import load_simulation_table

    path = tmp_path / "sim.csv"
    sim_df.write_csv(path)

    sim = load_simulation_table(path)
    assert isinstance(sim, SimulationTable)
    assert sim.scenarios == [0, 1]


def test_load_with_scenario_prefilter(tmp_path: Path, sim_df: pl.DataFrame) -> None:
    from antalens.io import load_simulation_table

    path = tmp_path / "sim.parquet"
    sim_df.write_parquet(path)

    sim = load_simulation_table(path, scenarios=[0])
    assert sim.scenarios == [0]


def test_load_rejects_unknown_extension(tmp_path: Path) -> None:
    from antalens.io import load_simulation_table

    bad = tmp_path / "sim.xyz"
    bad.write_text("nope")
    with pytest.raises(ValueError, match="parquet or .csv"):
        load_simulation_table(bad)
