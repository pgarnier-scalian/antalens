from datetime import datetime, timedelta

import polars as pl

start = datetime(2025, 1, 1)
hours = list(range(168))
df = pl.DataFrame(
    {
        "ts": [start + timedelta(hours=h) for h in hours] * 3,
        "fuel": ["nuclear"] * 168 + ["wind"] * 168 + ["gas"] * 168,
        "load": [50 + (h % 24) for h in hours]
        + [20 + ((h * 7) % 30) for h in hours]
        + [80 - (h % 24) for h in hours],
    }
)
df.write_parquet("data/demo.parquet")
print(df.head())
