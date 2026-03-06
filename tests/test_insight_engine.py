"""Tests for the insight engine."""

import pytest

from off_ai.data_adapter import Product
from off_ai.insight_engine import InsightEngine, ProductInsight


@pytest.fixture
def engine():
    return InsightEngine()


def _make_product(
    name="Test Product",
    nutriscore=None,
    nova_group=None,
    nutrients=None,
    additives=None,
    labels=None,
) -> Product:
    return Product(
        barcode="0000000000001",
        name=name,
        nutrients=nutrients or {},
        nutriscore=nutriscore,
        nova_group=nova_group,
        additives=additives or [],
        additives_count=len(additives) if additives else 0,
        labels=labels or [],
    )


# ---------------------------------------------------------------------------
# Health classification
# ---------------------------------------------------------------------------

class TestHealthClassification:
    def test_excellent_nutriscore_a(self, engine):
        p = _make_product(nutriscore="a", nova_group=1)
        insight = engine.analyze(p)
        assert insight.health_classification == "Excellent"

    def test_good_nutriscore_b(self, engine):
        p = _make_product(nutriscore="b", nova_group=2)
        insight = engine.analyze(p)
        assert insight.health_classification in ("Good", "Excellent")

    def test_risky_nutriscore_e(self, engine):
        p = _make_product(
            nutriscore="e",
            nova_group=4,
            nutrients={
                "sugars_100g": 30.0,
                "sodium_100g": 1.0,
                "fat_100g": 20.0,
            },
        )
        insight = engine.analyze(p)
        assert insight.health_classification == "Risky"

    def test_moderate_product(self, engine):
        p = _make_product(
            nutriscore="c",
            nova_group=3,
        )
        insight = engine.analyze(p)
        assert insight.health_classification in ("Moderate", "Risky")

    def test_unknown_nutriscore(self, engine):
        p = _make_product()
        insight = engine.analyze(p)
        assert insight.health_classification in ("Excellent", "Good", "Moderate", "Risky")


# ---------------------------------------------------------------------------
# Risk indicators
# ---------------------------------------------------------------------------

class TestRiskIndicators:
    def test_high_sodium_indicator(self, engine):
        p = _make_product(nutrients={"sodium_100g": 1.2})
        insight = engine.analyze(p)
        assert any("sodium" in r.lower() for r in insight.risk_indicators)

    def test_high_sugar_indicator(self, engine):
        p = _make_product(nutrients={"sugars_100g": 30.0})
        insight = engine.analyze(p)
        assert any("sugar" in r.lower() for r in insight.risk_indicators)

    def test_ultra_processed_indicator(self, engine):
        p = _make_product(nova_group=4)
        insight = engine.analyze(p)
        assert any("ultra-processed" in r.lower() or "nova 4" in r.lower() for r in insight.risk_indicators)

    def test_risky_additive_indicator(self, engine):
        p = _make_product(additives=["E102", "E211"])
        insight = engine.analyze(p)
        assert any("E102" in r or "E211" in r for r in insight.risk_indicators)

    def test_no_false_positive_low_sodium(self, engine):
        p = _make_product(nutrients={"sodium_100g": 0.1})
        insight = engine.analyze(p)
        assert not any("high sodium" in r.lower() for r in insight.risk_indicators)


# ---------------------------------------------------------------------------
# Positive indicators
# ---------------------------------------------------------------------------

class TestPositiveIndicators:
    def test_high_protein_positive(self, engine):
        p = _make_product(nutrients={"proteins_100g": 15.0})
        insight = engine.analyze(p)
        assert any("protein" in pi.lower() for pi in insight.positive_indicators)

    def test_high_fibre_positive(self, engine):
        p = _make_product(nutrients={"fiber_100g": 8.0})
        insight = engine.analyze(p)
        assert any("fibre" in pi.lower() or "fiber" in pi.lower() for pi in insight.positive_indicators)

    def test_minimal_processing_positive(self, engine):
        p = _make_product(nova_group=1)
        insight = engine.analyze(p)
        assert any("nova 1" in pi.lower() or "minimally" in pi.lower() for pi in insight.positive_indicators)

    def test_good_nutriscore_positive(self, engine):
        p = _make_product(nutriscore="a")
        insight = engine.analyze(p)
        assert any("nutri-score" in pi.lower() or "nutriscore" in pi.lower() for pi in insight.positive_indicators)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestSummary:
    def test_summary_non_empty(self, engine):
        p = _make_product(name="Test Cereal", nutriscore="b")
        insight = engine.analyze(p)
        assert len(insight.summary) > 10

    def test_summary_contains_product_name(self, engine):
        p = _make_product(name="Organic Oats", nutriscore="a")
        insight = engine.analyze(p)
        assert "Organic Oats" in insight.summary


# ---------------------------------------------------------------------------
# ProductInsight serialisation
# ---------------------------------------------------------------------------

class TestProductInsightSerialization:
    def test_to_dict(self, engine):
        p = _make_product(name="Granola", nutriscore="c", nova_group=3)
        insight = engine.analyze(p)
        d = insight.to_dict()
        assert "product_name" in d
        assert "health_classification" in d
        assert "risk_indicators" in d
        assert "positive_indicators" in d
        assert "summary" in d

    def test_str_contains_classification(self, engine):
        p = _make_product(nutriscore="e", nova_group=4)
        insight = engine.analyze(p)
        text = str(insight)
        assert "Risky" in text or "Classification" in text
