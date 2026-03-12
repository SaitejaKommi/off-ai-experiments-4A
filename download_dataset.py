#!/usr/bin/env python3
"""
download_dataset.py - Download a local subset of the Open Food Facts dataset.

This creates a curated Canada-only off_dev.parquet using one of two strategies:
    1. Streaming via huggingface_hub (fast, memory-efficient) — DEFAULT
    2. DuckDB parquet scan from a local or remote source

By default the script keeps only the columns used by the search stack and
limits the output to 50,000 Canadian products so DuckDB stays fast in dev.

Usage:
        python download_dataset.py
        python download_dataset.py --limit 20000
        python download_dataset.py --method duckdb --source-parquet off_products.parquet
        python download_dataset.py --all-columns
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List

OUTPUT_FILE = "off_dev.parquet"
HF_DATASET = "openfoodfacts/product-database"
HF_PARQUET_URL = (
    "https://huggingface.co/datasets/openfoodfacts/product-database"
    "/resolve/main/food.parquet"
)
DEFAULT_LIMIT = 50_000
DEFAULT_COUNTRY_TAG = "en:canada"

DEV_COLUMNS = [
    "code",
    "product_name",
    "brands",
    "categories",
    "categories_tags",
    "labels",
    "labels_tags",
    "ingredients_text",
    "ingredients_tags",
    "nutriscore_grade",
    "nova_group",
    "ecoscore_grade",
    "image_url",
    "images",
    "url",
    "additives_tags",
    "additives_n",
    "unique_scans_n",
    "countries_tags",
    "proteins_100g",
    "sugars_100g",
    "energy_kcal_100g",
    "fat_100g",
    "saturated_fat_100g",
    "carbohydrates_100g",
    "sodium_100g",
    "salt_100g",
    "fiber_100g",
]

FIELD_CANDIDATES = {
    "code": ["code", "_id"],
    "product_name": ["product_name", "product_name_en", "product_name_fr", "generic_name"],
    "brands": ["brands"],
    "categories": ["categories", "categories_tags"],
    "categories_tags": ["categories_tags", "categories"],
    "labels": ["labels", "labels_tags"],
    "labels_tags": ["labels_tags", "labels"],
    "ingredients_text": ["ingredients_text"],
    "ingredients_tags": ["ingredients_tags"],
    "nutriscore_grade": ["nutriscore_grade", "nutrition_grade_fr"],
    "nova_group": ["nova_group"],
    "ecoscore_grade": ["ecoscore_grade"],
    "image_url": ["image_url", "image_front_url"],
    "images": ["images"],
    "url": ["url", "link"],
    "additives_tags": ["additives_tags"],
    "additives_n": ["additives_n", "new_additives_n"],
    "unique_scans_n": ["unique_scans_n", "scans_n"],
    "countries_tags": ["countries_tags", "main_countries_tags"],
}

NUTRIENT_FIELDS = [
    "proteins_100g",
    "sugars_100g",
    "energy_kcal_100g",
    "fat_100g",
    "saturated_fat_100g",
    "carbohydrates_100g",
    "sodium_100g",
    "salt_100g",
    "fiber_100g",
]

NUTRIENT_ALIASES = {
    "proteins_100g": ["proteins_100g", "nutriments.proteins_100g"],
    "sugars_100g": ["sugars_100g", "nutriments.sugars_100g"],
    "energy_kcal_100g": ["energy_kcal_100g", "energy-kcal_100g", "nutriments.energy_kcal_100g"],
    "fat_100g": ["fat_100g", "nutriments.fat_100g"],
    "saturated_fat_100g": ["saturated_fat_100g", "saturated-fat_100g", "nutriments.saturated_fat_100g"],
    "carbohydrates_100g": ["carbohydrates_100g", "nutriments.carbohydrates_100g"],
    "sodium_100g": ["sodium_100g", "nutriments.sodium_100g"],
    "salt_100g": ["salt_100g", "nutriments.salt_100g"],
    "fiber_100g": ["fiber_100g", "fibre_100g", "nutriments.fiber_100g", "nutriments.fibre_100g"],
}

NUTRIMENT_LIST_NAMES = {
    "proteins_100g": ["proteins", "protein"],
    "sugars_100g": ["sugars", "sugar"],
    "energy_kcal_100g": ["energy-kcal", "energy_kcal", "energy"],
    "fat_100g": ["fat", "fats"],
    "saturated_fat_100g": ["saturated-fat", "saturated_fat", "saturated fat"],
    "carbohydrates_100g": ["carbohydrates", "carbohydrate", "carbs"],
    "sodium_100g": ["sodium"],
    "salt_100g": ["salt"],
    "fiber_100g": ["fiber", "fibre"],
}


def _quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _load_schema_from_parquet(connection: object, source: str) -> dict[str, str]:
    rows = connection.execute(f"DESCRIBE SELECT * FROM read_parquet('{source}')").fetchall()
    return {row[0]: row[1] for row in rows}


def _load_schema_from_relation(connection: object, relation: str) -> dict[str, str]:
    rows = connection.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()
    return {row[0]: row[1] for row in rows}


def _resolve_struct_field(schema: dict[str, str], parent_field: str, candidate: str) -> str | None:
    if "." not in candidate:
        return None
    parent, child = candidate.split(".", 1)
    if parent != parent_field:
        return None
    parent_schema = schema.get(parent_field, "")
    if child in parent_schema:
        return f"{_quote_ident(parent_field)}.{_quote_ident(child)}"
    return None


def _resolve_field_expression(schema: dict[str, str], logical_name: str) -> str | None:
    for candidate in FIELD_CANDIDATES.get(logical_name, []):
        if candidate in schema:
            return _quote_ident(candidate)
    return None


def _resolve_nutrient_expression(schema: dict[str, str], nutrient_name: str) -> str | None:
    for candidate in NUTRIENT_ALIASES[nutrient_name]:
        if candidate in schema:
            return _quote_ident(candidate)
        struct_expr = _resolve_struct_field(schema, "nutriments", candidate)
        if struct_expr is not None:
            return struct_expr
    return None


def _resolve_nutriment_list_expression(schema: dict[str, str], nutrient_name: str) -> str | None:
    nutriments_type = schema.get("nutriments", "")
    if not nutriments_type.endswith("[]"):
        return None

    names = NUTRIMENT_LIST_NAMES.get(nutrient_name, [])
    if not names:
        return None

    quoted_names = ", ".join([f"'{name}'" for name in names])
    # OFF variants often store nutriments as LIST<STRUCT{name,100g,value,...}>.
    return (
        "(" 
        "SELECT MAX(COALESCE(TRY_CAST(n.\"100g\" AS DOUBLE), TRY_CAST(n.value AS DOUBLE))) "
        "FROM UNNEST(\"nutriments\") AS u(n) "
        f"WHERE LOWER(COALESCE(CAST(n.name AS VARCHAR), '')) IN ({quoted_names})"
        ")"
    )


def _build_duckdb_projection(schema: dict[str, str], include_all_columns: bool) -> str:
    if include_all_columns:
        return "*"

    select_parts: List[str] = []
    for logical_name in DEV_COLUMNS:
        if logical_name in NUTRIENT_FIELDS:
            expr = _resolve_nutrient_expression(schema, logical_name)
            if expr is None:
                expr = _resolve_nutriment_list_expression(schema, logical_name)
        else:
            expr = _resolve_field_expression(schema, logical_name)

        if expr is None:
            select_parts.append(f"NULL AS {_quote_ident(logical_name)}")
        else:
            select_parts.append(f"{expr} AS {_quote_ident(logical_name)}")

    return ",\n            ".join(select_parts)


def _is_canada_record(record: dict, country_tag: str) -> bool:
    tags = record.get("countries_tags") or []
    normalized_country = country_tag.lower()
    if isinstance(tags, str):
        haystack = tags.lower()
        return normalized_country in haystack or "canada" in haystack
    if isinstance(tags, (list, tuple, set)):
        return any(str(tag).lower() == normalized_country for tag in tags)
    return False


def _project_record(record: dict, include_all_columns: bool) -> dict:
    if include_all_columns:
        return dict(record)
    return {column: record.get(column) for column in DEV_COLUMNS}


def _resolve_source_parquet(source_parquet: str | None) -> str:
    if source_parquet:
        return source_parquet

    local_candidate = Path("off_products.parquet")
    if local_candidate.exists():
        return str(local_candidate)

    return HF_PARQUET_URL


# ---------------------------------------------------------------------------
# Strategy 1: huggingface_hub streaming (preferred)
# ---------------------------------------------------------------------------

def _stream_via_hf(limit: int, output_file: str, include_all_columns: bool, country_tag: str) -> None:
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
        if _is_canada_record(record, country_tag):
            rows.append(_project_record(record, include_all_columns))
            if len(rows) % 5000 == 0:
                print(f"  Collected {len(rows):,} rows...", flush=True)
            if len(rows) >= limit:
                break
        seen += 1
        if seen % 100_000 == 0:
            print(f"  Scanned {seen:,} total records...", flush=True)

    print(f"Writing {len(rows):,} rows to {output_file}...")
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, output_file, compression="snappy")


# ---------------------------------------------------------------------------
# Strategy 2: DuckDB httpfs scan (fallback)
# ---------------------------------------------------------------------------

def _scan_via_duckdb(
    limit: int,
    output_file: str,
    source_parquet: str | None,
    include_all_columns: bool,
    country_tag: str,
) -> None:
    try:
        import duckdb
    except ImportError:
        print("ERROR: duckdb not installed. Run: pip install duckdb")
        sys.exit(1)

    source = _resolve_source_parquet(source_parquet)

    print("Connecting to DuckDB...")
    con = duckdb.connect()
    if source.startswith("https://"):
        print("Loading DuckDB httpfs extension for remote parquet access...")
        con.execute("INSTALL httpfs; LOAD httpfs;")
    print("Creating curated Canada-only dev parquet...")
    print(f"  Source: {source}")
    safe_country_tag = country_tag.replace("'", "''")
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE off_subset AS
        SELECT *
        FROM read_parquet('{source}')
        WHERE CAST(countries_tags AS VARCHAR) ILIKE '%{safe_country_tag}%'
        LIMIT {limit}
    """)

    schema = _load_schema_from_relation(con, "off_subset")
    projection = _build_duckdb_projection(schema, include_all_columns)

    con.execute(f"""
        COPY (
            SELECT {projection}
            FROM off_subset
        )
        TO '{output_file}' (FORMAT PARQUET)
    """)
    con.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Download OFF dev dataset")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"Max Canadian products to download (default: {DEFAULT_LIMIT})")
    parser.add_argument("--method", choices=["stream", "duckdb"], default="stream",
                        help="Download method (default: stream)")
    parser.add_argument("--output", default=OUTPUT_FILE,
                        help=f"Output parquet path (default: {OUTPUT_FILE})")
    parser.add_argument("--source-parquet", default=None,
                        help="Local parquet path to curate when using --method duckdb (defaults to off_products.parquet if present)")
    parser.add_argument("--country-tag", default=DEFAULT_COUNTRY_TAG,
                        help=f"Country tag to keep (default: {DEFAULT_COUNTRY_TAG})")
    parser.add_argument("--all-columns", action="store_true",
                        help="Keep all source columns instead of the lean search schema")
    args = parser.parse_args()

    print(f"OFF AI - Dataset Downloader")
    print(f"  Output : {args.output}")
    print(f"  Limit  : {args.limit:,} rows")
    print(f"  Method : {args.method}")
    print(f"  Country: {args.country_tag}")
    if args.method == "duckdb":
        print(f"  Source : {_resolve_source_parquet(args.source_parquet)}")
    print(f"  Columns: {'all source columns' if args.all_columns else f'{len(DEV_COLUMNS)} lean search columns'}")
    print()

    start = time.time()

    if args.method == "duckdb":
        _scan_via_duckdb(
            args.limit,
            args.output,
            args.source_parquet,
            args.all_columns,
            args.country_tag,
        )
    else:
        _stream_via_hf(
            args.limit,
            args.output,
            args.all_columns,
            args.country_tag,
        )

    elapsed = time.time() - start

    # Verify output
    try:
        import duckdb
        con = duckdb.connect()
        row_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{args.output}')").fetchone()[0]
        column_count = len(con.execute(f"DESCRIBE SELECT * FROM read_parquet('{args.output}')").fetchall())
        con.close()
        print(f"\nDone in {elapsed:.1f}s — {row_count:,} rows and {column_count} columns saved to {args.output}")
    except Exception:
        print(f"\nDone in {elapsed:.1f}s — saved to {args.output}")

    print()
    if Path(args.output).name == OUTPUT_FILE:
        print("The API will use this file automatically (it prefers off_dev.parquet by default).")
    print(f"Or set the path explicitly:  $env:OFF_PARQUET_PATH = \"{args.output}\"")


if __name__ == "__main__":
    main()
