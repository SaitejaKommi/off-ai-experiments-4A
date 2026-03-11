"""Constraint extraction layer between NLP parsing and SQL query building."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional

from .intent_parser import FoodQuery, NutrientConstraint

_NUTRIENT_TO_KEY = {
    "proteins_100g": "protein",
    "energy_kcal_100g": "calories",
    "sugars_100g": "sugar",
    "sodium_100g": "sodium",
    "fat_100g": "fat",
    "saturated_fat_100g": "saturated_fat",
    "fiber_100g": "fiber",
    "carbohydrates_100g": "carbohydrates",
    "salt_100g": "salt",
}


@dataclass
class ExtractedConstraints:
    """Structured constraints for downstream taxonomy mapping and SQL generation."""

    raw_text: str
    detected_language: str = "en"
    normalized_text: Optional[str] = None
    category: Optional[str] = None
    category_tag: Optional[str] = None
    nutrient_constraints: List[NutrientConstraint] = field(default_factory=list)
    dietary_tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    ranking_preferences: List[str] = field(default_factory=list)
    excluded_ingredients: List[str] = field(default_factory=list)
    max_results: int = 10

    def clone(self) -> "ExtractedConstraints":
        return replace(
            self,
            nutrient_constraints=[NutrientConstraint(**vars(c)) for c in self.nutrient_constraints],
            dietary_tags=list(self.dietary_tags),
            keywords=list(self.keywords),
            ranking_preferences=list(self.ranking_preferences),
            excluded_ingredients=list(self.excluded_ingredients),
        )

    def interpreted_query(self) -> Dict[str, object]:
        payload: Dict[str, object] = {}
        if self.category:
            payload["category"] = self.category
        for constraint in self.nutrient_constraints:
            prefix = _NUTRIENT_TO_KEY.get(constraint.nutrient, constraint.nutrient.replace("_100g", ""))
            if constraint.operator in (">", ">="):
                payload[f"{prefix}_min"] = constraint.value
            elif constraint.operator in ("<", "<="):
                payload[f"{prefix}_max"] = constraint.value
        for tag in self.dietary_tags:
            payload[tag.replace("-", "_")] = True
        if self.keywords:
            payload["keywords"] = self.keywords
        if self.excluded_ingredients:
            payload["exclude_ingredients"] = self.excluded_ingredients
        return payload

    def applied_filters(self) -> List[str]:
        filters: List[str] = []
        if self.category:
            filters.append(f"category: {self.category}")
        for constraint in self.nutrient_constraints:
            nutrient_label = _NUTRIENT_TO_KEY.get(constraint.nutrient, constraint.nutrient).replace("_", " ")
            unit_suffix = "kcal" if constraint.nutrient == "energy_kcal_100g" else "g"
            filters.append(f"{nutrient_label} {constraint.operator} {constraint.value:g}{unit_suffix}")
        filters.extend(self.dietary_tags)
        filters.extend(f"exclude ingredient: {ingredient}" for ingredient in self.excluded_ingredients)
        return filters


class ConstraintExtractor:
    """Extracts normalized query constraints from parser output."""

    def extract(self, query: FoodQuery) -> ExtractedConstraints:
        return ExtractedConstraints(
            raw_text=query.raw_text,
            detected_language=query.detected_language,
            normalized_text=query.normalized_text,
            category=query.category,
            nutrient_constraints=[NutrientConstraint(**vars(c)) for c in query.nutrient_constraints],
            dietary_tags=list(dict.fromkeys(query.dietary_tags)),
            keywords=list(dict.fromkeys(query.search_terms)),
            ranking_preferences=list(dict.fromkeys(query.ranking_preferences)),
            excluded_ingredients=list(dict.fromkeys(query.excluded_ingredients)),
            max_results=query.max_results,
        )
