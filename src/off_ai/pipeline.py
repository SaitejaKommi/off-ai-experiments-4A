"""
pipeline.py – End-to-end Food Intelligence Pipeline

Orchestrates the full query flow:
    User Query
        ↓ IntentParser
    Structured FoodQuery
        ↓ OFFDataAdapter
    List[Product]
        ↓ InsightEngine
    List[ProductInsight]
        ↓ RecommendationEngine (when comparison_product is set)
    PipelineResult
"""

from __future__ import annotations

import logging
import textwrap
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .data_adapter import OFFDataAdapter, Product
from .insight_engine import InsightEngine, ProductInsight
from .intent_parser import FoodQuery, IntentParser
from .query_preprocessor import QueryPreprocessor
from .recommendation_engine import Recommendation, RecommendationEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Full result of a food intelligence query."""

    query: FoodQuery
    products: List[Product] = field(default_factory=list)
    insights: List[ProductInsight] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)
    reference_product: Optional[Product] = None
    relaxation_log: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "query": self.query.to_dict(),
            "products": [p.to_dict() for p in self.products],
            "insights": [i.to_dict() for i in self.insights],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "reference_product": self.reference_product.to_dict() if self.reference_product else None,
        }

    def __str__(self) -> str:
        lines: List[str] = []

        # --- Query interpretation ---
        lines.append("=" * 60)
        lines.append("QUERY INTERPRETATION")
        lines.append("=" * 60)
        lines.append(f"User query: {self.query.raw_text}")
        lines.append("")
        lines.append("Structured interpretation:")
        lines.append(textwrap.indent(str(self.query), "  "))
        lines.append("")

        # --- Comparison mode ---
        if self.reference_product:
            lines.append("=" * 60)
            lines.append("REFERENCE PRODUCT")
            lines.append("=" * 60)
            lines.append(f"  {self.reference_product.name} ({self.reference_product.brands})")
            ns = (self.reference_product.nutriscore or "?").upper()
            lines.append(f"  Nutri-Score: {ns}")
            if self.reference_product.nova_group:
                lines.append(f"  NOVA group: {self.reference_product.nova_group}")
            lines.append("")

        # --- Constraint relaxation ---
        if self.relaxation_log:
            lines.append("=" * 60)
            lines.append("CONSTRAINT RELAXATION")
            lines.append("=" * 60)
            lines.append("No products found with strict filters. Relaxing constraints:")
            for log_entry in self.relaxation_log:
                lines.append(f"  ✓ {log_entry}")
            lines.append("")

        # --- Recommendations ---
        if self.recommendations:
            lines.append("=" * 60)
            lines.append("BETTER ALTERNATIVES")
            lines.append("=" * 60)
            for rec in self.recommendations:
                lines.append(str(rec))
                lines.append("")
        elif self.insights:
            # --- Product search results ---
            lines.append("=" * 60)
            lines.append(f"TOP RESULTS  ({len(self.products)} products found)")
            lines.append("=" * 60)
            for insight in self.insights[:5]:
                lines.append(str(insight))
                lines.append("-" * 40)
        else:
            lines.append("=" * 60)
            lines.append("NO PRODUCTS FOUND")
            lines.append("=" * 60)
            lines.append("No products matched all current filters.")
            lines.append("Try relaxing one constraint (e.g. calories/protein/fat) or broadening category terms.")
            lines.append("Results can also be limited by country filter and missing nutrient data in OFF.")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class FoodIntelligencePipeline:
    """Main pipeline orchestrating all components.

    Parameters
    ----------
    adapter:
        An :class:`OFFDataAdapter` instance.  If *None*, a default one is
        created.
    max_results:
        Default number of products to retrieve.
    """

    def __init__(
        self,
        adapter: Optional[OFFDataAdapter] = None,
        max_results: int = 10,
    ) -> None:
        self._parser = IntentParser()
        self._preprocessor = QueryPreprocessor()
        self._adapter = adapter or OFFDataAdapter()
        self._insight_engine = InsightEngine()
        self._rec_engine = RecommendationEngine()
        self.max_results = max_results

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, user_query: str) -> PipelineResult:
        """Execute the full pipeline for *user_query*."""
        # 1. Detect language + normalize EN/FR text
        pre = self._preprocessor.preprocess(user_query)

        # 2. Parse normalized query into structured intent
        query = self._parser.parse(pre.normalized_text)
        query.raw_text = user_query
        query.detected_language = pre.language
        query.normalized_text = pre.normalized_text
        query.max_results = self.max_results
        result = PipelineResult(query=query)

        if query.comparison_product:
            # 2a. Comparison mode – find reference product then alternatives
            result = self._run_comparison(query, result)
        else:
            # 2b. Search mode – find and score matching products
            result = self._run_search(query, result)

        return result

    def run_parsed(self, query: FoodQuery) -> PipelineResult:
        """Execute the pipeline with an already-parsed :class:`FoodQuery`."""
        result = PipelineResult(query=query)
        if query.comparison_product:
            return self._run_comparison(query, result)
        return self._run_search(query, result)

    # ------------------------------------------------------------------
    # Internal flow
    # ------------------------------------------------------------------

    def _find_relaxable_constraint(self, query: FoodQuery) -> Optional[Tuple[int, 'NutrientConstraint']]:
        """Find the next constraint to relax (by importance order).
        
        Returns (index, constraint) for the least important constraint,
        or None if all constraints have been explored or none are relaxable.
        
        Importance order (least to most important):
        1. Calorie constraints (most flexible for user)
        2. Fat/carbs/sugar constraints
        3. Protein constraints (often functional requirement)
        4. NOVA group constraints
        (Never relax: excluded_ingredients, dietary_tags, category)
        """
        # Priority order: nutrients to relax first (by importance ascending)
        relax_priority = [
            "energy-kcal_100g",  # calories - least important
            "fat_100g",
            "carbohydrates_100g",
            "sugars_100g",
            "proteins_100g",     # high protein often intentional
        ]
        
        # Find first constraint that matches the relax priority
        for nutrient in relax_priority:
            for idx, constraint in enumerate(query.nutrient_constraints):
                if constraint.nutrient == nutrient:
                    return (idx, constraint)
        
        # If no priority match, relax the first unvisited constraint
        if query.nutrient_constraints:
            return (0, query.nutrient_constraints[0])
        
        return None

    def _run_search(
        self, query: FoodQuery, result: PipelineResult
    ) -> PipelineResult:
        """Search mode: retrieve products and generate insights.
        
        If strict search returns no results, progressively relaxes constraints
        (lowest importance first) and retries up to max attempts.
        """
        products = self._adapter.search(query)
        relaxation_log = []
        
        # If no results, try relaxing constraints
        max_relaxation_attempts = len(query.nutrient_constraints)
        attempt = 0
        current_query = query
        
        logger.info(f"Starting relaxation loop. Initial products: {len(products)}, max_attempts: {max_relaxation_attempts}")
        while not products and attempt < max_relaxation_attempts:
            # Find the best constraint to relax (lowest importance first)
            constraint_to_relax = self._find_relaxable_constraint(current_query)
            if constraint_to_relax is None:
                # No more constraints to relax
                logger.info("No more constraints to relax")
                break
            
            constraint_idx, constraint_obj = constraint_to_relax
            
            # Log and relax
            log_msg = f"Relaxing constraint: {constraint_obj}"
            relaxation_log.append(log_msg)
            logger.info(log_msg)
            current_query = current_query.copy_with_relaxed_constraint(constraint_idx, relax_factor=1.2)
            
            # Retry search with relaxed constraints
            products = self._adapter.search(current_query)
            logger.info(f"After relaxation attempt {attempt + 1}: {len(products)} products found")
            attempt += 1
        
        # Final fallback: if still no products after all relaxations,
        # try again allowing products with missing nutrient data
        if not products and relaxation_log:
            logger.info("Final fallback: allowing products with missing nutrient data")
            products = self._adapter.search(current_query, allow_missing_nutrients=True)
            logger.info(f"After allowing missing nutrients: {len(products)} products found")
            if products:
                relaxation_log.append("Allowing products with incomplete nutritional data")
        
        # Always add relaxation_log to result (even if no products found)
        # This gives transparency to the user about what was attempted
        if relaxation_log:
            result.relaxation_log = relaxation_log
            logger.info(f"Relaxation log added: {relaxation_log}")
        
        result.products = products
        result.insights = [self._insight_engine.analyze(p) for p in products]
        
        # Sort results by health classification (best to worst)
        classification_rank = {
            "Excellent": 4,
            "Good": 3,
            "Moderate": 2,
            "Risky": 1,
        }
        result.insights.sort(
            key=lambda insight: classification_rank.get(insight.health_classification, 0),
            reverse=True
        )
        
        return result

    def _run_comparison(
        self, query: FoodQuery, result: PipelineResult
    ) -> PipelineResult:
        """Comparison mode: find the reference product then recommend alternatives."""
        # Search for the reference product
        ref_query = FoodQuery(
            raw_text=query.comparison_product,
            max_results=1,
        )
        ref_products = self._adapter.search(ref_query)
        if not ref_products:
            # Fall back to regular search with the full query
            return self._run_search(query, result)

        reference = ref_products[0]
        result.reference_product = reference
        result.insights = [self._insight_engine.analyze(reference)]

        # Determine category for candidates
        category = query.category or (reference.categories[0] if reference.categories else None)

        if category:
            candidates = self._adapter.get_category_products(
                category, max_results=self.max_results * 3
            )
        else:
            # Broad search without category
            broad_query = FoodQuery(
                raw_text=query.comparison_product,
                max_results=self.max_results * 3,
            )
            candidates = self._adapter.search(broad_query)

        recommendations = self._rec_engine.recommend(reference, candidates)
        result.recommendations = recommendations
        result.products = [r.product for r in recommendations]
        return result
