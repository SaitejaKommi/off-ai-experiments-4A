"""Post-processing layer for query relaxation and result explanation."""

from __future__ import annotations

from typing import List, Tuple

from .constraint_extractor import ExtractedConstraints


class RankingPostProcessor:
    """Handles relaxation loop bookkeeping and rationale enrichment."""

    def relax_nutrients(self, constraints: ExtractedConstraints) -> Tuple[ExtractedConstraints, List[str]]:
        """Relax nutrient bounds in small deterministic steps.

        - Calories upper bound: +50 per pass (e.g. 300 -> 350 -> 400).
        - Other upper bounds: +15% per pass.
        - Protein/Fiber lower bounds: -2 per pass.
        - Other lower bounds: -10% per pass.
        """
        updated = constraints.clone()
        changes: List[str] = []
        for index, constraint in enumerate(updated.nutrient_constraints):
            old_value = constraint.value
            if constraint.operator in (">", ">="):
                if constraint.nutrient in {"proteins_100g", "fiber_100g"}:
                    updated.nutrient_constraints[index].value = round(max(0.0, old_value - 2.0), 3)
                else:
                    updated.nutrient_constraints[index].value = round(max(0.0, old_value * 0.9), 3)
            elif constraint.operator in ("<", "<="):
                if constraint.nutrient == "energy_kcal_100g":
                    updated.nutrient_constraints[index].value = round(old_value + 50.0, 3)
                else:
                    updated.nutrient_constraints[index].value = round(old_value * 1.15, 3)
            if updated.nutrient_constraints[index].value != old_value:
                nutrient = constraint.nutrient.replace("_100g", "")
                changes.append(
                    f"{nutrient} {constraint.operator} changed from {old_value:g} to {updated.nutrient_constraints[index].value:g}"
                )
        return updated, changes

    def remove_category(self, constraints: ExtractedConstraints) -> Tuple[ExtractedConstraints, List[str]]:
        if not constraints.category and not constraints.category_tag:
            return constraints, []
        updated = constraints.clone()
        prior_category = updated.category
        prior_tag = updated.category_tag
        updated.category = None
        updated.category_tag = None
        if prior_category or prior_tag:
            details = ", ".join([d for d in [f"category={prior_category}" if prior_category else "", f"tag={prior_tag}" if prior_tag else ""] if d])
            return updated, [f"category constraint removed ({details})"]
        return updated, ["category constraint removed"]

    def ranking_rationale(
        self,
        has_category: bool,
        has_dietary_tags: bool,
        nutrient_constraints=None,
        excluded_ingredients=None,
        prefer_healthy: bool = True,
    ) -> List[str]:
        rationale = ["Best Nutri-Score"]
        if nutrient_constraints:
            for c in nutrient_constraints:
                nutrient_label = c.nutrient.replace("_100g", "").replace("_", " ").title()
                direction = "Low" if c.operator in ("<=", "<") else "High"
                rationale.append(f"{direction} {nutrient_label}")
        elif prefer_healthy:
            rationale += ["High protein", "Low sugar", "Low sodium", "Lower calories"]
        if has_category:
            rationale.append("Category relevance")
        if has_dietary_tags:
            rationale.append("Dietary label match")
        if excluded_ingredients:
            rationale.extend([f"No {ingredient}" for ingredient in excluded_ingredients[:2]])
        return rationale
