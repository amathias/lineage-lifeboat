from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "demo" / "snapshots" / "raw_orders.csv"
DESTINATION = ROOT / "demo" / "snapshots" / "raw_orders.parquet"


def main() -> None:
    source = str(SOURCE).replace("'", "''")
    destination = str(DESTINATION).replace("'", "''")
    duckdb.sql(
        "COPY (SELECT order_id, customer_id, CAST(amount AS DOUBLE) AS amount "
        f"FROM read_csv('{source}', header=true) ORDER BY order_id) "
        f"TO '{destination}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    print(f"generated {DESTINATION} ({DESTINATION.stat().st_size} bytes)")


if __name__ == "__main__":
    main()