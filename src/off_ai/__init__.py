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
from .recommendation_engine import RecommendationEngine, Recommendation
from .pipeline import FoodIntelligencePipeline

__all__ = [
    "IntentParser",
    "FoodQuery",
    "OFFDataAdapter",
    "Product",
    "InsightEngine",
    "ProductInsight",
    "RecommendationEngine",
    "Recommendation",
    "FoodIntelligencePipeline",
]
