"""Public loader namespace for AntaLens.

Re-exports the loaders from :mod:`antalens.data.loaders` so users can write
``al.io.load_parquet(...)`` instead of reaching into the internal data
package.

The split is intentional: ``antalens.data`` holds implementation, while
``antalens.io`` is the stable public API. Adding a new loader in
``antalens.data.loaders`` requires explicitly re-exporting it here, which
serves as a checkpoint for "is this ready to be promised to users?".
"""

from __future__ import annotations

from antalens.data.loaders import from_dataframe, load_csv, load_parquet

__all__ = [
    "from_dataframe",
    "load_csv",
    "load_parquet",
]
