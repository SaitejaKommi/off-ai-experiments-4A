"""Tests for constraint extraction, taxonomy mapping, and post-processing layers."""

from off_ai.constraint_extractor import ConstraintExtractor
from off_ai.intent_parser import FoodQuery, NutrientConstraint
from off_ai.post_processor import RankingPostProcessor
from off_ai.taxonomy_mapper import TaxonomyMapper


def test_constraint_extractor_builds_flat_interpreted_query():
    extractor = ConstraintExtractor()
    query = FoodQuery(
        raw_text="healthy vegan snacks under 300 calories with over 10g protein",
        category="snacks",
        nutrient_constraints=[
            NutrientConstraint("energy_kcal_100g", "<=", 300.0, "kcal"),
            NutrientConstraint("proteins_100g", ">=", 10.0, "g"),
        ],
        dietary_tags=["vegan"],
        search_terms=["healthy", "snacks"],
    )

    constraints = extractor.extract(query)
    interpreted = constraints.interpreted_query()

    assert interpreted["category"] == "snacks"
    assert interpreted["calories_max"] == 300.0
    assert interpreted["protein_min"] == 10.0
    assert interpreted["vegan"] is True


def test_taxonomy_mapper_maps_user_terms_to_off_tags():
    extractor = ConstraintExtractor()
    mapper = TaxonomyMapper()

    query = FoodQuery(raw_text="kids cereal", category="cereal")
    constraints = extractor.extract(query)
    mapped = mapper.map_constraints(constraints)

    assert mapped.category_tag == "en:breakfast-cereals"


def test_taxonomy_mapper_normalizes_requested_categories():
    extractor = ConstraintExtractor()
    mapper = TaxonomyMapper()

    for user_category, expected in [
        ("soup", "en:soups"),
        ("cookies", "en:cookies"),
        ("bars", "en:snack-bars"),
        ("chips", "en:chips"),
    ]:
        constraints = extractor.extract(FoodQuery(raw_text=user_category, category=user_category))
        mapped = mapper.map_constraints(constraints)
        assert mapped.category_tag == expected


def test_post_processor_relaxation_and_rationale():
    processor = RankingPostProcessor()
    constraints = ConstraintExtractor().extract(
        FoodQuery(
            raw_text="protein bars under 200 calories",
            category="protein bars",
            nutrient_constraints=[
                NutrientConstraint("proteins_100g", ">=", 10.0, "g"),
                NutrientConstraint("energy_kcal_100g", "<=", 200.0, "kcal"),
            ],
        )
    )

    relaxed, changes = processor.relax_nutrients(constraints)
    assert relaxed.nutrient_constraints[0].value < 10.0
    assert relaxed.nutrient_constraints[1].value > 200.0
    assert changes

    removed, category_changes = processor.remove_category(relaxed)
    assert removed.category is None
    assert category_changes
    assert "category constraint removed" in category_changes[0]

    rationale = processor.ranking_rationale(
        has_category=True,
        has_dietary_tags=True,
        nutrient_constraints=constraints.nutrient_constraints,
    )
    assert "Best Nutri-Score" in rationale
    assert "Low Energy Kcal" in rationale
