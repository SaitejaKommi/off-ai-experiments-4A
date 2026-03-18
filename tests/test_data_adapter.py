"""Tests for the DuckDB data adapter."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from off_ai.data_adapter import OFFDataAdapter, Product, _parse_product
from off_ai.intent_parser import FoodQuery, NutrientConstraint


@pytest.fixture
def parquet_path(tmp_path: Path) -> Path:
    parquet_file = tmp_path / "off_canada.parquet"
    connection = duckdb.connect()
    connection.execute(
        """
        COPY (
            SELECT
                code,
                product_name,
                brands,
                categories,
                labels,
                ingredients_text,
                nutriscore_grade,
                nova_group,
                image_url,
                url,
                struct_pack(
                    proteins_100g := proteins_100g,
                    sugars_100g := sugars_100g,
                    energy_kcal_100g := energy_kcal_100g,
                    sodium_100g := sodium_100g,
                    fiber_100g := fiber_100g,
                    fat_100g := fat_100g
                ) AS nutriments
            FROM (
                VALUES
                    ('1', 'Sea Salt Lentil Chips', 'Good Foods', 'snacks, chips', 'vegan, organic', 'lentils, sea salt', 'a', 2, 'https://img/1', 'https://product/1', 12.0, 1.2, 280.0, 0.09, 7.0, 8.0),
                    ('2', 'Sweet Kids Cereal', 'Sugar Town', 'cereals, breakfast cereals', 'vegetarian', 'corn, sugar, salt', 'c', 4, 'https://img/2', 'https://product/2', 4.0, 24.0, 390.0, 0.42, 2.0, 4.0),
                    ('3', 'Plain Oat Crackers', 'North Grain', 'snacks, crackers', 'vegan', 'oats, salt', 'b', 3, 'https://img/3', 'https://product/3', 11.0, 2.5, 260.0, 0.11, 6.0, 7.0)
            ) AS source(
                code,
                product_name,
                brands,
                categories,
                labels,
                ingredients_text,
                nutriscore_grade,
                nova_group,
                image_url,
                url,
                proteins_100g,
                sugars_100g,
                energy_kcal_100g,
                sodium_100g,
                fiber_100g,
                fat_100g
            )
        ) TO ? (FORMAT parquet)
        """,
        [str(parquet_file)],
    )
    connection.close()
    return parquet_file


def test_parse_product_normalizes_nutrients():
    raw = {
        "code": "3017620422003",
        "product_name": "Nutella",
        "brands": "Ferrero",
        "nutriscore_grade": "e",
        "nova_group": 4,
        "nutriments": {
            "energy-kcal_100g": 530.0,
            "sugars_100g": 56.3,
            "fat_100g": 30.9,
            "proteins_100g": 6.3,
        },
        "categories_tags": ["en:spreads", "en:chocolate-spreads"],
    }
    product = _parse_product(raw)
    assert product.barcode == "3017620422003"
    assert product.nutrient("energy_kcal_100g") == 530.0
    assert "spreads" in product.categories


def test_parse_product_normalizes_unknown_grades_to_none():
    raw = {
        "code": "42",
        "product_name": "Mystery Snack",
        "nutriscore_grade": "unknown",
        "ecoscore_grade": "not-applicable",
    }

    product = _parse_product(raw)

    assert product.nutriscore is None
    assert product.ecoscore is None


def test_parse_product_picks_text_from_localized_name_structs():
    raw = {
        "code": "999",
        "product_name": [
            {"lang": "main", "text": "Flocons avoine"},
            {"lang": "en", "text": "Oat Flakes"},
            {"lang": "fr", "text": "Flocons d'avoine"},
        ],
        "brands": "LIDL",
    }
    product = _parse_product(raw)
    assert product.name == "Oat Flakes"


def test_parse_product_derives_image_url_from_images_struct():
    raw = {
        "code": "0000101209159",
        "product_name": "Test Product",
        "images": [
            {
                "key": "front_fr",
                "imgid": 1,
                "rev": 4,
                "sizes": {
                    "100": {"h": 100, "w": 75},
                    "200": {"h": 200, "w": 150},
                    "400": {"h": 400, "w": 300},
                },
            }
        ],
    }
    product = _parse_product(raw)
    assert product.image_url.endswith("/000/010/120/9159/front_fr.4.400.jpg")


def test_parse_product_rewrites_off_world_url_to_canada_site():
    raw = {
        "code": "3017620422003",
        "product_name": "Nutella",
        "url": "https://world.openfoodfacts.org/product/3017620422003/nutella",
    }

    product = _parse_product(raw)

    assert product.product_url == "https://ca.openfoodfacts.org/product/3017620422003/nutella"


def test_parse_product_defaults_missing_off_url_to_canada_site():
    raw = {
        "code": "3017620422003",
        "product_name": "Nutella",
    }

    product = _parse_product(raw)

    assert product.product_url == "https://ca.openfoodfacts.org/product/3017620422003/nutella"


def test_parse_product_replaces_external_url_with_canada_off_product_page():
    raw = {
        "code": "0068826176033",
        "product_name": "Tortilla chips",
        "url": "https://www.presidentschoice.ca/product/pc-kettle-style-blue-corn-tortilla-chips-seasoned-with-sea-salt/21003407_EA",
    }

    product = _parse_product(raw)

    assert product.product_url == "https://ca.openfoodfacts.org/product/0068826176033/tortilla-chips"


def test_product_passes_constraints_works_with_canonical_names():
    product = Product(barcode="1", name="Test", nutrients={"energy_kcal_100g": 150.0})
    constraint = NutrientConstraint("energy_kcal_100g", "<=", 200.0, "kcal")
    assert product.passes_constraints([constraint]) is True


def test_build_search_sql_uses_duckdb_parquet(parquet_path: Path):
    adapter = OFFDataAdapter(parquet_path=str(parquet_path))
    query = FoodQuery(
        raw_text="healthy vegan snacks",
        category="snacks",
        dietary_tags=["vegan"],
        ranking_preferences=["healthy"],
        max_results=5,
    )
    sql, parameters = adapter.build_search_sql(query, limit=5)
    assert "FROM products" in sql
    assert "ILIKE ?" in sql
    assert parameters[-1] == 5


def test_search_returns_matching_products_from_parquet(parquet_path: Path):
    adapter = OFFDataAdapter(parquet_path=str(parquet_path))
    query = FoodQuery(
        raw_text="Show me healthy snacks suitable for a low-sodium diet that are also vegan",
        category="snacks",
        dietary_tags=["vegan"],
        nutrient_constraints=[NutrientConstraint("sodium_100g", "<=", 0.1, "g")],
        ranking_preferences=["healthy"],
        max_results=5,
    )
    results = adapter.search(query)
    assert len(results) == 1
    assert results[0].name == "Sea Salt Lentil Chips"


def test_vegan_filter_does_not_treat_plant_based_categories_as_labels(tmp_path: Path):
    parquet_file = tmp_path / "vegan_labels_only.parquet"
    connection = duckdb.connect()
    connection.execute(
        """
        COPY (
            SELECT
                code,
                product_name,
                categories,
                labels,
                nutriscore_grade,
                sodium_100g
            FROM (
                VALUES
                    ('1', 'Category Only Tortillas', 'Plant-based foods, Snacks', 'Sans conservateurs', 'a', 0.07),
                    ('2', 'Explicit Vegan Crackers', 'Snacks, Crackers', 'Vegan', 'b', 0.02)
            ) AS source(code, product_name, categories, labels, nutriscore_grade, sodium_100g)
        ) TO ? (FORMAT parquet)
        """,
        [str(parquet_file)],
    )
    connection.close()

    adapter = OFFDataAdapter(parquet_path=str(parquet_file))
    query = FoodQuery(raw_text="vegan snacks", category="snacks", dietary_tags=["vegan"], max_results=5)

    results = adapter.search(query)

    assert [product.name for product in results] == ["Explicit Vegan Crackers"]


def test_execute_search_reports_timing(parquet_path: Path):
    adapter = OFFDataAdapter(parquet_path=str(parquet_path))
    execution = adapter.execute_search(FoodQuery(raw_text="vegan snacks", max_results=5))
    assert execution.execution_time_ms >= 0
    assert execution.rows_returned >= 0


def test_find_reference_product_searches_text_fields(parquet_path: Path):
    adapter = OFFDataAdapter(parquet_path=str(parquet_path))
    result = adapter.find_reference_product("sweet kids cereal")
    assert result is not None
    assert result.name == "Sweet Kids Cereal"


def test_product_has_label_supports_french_vegan_synonyms():
    product = Product(barcode="1", name="Test", labels=["Végétalien", "Biologique"])
    assert product.has_label("vegan")
    assert product.has_label("organic")


def test_build_search_sql_vegan_includes_french_label_patterns(parquet_path: Path):
    adapter = OFFDataAdapter(parquet_path=str(parquet_path))
    query = FoodQuery(raw_text="vegan snacks", dietary_tags=["vegan"], max_results=5)
    sql, parameters = adapter.build_search_sql(query, limit=5)
    assert "ILIKE ?" in sql
    assert any("vegetalien" in str(param) for param in parameters)


def test_build_search_sql_calorie_upper_bound_excludes_zero_values(parquet_path: Path):
    adapter = OFFDataAdapter(parquet_path=str(parquet_path))
    query = FoodQuery(
        raw_text="snacks under 390 calories",
        category="snacks",
        nutrient_constraints=[NutrientConstraint("energy_kcal_100g", "<=", 390.0, "kcal")],
        max_results=5,
    )
    sql, _ = adapter.build_search_sql(query, limit=5)
    assert "energy_kcal_100g" in sql
    assert "> 0" in sql
