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

import textwrap
from dataclasses import dataclass, field
from typing import List, Optional

from .data_adapter import OFFDataAdapter, Product
from .insight_engine import InsightEngine, ProductInsight
from .intent_parser import FoodQuery, IntentParser
from .recommendation_engine import Recommendation, RecommendationEngine


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
        self._adapter = adapter or OFFDataAdapter()
        self._insight_engine = InsightEngine()
        self._rec_engine = RecommendationEngine()
        self.max_results = max_results

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, user_query: str) -> PipelineResult:
        """Execute the full pipeline for *user_query*."""
        # 1. Parse intent
        query = self._parser.parse(user_query)
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

    def _run_search(
        self, query: FoodQuery, result: PipelineResult
    ) -> PipelineResult:
        """Search mode: retrieve products and generate insights."""
        products = self._adapter.search(query)
        result.products = products
        result.insights = [self._insight_engine.analyze(p) for p in products]
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
