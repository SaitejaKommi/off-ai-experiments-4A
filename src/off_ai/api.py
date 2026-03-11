"""FastAPI interface for DuckDB-backed natural language food search."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .pipeline import FoodIntelligencePipeline, PipelineResult, RankedProduct

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="OFF AI Search API",
    description="DuckDB-powered natural language search for Open Food Facts Parquet data",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str
    max_results: int = Field(default=10, ge=1, le=50)


class ProductCard(BaseModel):
    name: str
    brand: str = ""
    image: str = ""
    nutriscore: Optional[str] = None
    category: str = ""
    summary: str
    explanation: List[str] = []
    url: str = ""
    barcode: str = ""


class SearchResponse(BaseModel):
    query: str
    interpreted_query: Dict[str, Any]
    applied_filters: List[str] = []
    generated_sql: str = ""
    ranking_rationale: List[str] = []
    relaxation: List[str] = []
    performance: Dict[str, Any] = {}
    products: List[ProductCard]


@lru_cache(maxsize=1)
def get_pipeline() -> FoodIntelligencePipeline:
    return FoodIntelligencePipeline()


def map_food_query_to_interpreted_query(result: PipelineResult) -> Dict[str, Any]:
    interpreted = dict(result.interpreted_query or {})
    interpreted.setdefault("language", result.query.detected_language)
    interpreted.setdefault("keywords", result.query.search_terms)
    return interpreted


def build_summary(item: RankedProduct) -> str:
    if item.explanation:
        return item.explanation[0]
    return item.insight.summary


def map_ranked_product_to_card(item: RankedProduct) -> ProductCard:
    product = item.product
    category = product.categories[0] if product.categories else ""
    return ProductCard(
        name=product.name or "Unknown Product",
        brand=product.brands or "",
        image=product.image_url or "",
        nutriscore=product.nutriscore,
        category=category,
        summary=build_summary(item),
        explanation=item.explanation,
        url=product.product_url,
        barcode=product.barcode,
    )


@app.get("/")
async def root():
    health = get_pipeline().health_check()
    return {
        "service": "OFF AI Search API",
        "status": "running",
        "version": "2.0.0",
        "mode": "duckdb",
        "dataset": health,
    }


@app.post("/nl-search", response_model=SearchResponse)
async def natural_language_search(request: SearchRequest) -> SearchResponse:
    try:
        pipeline = FoodIntelligencePipeline(max_results=request.max_results)
        result = pipeline.run(request.query)
        return SearchResponse(
            query=request.query,
            interpreted_query=map_food_query_to_interpreted_query(result),
            applied_filters=result.applied_filters,
            generated_sql=result.generated_sql,
            ranking_rationale=result.ranking_rationale,
            relaxation=result.relaxation_log,
            performance=result.performance,
            products=[map_ranked_product_to_card(item) for item in result.results],
        )
    except FileNotFoundError as exc:
        logger.error("Dataset unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Search failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc


@app.get("/health")
async def health_check():
    try:
        return get_pipeline().health_check()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
