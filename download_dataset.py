#!/usr/bin/env python3
"""
download_dataset.py - Download a local subset of the Open Food Facts dataset.

This creates off_dev.parquet using one of two strategies:
  1. Streaming via huggingface_hub (fast, memory-efficient) — DEFAULT
  2. DuckDB remote parquet scan (fallback, slower)

Usage:
    python download_dataset.py            # stream ~100k Canadian products
    python download_dataset.py --limit 20000   # smaller/faster test set
    python download_dataset.py --method duckdb # use DuckDB scan instead
"""

from __future__ import annotations

import argparse
import sys
import time

OUTPUT_FILE = "off_dev.parquet"
HF_DATASET = "openfoodfacts/product-database"
HF_PARQUET_URL = (
    "https://huggingface.co/datasets/openfoodfacts/product-database"
    "/resolve/main/food.parquet"
)


# ---------------------------------------------------------------------------
# Strategy 1: huggingface_hub streaming (preferred)
# ---------------------------------------------------------------------------

def _stream_via_hf(limit: int) -> None:
    try:
        from datasets import load_dataset  # type: ignore
    except ImportError:
        print("  'datasets' package not found. Trying: pip install datasets")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets", "-q"])
        from datasets import load_dataset  # type: ignore

    try:
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore
    except ImportError:
        print("  'pyarrow' not found. Installing...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyarrow", "-q"])
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore

    print(f"Loading dataset in streaming mode: {HF_DATASET}")
    ds = load_dataset(HF_DATASET, split="food", streaming=True, trust_remote_code=False)

    rows: list = []
    seen = 0
    print(f"Scanning for Canadian products (limit {limit:,})...")
    for record in ds:
        tags = record.get("countries_tags") or []
        if "en:canada" in tags:
            rows.append(record)
            if len(rows) % 5000 == 0:
                print(f"  Collected {len(rows):,} rows...", flush=True)
            if len(rows) >= limit:
                break
        seen += 1
        if seen % 100_000 == 0:
            print(f"  Scanned {seen:,} total records...", flush=True)

    print(f"Writing {len(rows):,} rows to {OUTPUT_FILE}...")
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, OUTPUT_FILE, compression="snappy")


# ---------------------------------------------------------------------------
# Strategy 2: DuckDB httpfs scan (fallback)
# ---------------------------------------------------------------------------

def _scan_via_duckdb(limit: int) -> None:
    try:
        import duckdb
    except ImportError:
        print("ERROR: duckdb not installed. Run: pip install duckdb")
        sys.exit(1)

    print("Connecting to DuckDB and installing httpfs...")
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")

    print(f"Scanning remote parquet (this may take 5-15 minutes)...")
    print(f"  Source: {HF_PARQUET_URL}")
    con.execute(f"""
        COPY (
            SELECT *
            FROM read_parquet('{HF_PARQUET_URL}')
            WHERE list_contains(countries_tags, 'en:canada')
            LIMIT {limit}
        )
        TO '{OUTPUT_FILE}' (FORMAT PARQUET)
    """)
    con.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Download OFF dev dataset")
    parser.add_argument("--limit", type=int, default=100_000,
                        help="Max Canadian products to download (default: 100000)")
    parser.add_argument("--method", choices=["stream", "duckdb"], default="stream",
                        help="Download method (default: stream)")
    args = parser.parse_args()

    print(f"OFF AI - Dataset Downloader")
    print(f"  Output : {OUTPUT_FILE}")
    print(f"  Limit  : {args.limit:,} rows")
    print(f"  Method : {args.method}")
    print()

    start = time.time()

    if args.method == "duckdb":
        _scan_via_duckdb(args.limit)
    else:
        _stream_via_hf(args.limit)

    elapsed = time.time() - start

    # Verify output
    try:
        import duckdb
        con = duckdb.connect()
        row_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{OUTPUT_FILE}')").fetchone()[0]
        con.close()
        print(f"\nDone in {elapsed:.1f}s — {row_count:,} rows saved to {OUTPUT_FILE}")
    except Exception:
        print(f"\nDone in {elapsed:.1f}s — saved to {OUTPUT_FILE}")

    print()
    print("The API will use this file automatically (it checks off_dev.parquet by default).")
    print("Or set the path explicitly:  $env:OFF_PARQUET_PATH = \"off_dev.parquet\"")


if __name__ == "__main__":
    main()
