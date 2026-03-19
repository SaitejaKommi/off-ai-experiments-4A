"""
recommendation_engine.py – Intelligent food recommendation system

Given a "reference" product (the one a user is currently viewing), this
engine finds and ranks better alternatives from the same OFF category.

Ranking criteria (weighted composite score):
  1. Nutri-Score (A–E)                           weight 40 %
  2. NOVA group  (1 = best, 4 = worst)            weight 25 %
  3. Additive count                               weight 15 %
  4. Key nutrient improvement vs reference        weight 20 %

Only products that are strictly better in at least one dimension are
returned as recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .data_adapter import Product
from .insight_engine import InsightEngine, ProductInsight

# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------

_NUTRISCORE_SCORE: Dict[str, float] = {
    "a": 5.0,
    "b": 4.0,
    "c": 3.0,
    "d": 2.0,
    "e": 1.0,
}

# Per-100-g nutrients where LOWER is better for comparison
_LOWER_IS_BETTER = {
    "sodium_100g",
    "salt_100g",
    "sugars_100g",
    "fat_100g",
    "saturated-fat_100g",
    "energy-kcal_100g",
}

# Per-100-g nutrients where HIGHER is better
_HIGHER_IS_BETTER = {
    "proteins_100g",
    "fiber_100g",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Recommendation:
    """A single product recommendation with context."""

    product: Product
    insight: ProductInsight
    score: float                               # composite ranking score
    improvements: List[str] = field(default_factory=list)  # human-readable deltas
    rank: int = 0

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "product": self.product.to_dict(),
            "insight": self.insight.to_dict(),
            "score": round(self.score, 3),
            "improvements": self.improvements,
        }

    def __str__(self) -> str:
        lines = [
            f"{self.rank}. {self.product.name}",
            f"   Nutri-Score: {(self.product.nutriscore or '?').upper()}",
        ]
        if self.product.nova_group:
            lines.append(f"   NOVA group: {self.product.nova_group}")
        for imp in self.improvements[:3]:
            lines.append(f"   → {imp}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RecommendationEngine:
    """Finds better product alternatives for a reference product.

    Parameters
    ----------
    min_improvement_ratio:
        Minimum fractional improvement in composite score required before a
        candidate is returned.  Default 0.05 (5 %).
    max_recommendations:
        Maximum number of recommendations to return.
    """

    def __init__(
        self,
        min_improvement_ratio: float = 0.05,
        max_recommendations: int = 5,
    ) -> None:
        self.min_improvement_ratio = min_improvement_ratio
        self.max_recommendations = max_recommendations
        self._insight_engine = InsightEngine()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def recommend(
        self,
        reference: Product,
        candidates: List[Product],
    ) -> List[Recommendation]:
        """Return ranked recommendations better than *reference*.

        Parameters
        ----------
        reference:
            The product the user is currently viewing.
        candidates:
            A pool of candidate products from the same category.
        """
        ref_score = self._composite_score(reference)
        threshold = ref_score * (1 + self.min_improvement_ratio)

        recommendations: List[Recommendation] = []
        for candidate in candidates:
            if candidate.barcode == reference.barcode:
                continue
            cand_score = self._composite_score(candidate)
            if cand_score <= threshold:
                continue
            improvements = self._describe_improvements(reference, candidate)
            insight = self._insight_engine.analyze(candidate)
            recommendations.append(
                Recommendation(
                    product=candidate,
                    insight=insight,
                    score=cand_score,
                    improvements=improvements,
                )
            )

        # Sort best-first
        recommendations.sort(key=lambda r: r.score, reverse=True)
        recommendations = recommendations[: self.max_recommendations]

        # Assign ranks
        for i, rec in enumerate(recommendations, start=1):
            rec.rank = i

        return recommendations

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _composite_score(self, product: Product) -> float:
        """Compute a composite quality score (higher = better)."""
        score = 0.0

        # Nutri-Score component (40 %)
        ns = _NUTRISCORE_SCORE.get(product.nutriscore or "", 2.5)
        score += ns * 0.40

        # NOVA component (25 %) – invert so 1 = best
        nova = product.nova_group
        if nova and 1 <= nova <= 4:
            score += ((5 - nova) / 4) * 5 * 0.25  # map to 0-5 range
        else:
            score += 1.25  # neutral

        # Additive penalty (15 %) – fewer additives is better
        max_additives = 10
        add_score = max(0, (max_additives - product.additives_count) / max_additives) * 5
        score += add_score * 0.15

        # Nutrient component (20 %)
        score += self._nutrient_score(product) * 0.20

        return score

    @staticmethod
    def _nutrient_score(product: Product) -> float:
        """Heuristic nutrient quality score in [0, 5]."""
        points = 0.0
        count = 0

        # Penalise high-harm nutrients
        thresholds_bad = {
            "sodium_100g": (0.6, 1.5),
            "sugars_100g": (22.5, 45.0),
            "fat_100g": (17.5, 35.0),
            "saturated-fat_100g": (5.0, 10.0),
        }
        for key, (warn, bad) in thresholds_bad.items():
            val = product.nutrient(key)
            if val is not None:
                if val <= warn:
                    points += 5
                elif val >= bad:
                    points += 0
                else:
                    points += 5 * (bad - val) / (bad - warn)
                count += 1

        # Reward good nutrients
        for key, threshold in [("proteins_100g", 10.0), ("fiber_100g", 6.0)]:
            val = product.nutrient(key)
            if val is not None:
                points += min(5.0, val / threshold * 5)
                count += 1

        return (points / count) if count else 2.5

    # ------------------------------------------------------------------
    # Human-readable improvements
    # ------------------------------------------------------------------

    @staticmethod
    def _describe_improvements(
        ref: Product, candidate: Product
    ) -> List[str]:
        improvements: List[str] = []

        # Nutri-Score comparison
        ref_ns = _NUTRISCORE_SCORE.get(ref.nutriscore or "", 0)
        cand_ns = _NUTRISCORE_SCORE.get(candidate.nutriscore or "", 0)
        if cand_ns > ref_ns and candidate.nutriscore:
            improvements.append(
                f"Better Nutri-Score ({candidate.nutriscore.upper()} vs {(ref.nutriscore or '?').upper()})"
            )

        # Nutrient deltas – lower is better
        for key in _LOWER_IS_BETTER:
            ref_val = ref.nutrient(key)
            cand_val = candidate.nutrient(key)
            if ref_val and cand_val and ref_val > 0:
                pct = (ref_val - cand_val) / ref_val * 100
                if pct >= 20:
                    label = key.replace("_100g", "").replace("-", " ").title()
                    improvements.append(f"{pct:.0f}% less {label.lower()}")

        # Higher is better
        for key in _HIGHER_IS_BETTER:
            ref_val = ref.nutrient(key)
            cand_val = candidate.nutrient(key)
            if cand_val and (ref_val is None or cand_val > ref_val * 1.20):
                label = key.replace("_100g", "").replace("-", " ").title()
                if ref_val and ref_val > 0:
                    pct = (cand_val - ref_val) / ref_val * 100
                    improvements.append(f"{pct:.0f}% more {label.lower()}")
                else:
                    improvements.append(f"Higher {label.lower()}")

        # NOVA improvement
        if (
            ref.nova_group
            and candidate.nova_group
            and candidate.nova_group < ref.nova_group
        ):
            improvements.append(
                f"Less processed (NOVA {candidate.nova_group} vs {ref.nova_group})"
            )

        # Fewer additives
        if candidate.additives_count < ref.additives_count:
            diff = ref.additives_count - candidate.additives_count
            improvements.append(f"{diff} fewer additive(s)")

        return improvements
