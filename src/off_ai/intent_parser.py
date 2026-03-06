"""
intent_parser.py – Natural language → structured food query

Converts free-text user queries into a FoodQuery dataclass that encodes:
- Nutrient constraints  (e.g. protein >= 10, calories <= 200)
- Dietary tags          (vegan, gluten-free, organic, …)
- Product category      (snacks, cereal, beverages, …)
- Comparison mode       ("healthier alternative to <product>")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class NutrientConstraint:
    """A single nutrient bound, e.g. protein >= 10 g."""

    nutrient: str          # canonical name, e.g. "proteins_100g"
    operator: str          # ">=" | "<=" | "==" | ">" | "<"
    value: float           # numeric threshold
    unit: str = "g"        # "g" | "kcal" | "mg"

    def __str__(self) -> str:
        return f"{self.nutrient} {self.operator} {self.value} {self.unit}"


@dataclass
class FoodQuery:
    """Structured representation of a user food query."""

    raw_text: str
    category: Optional[str] = None
    nutrient_constraints: List[NutrientConstraint] = field(default_factory=list)
    dietary_tags: List[str] = field(default_factory=list)
    comparison_product: Optional[str] = None   # "healthier alternative to X"
    max_results: int = 10

    def to_dict(self) -> dict:
        return {
            "raw_text": self.raw_text,
            "category": self.category,
            "nutrient_constraints": [
                {
                    "nutrient": c.nutrient,
                    "operator": c.operator,
                    "value": c.value,
                    "unit": c.unit,
                }
                for c in self.nutrient_constraints
            ],
            "dietary_tags": self.dietary_tags,
            "comparison_product": self.comparison_product,
            "max_results": self.max_results,
        }

    def __str__(self) -> str:
        parts = []
        if self.category:
            parts.append(f"category = {self.category}")
        for c in self.nutrient_constraints:
            parts.append(str(c))
        for t in self.dietary_tags:
            parts.append(f"{t} = true")
        if self.comparison_product:
            parts.append(f"alternative to: {self.comparison_product}")
        return "\n".join(parts) if parts else "(no constraints)"


# ---------------------------------------------------------------------------
# Keyword mappings
# ---------------------------------------------------------------------------

# Maps query keywords → OFF field names
NUTRIENT_ALIASES: Dict[str, str] = {
    "protein": "proteins_100g",
    "proteins": "proteins_100g",
    "calorie": "energy-kcal_100g",
    "calories": "energy-kcal_100g",
    "kcal": "energy-kcal_100g",
    "fat": "fat_100g",
    "fats": "fat_100g",
    "saturated fat": "saturated-fat_100g",
    "saturated": "saturated-fat_100g",
    "sugar": "sugars_100g",
    "sugars": "sugars_100g",
    "carbs": "carbohydrates_100g",
    "carbohydrates": "carbohydrates_100g",
    "sodium": "sodium_100g",
    "salt": "salt_100g",
    "fiber": "fiber_100g",
    "fibre": "fiber_100g",
}

DIETARY_TAGS: List[str] = [
    "vegan",
    "vegetarian",
    "gluten-free",
    "gluten free",
    "organic",
    "dairy-free",
    "dairy free",
    "lactose-free",
    "lactose free",
    "halal",
    "kosher",
    "low-sugar",
    "low sugar",
    "low-fat",
    "low fat",
    "low-sodium",
    "low sodium",
    "high-protein",
    "high protein",
    "keto",
    "paleo",
    "whole grain",
    "wholegrain",
    "no additives",
    "no preservatives",
]

CATEGORY_KEYWORDS: Dict[str, str] = {
    "snack": "snacks",
    "snacks": "snacks",
    "cereal": "cereals",
    "cereals": "cereals",
    "breakfast cereal": "cereals",
    "beverage": "beverages",
    "beverages": "beverages",
    "drink": "beverages",
    "drinks": "beverages",
    "juice": "juices",
    "yogurt": "dairy",
    "yoghurt": "dairy",
    "dairy": "dairy",
    "milk": "dairy",
    "cheese": "dairy",
    "bread": "breads",
    "breads": "breads",
    "chocolate": "chocolates",
    "candy": "candies",
    "candies": "candies",
    "sweet": "candies",
    "cookie": "cookies",
    "cookies": "cookies",
    "biscuit": "cookies",
    "biscuits": "cookies",
    "chip": "chips",
    "chips": "chips",
    "crisps": "chips",
    "cracker": "crackers",
    "crackers": "crackers",
    "pasta": "pastas",
    "noodle": "pastas",
    "noodles": "pastas",
    "rice": "rices",
    "sauce": "sauces",
    "dressing": "sauces",
    "spread": "spreads",
    "jam": "spreads",
    "peanut butter": "spreads",
    "butter": "spreads",
    "oil": "oils",
    "meat": "meats",
    "fish": "fishes",
    "seafood": "fishes",
    "vegetable": "vegetables",
    "fruit": "fruits",
}

# Qualitative descriptors → rough numeric thresholds per 100 g
QUALITATIVE_THRESHOLDS: Dict[str, Dict[str, Tuple[str, float]]] = {
    "high": {
        "proteins_100g": (">=", 10.0),
        "fiber_100g": (">=", 6.0),
        "energy-kcal_100g": (">=", 400.0),
        "fat_100g": (">=", 17.5),
        "sugars_100g": (">=", 22.5),
        "sodium_100g": (">=", 0.6),
    },
    "low": {
        "proteins_100g": ("<=", 3.0),
        "fiber_100g": ("<=", 2.0),
        "energy-kcal_100g": ("<=", 150.0),
        "fat_100g": ("<=", 3.0),
        "sugars_100g": ("<=", 5.0),
        "sodium_100g": ("<=", 0.1),
        "saturated-fat_100g": ("<=", 1.5),
    },
}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class IntentParser:
    """Rule-based natural-language food query parser.

    Designed so that an LLM back-end can later replace or augment the
    rule engine without changing the public API (parse → FoodQuery).
    """

    # Numeric constraint patterns, e.g. "under 200 calories", "≥10g protein"
    _NUMERIC_PATTERNS: List[Tuple[re.Pattern, str]] = [
        (
            re.compile(
                r"(under|less than|below|at most|max(?:imum)?|<=?)\s*"
                r"(\d+(?:\.\d+)?)\s*(?:g|mg|kcal|cal)?\s*"
                r"(of\s+)?({nutrients})".format(nutrients="|".join(NUTRIENT_ALIASES)),
                re.IGNORECASE,
            ),
            "upper",
        ),
        (
            re.compile(
                r"({nutrients})\s*(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:g|mg|kcal|cal)?\s*"
                r"(or less|or under|max(?:imum)?|and under|<=?)".format(
                    nutrients="|".join(NUTRIENT_ALIASES)
                ),
                re.IGNORECASE,
            ),
            "upper_rev",
        ),
        (
            re.compile(
                r"(over|more than|above|at least|min(?:imum)?|>=?)\s*"
                r"(\d+(?:\.\d+)?)\s*(?:g|mg|kcal|cal)?\s*"
                r"(of\s+)?({nutrients})".format(nutrients="|".join(NUTRIENT_ALIASES)),
                re.IGNORECASE,
            ),
            "lower",
        ),
        (
            re.compile(
                r"({nutrients})\s*(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:g|mg|kcal|cal)?\s*"
                r"(or more|or over|min(?:imum)?|and over|>=?)".format(
                    nutrients="|".join(NUTRIENT_ALIASES)
                ),
                re.IGNORECASE,
            ),
            "lower_rev",
        ),
    ]

    # "X calories" / "X g protein" shorthand
    _BARE_NUMERIC = re.compile(
        r"(\d+(?:\.\d+)?)\s*(kcal|cal(?:ories)?|g|mg)\s+"
        r"(?:of\s+)?({nutrients})".format(nutrients="|".join(NUTRIENT_ALIASES)),
        re.IGNORECASE,
    )

    # "alternative to <product>" or "instead of <product>"
    _ALTERNATIVE_PATTERN = re.compile(
        r"(?:healthier\s+)?alternative\s+to\s+(.+?)(?:\s*$|[,.])",
        re.IGNORECASE,
    )
    _INSTEAD_OF_PATTERN = re.compile(
        r"instead\s+of\s+(.+?)(?:\s*$|[,.])",
        re.IGNORECASE,
    )
    _REPLACE_PATTERN = re.compile(
        r"replace\s+(.+?)(?:\s+with\s+|\s*$|[,.])",
        re.IGNORECASE,
    )

    def parse(self, text: str) -> FoodQuery:
        """Parse *text* into a :class:`FoodQuery`."""
        query = FoodQuery(raw_text=text)
        lower = text.lower()

        # 1. Alternative / comparison mode
        for pattern in (
            self._ALTERNATIVE_PATTERN,
            self._INSTEAD_OF_PATTERN,
            self._REPLACE_PATTERN,
        ):
            m = pattern.search(text)
            if m:
                query.comparison_product = m.group(1).strip()
                break

        # 2. Category detection
        query.category = self._extract_category(lower)

        # 3. Dietary tags
        query.dietary_tags = self._extract_dietary_tags(lower)

        # 4. Nutrient constraints – explicit numeric
        constraints = self._extract_numeric_constraints(text)

        # 5. Qualitative adjectives ("high protein", "low sodium", …)
        constraints.extend(self._extract_qualitative_constraints(lower, constraints))

        query.nutrient_constraints = constraints
        return query

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_category(self, lower: str) -> Optional[str]:
        # Prefer longer matches to avoid "chip" matching inside "chocolate"
        matched: Optional[Tuple[int, str]] = None
        for kw, cat in CATEGORY_KEYWORDS.items():
            if kw in lower:
                if matched is None or len(kw) > matched[0]:
                    matched = (len(kw), cat)
        return matched[1] if matched else None

    def _extract_dietary_tags(self, lower: str) -> List[str]:
        found: List[str] = []
        # Normalise hyphens when checking
        norm = lower.replace("-", " ")
        for tag in DIETARY_TAGS:
            norm_tag = tag.replace("-", " ")
            if norm_tag in norm:
                canonical = tag.replace(" ", "-")
                if canonical not in found:
                    found.append(canonical)
        return found

    def _extract_numeric_constraints(self, text: str) -> List[NutrientConstraint]:
        constraints: List[NutrientConstraint] = []
        seen_ops: set = set()          # (nutrient, op) pairs already added
        seen_directed: set = set()     # nutrients that have a directed constraint

        def _add_directed(nutrient: str, op: str, value: float, unit: str = "g") -> None:
            key = (nutrient, op)
            if key not in seen_ops:
                seen_ops.add(key)
                seen_directed.add(nutrient)
                constraints.append(
                    NutrientConstraint(nutrient=nutrient, operator=op, value=value, unit=unit)
                )

        def _add_bare(nutrient: str, op: str, value: float, unit: str = "g") -> None:
            # Skip if a directed constraint already covers this nutrient
            if nutrient in seen_directed:
                return
            key = (nutrient, op)
            if key not in seen_ops:
                seen_ops.add(key)
                constraints.append(
                    NutrientConstraint(nutrient=nutrient, operator=op, value=value, unit=unit)
                )

        for pattern, direction in self._NUMERIC_PATTERNS:
            for m in pattern.finditer(text):
                groups = [g for g in m.groups() if g is not None]
                # Extract numeric value and nutrient name from groups
                nums = [g for g in groups if re.match(r"^\d", g)]
                words = [g for g in groups if re.match(r"[a-z]", g, re.I) and not re.match(r"^\d", g)]
                if not nums or not words:
                    continue
                value = float(nums[0])
                nutrient_word = next(
                    (w for w in words if w.lower() in NUTRIENT_ALIASES), None
                )
                if nutrient_word is None:
                    continue
                field = NUTRIENT_ALIASES[nutrient_word.lower()]
                unit = "kcal" if "kcal" in field else "g"
                op = "<=" if direction in ("upper", "upper_rev") else ">="
                _add_directed(field, op, value, unit)

        # Bare numeric: "200 calories", "10g protein" – only when no directed constraint found
        for m in self._BARE_NUMERIC.finditer(text):
            value_s, unit_s, nutrient_word = m.group(1), m.group(2), m.group(3)
            field = NUTRIENT_ALIASES.get(nutrient_word.lower())
            if field is None:
                continue
            unit = "kcal" if unit_s.lower().startswith("kcal") or "cal" in unit_s.lower() else "g"
            # "200 calories" without direction – treat as ceiling (context-free default)
            _add_bare(field, "<=", float(value_s), unit)

        return constraints

    def _extract_qualitative_constraints(
        self, lower: str, existing: List[NutrientConstraint]
    ) -> List[NutrientConstraint]:
        """Add qualitative bounds for 'high X' / 'low X' when no numeric bound exists."""
        existing_fields = {c.nutrient for c in existing}
        new_constraints: List[NutrientConstraint] = []

        for quality, mappings in QUALITATIVE_THRESHOLDS.items():
            for kw, field in NUTRIENT_ALIASES.items():
                phrase = f"{quality} {kw}"
                if phrase in lower and field in mappings and field not in existing_fields:
                    op, value = mappings[field]
                    unit = "kcal" if "kcal" in field else "g"
                    new_constraints.append(
                        NutrientConstraint(
                            nutrient=field, operator=op, value=value, unit=unit
                        )
                    )
                    existing_fields.add(field)

        return new_constraints
