"""
off_ai - Open Food Facts AI Intelligence Engine

Modules:
    intent_parser        - Natural language → structured food queries
    data_adapter         - Open Food Facts API interface
    insight_engine       - Automated product health insights
    recommendation_engine - Intelligent food recommendations
    pipeline             - End-to-end query pipeline
"""

from .intent_parser import IntentParser, FoodQuery
from .data_adapter import OFFDataAdapter, Product
from .insight_engine import InsightEngine, ProductInsight
from .query_preprocessor import QueryPreprocessor
from .recommendation_engine import RecommendationEngine, Recommendation
from .constraint_extractor import ConstraintExtractor, ExtractedConstraints
from .taxonomy_mapper import TaxonomyMapper
from .query_builder import QueryBuilder
from .post_processor import RankingPostProcessor
from .semantic_reranker import SemanticReranker
from .pipeline import FoodIntelligencePipeline

__all__ = [
    "IntentParser",
    "FoodQuery",
    "OFFDataAdapter",
    "Product",
    "InsightEngine",
    "ProductInsight",
    "QueryPreprocessor",
    "RecommendationEngine",
    "Recommendation",
    "ConstraintExtractor",
    "ExtractedConstraints",
    "TaxonomyMapper",
    "QueryBuilder",
    "RankingPostProcessor",
    "SemanticReranker",
    "FoodIntelligencePipeline",
]
