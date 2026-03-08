"""
api.py - FastAPI REST wrapper for OFF AI Search

Exposes the existing CLI pipeline as a web service for the browser extension.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .data_adapter import Product
from .intent_parser import FoodQuery
from .pipeline import FoodIntelligencePipeline, PipelineResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app initialization
# ---------------------------------------------------------------------------

app = FastAPI(
    title="OFF AI Search API",
    description="Natural language search interface for Open Food Facts Canada",
    version="1.0.0",
)

# Enable CORS for browser extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to extension origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    """Request body for /nl-search endpoint."""

    query: str


class InterpretedQuery(BaseModel):
    """Structured interpretation of the natural language query."""

    language: str
    raw_text: str
    category: Optional[str] = None
    dietary_tags: List[str] = []
    nutrient_constraints: Dict[str, Any] = {}
    ingredient_exclusions: List[str] = []


class ProductCard(BaseModel):
    """Product card for frontend display."""

    name: str
    image: str
    nutriscore: Optional[str] = None
    category: str
    summary: str
    url: str
    barcode: str


class SearchResponse(BaseModel):
    """Response body for /nl-search endpoint."""

    interpreted_query: InterpretedQuery
    products: List[ProductCard]
    relaxation_applied: bool = False
    relaxation_info: List[str] = []


# ---------------------------------------------------------------------------
# Nutrition summary generator (rule-based)
# ---------------------------------------------------------------------------


def generate_nutrition_summary(product: Product, query: FoodQuery) -> str:
    """
    Generate a human-readable nutrition summary based on product attributes.

    This is rule-based (not LLM-based) for:
    - Speed
    - Determinism
    - Testability
    - Explainability

    Returns up to 2 key insights.
    """
    insights = []

    # Nutritional quality scoring
    if product.nutriscore in ["a", "b"]:
        insights.append("Good nutritional quality")

    # Protein content
    protein = product.nutrient("proteins_100g")
    if protein and protein >= 10:
        insights.append("High protein")

    # Sugar content
    sugars = product.nutrient("sugars_100g")
    if sugars is not None and sugars < 5:
        insights.append("Low sugar")

    # Fiber content
    fiber = product.nutrient("fiber_100g")
    if fiber and fiber >= 6:
        insights.append("High fiber")

    # Processing level
    if product.nova_group and product.nova_group <= 2:
        insights.append("Minimally processed")

    # Sodium content
    sodium = product.nutrient("sodium_100g")
    if sodium is not None and sodium < 0.1:
        insights.append("Low sodium")

    # Fat content
    fat = product.nutrient("fat_100g")
    if fat is not None and fat < 3:
        insights.append("Low fat")

    # If no specific insights, use generic quality indicators
    if not insights:
        if product.nutriscore:
            insights.append(f"NutriScore {product.nutriscore.upper()}")
        if product.nova_group:
            insights.append(f"NOVA group {product.nova_group}")

    # Return top 2 insights
    return ", ".join(insights[:2]) if insights else "See details"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def map_food_query_to_interpreted_query(query: FoodQuery) -> InterpretedQuery:
    """Convert internal FoodQuery to API InterpretedQuery format."""
    nutrient_constraints = {}

    for constraint in query.nutrient_constraints:
        key = f"{constraint.nutrient}_{constraint.operator}"
        nutrient_constraints[key] = constraint.value

    return InterpretedQuery(
        language=query.detected_language,
        raw_text=query.raw_text,
        category=query.category,
        dietary_tags=query.dietary_tags,
        nutrient_constraints=nutrient_constraints,
        ingredient_exclusions=query.excluded_ingredients,
    )


def map_product_to_card(product: Product, query: FoodQuery) -> ProductCard:
    """Convert internal Product to API ProductCard format."""
    # Generate nutrition summary
    summary = generate_nutrition_summary(product, query)

    # Get primary category (first one if multiple)
    category = product.categories[0] if product.categories else "Unknown"

    return ProductCard(
        name=product.name or "Unknown Product",
        image=product.image_url or "",
        nutriscore=product.nutriscore,
        category=category,
        summary=summary,
        url=product.product_url or f"https://ca.openfoodfacts.org/product/{product.barcode}",
        barcode=product.barcode,
    )


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "OFF AI Search API",
        "status": "running",
        "version": "1.0.0",
    }


@app.post("/nl-search", response_model=SearchResponse)
async def natural_language_search(request: SearchRequest) -> SearchResponse:
    """
    Natural language search endpoint.

    Accepts conversational queries like:
    - "high protein vegan snack under 200 calories"
    - "low sugar cereal for kids"
    - "céréales faibles en sucre"

    Returns structured interpretation + matching products.
    """
    try:
        # Initialize pipeline
        pipeline = FoodIntelligencePipeline()

        # Execute search
        result: PipelineResult = pipeline.run(request.query)

        # Map to API response format
        interpreted_query = map_food_query_to_interpreted_query(result.query)
        product_cards = [
            map_product_to_card(product, result.query) for product in result.products
        ]

        # Check if constraint relaxation was applied
        relaxation_applied = len(result.relaxation_log) > 0
        relaxation_info = result.relaxation_log if relaxation_applied else []

        return SearchResponse(
            interpreted_query=interpreted_query,
            products=product_cards,
            relaxation_applied=relaxation_applied,
            relaxation_info=relaxation_info,
        )

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}",
        )


@app.get("/health")
async def health_check():
    """Detailed health check with OFF API connectivity test."""
    import requests

    try:
        # Test OFF API connectivity
        response = requests.get(
            "https://ca.openfoodfacts.org/api/v2/search",
            params={"page_size": 1, "countries_tags": "canada"},
            timeout=5,
        )
        off_status = "ok" if response.status_code == 200 else "error"
    except Exception as e:
        off_status = f"error: {str(e)}"

    return {
        "service": "OFF AI Search API",
        "status": "healthy",
        "off_api": off_status,
    }
