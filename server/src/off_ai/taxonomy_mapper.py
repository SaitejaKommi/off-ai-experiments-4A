"""Maps user-friendly category terms to OFF taxonomy tags."""

from __future__ import annotations

from dataclasses import replace

from .constraint_extractor import ExtractedConstraints

CATEGORY_MAP = {
    "chips": "en:chips",
    "chip": "en:chips",
    "crisps": "en:chips",
    "crisps and chips": "en:chips",
    "protein bars": "en:protein-bars",
    "protein bar": "en:protein-bars",
    "bars": "en:snack-bars",
    "bar": "en:snack-bars",
    "snack bars": "en:snack-bars",
    "snack bar": "en:snack-bars",
    "cereal": "en:breakfast-cereals",
    "cereals": "en:breakfast-cereals",
    "kids cereal": "en:breakfast-cereals",
    "energy drinks": "en:energy-drinks",
    "energy drink": "en:energy-drinks",
    # OFF 'en:snacks' can be overly broad (includes beverage-side taxonomy links in some records).
    # Use a tighter default for generic snack queries.
    "snacks": "en:salty-snacks",
    "snack": "en:salty-snacks",
    "crackers": "en:crackers",
    "cookies": "en:cookies",
    "cookie": "en:cookies",
    "prepared-meals": "en:prepared-meals",
    "ready meals": "en:prepared-meals",
    "ready meal": "en:prepared-meals",
    "soups": "en:soups",
    "soup": "en:soups",
}


class TaxonomyMapper:
    """Applies OFF taxonomy mapping before SQL generation."""

    def map_constraints(self, constraints: ExtractedConstraints) -> ExtractedConstraints:
        if not constraints.category:
            return constraints

        normalized = constraints.category.strip().lower()
        category_tag = CATEGORY_MAP.get(normalized)
        if category_tag is None:
            singular = normalized[:-1] if normalized.endswith("s") else normalized
            category_tag = CATEGORY_MAP.get(singular)

        if category_tag is None:
            category_tag = f"en:{normalized.replace(' ', '-') }"

        return replace(constraints, category_tag=category_tag)
