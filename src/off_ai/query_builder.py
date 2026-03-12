"""DuckDB query builder layer for OFF product search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from .constraint_extractor import ExtractedConstraints

_LABEL_PATTERNS = {
    "vegan": ["%vegan%", "%plant-based%"],
    "vegetarian": ["%vegetarian%"],
    "gluten-free": ["%gluten-free%", "%gluten free%"],
    "organic": ["%organic%", "%bio%"],
    "dairy-free": ["%dairy-free%", "%dairy free%", "%lactose-free%"],
    "lactose-free": ["%lactose-free%", "%lactose free%"],
    "halal": ["%halal%"],
    "kosher": ["%kosher%"],
}


@dataclass
class BuiltQuery:
    sql: str
    parameters: List[Any]


class QueryBuilder:
    """Builds SQL using extracted constraints and resolved schema expressions."""

    def build(
        self,
        adapter: Any,
        constraints: ExtractedConstraints,
        allow_missing_nutrients: bool = False,
        limit: Optional[int] = None,
    ) -> BuiltQuery:
        combined_text = adapter._combined_text_expr()
        product_name_text = adapter._string_expr("product_name")
        brand_text = adapter._string_expr("brands")
        category_text_field = adapter._string_expr("categories")
        ingredient_text_field = adapter._string_expr("ingredients_text")
        label_text = adapter._label_text_expr()
        ingredient_text = adapter._ingredient_text_expr()
        category_text = adapter._category_text_expr()
        countries_text = adapter._field_expr("countries_tags")

        where_clauses: List[str] = []
        parameters: List[Any] = []

        product_name_expr = adapter._field_expr("product_name")
        if product_name_expr is not None:
            where_clauses.append(f"NULLIF(TRIM(CAST({product_name_expr} AS VARCHAR)), '') IS NOT NULL")

        if countries_text is not None:
            where_clauses.append(f"CAST({countries_text} AS VARCHAR) ILIKE ?")
            parameters.append("%en:canada%")

        if constraints.category_tag and category_text:
            where_clauses.append(f"{category_text} ILIKE ?")
            parameters.append(f"%{constraints.category_tag}%")
        elif constraints.category and category_text:
            where_clauses.append(f"{category_text} ILIKE ?")
            parameters.append(f"%{constraints.category}%")

        for tag in constraints.dietary_tags:
            patterns = _LABEL_PATTERNS.get(tag, [f"%{tag}%"])
            tag_clause = " OR ".join([f"{label_text} ILIKE ?" for _ in patterns])
            where_clauses.append(f"({tag_clause})")
            parameters.extend(patterns)

        for constraint in constraints.nutrient_constraints:
            nutrient_expr = adapter._field_expr(constraint.nutrient)
            if nutrient_expr is None:
                continue
            clause = f"{nutrient_expr} {constraint.operator} ?"
            if allow_missing_nutrients:
                clause = f"({clause} OR {nutrient_expr} IS NULL)"
            where_clauses.append(clause)
            parameters.append(constraint.value)

        for ingredient in constraints.excluded_ingredients:
            normalized = ingredient.strip().lower()
            if not normalized:
                continue
            patterns = [f"%{normalized}%"]
            if " " in normalized:
                patterns.append(f"%{normalized.replace(' ', '-')}%")
            for pattern in dict.fromkeys(patterns):
                where_clauses.append(f"{ingredient_text} NOT ILIKE ?")
                parameters.append(pattern)

        keyword_terms = [term.strip().lower() for term in constraints.keywords if len(term.strip()) >= 3]
        keyword_terms = list(dict.fromkeys(keyword_terms))[:3]
        for term in keyword_terms:
            pattern = f"%{term}%"
            where_clauses.append(
                "("
                f"{product_name_text} ILIKE ? OR "
                f"{brand_text} ILIKE ? OR "
                f"{category_text_field} ILIKE ? OR "
                f"{ingredient_text_field} ILIKE ? OR "
                f"{combined_text} ILIKE ?"
                ")"
            )
            parameters.extend([pattern, pattern, pattern, pattern, pattern])

        limit_value = limit or constraints.max_results or adapter.page_size
        parameters.append(limit_value)

        sql = adapter._select_clause()
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        sql += adapter._order_clause(constraints)
        sql += " LIMIT ?"
        return BuiltQuery(sql=sql, parameters=parameters)

    def sql_score_expression(self, adapter: Any) -> str:
        proteins = adapter._field_expr("proteins_100g") or "NULL"
        sugars = adapter._field_expr("sugars_100g") or "NULL"
        sodium = adapter._field_expr("sodium_100g") or "NULL"
        calories = adapter._field_expr("energy_kcal_100g") or "NULL"
        return (
            f"(COALESCE({proteins}, 0) * 2 "
            f"- COALESCE({sugars}, 0) "
            f"- COALESCE({sodium}, 0) * 1.5 "
            f"- COALESCE({calories}, 0) * 0.1)"
        )
