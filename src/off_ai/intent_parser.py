"""Natural language intent parsing for DuckDB-backed food search."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class NutrientConstraint:
    """A single numeric nutrient filter."""

    nutrient: str
    operator: str
    value: float
    unit: str = "g"

    def __str__(self) -> str:
        return f"{self.nutrient} {self.operator} {self.value} {self.unit}"


@dataclass
class FoodQuery:
    """Structured representation of a user food query."""

    raw_text: str
    category: Optional[str] = None
    nutrient_constraints: List[NutrientConstraint] = field(default_factory=list)
    dietary_tags: List[str] = field(default_factory=list)
    search_terms: List[str] = field(default_factory=list)
    ranking_preferences: List[str] = field(default_factory=list)
    comparison_product: Optional[str] = None   # "healthier alternative to X"
    excluded_ingredients: List[str] = field(default_factory=list)  # e.g. ["palm oil"]
    detected_language: str = "en"
    normalized_text: Optional[str] = None
    max_results: int = 10

    def copy_without_constraint(self, constraint_index: int) -> FoodQuery:
        """Return a copy of this query with the constraint at *constraint_index* removed."""
        new_query = copy.deepcopy(self)
        if 0 <= constraint_index < len(new_query.nutrient_constraints):
            new_query.nutrient_constraints.pop(constraint_index)
        return new_query

    def copy_with_relaxed_constraint(self, constraint_index: int, relax_factor: float = 1.2) -> FoodQuery:
        """Return a copy of this query with the constraint at *constraint_index* relaxed.
        
        For "<=" constraints, increases bound by relax_factor (e.g. 1.2 = 20% increase).
        For ">=" constraints, decreases bound by relax_factor (e.g. 1.2 = 20% decrease).
        """
        new_query = copy.deepcopy(self)
        if 0 <= constraint_index < len(new_query.nutrient_constraints):
            c = new_query.nutrient_constraints[constraint_index]
            if c.operator in ("<=", "<"):
                # Upper bound: increase it
                c.value = c.value * relax_factor
            elif c.operator in (">=", ">"):
                # Lower bound: decrease it
                c.value = c.value / relax_factor
        return new_query

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
            "search_terms": self.search_terms,
            "ranking_preferences": self.ranking_preferences,
            "excluded_ingredients": self.excluded_ingredients,
            "detected_language": self.detected_language,
            "normalized_text": self.normalized_text,
            "comparison_product": self.comparison_product,
            "max_results": self.max_results,
        }

    def __str__(self) -> str:
        parts = []
        if self.detected_language:
            parts.append(f"language = {self.detected_language}")
        if self.normalized_text and self.normalized_text != self.raw_text.lower():
            parts.append(f"normalized = {self.normalized_text}")
        if self.category:
            parts.append(f"category = {self.category}")
        for c in self.nutrient_constraints:
            parts.append(str(c))
        for t in self.dietary_tags:
            parts.append(f"{t} = true")
        for pref in self.ranking_preferences:
            parts.append(f"prefer {pref}")
        if self.search_terms:
            parts.append(f"text = {', '.join(self.search_terms)}")
        for ing in self.excluded_ingredients:
            parts.append(f"no {ing}")
        if self.comparison_product:
            parts.append(f"alternative to: {self.comparison_product}")
        return "\n".join(parts) if parts else "(no constraints)"


# ---------------------------------------------------------------------------
# Keyword mappings
# ---------------------------------------------------------------------------

NUTRIENT_ALIASES: Dict[str, str] = {
    "protein": "proteins_100g",
    "proteins": "proteins_100g",
    "calorie": "energy_kcal_100g",
    "calories": "energy_kcal_100g",
    "kcal": "energy_kcal_100g",
    "energy": "energy_kcal_100g",
    "fat": "fat_100g",
    "fats": "fat_100g",
    "saturated fat": "saturated_fat_100g",
    "saturated fats": "saturated_fat_100g",
    "saturated": "saturated_fat_100g",
    "sugar": "sugars_100g",
    "sugars": "sugars_100g",
    "carb": "carbohydrates_100g",
    "carbs": "carbohydrates_100g",
    "carbohydrate": "carbohydrates_100g",
    "carbohydrates": "carbohydrates_100g",
    "sodium": "sodium_100g",
    "salt": "salt_100g",
    "fiber": "fiber_100g",
    "fibre": "fiber_100g",
}

NUTRIENT_UNITS: Dict[str, str] = {
    "proteins_100g": "g",
    "energy_kcal_100g": "kcal",
    "fat_100g": "g",
    "saturated_fat_100g": "g",
    "sugars_100g": "g",
    "carbohydrates_100g": "g",
    "sodium_100g": "g",
    "salt_100g": "g",
    "fiber_100g": "g",
}

DIETARY_TAG_ALIASES: Dict[str, str] = {
    "vegan": "vegan",
    "plant based": "vegan",
    "plant-based": "vegan",
    "vegetarian": "vegetarian",
    "gluten free": "gluten-free",
    "gluten-free": "gluten-free",
    "organic": "organic",
    "bio": "organic",
    "dairy free": "dairy-free",
    "dairy-free": "dairy-free",
    "lactose free": "lactose-free",
    "lactose-free": "lactose-free",
    "halal": "halal",
    "kosher": "kosher",
}

CATEGORY_KEYWORDS: Dict[str, str] = {
    "snack": "snacks",
    "snacks": "snacks",
    "healthy snack": "snacks",
    "cereal": "cereals",
    "cereals": "cereals",
    "cerals": "cereals",  # common typo
    "muesli": "cereals",
    "breakfast cereal": "cereals",
    "granola": "cereals",
    "bar": "snack-bars",
    "bars": "snack-bars",
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
    "chocolates": "chocolates",
    "choclates": "chocolates",  # common typo
    "choco": "chocolates",
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
    "olive oils": "olive-oils",
    "olive oil": "olive-oils",
    "oil": "oils",
    "meat": "meats",
    "fish": "fishes",
    "seafood": "fishes",
    "vegetable": "vegetables",
    "fruit": "fruits",
}

# Qualitative descriptors -> numeric thresholds per 100 g
QUALITATIVE_THRESHOLDS: Dict[str, Dict[str, Tuple[str, float]]] = {
    "high": {
        "proteins_100g": (">=", 10.0),
        "fiber_100g": (">=", 6.0),
        "energy_kcal_100g": (">=", 800.0),
        "fat_100g": (">=", 17.5),
        "sugars_100g": (">=", 22.5),
        "sodium_100g": (">=", 0.6),
    },
    "low": {
        "proteins_100g": ("<=", 3.0),
        "fiber_100g": ("<=", 2.0),
        "energy_kcal_100g": ("<=", 400.0),
        "fat_100g": ("<=", 3.0),
        "sugars_100g": ("<=", 5.0),
        "sodium_100g": ("<=", 0.1),
        "saturated_fat_100g": ("<=", 1.5),
    },
    "less": {
        "proteins_100g": ("<=", 3.0),
        "fiber_100g": ("<=", 2.0),
        "energy_kcal_100g": ("<=", 400.0),
        "fat_100g": ("<=", 3.0),
        "sugars_100g": ("<=", 5.0),
        "sodium_100g": ("<=", 0.1),
        "saturated_fat_100g": ("<=", 1.5),
    },
}

HEALTH_PREFERENCES = {
    "healthy": "healthy",
    "healthiest": "healthy",
    "nutritious": "healthy",
    "clean": "healthy",
    "better for you": "healthy",
    "for kids": "kids",
    "kid friendly": "kids",
    "kid-friendly": "kids",
    "kids": "kids",
    "children": "kids",
}

EXCLUDED_INGREDIENT_PATTERNS: Dict[str, str] = {
    r"(?:no|without|free\s+from)\s+palm\s+oil": "palm oil",
    r"(?:no|without|free\s+from)\s+soy": "soy",
    r"(?:no|without|free\s+from)\s+dairy": "dairy",
    r"(?:no|without|free\s+from)\s+gluten": "gluten",
}

STRUCTURAL_STOPWORDS = {
    "show",
    "me",
    "find",
    "best",
    "top",
    "foods",
    "food",
    "product",
    "products",
    "suitable",
    "that",
    "are",
    "also",
    "for",
    "diet",
    "a",
    "an",
    "the",
    "with",
    "and",
    "or",
    "to",
    "of",
    "under",
    "over",
    "below",
    "above",
    "less",
    "than",
    "more",
    "at",
    "least",
    "most",
    "maximum",
    "minimum",
    "per",
    "100g",
    "100ml",
    "diet",
    "healthy",
    "healthiest",
    "kids",
    "kid",
    "children",
    # Nutrient qualifiers — consumed by parser, must not become text search terms
    "high",
    "low",
    "rich",
    "light",
    "lite",
    "zero",
    "no",
    "without",
    "free",
    "plus",
    "extra",
    "ultra",
    "super",
    "lower",
    "higher",
    "reduced",
    "added",
    "good",
    "source",
    "excellent",
    # Common English conversational/grammatical words that carry no food meaning
    "i",
    "im",
    "am",
    "in",
    "on",
    "it",
    "its",
    "is",
    "be",
    "been",
    "was",
    "were",
    "do",
    "does",
    "did",
    "have",
    "has",
    "had",
    "will",
    "would",
    "can",
    "could",
    "should",
    "may",
    "might",
    "my",
    "get",
    "got",
    "give",
    "want",
    "need",
    "like",
    "go",
    "going",
    "looking",
    "searching",
    "search",
    "suggest",
    "suggested",
    "recommend",
    "recommended",
    "tell",
    "know",
    "help",
    "has",
    "which",
    "please",
    "just",
    "really",
    "very",
    "quite",
    "some",
    "any",
    "all",
    "not",
    "from",
    "out",
    "up",
}

_NUTRIENT_PATTERN = "|".join(
    sorted((re.escape(term) for term in NUTRIENT_ALIASES.keys()), key=len, reverse=True)
)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class IntentParser:
    """Rule-driven semantic parser that maps natural language to filters."""

    # Numeric constraint patterns, e.g. "under 200 calories", "≥10g protein"
    _NUMERIC_PATTERNS: List[Tuple[re.Pattern, str]] = [
        (
            re.compile(
                r"(under|less than|below|at most|max(?:imum)?|<=?)\s*"
                r"(\d+(?:\.\d+)?)\s*(?:g|mg|kcal|cal)?\s*"
                r"(of\s+)?({nutrients})".format(nutrients=_NUTRIENT_PATTERN),
                re.IGNORECASE,
            ),
            "upper",
        ),
        (
            re.compile(
                r"({nutrients})\s*(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:g|mg|kcal|cal)?\s*"
                r"(or less|or under|max(?:imum)?|and under|<=?)".format(
                    nutrients=_NUTRIENT_PATTERN
                ),
                re.IGNORECASE,
            ),
            "upper_rev",
        ),
        (
            re.compile(
                r"(over|more than|above|at least|min(?:imum)?|>=?)\s*"
                r"(\d+(?:\.\d+)?)\s*(?:g|mg|kcal|cal)?\s*"
                r"(of\s+)?({nutrients})".format(nutrients=_NUTRIENT_PATTERN),
                re.IGNORECASE,
            ),
            "lower",
        ),
        (
            re.compile(
                r"({nutrients})\s*(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:g|mg|kcal|cal)?\s*"
                r"(or more|or over|min(?:imum)?|and over|>=?)".format(
                    nutrients=_NUTRIENT_PATTERN
                ),
                re.IGNORECASE,
            ),
            "lower_rev",
        ),
    ]

    # "X calories" / "X g protein" shorthand
    _BARE_NUMERIC = re.compile(
        r"(\d+(?:\.\d+)?)\s*(kcal|cal(?:ories)?|g|mg)\s+"
        r"(?:of\s+)?({nutrients})".format(nutrients=_NUTRIENT_PATTERN),
        re.IGNORECASE,
    )

    # Standalone calorie pattern: "350 calorie" or "350 calories" without nutrient keyword
    _BARE_CALORIE = re.compile(
        r"(\d+(?:\.\d+)?)\s*(kcal|cal(?:ories)?)",
        re.IGNORECASE,
    )

    _ZERO_SUGAR_PATTERN = re.compile(
        r"(?:0|zero|no|none)\s*(?:added\s+)?sugar",
        re.IGNORECASE,
    )

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
        lower_normalized = lower.replace("-", " ")

        for pattern in (
            self._ALTERNATIVE_PATTERN,
            self._INSTEAD_OF_PATTERN,
            self._REPLACE_PATTERN,
        ):
            m = pattern.search(text)
            if m:
                query.comparison_product = m.group(1).strip()
                break

        query.excluded_ingredients = self._extract_excluded_ingredients(text)
        category_text = lower_normalized
        for ingredient in query.excluded_ingredients:
            normalized = ingredient.strip().lower()
            if not normalized:
                continue
            category_text = re.sub(rf"\b{re.escape(normalized)}\b", " ", category_text)
            if " " in normalized:
                category_text = re.sub(rf"\b{re.escape(normalized.replace(' ', '-'))}\b", " ", category_text)

        query.category = self._extract_category(category_text)
        query.dietary_tags = self._extract_dietary_tags(lower_normalized)
        constraints = self._extract_numeric_constraints(text)
        constraints.extend(self._extract_qualitative_constraints(lower_normalized, constraints))
        query.nutrient_constraints = self._dedupe_constraints(constraints)
        query.ranking_preferences = self._extract_ranking_preferences(lower_normalized)
        query.search_terms = self._extract_search_terms(lower_normalized, query)
        return query

    def _extract_category(self, text: str) -> Optional[str]:
        best_match: Optional[Tuple[int, int, str]] = None
        for keyword, category in CATEGORY_KEYWORDS.items():
            for match in re.finditer(rf"\b{re.escape(keyword)}\b", text):
                candidate = (match.start(), len(keyword), category)
                if best_match is None or candidate[0] > best_match[0] or (
                    candidate[0] == best_match[0] and candidate[1] > best_match[1]
                ):
                    best_match = candidate
        return best_match[2] if best_match else None

    def _extract_dietary_tags(self, text: str) -> List[str]:
        tags: List[str] = []
        for alias, canonical in DIETARY_TAG_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", text):
                tags.append(canonical)
        return list(dict.fromkeys(tags))

    def _extract_excluded_ingredients(self, text: str) -> List[str]:
        exclusions: List[str] = []
        lowered = text.lower()
        for pattern, ingredient in EXCLUDED_INGREDIENT_PATTERNS.items():
            if re.search(pattern, lowered, re.IGNORECASE):
                exclusions.append(ingredient)
        if self._ZERO_SUGAR_PATTERN.search(text):
            exclusions.append("added sugar")
        return list(dict.fromkeys(exclusions))

    def _extract_numeric_constraints(self, text: str) -> List[NutrientConstraint]:
        constraints: List[NutrientConstraint] = []
        directed_nutrients: set[str] = set()
        directed_spans: List[Tuple[int, int]] = []

        for pattern, pattern_type in self._NUMERIC_PATTERNS:
            for match in pattern.finditer(text):
                if pattern_type in {"upper", "lower"}:
                    amount = match.group(2)
                    nutrient_term = match.group(4)
                else:
                    nutrient_term = match.group(1)
                    amount = match.group(2)
                constraint = self._build_constraint(nutrient_term, amount, pattern_type, text)
                if constraint:
                    constraints.append(constraint)
                    directed_nutrients.add(constraint.nutrient)
                    directed_spans.append(match.span())

        for match in self._BARE_NUMERIC.finditer(text):
            if any(start <= match.start() and match.end() <= end for start, end in directed_spans):
                continue
            amount = float(match.group(1))
            unit = match.group(2).lower()
            nutrient_term = match.group(3)
            nutrient = NUTRIENT_ALIASES[nutrient_term.lower()]
            if nutrient in directed_nutrients:
                continue
            amount = self._normalize_numeric_value(amount, unit, nutrient)
            operator = ">=" if nutrient in {"proteins_100g", "fiber_100g"} else "<="
            constraints.append(
                NutrientConstraint(
                    nutrient=nutrient,
                    operator=operator,
                    value=amount,
                    unit=NUTRIENT_UNITS.get(nutrient, "g"),
                )
            )

        for match in self._BARE_CALORIE.finditer(text):
            amount = float(match.group(1))
            constraints.append(
                NutrientConstraint(
                    nutrient="energy_kcal_100g",
                    operator="<=",
                    value=amount,
                    unit="kcal",
                )
            )

        if self._ZERO_SUGAR_PATTERN.search(text):
            constraints.append(
                NutrientConstraint(
                    nutrient="sugars_100g",
                    operator="<=",
                    value=0.5,
                    unit="g",
                )
            )

        return constraints

    def _build_constraint(
        self,
        nutrient_term: str,
        amount_text: str,
        pattern_type: str,
        raw_text: str,
    ) -> Optional[NutrientConstraint]:
        nutrient = NUTRIENT_ALIASES.get(nutrient_term.lower())
        if nutrient is None:
            return None
        amount = self._normalize_numeric_value(float(amount_text), self._extract_unit_hint(raw_text), nutrient)
        operator = "<=" if pattern_type.startswith("upper") else ">="
        return NutrientConstraint(
            nutrient=nutrient,
            operator=operator,
            value=amount,
            unit=NUTRIENT_UNITS.get(nutrient, "g"),
        )

    def _extract_unit_hint(self, text: str) -> str:
        unit_match = re.search(r"\b(mg|g|kcal|cal(?:ories)?)\b", text.lower())
        return unit_match.group(1) if unit_match else "g"

    def _normalize_numeric_value(self, value: float, unit: str, nutrient: str) -> float:
        if unit == "mg":
            return value / 1000.0
        if unit.startswith("cal"):
            return value
        return value

    def _extract_qualitative_constraints(
        self,
        text: str,
        existing_constraints: List[NutrientConstraint],
    ) -> List[NutrientConstraint]:
        existing_nutrients = {constraint.nutrient for constraint in existing_constraints}
        constraints: List[NutrientConstraint] = []

        for descriptor, threshold_map in QUALITATIVE_THRESHOLDS.items():
            for nutrient_term, nutrient in NUTRIENT_ALIASES.items():
                if nutrient in existing_nutrients:
                    continue
                phrase = f"{descriptor} {nutrient_term}"
                if re.search(rf"\b{re.escape(phrase)}\b", text):
                    operator, value = threshold_map.get(nutrient, (None, None))
                    if operator is None:
                        continue
                    constraints.append(
                        NutrientConstraint(
                            nutrient=nutrient,
                            operator=operator,
                            value=value,
                            unit=NUTRIENT_UNITS.get(nutrient, "g"),
                        )
                    )

        if "low sodium diet" in text or "low salt diet" in text:
            constraints.append(NutrientConstraint("sodium_100g", "<=", 0.12, "g"))

        return constraints

    def _extract_ranking_preferences(self, text: str) -> List[str]:
        preferences: List[str] = []
        for phrase, canonical in HEALTH_PREFERENCES.items():
            if phrase in text:
                preferences.append(canonical)
        return list(dict.fromkeys(preferences))

    def _extract_search_terms(self, text: str, query: FoodQuery) -> List[str]:
        cleaned = text
        if query.category:
            for phrase in sorted(CATEGORY_KEYWORDS.keys(), key=len, reverse=True):
                if CATEGORY_KEYWORDS[phrase] == query.category:
                    cleaned = re.sub(rf"\b{re.escape(phrase)}\b", " ", cleaned)
        for phrase in sorted(DIETARY_TAG_ALIASES.keys(), key=len, reverse=True):
            cleaned = re.sub(rf"\b{re.escape(phrase)}\b", " ", cleaned)
        for phrase in sorted(HEALTH_PREFERENCES.keys(), key=len, reverse=True):
            cleaned = re.sub(rf"\b{re.escape(phrase)}\b", " ", cleaned)
        for nutrient_term in sorted(NUTRIENT_ALIASES.keys(), key=len, reverse=True):
            cleaned = re.sub(rf"\b{re.escape(nutrient_term)}\b", " ", cleaned)

        # Exclusion phrases are filters and should not become positive-match keywords.
        for ingredient in query.excluded_ingredients:
            normalized = ingredient.strip().lower()
            if not normalized:
                continue
            cleaned = re.sub(rf"\b{re.escape(normalized)}\b", " ", cleaned)
            if " " in normalized:
                hyphenated = normalized.replace(" ", "-")
                cleaned = re.sub(rf"\b{re.escape(hyphenated)}\b", " ", cleaned)
            for token in re.findall(r"[a-z]+", normalized):
                cleaned = re.sub(rf"\b{re.escape(token)}\b", " ", cleaned)

        tokens = re.findall(r"[a-z]+", cleaned)
        terms: List[str] = []
        for token in tokens:
            if token in STRUCTURAL_STOPWORDS or token.isdigit():
                continue
            terms.append(token)

        if query.comparison_product:
            terms.extend(re.findall(r"[a-z]+", query.comparison_product.lower()))

        return list(dict.fromkeys(terms))

    def _dedupe_constraints(self, constraints: List[NutrientConstraint]) -> List[NutrientConstraint]:
        deduped: Dict[Tuple[str, str], NutrientConstraint] = {}
        for constraint in constraints:
            key = (constraint.nutrient, constraint.operator)
            current = deduped.get(key)
            if current is None:
                deduped[key] = constraint
                continue
            if constraint.operator.startswith("<"):
                deduped[key] = constraint if constraint.value < current.value else current
            else:
                deduped[key] = constraint if constraint.value > current.value else current
        return list(deduped.values())
