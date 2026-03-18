from off_ai.data_adapter import Product, QueryExecution
from off_ai.intent_parser import FoodQuery, NutrientConstraint
from off_ai.pipeline import FoodIntelligencePipeline


class _StubAdapter:
    def __init__(self, products):
        self._products = list(products)

    def execute_constraints(self, constraints, allow_missing_nutrients=False, candidate_limit=None):
        return QueryExecution(
            sql="SELECT * FROM products",
            parameters=[],
            products=list(self._products),
            execution_time_ms=0.0,
            rows_returned=len(self._products),
        )

    def health_check(self):
        return {"dataset_available": True}


def test_pipeline_reranks_all_candidates_before_limiting():
    weaker = Product(
        barcode="1",
        name="Average Pick",
        nutrients={"sugars_100g": 18.0, "sodium_100g": 0.4},
        nutriscore="c",
        nova_group=4,
    )
    stronger = Product(
        barcode="2",
        name="Best Pick",
        nutrients={"proteins_100g": 12.0, "fiber_100g": 7.0, "sugars_100g": 2.0, "sodium_100g": 0.08},
        nutriscore="a",
        nova_group=1,
    )
    pipeline = FoodIntelligencePipeline(adapter=_StubAdapter([weaker, stronger]), max_results=1)

    result = pipeline.run_parsed(FoodQuery(raw_text="healthy option", ranking_preferences=["healthy"]))

    assert len(result.results) == 1
    assert result.results[0].product.name == "Best Pick"


def test_rank_results_prioritize_query_match_over_raw_energy_density():
    pipeline = FoodIntelligencePipeline(max_results=5)
    query = FoodQuery(
        raw_text="healthy vegan low sodium snacks",
        category="snacks",
        dietary_tags=["vegan"],
        nutrient_constraints=[NutrientConstraint("sodium_100g", "<=", 0.1, "g")],
        ranking_preferences=["healthy"],
    )
    generic_low_energy = Product(
        barcode="10",
        name="Mixed Vegetables",
        categories=["plant-based foods"],
        labels=["kosher"],
        nutrients={
            "proteins_100g": 2.48,
            "sugars_100g": 3.28,
            "sodium_100g": 0.02,
            "energy_kcal_100g": 184.0,
        },
        nova_group=3,
    )
    strong_snack_match = Product(
        barcode="11",
        name="Vegan Crackers",
        categories=["snacks", "crackers"],
        labels=["vegan"],
        nutrients={
            "proteins_100g": 16.7,
            "sugars_100g": 0.0,
            "sodium_100g": 0.0,
            "energy_kcal_100g": 1750.0,
        },
        nutriscore="a",
        nova_group=3,
    )

    ranked = pipeline._rank_results([generic_low_energy, strong_snack_match], query)

    assert ranked[0].product.name == "Vegan Crackers"