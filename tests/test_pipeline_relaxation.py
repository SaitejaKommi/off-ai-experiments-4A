from __future__ import annotations

from pathlib import Path

import duckdb

from off_ai.pipeline import FoodIntelligencePipeline


def test_high_protein_query_does_not_allow_missing_nutrients(tmp_path: Path):
    parquet_file = tmp_path / "off_relaxation.parquet"
    con = duckdb.connect()
    con.execute(
        """
        COPY (
            SELECT *
            FROM (
                VALUES
                    ('1', 'Sparkling Water', 'TestBrand', 'beverages', ['en:beverages'], 'a', 1, NULL, 0.0),
                    ('2', 'Snack Mix Zero Protein', 'TestBrand', 'snacks', ['en:snacks'], 'b', 3, NULL, 0.0)
            ) AS t(code, product_name, brands, categories, categories_tags, nutriscore_grade, nova_group, proteins_100g, sugars_100g)
        ) TO ? (FORMAT parquet)
        """,
        [str(parquet_file)],
    )
    con.close()

    pipeline = FoodIntelligencePipeline(max_results=10)
    pipeline._adapter = pipeline._adapter.__class__(parquet_path=str(parquet_file))

    result = pipeline.run("high protein snack")

    assert result.products == []
    assert "allowing missing nutrient values" not in result.relaxation_log


def test_pipeline_removes_keywords_before_dropping_category(tmp_path: Path):
    parquet_file = tmp_path / "off_relaxation_keywords.parquet"
    con = duckdb.connect()
    con.execute(
        """
        COPY (
            SELECT *
            FROM (
                VALUES
                    ('10', 'Simple Rice Crackers', 'TestBrand', 'snacks', ['en:salty-snacks'], 'b', 2, 4.0, 1.0)
            ) AS t(code, product_name, brands, categories, categories_tags, nutriscore_grade, nova_group, proteins_100g, sugars_100g)
        ) TO ? (FORMAT parquet)
        """,
        [str(parquet_file)],
    )
    con.close()

    pipeline = FoodIntelligencePipeline(max_results=10)
    pipeline._adapter = pipeline._adapter.__class__(parquet_path=str(parquet_file))

    result = pipeline.run("snack xyznonexistent")

    assert result.products
    assert any("keywords removed to broaden in-category match" in item for item in result.relaxation_log)
    assert not any("category constraint removed" in item for item in result.relaxation_log)


def test_pipeline_relaxes_dietary_tags_before_dropping_category(tmp_path: Path):
    parquet_file = tmp_path / "off_relaxation_dietary.parquet"
    con = duckdb.connect()
    con.execute(
        """
        COPY (
            SELECT *
            FROM (
                VALUES
                    ('20', 'Classic Butter Cookies', 'TestBrand', 'cookies', ['en:cookies'], 'c', 3, 6.0, 20.0),
                    ('21', 'Plain Milk', 'TestBrand', 'milk', ['en:milk'], 'b', 2, 3.0, 5.0)
            ) AS t(code, product_name, brands, categories, categories_tags, nutriscore_grade, nova_group, proteins_100g, sugars_100g)
        ) TO ? (FORMAT parquet)
        """,
        [str(parquet_file)],
    )
    con.close()

    pipeline = FoodIntelligencePipeline(max_results=10)
    pipeline._adapter = pipeline._adapter.__class__(parquet_path=str(parquet_file))

    result = pipeline.run("gluten free cookies")

    assert result.products
    assert any("dietary tags removed to preserve category match" in item for item in result.relaxation_log)
    assert not any("category constraint removed" in item for item in result.relaxation_log)
    assert all("cookies" in " ".join(product.categories).lower() for product in result.products)
