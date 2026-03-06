"""Tests for the recommendation engine."""

import pytest

from off_ai.data_adapter import Product
from off_ai.recommendation_engine import Recommendation, RecommendationEngine


@pytest.fixture
def engine():
    return RecommendationEngine(min_improvement_ratio=0.0)  # any improvement accepted


def _make_product(
    barcode="0000000000001",
    name="Test Product",
    nutriscore=None,
    nova_group=None,
    nutrients=None,
    additives=None,
    categories=None,
) -> Product:
    additives = additives or []
    return Product(
        barcode=barcode,
        name=name,
        nutrients=nutrients or {},
        nutriscore=nutriscore,
        nova_group=nova_group,
        additives=additives,
        additives_count=len(additives),
        categories=categories or [],
    )


# ---------------------------------------------------------------------------
# Basic recommendation
# ---------------------------------------------------------------------------

class TestBasicRecommendation:
    def test_better_alternative_returned(self, engine):
        reference = _make_product(barcode="001", name="Nutella", nutriscore="e", nova_group=4)
        alternative = _make_product(barcode="002", name="Organic Spread", nutriscore="b", nova_group=2)
        recs = engine.recommend(reference, [reference, alternative])
        assert len(recs) >= 1
        assert any(r.product.barcode == "002" for r in recs)

    def test_same_product_excluded(self, engine):
        p = _make_product(barcode="001", name="Same Product", nutriscore="c")
        recs = engine.recommend(p, [p])
        assert all(r.product.barcode != "001" for r in recs)

    def test_worse_product_excluded(self, engine):
        reference = _make_product(barcode="001", name="Good Product", nutriscore="a", nova_group=1)
        worse = _make_product(barcode="002", name="Worse Product", nutriscore="e", nova_group=4)
        recs = engine.recommend(reference, [reference, worse])
        assert not any(r.product.barcode == "002" for r in recs)

    def test_empty_candidates(self, engine):
        reference = _make_product(barcode="001", name="Product", nutriscore="c")
        recs = engine.recommend(reference, [])
        assert recs == []


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

class TestRanking:
    def test_ranked_in_order(self, engine):
        reference = _make_product(barcode="001", name="Ref", nutriscore="d", nova_group=4)
        better = _make_product(barcode="002", name="Better", nutriscore="b", nova_group=3)
        best = _make_product(barcode="003", name="Best", nutriscore="a", nova_group=1)
        recs = engine.recommend(reference, [reference, better, best])
        assert len(recs) >= 2
        # Ranks should be ascending
        ranks = [r.rank for r in recs]
        assert ranks == sorted(ranks)
        # Best product should be rank 1
        assert recs[0].product.barcode == "003"

    def test_max_recommendations_respected(self):
        eng = RecommendationEngine(min_improvement_ratio=0.0, max_recommendations=2)
        reference = _make_product(barcode="000", name="Ref", nutriscore="e")
        candidates = [
            _make_product(barcode=f"00{i}", name=f"Alt {i}", nutriscore="a")
            for i in range(1, 6)
        ]
        recs = eng.recommend(reference, [reference] + candidates)
        assert len(recs) <= 2


# ---------------------------------------------------------------------------
# Improvements descriptions
# ---------------------------------------------------------------------------

class TestImprovementDescriptions:
    def test_better_nutriscore_described(self, engine):
        reference = _make_product(barcode="001", nutriscore="d")
        better = _make_product(barcode="002", nutriscore="a")
        recs = engine.recommend(reference, [reference, better])
        assert len(recs) >= 1
        improvements = recs[0].improvements
        assert any("nutri-score" in i.lower() or "Nutri" in i for i in improvements)

    def test_lower_sodium_described(self, engine):
        reference = _make_product(
            barcode="001",
            nutriscore="d",
            nutrients={"sodium_100g": 1.0, "sugars_100g": 0.5},
        )
        better = _make_product(
            barcode="002",
            nutriscore="b",
            nutrients={"sodium_100g": 0.1, "sugars_100g": 0.5},
        )
        recs = engine.recommend(reference, [reference, better])
        assert len(recs) >= 1
        improvements = recs[0].improvements
        assert any("sodium" in i.lower() for i in improvements)

    def test_fewer_additives_described(self, engine):
        reference = _make_product(
            barcode="001",
            nutriscore="d",
            additives=["E102", "E211", "E320", "E471"],
        )
        better = _make_product(
            barcode="002",
            nutriscore="b",
            additives=[],
        )
        recs = engine.recommend(reference, [reference, better])
        assert len(recs) >= 1
        improvements = recs[0].improvements
        assert any("additive" in i.lower() for i in improvements)


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

class TestRecommendationSerialization:
    def test_to_dict_keys(self, engine):
        reference = _make_product(barcode="001", nutriscore="d", nova_group=4)
        better = _make_product(barcode="002", nutriscore="a", nova_group=1)
        recs = engine.recommend(reference, [reference, better])
        assert len(recs) >= 1
        d = recs[0].to_dict()
        assert "rank" in d
        assert "product" in d
        assert "insight" in d
        assert "improvements" in d
        assert "score" in d
