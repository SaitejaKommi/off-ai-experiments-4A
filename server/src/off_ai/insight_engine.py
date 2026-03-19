"""
insight_engine.py – Automated product health insight generator

Generates a :class:`ProductInsight` for any :class:`Product` containing:
- health_classification  (Excellent / Good / Moderate / Risky)
- risk_indicators        (list of human-readable warnings)
- positive_indicators    (list of positive attributes)
- summary                (one-sentence explanation)

Scoring uses Nutri-Score, NOVA group, additive counts, and nutrient
levels relative to WHO / EU reference thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .data_adapter import Product

# ---------------------------------------------------------------------------
# Reference nutrient thresholds (per 100 g)
# ---------------------------------------------------------------------------

# (threshold, label) pairs – value above threshold triggers indicator
_HIGH_THRESHOLDS: List[Tuple[str, float, str]] = [
    ("sodium_100g",           0.600, "High sodium"),
    ("salt_100g",             1.500, "High salt"),
    ("sugars_100g",          22.500, "High sugar"),
    ("fat_100g",             17.500, "High fat"),
    ("saturated-fat_100g",    5.000, "High saturated fat"),
    ("energy-kcal_100g",    400.000, "High calorie density"),
]

# value below threshold triggers positive indicator
_HIGH_POSITIVE_THRESHOLDS: List[Tuple[str, float, str]] = [
    ("proteins_100g",   10.0, "High protein"),
    ("fiber_100g",       6.0, "High fibre"),
]

# Risky additives list (a conservative subset of commonly flagged E-numbers)
_RISKY_ADDITIVES = {
    "E102", "E110", "E122", "E124", "E129",  # artificial colours
    "E211", "E212", "E213",                   # benzoate preservatives
    "E320", "E321",                            # BHA / BHT antioxidants
    "E621",                                    # MSG
    "E950", "E951", "E952", "E954", "E955",   # artificial sweeteners
    "E471", "E472",                            # emulsifiers
}

# Nutri-Score → health classification contribution
_NUTRISCORE_CLASS = {
    "a": ("Excellent", 4),
    "b": ("Good", 3),
    "c": ("Moderate", 2),
    "d": ("Risky", 1),
    "e": ("Risky", 0),
}

# NOVA group contributions to score
_NOVA_PENALTY = {
    1: 0,   # unprocessed
    2: 0,   # processed culinary ingredients
    3: -1,  # processed foods
    4: -2,  # ultra-processed
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ProductInsight:
    """Health insight for a single product."""

    product_name: str
    health_classification: str           # Excellent | Good | Moderate | Risky
    risk_indicators: List[str] = field(default_factory=list)
    positive_indicators: List[str] = field(default_factory=list)
    summary: str = ""

    # Raw scores used internally
    _score: int = field(default=0, repr=False)

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "health_classification": self.health_classification,
            "risk_indicators": self.risk_indicators,
            "positive_indicators": self.positive_indicators,
            "summary": self.summary,
        }

    def __str__(self) -> str:
        lines = [
            f"Product: {self.product_name}",
            f"Classification: {self.health_classification}",
        ]
        if self.risk_indicators:
            lines.append("Risk indicators:")
            for r in self.risk_indicators:
                lines.append(f"  ⚠ {r}")
        if self.positive_indicators:
            lines.append("Positive indicators:")
            for p in self.positive_indicators:
                lines.append(f"  ✓ {p}")
        lines.append(f"Summary: {self.summary}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class InsightEngine:
    """Produces :class:`ProductInsight` objects from :class:`Product` data."""

    def analyze(self, product: Product) -> ProductInsight:
        """Generate health insight for *product*."""
        risk: List[str] = []
        positive: List[str] = []
        score: int = 5  # base score

        # 1. Nutri-Score
        if product.nutriscore and product.nutriscore in _NUTRISCORE_CLASS:
            label, points = _NUTRISCORE_CLASS[product.nutriscore]
            score += points - 2  # centre around 0
            risk.append(f"Nutri-Score {product.nutriscore.upper()}")
        else:
            label = "Unknown"

        # 2. NOVA group
        if product.nova_group is not None:
            penalty = _NOVA_PENALTY.get(product.nova_group, 0)
            score += penalty
            if product.nova_group == 4:
                risk.append("Ultra-processed (NOVA 4)")
            elif product.nova_group == 3:
                risk.append("Processed food (NOVA 3)")
            elif product.nova_group == 1:
                positive.append("Minimally processed (NOVA 1)")

        # 3. High-nutrient warnings
        for key, threshold, label_text in _HIGH_THRESHOLDS:
            val = product.nutrient(key)
            if val is not None and val > threshold:
                risk.append(label_text)
                score -= 1

        # 4. Positive nutrient attributes
        for key, threshold, label_text in _HIGH_POSITIVE_THRESHOLDS:
            val = product.nutrient(key)
            if val is not None and val >= threshold:
                positive.append(label_text)
                score += 1

        # 5. Risky additives
        found_risky = [a for a in product.additives if a in _RISKY_ADDITIVES]
        for a in found_risky:
            risk.append(f"Contains additive {a}")
            score -= 1

        # 6. Label bonuses
        beneficial_labels = {"organic", "no-additives", "no-preservatives"}
        for lbl in product.labels:
            if any(b in lbl for b in beneficial_labels):
                positive.append(f"Labelled: {lbl.replace('-', ' ').title()}")
                score += 1

        # Remove the Nutri-Score line from risks if it's good (a/b)
        if product.nutriscore in ("a", "b"):
            positive.insert(0, f"Nutri-Score {product.nutriscore.upper()}")
            risk = [r for r in risk if not r.startswith("Nutri-Score")]

        # 7. Final classification
        health_class = self._score_to_class(score)
        summary = self._generate_summary(product, health_class, risk, positive)

        return ProductInsight(
            product_name=product.name or "Unknown product",
            health_classification=health_class,
            risk_indicators=risk,
            positive_indicators=positive,
            summary=summary,
            _score=score,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_to_class(score: int) -> str:
        if score >= 7:
            return "Excellent"
        if score >= 5:
            return "Good"
        if score >= 3:
            return "Moderate"
        return "Risky"

    @staticmethod
    def _generate_summary(
        product: Product,
        health_class: str,
        risk: List[str],
        positive: List[str],
    ) -> str:
        name = product.name or "This product"
        if health_class == "Excellent":
            return (
                f"{name} has an excellent nutritional profile"
                + (f" with {positive[0].lower()}" if positive else "")
                + "."
            )
        if health_class == "Good":
            return (
                f"{name} is generally a good nutritional choice"
                + (f" though note: {risk[0].lower()}" if risk else "")
                + "."
            )
        if health_class == "Moderate":
            concerns = ", ".join(r.lower() for r in risk[:2]) if risk else "some nutritional concerns"
            return f"{name} has moderate nutritional quality due to {concerns}."
        # Risky
        concerns = ", ".join(r.lower() for r in risk[:3]) if risk else "poor nutritional profile"
        return f"{name} raises health concerns: {concerns}."
