"""End-to-end semantic food search pipeline."""

from __future__ import annotations

import copy
import logging
import time
import textwrap
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .constraint_extractor import ConstraintExtractor, ExtractedConstraints
from .data_adapter import OFFDataAdapter, Product
from .insight_engine import InsightEngine, ProductInsight
from .intent_parser import FoodQuery, IntentParser, NutrientConstraint
from .post_processor import RankingPostProcessor
from .query_preprocessor import QueryPreprocessor
from .recommendation_engine import Recommendation, RecommendationEngine
from .semantic_reranker import SemanticReranker
from .taxonomy_mapper import TaxonomyMapper

logger = logging.getLogger(__name__)


@dataclass
class RankedProduct:
    product: Product
    insight: ProductInsight
    score: float
    explanation: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "product": self.product.to_dict(),
            "insight": self.insight.to_dict(),
            "score": round(self.score, 3),
            "explanation": self.explanation,
        }


@dataclass
class PipelineResult:
    """Full result of a food intelligence query."""

    query: FoodQuery
    results: List[RankedProduct] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)
    reference_product: Optional[Product] = None
    relaxation_log: List[str] = field(default_factory=list)
    applied_filters: List[str] = field(default_factory=list)
    interpreted_query: dict = field(default_factory=dict)
    generated_sql: str = ""
    ranking_rationale: List[str] = field(default_factory=list)
    performance: dict = field(default_factory=dict)

    @property
    def products(self) -> List[Product]:
        return [item.product for item in self.results]

    @property
    def insights(self) -> List[ProductInsight]:
        return [item.insight for item in self.results]

    def to_dict(self) -> dict:
        return {
            "query": self.query.to_dict(),
            "interpreted_query": self.interpreted_query,
            "applied_filters": self.applied_filters,
            "generated_sql": self.generated_sql,
            "results": [item.to_dict() for item in self.results],
            "products": [product.to_dict() for product in self.products],
            "insights": [insight.to_dict() for insight in self.insights],
            "recommendations": [recommendation.to_dict() for recommendation in self.recommendations],
            "reference_product": self.reference_product.to_dict() if self.reference_product else None,
            "relaxation_log": self.relaxation_log,
            "ranking_rationale": self.ranking_rationale,
            "performance": self.performance,
        }

    def __str__(self) -> str:
        lines: List[str] = []
        lines.append("=" * 60)
        lines.append("QUERY INTERPRETATION")
        lines.append("=" * 60)
        lines.append(f"User query: {self.query.raw_text}")
        lines.append("")
        lines.append("Structured interpretation:")
        lines.append(textwrap.indent(str(self.query), "  "))
        lines.append("")

        if self.generated_sql:
            lines.append("Generated DuckDB SQL:")
            lines.append(textwrap.indent(self.generated_sql, "  "))
            lines.append("")

        if self.ranking_rationale:
            lines.append("Ranked by:")
            for criterion in self.ranking_rationale:
                lines.append(f"  - {criterion}")
            lines.append("")

        if self.reference_product:
            lines.append("=" * 60)
            lines.append("REFERENCE PRODUCT")
            lines.append("=" * 60)
            lines.append(f"  {self.reference_product.name} ({self.reference_product.brands})")
            lines.append("")

        if self.relaxation_log:
            lines.append("Relaxation applied:")
            for log_entry in self.relaxation_log:
                lines.append(f"  - {log_entry}")
            lines.append("")

        if self.recommendations:
            lines.append("=" * 60)
            lines.append("BETTER ALTERNATIVES")
            lines.append("=" * 60)
            for recommendation in self.recommendations:
                lines.append(str(recommendation))
                lines.append("")
            return "\n".join(lines)

        if not self.results:
            lines.append("No products matched the current filters.")
            return "\n".join(lines)

        lines.append("=" * 60)
        lines.append(f"TOP RESULTS ({len(self.results)} products)")
        lines.append("=" * 60)
        for item in self.results[:5]:
            lines.append(f"- {item.product.name} ({item.product.brands})")
            lines.append(f"  Score: {item.score:.2f} | Health: {item.insight.health_classification}")
            for reason in item.explanation[:3]:
                lines.append(f"  * {reason}")
            lines.append("")
        return "\n".join(lines)


class FoodIntelligencePipeline:
    """Pipeline for preprocessing, parsing, SQL generation, ranking, and explanations."""

    def __init__(
        self,
        adapter: Optional[OFFDataAdapter] = None,
        max_results: int = 10,
    ) -> None:
        self._parser = IntentParser()
        self._preprocessor = QueryPreprocessor()
        self._constraint_extractor = ConstraintExtractor()
        self._taxonomy_mapper = TaxonomyMapper()
        self._post_processor = RankingPostProcessor()
        self._adapter = adapter or OFFDataAdapter()
        self._insight_engine = InsightEngine()
        self._rec_engine = RecommendationEngine()
        self._semantic_reranker = SemanticReranker()
        self.max_results = max_results

    def run(self, user_query: str) -> PipelineResult:
        total_start = time.perf_counter()
        preprocess_start = time.perf_counter()
        pre = self._preprocessor.preprocess(user_query)
        preprocess_ms = (time.perf_counter() - preprocess_start) * 1000.0
        parse_start = time.perf_counter()
        query = self._parser.parse(pre.normalized_text)
        selected_normalized = pre.normalized_text
        if pre.language == "fr":
            deterministic_fr = self._preprocessor.normalize(user_query.lower().strip(), "fr")
            deterministic_query = self._parser.parse(deterministic_fr)
            query, used_deterministic = self._merge_parsed_queries(query, deterministic_query)
            if used_deterministic:
                selected_normalized = deterministic_fr
        parse_ms = (time.perf_counter() - parse_start) * 1000.0
        query.raw_text = user_query
        query.detected_language = pre.language
        query.normalized_text = selected_normalized
        query.max_results = self.max_results

        logger.debug(
            "PIPELINE | lang=%s | norm=%r | category=%s | dietary=%s | nutrients=%r",
            pre.language,
            pre.normalized_text,
            query.category,
            query.dietary_tags,
            [(c.nutrient, c.operator, c.value) for c in query.nutrient_constraints],
        )
        logger.debug("FOOD_QUERY: %s", query.to_dict())

        result = PipelineResult(query=query)
        if query.comparison_product:
            result = self._run_comparison(query, result)
        else:
            result = self._run_search(query, result)

        total_ms = (time.perf_counter() - total_start) * 1000.0
        result.performance.update(
            {
                "preprocess_ms": round(preprocess_ms, 3),
                "parse_ms": round(parse_ms, 3),
                "total_ms": round(total_ms, 3),
                "results_returned": len(result.results),
            }
        )
        return result

    def run_parsed(self, query: FoodQuery) -> PipelineResult:
        if query.comparison_product:
            return self._run_comparison(query, PipelineResult(query=query))
        return self._run_search(query, PipelineResult(query=query))

    def health_check(self) -> dict:
        return self._adapter.health_check()

    def _find_relaxable_constraint(self, query: FoodQuery) -> Optional[Tuple[int, NutrientConstraint]]:
        relax_priority = [
            "energy_kcal_100g",
            "fat_100g",
            "carbohydrates_100g",
            "sugars_100g",
            "proteins_100g",
        ]
        for nutrient in relax_priority:
            for index, constraint in enumerate(query.nutrient_constraints):
                if constraint.nutrient == nutrient:
                    return index, constraint
        if query.nutrient_constraints:
            return 0, query.nutrient_constraints[0]
        return None

    def _query_signal_score(self, query: FoodQuery) -> int:
        return (
            (2 if query.category else 0)
            + (len(query.dietary_tags) * 2)
            + (len(query.nutrient_constraints) * 3)
            + len(query.ranking_preferences)
        )

    def _canonicalize_dietary_tags(self, tags: List[str]) -> List[str]:
        deduped = list(dict.fromkeys(tags))
        # Vegan is stricter and implies vegetarian; keep only vegan when both are present.
        if "vegan" in deduped and "vegetarian" in deduped:
            deduped = [tag for tag in deduped if tag != "vegetarian"]
        return deduped

    def _merge_parsed_queries(self, primary: FoodQuery, secondary: FoodQuery) -> Tuple[FoodQuery, bool]:
        merged = copy.deepcopy(primary)

        if not merged.category and secondary.category:
            merged.category = secondary.category

        merged.dietary_tags = self._canonicalize_dietary_tags(
            list(primary.dietary_tags) + list(secondary.dietary_tags)
        )
        merged.ranking_preferences = list(
            dict.fromkeys(list(primary.ranking_preferences) + list(secondary.ranking_preferences))
        )

        strictest: dict[Tuple[str, str], NutrientConstraint] = {}
        for constraint in list(primary.nutrient_constraints) + list(secondary.nutrient_constraints):
            key = (constraint.nutrient, constraint.operator)
            current = strictest.get(key)
            if current is None:
                strictest[key] = copy.deepcopy(constraint)
                continue
            if constraint.operator.startswith("<"):
                if constraint.value < current.value:
                    strictest[key] = copy.deepcopy(constraint)
            elif constraint.operator.startswith(">"):
                if constraint.value > current.value:
                    strictest[key] = copy.deepcopy(constraint)
        merged.nutrient_constraints = list(strictest.values())

        merged.search_terms = list(dict.fromkeys(list(primary.search_terms) + list(secondary.search_terms)))
        merged.comparison_product = primary.comparison_product or secondary.comparison_product

        used_secondary_as_primary = self._query_signal_score(secondary) > self._query_signal_score(primary)
        return merged, used_secondary_as_primary

    def _run_search(self, query: FoodQuery, result: PipelineResult) -> PipelineResult:
        extracted = self._constraint_extractor.extract(query)
        mapped_constraints = self._taxonomy_mapper.map_constraints(extracted)
        result.interpreted_query = mapped_constraints.interpreted_query()
        result.applied_filters = mapped_constraints.applied_filters()

        execution = self._adapter.execute_constraints(mapped_constraints, candidate_limit=50)
        products = execution.products
        relaxation_log: List[str] = []
        current_query = copy.deepcopy(query)
        current_constraints = mapped_constraints
        current_execution = execution

        # Step 1: initial query run is done above.
        # Step 2: if empty, relax nutrients gradually (numeric-only safety mode).
        if not products and current_constraints.nutrient_constraints:
            for _relax_pass in range(2):
                current_constraints, nutrient_changes = self._post_processor.relax_nutrients(current_constraints)
                relaxation_log.extend(nutrient_changes)
                current_execution = self._adapter.execute_constraints(current_constraints, candidate_limit=50)
                products = current_execution.products
                logger.debug(
                    "RELAX pass %d | changes=%s | results=%d",
                    _relax_pass + 1, nutrient_changes, len(products),
                )
                if products:
                    break

        # Strict mode: preserve semantic intent exactly. No keyword/category/tag dropping.
        if not products and (current_constraints.keywords or current_constraints.dietary_tags or current_constraints.category):
            relaxation_log.append("semantic constraints preserved (no keyword/tag/category removal)")

        # Keep ranking/explanations aligned with the final executed constraints.
        current_query.category = current_constraints.category
        current_query.nutrient_constraints = list(current_constraints.nutrient_constraints)
        current_query.dietary_tags = list(current_constraints.dietary_tags)
        current_query.search_terms = list(current_constraints.keywords)

        # Show what actually got executed after any relaxation.
        result.interpreted_query = current_constraints.interpreted_query()
        result.applied_filters = current_constraints.applied_filters()

        result.generated_sql = current_execution.sql
        result.relaxation_log = relaxation_log
        logger.debug("SQL: %.600s", current_execution.sql)
        logger.debug("RELAX_LOG: %s", relaxation_log)
        result.performance.update(
            {
                "duckdb_execution_ms": round(current_execution.execution_time_ms, 3),
                "candidate_rows": current_execution.rows_returned,
            }
        )
        ranking_start = time.perf_counter()
        ranked_results = self._rank_results(products, current_query)
        result.results = ranked_results[: self.max_results]
        result.performance["ranking_ms"] = round((time.perf_counter() - ranking_start) * 1000.0, 3)
        result.ranking_rationale = self._post_processor.ranking_rationale(
            has_category=bool(current_constraints.category),
            has_dietary_tags=bool(current_constraints.dietary_tags),
            nutrient_constraints=current_constraints.nutrient_constraints,
            excluded_ingredients=current_constraints.excluded_ingredients,
            prefer_healthy=("healthy" in current_query.ranking_preferences),
        )
        return result

    def _rank_results(self, products: List[Product], query: FoodQuery) -> List[RankedProduct]:
        semantic_scores = self._semantic_reranker.score_products(query.raw_text or query.normalized_text or "", products)
        ranked: List[RankedProduct] = []
        for product in products:
            insight = self._insight_engine.analyze(product)
            score = self._score_product(product, query, insight, semantic_scores.get(product.barcode, 0.0))
            explanation = self._build_explanation(product, query, insight)
            ranked.append(RankedProduct(product=product, insight=insight, score=score, explanation=explanation))
        ranked.sort(key=lambda item: item.score, reverse=True)
        for _i, _item in enumerate(ranked[:5]):
            logger.debug(
                "RANK #%d | score=%.2f | semantic=%.3f | %s | nutrients=%s",
                _i + 1,
                _item.score,
                semantic_scores.get(_item.product.barcode, 0.0),
                _item.product.name,
                {c.nutrient.replace("_100g", ""): _item.product.nutrient(c.nutrient) for c in query.nutrient_constraints},
            )
        return ranked

    def _score_product(self, product: Product, query: FoodQuery, insight: ProductInsight, semantic_similarity: float) -> float:
        score = self._rec_engine._composite_score(product) * 8

        # Semantic similarity from embedding/lexical reranker in [0, 1]
        score += semantic_similarity * 40.0

        # Always reward better Nutri-Score so results are ordered A→B→C→D→E
        _NUTRISCORE_BONUS = {"a": 15, "b": 10, "c": 5, "d": 2, "e": 0}
        if product.nutriscore:
            score += _NUTRISCORE_BONUS.get(product.nutriscore.lower(), 0)

        if query.category and any(query.category in category.lower() for category in product.categories):
            score += 8

        for tag in query.dietary_tags:
            if product.has_label(tag):
                score += 6

        for constraint in query.nutrient_constraints:
            value = product.nutrient(constraint.nutrient)
            if value is None or not self._matches_constraint(product, constraint):
                continue
            score += 5
            score += self._constraint_headroom_bonus(value, constraint)

        # Penalty for products that violate any stated nutrient constraint.
        # This down-ranks items that slipped through a relaxed SQL filter but
        # still violate the user's original intent.
        for constraint in query.nutrient_constraints:
            value = product.nutrient(constraint.nutrient)
            if value is not None and not self._matches_constraint(product, constraint):
                score -= 15.0

        # Sugar penalty: penalise high-sugar products unless category is confectionery.
        _sweet_cats = {"candies", "chocolates", "cookies"}
        if not any(sc in " ".join(product.categories).lower() for sc in _sweet_cats):
            sugars = product.nutrient("sugars_100g")
            if sugars is not None and sugars > 15.0:
                score -= min(10.0, (sugars - 15.0) * 0.4)

        # Calorie penalty: for queries with an explicit upper-calorie limit,
        # penalise products that exceed that limit (after relaxation they may pass SQL).
        _calorie_limits = [
            c.value for c in query.nutrient_constraints
            if c.nutrient == "energy_kcal_100g" and c.operator in ("<", "<=")
        ]
        if _calorie_limits:
            calories = product.nutrient("energy_kcal_100g")
            _limit = min(_calorie_limits)
            if calories is not None and calories > _limit:
                score -= min(20.0, (calories - _limit) * 0.05)

        if "healthy" in query.ranking_preferences:
            score += {"Excellent": 10, "Good": 7, "Moderate": 3, "Risky": 0}.get(
                insight.health_classification,
                0,
            )
            score += self._healthy_preference_bonus(product)

        if "kids" in query.ranking_preferences:
            sugars = product.nutrient("sugars_100g")
            if sugars is not None:
                score += self._bounded_lower_is_better_bonus(sugars, good_threshold=3.0, cutoff_threshold=15.0, max_bonus=8.0)

        for term in query.search_terms:
            if self._term_matches_product(term, product):
                score += 0.5

        return score

    def _constraint_headroom_bonus(self, value: float, constraint: NutrientConstraint) -> float:
        baseline = max(abs(constraint.value), 1.0)
        if constraint.operator in ("<", "<="):
            margin = max(0.0, constraint.value - value)
        elif constraint.operator in (">", ">="):
            margin = max(0.0, value - constraint.value)
        else:
            return 0.0
        return min(2.5, (margin / baseline) * 2.5)

    def _healthy_preference_bonus(self, product: Product) -> float:
        bonus = self._rec_engine._nutrient_score(product) * 3.0
        bonus += self._bounded_lower_is_better_bonus(
            product.nutrient("sodium_100g"),
            good_threshold=0.12,
            cutoff_threshold=0.6,
            max_bonus=3.0,
        )
        bonus += self._bounded_lower_is_better_bonus(
            product.nutrient("sugars_100g"),
            good_threshold=5.0,
            cutoff_threshold=22.5,
            max_bonus=2.5,
        )
        bonus += self._bounded_lower_is_better_bonus(
            product.nutrient("energy_kcal_100g"),
            good_threshold=250.0,
            cutoff_threshold=450.0,
            max_bonus=1.5,
        )
        bonus += self._bounded_higher_is_better_bonus(
            product.nutrient("proteins_100g"),
            minimum_threshold=5.0,
            target_threshold=15.0,
            max_bonus=2.5,
        )
        bonus += self._bounded_higher_is_better_bonus(
            product.nutrient("fiber_100g"),
            minimum_threshold=3.0,
            target_threshold=8.0,
            max_bonus=2.0,
        )
        return bonus

    def _bounded_lower_is_better_bonus(
        self,
        value: Optional[float],
        good_threshold: float,
        cutoff_threshold: float,
        max_bonus: float,
    ) -> float:
        if value is None:
            return 0.0
        if value <= good_threshold:
            return max_bonus
        if value >= cutoff_threshold:
            return 0.0
        span = cutoff_threshold - good_threshold
        if span <= 0:
            return 0.0
        return max_bonus * ((cutoff_threshold - value) / span)

    def _bounded_higher_is_better_bonus(
        self,
        value: Optional[float],
        minimum_threshold: float,
        target_threshold: float,
        max_bonus: float,
    ) -> float:
        if value is None:
            return 0.0
        if value <= minimum_threshold:
            return 0.0
        if value >= target_threshold:
            return max_bonus
        span = target_threshold - minimum_threshold
        if span <= 0:
            return 0.0
        return max_bonus * ((value - minimum_threshold) / span)

    def _ranking_rationale(self, query: FoodQuery) -> List[str]:
        return self._post_processor.ranking_rationale(
            has_category=bool(query.category),
            has_dietary_tags=bool(query.dietary_tags),
        )

    def _build_explanation(
        self,
        product: Product,
        query: FoodQuery,
        insight: ProductInsight,
    ) -> List[str]:
        reasons: List[str] = []

        if query.category and any(query.category in category.lower() for category in product.categories):
            reasons.append(f"Matches category '{query.category}'")

        for tag in query.dietary_tags:
            if product.has_label(tag):
                reasons.append(f"Matches {tag} label")

        for constraint in query.nutrient_constraints:
            value = product.nutrient(constraint.nutrient)
            if value is None or not self._matches_constraint(product, constraint):
                continue
            nutrient_label = constraint.nutrient.replace("_100g", "").replace("_", " ")
            reasons.append(
                f"{nutrient_label.title()} {value:g} satisfies {constraint.operator} {constraint.value:g} {constraint.unit}/100g"
            )

        if "healthy" in query.ranking_preferences and product.nutriscore in {"a", "b", "c", "d", "e"}:
            reasons.append(f"Nutri-Score {product.nutriscore.upper()} supports healthy preference")

        if "kids" in query.ranking_preferences:
            sugars = product.nutrient("sugars_100g")
            if sugars is not None:
                reasons.append(f"Sugar level {sugars:g} g/100g is suitable for kid-focused ranking")

        for term in query.search_terms:
            if self._term_matches_product(term, product):
                reasons.append(f"Matches search term '{term}'")

        if not reasons:
            reasons.append(insight.summary)

        return list(dict.fromkeys(reasons))[:4]

    def _matches_constraint(self, product: Product, constraint: NutrientConstraint) -> bool:
        return product.passes_constraints([constraint], allow_missing=False)

    def _term_matches_product(self, term: str, product: Product) -> bool:
        haystack = " ".join(
            [
                product.name,
                product.brands,
                " ".join(product.categories),
                product.ingredients_text,
            ]
        ).lower()
        return term.lower() in haystack

    def _run_comparison(self, query: FoodQuery, result: PipelineResult) -> PipelineResult:
        reference_product = self._adapter.find_reference_product(query.comparison_product or "")
        if reference_product is None:
            return result

        result.reference_product = reference_product
        category = reference_product.categories[0] if reference_product.categories else query.category
        if category:
            candidates = self._adapter.get_category_products(category, max_results=50)
        else:
            fallback_query = FoodQuery(raw_text=reference_product.name, search_terms=query.search_terms, max_results=50)
            candidates = self._adapter.search(fallback_query)

        result.recommendations = self._rec_engine.recommend(reference_product, candidates)
        return result
