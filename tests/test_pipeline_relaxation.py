from __future__ import annotations

from pathlib import Path

import duckdb

from off_ai.pipeline import FoodIntelligencePipeline
from off_ai.query_preprocessor import QueryPreprocessor


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


def test_pipeline_preserves_keywords_and_category_in_strict_semantic_mode(tmp_path: Path):
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

    assert result.products == []
    assert any("semantic constraints preserved" in item for item in result.relaxation_log)
    assert not any("keywords removed" in item for item in result.relaxation_log)


def test_pipeline_preserves_dietary_tags_and_category_when_no_match(tmp_path: Path):
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

    assert result.products == []
    assert any("semantic constraints preserved" in item for item in result.relaxation_log)
    assert not any("dietary tags removed" in item for item in result.relaxation_log)
    assert not any("category constraint removed" in item for item in result.relaxation_log)


def test_pipeline_preserves_category_and_dietary_for_high_intent_query(tmp_path: Path):
    parquet_file = tmp_path / "off_relaxation_preserve_intent.parquet"
    con = duckdb.connect()
    con.execute(
        """
        COPY (
            SELECT *
            FROM (
                VALUES
                    ('30', 'Protein Yogurt', 'TestBrand', 'dairy', ['en:dairies'], 'vegan', 'a', 2, 12.0, 180.0, 3.0),
                    ('31', 'Salty Snack', 'TestBrand', 'snacks', ['en:salty-snacks'], 'contains-milk', 'b', 3, 2.0, 350.0, 1.0)
            ) AS t(code, product_name, brands, categories, categories_tags, labels, nutriscore_grade, nova_group, proteins_100g, energy_kcal_100g, sugars_100g)
        ) TO ? (FORMAT parquet)
        """,
        [str(parquet_file)],
    )
    con.close()

    pipeline = FoodIntelligencePipeline(max_results=10)
    pipeline._adapter = pipeline._adapter.__class__(parquet_path=str(parquet_file))

    result = pipeline.run("high protein vegan snacks under 300 calories")

    assert result.products == []
    assert any("semantic constraints preserved" in item for item in result.relaxation_log)
    assert not any("category constraint removed" in item for item in result.relaxation_log)


def test_pipeline_french_merge_recovers_protein_constraint_when_translation_drops_it(tmp_path: Path):
    parquet_file = tmp_path / "off_relaxation_fr_merge.parquet"
    con = duckdb.connect()
    con.execute(
        """
        COPY (
            SELECT *
            FROM (
                VALUES
                    ('40', 'Vegan Protein Snack', 'TestBrand', 'snacks', ['en:salty-snacks'], 'vegan', 'a', 2, 11.0, 280.0, 2.0)
            ) AS t(code, product_name, brands, categories, categories_tags, labels, nutriscore_grade, nova_group, proteins_100g, energy_kcal_100g, sugars_100g)
        ) TO ? (FORMAT parquet)
        """,
        [str(parquet_file)],
    )
    con.close()

    pipeline = FoodIntelligencePipeline(max_results=10)
    pipeline._adapter = pipeline._adapter.__class__(parquet_path=str(parquet_file))
    pipeline._preprocessor = QueryPreprocessor(
        translator=lambda _text: "show me vegan snacks under 300 calories"
    )

    result = pipeline.run("montrez moi des en cas vegetaliens riches en proteines avec moins de 300 calories")

    assert any(c.nutrient == "proteins_100g" for c in result.query.nutrient_constraints)
