"""Tests for :mod:`antalens.data.schema`."""

from __future__ import annotations

from datetime import datetime

import polars as pl
import pytest

from antalens.data.schema import Schema, infer_schema

# ─── time column detection ─────────────────────────────────────────────────


def test_detects_datetime_dtype_as_time_col() -> None:
    df = pl.DataFrame(
        {
            "ts": [datetime(2025, 1, 1), datetime(2025, 1, 2)],
            "value": [1.0, 2.0],
        }
    )
    schema = infer_schema(df.lazy())
    assert schema.time_col == "ts"


def test_detects_time_col_by_name_hint_when_no_temporal_dtype() -> None:
    df = pl.DataFrame({"timestamp": [1, 2, 3], "value": [10, 20, 30]})
    schema = infer_schema(df.lazy())
    assert schema.time_col == "timestamp"


def test_prefers_temporal_dtype_over_name_hint() -> None:
    df = pl.DataFrame(
        {
            "time": [1, 2, 3],  # name hint, but integer dtype
            "actual_ts": [datetime(2025, 1, 1), datetime(2025, 1, 2), datetime(2025, 1, 3)],
        }
    )
    schema = infer_schema(df.lazy())
    assert schema.time_col == "actual_ts"


def test_no_time_col_when_nothing_matches() -> None:
    df = pl.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0]})
    schema = infer_schema(df.lazy())
    assert schema.time_col is None


def test_time_col_override_works() -> None:
    df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
    schema = infer_schema(df.lazy(), time_col="a")
    assert schema.time_col == "a"


def test_time_col_override_with_empty_string_means_no_time() -> None:
    df = pl.DataFrame({"timestamp": [datetime(2025, 1, 1)], "value": [1.0]})
    schema = infer_schema(df.lazy(), time_col="")
    assert schema.time_col is None


def test_time_col_override_must_exist() -> None:
    df = pl.DataFrame({"a": [1, 2]})
    with pytest.raises(ValueError, match="does not exist"):
        infer_schema(df.lazy(), time_col="missing")


# ─── categorical detection ─────────────────────────────────────────────────


def test_low_cardinality_string_is_categorical() -> None:
    df = pl.DataFrame(
        {
            "ts": [datetime(2025, 1, 1)] * 6,
            "fuel": ["nuclear", "wind", "solar", "nuclear", "wind", "gas"],
            "load": [50.0] * 6,
        }
    )
    schema = infer_schema(df.lazy())
    assert "fuel" in schema.categorical_cols
    assert sorted(schema.categorical_cols["fuel"]) == ["gas", "nuclear", "solar", "wind"]


def test_high_cardinality_string_is_not_categorical() -> None:
    df = pl.DataFrame(
        {
            "id": [f"user_{i}" for i in range(300)],
            "value": [1.0] * 300,
        }
    )
    schema = infer_schema(df.lazy())
    assert "id" not in schema.categorical_cols
    # And not in numeric either — it's an unknown / free-form string
    assert "id" not in schema.numeric_cols


def test_cardinality_limit_is_configurable() -> None:
    df = pl.DataFrame({"x": [f"v{i}" for i in range(50)], "y": [1.0] * 50})
    schema = infer_schema(df.lazy(), cardinality_limit=10)
    assert "x" not in schema.categorical_cols

    schema_lax = infer_schema(df.lazy(), cardinality_limit=100)
    assert "x" in schema_lax.categorical_cols


def test_categorical_dtype_treated_as_categorical() -> None:
    df = pl.DataFrame({"cat": pl.Series(["a", "b", "a"], dtype=pl.Categorical)})
    schema = infer_schema(df.lazy())
    assert "cat" in schema.categorical_cols


# ─── numeric detection ─────────────────────────────────────────────────────


def test_int_and_float_columns_are_numeric() -> None:
    df = pl.DataFrame(
        {
            "ts": [datetime(2025, 1, 1)],
            "i": pl.Series([1], dtype=pl.Int64),
            "f": pl.Series([1.5], dtype=pl.Float64),
        }
    )
    schema = infer_schema(df.lazy())
    assert set(schema.numeric_cols) == {"i", "f"}


def test_time_col_is_not_in_numeric_cols() -> None:
    df = pl.DataFrame({"timestamp": [1, 2, 3], "value": [10, 20, 30]})
    schema = infer_schema(df.lazy())
    assert "timestamp" not in schema.numeric_cols
    assert "value" in schema.numeric_cols


# ─── geo columns ────────────────────────────────────────────────────────────


def test_lat_lon_detected_as_geo() -> None:
    df = pl.DataFrame({"lat": [48.8], "lon": [2.3], "value": [1.0]})
    schema = infer_schema(df.lazy())
    assert schema.geo_cols == ["lat", "lon"]


def test_area_id_detected_as_geo() -> None:
    df = pl.DataFrame({"area_id": ["FR"], "value": [1.0]})
    schema = infer_schema(df.lazy())
    assert schema.geo_cols == ["area_id"]


def test_no_geo_cols_returns_none() -> None:
    df = pl.DataFrame({"x": [1.0], "y": [2.0]})
    schema = infer_schema(df.lazy())
    assert schema.geo_cols is None


def test_geo_col_excluded_from_numeric() -> None:
    df = pl.DataFrame({"lat": [48.8], "lon": [2.3], "load": [50.0]})
    schema = infer_schema(df.lazy())
    assert "lat" not in schema.numeric_cols
    assert "lon" not in schema.numeric_cols
    assert "load" in schema.numeric_cols


# ─── Schema methods ────────────────────────────────────────────────────────


def test_schema_has_returns_true_for_known_columns() -> None:
    schema = Schema(
        time_col="ts",
        categorical_cols={"area": ["FR", "DE"]},
        numeric_cols=["load"],
        geo_cols=["lat"],
    )
    assert schema.has("ts")
    assert schema.has("area")
    assert schema.has("load")
    assert schema.has("lat")
    assert not schema.has("missing")


def test_schema_kind_of_classifies_columns() -> None:
    schema = Schema(
        time_col="ts",
        categorical_cols={"area": ["FR"]},
        numeric_cols=["load"],
        geo_cols=["lat"],
    )
    assert schema.kind_of("ts") == "time"
    assert schema.kind_of("area") == "categorical"
    assert schema.kind_of("load") == "numeric"
    assert schema.kind_of("lat") == "geo"
    assert schema.kind_of("missing") == "unknown"


def test_schema_is_frozen() -> None:
    schema = Schema()
    with pytest.raises((AttributeError, TypeError)):
        schema.time_col = "x"  # type: ignore[misc]
