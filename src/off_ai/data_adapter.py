"""
data_adapter.py – Open Food Facts API adapter

Wraps the OFF v2 search API and product detail API.
Returns :class:`Product` objects for consumption by the insight and
recommendation engines.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

from .intent_parser import FoodQuery, NutrientConstraint

logger = logging.getLogger(__name__)

# Base URLs
_OFF_SEARCH_URL = "https://world.openfoodfacts.org/api/v2/search"
_OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"

# Fields to request from OFF API
_PRODUCT_FIELDS = (
    "product_name,brands,categories,categories_tags,"
    "nutriscore_grade,nova_group,"
    "nutriments,"
    "additives_tags,additives_n,"
    "labels,labels_tags,"
    "ecoscore_grade,"
    "image_url,url,"
    "code"
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Product:
    """Minimal representation of an Open Food Facts product."""

    barcode: str
    name: str
    brands: str = ""
    categories: List[str] = field(default_factory=list)

    # Nutritional values per 100 g / 100 ml
    nutrients: Dict[str, float] = field(default_factory=dict)

    # Scores
    nutriscore: Optional[str] = None       # a–e
    nova_group: Optional[int] = None       # 1–4
    ecoscore: Optional[str] = None         # a–e

    # Processing / additives
    additives: List[str] = field(default_factory=list)
    additives_count: int = 0

    # Labels (vegan, organic, …)
    labels: List[str] = field(default_factory=list)

    # Links
    image_url: str = ""
    product_url: str = ""

    # ----------------------------------------------------------------
    def nutrient(self, key: str) -> Optional[float]:
        """Return a nutrient value or *None* if absent."""
        return self.nutrients.get(key)

    def passes_constraints(self, constraints: List[NutrientConstraint]) -> bool:
        """Return True if the product satisfies all nutrient constraints."""
        for c in constraints:
            value = self.nutrient(c.nutrient)
            if value is None:
                continue  # missing data – don't filter out
            if c.operator == ">=" and value < c.value:
                return False
            if c.operator == "<=" and value > c.value:
                return False
            if c.operator == ">" and value <= c.value:
                return False
            if c.operator == "<" and value >= c.value:
                return False
            if c.operator == "==" and abs(value - c.value) > 1e-6:
                return False
        return True

    def to_dict(self) -> dict:
        return {
            "barcode": self.barcode,
            "name": self.name,
            "brands": self.brands,
            "categories": self.categories,
            "nutrients": self.nutrients,
            "nutriscore": self.nutriscore,
            "nova_group": self.nova_group,
            "ecoscore": self.ecoscore,
            "additives": self.additives,
            "additives_count": self.additives_count,
            "labels": self.labels,
            "image_url": self.image_url,
            "product_url": self.product_url,
        }


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------

def _parse_product(raw: Dict[str, Any]) -> Product:
    """Convert a raw OFF API product dict into a :class:`Product`."""
    nutriments = raw.get("nutriments") or {}

    # Normalise NOVA group to int
    nova_raw = raw.get("nova_group")
    nova: Optional[int] = None
    if nova_raw is not None:
        try:
            nova = int(nova_raw)
        except (ValueError, TypeError):
            pass

    # Category tags → human-readable
    cat_tags: List[str] = raw.get("categories_tags") or []
    categories = [re.sub(r"^[a-z]{2}:", "", t) for t in cat_tags]

    # Label tags
    label_tags: List[str] = raw.get("labels_tags") or []
    labels = [re.sub(r"^[a-z]{2}:", "", t) for t in label_tags]

    # Additive tags
    additives_raw: List[str] = raw.get("additives_tags") or []
    additives = [a.upper().replace("en:", "") for a in additives_raw]

    return Product(
        barcode=str(raw.get("code", "")),
        name=raw.get("product_name", "Unknown"),
        brands=raw.get("brands", ""),
        categories=categories,
        nutrients={k: float(v) for k, v in nutriments.items() if isinstance(v, (int, float))},
        nutriscore=(raw.get("nutriscore_grade") or "").lower() or None,
        nova_group=nova,
        ecoscore=(raw.get("ecoscore_grade") or "").lower() or None,
        additives=additives,
        additives_count=int(raw.get("additives_n") or len(additives)),
        labels=labels,
        image_url=raw.get("image_url", ""),
        product_url=raw.get("url", ""),
    )


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class OFFDataAdapter:
    """Retrieves products from the Open Food Facts public API.

    Parameters
    ----------
    page_size:
        Maximum products per API call (capped at 50 by OFF).
    timeout:
        HTTP request timeout in seconds.
    rate_limit_delay:
        Seconds to wait between consecutive API calls.
    """

    def __init__(
        self,
        page_size: int = 20,
        timeout: int = 15,
        rate_limit_delay: float = 0.5,
    ) -> None:
        self.page_size = min(page_size, 50)
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "off-ai-experiments/1.0 (research; github.com/SaitejaKommi/off-ai-experiments)"}
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def search(self, query: FoodQuery) -> List[Product]:
        """Search OFF for products matching *query*."""
        params = self._build_search_params(query)
        raw_products = self._fetch_search(params, query.max_results)
        products = [_parse_product(p) for p in raw_products]
        # Apply nutrient constraints locally (OFF API filtering is coarse)
        if query.nutrient_constraints:
            products = [p for p in products if p.passes_constraints(query.nutrient_constraints)]
        return products

    def get_product(self, barcode: str) -> Optional[Product]:
        """Fetch a single product by barcode."""
        url = _OFF_PRODUCT_URL.format(barcode=barcode)
        try:
            resp = self._session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != 1:
                return None
            return _parse_product(data.get("product") or {})
        except requests.RequestException as exc:
            logger.warning("OFF product fetch failed for %s: %s", barcode, exc)
            return None

    def get_category_products(
        self,
        category: str,
        max_results: int = 30,
    ) -> List[Product]:
        """Fetch products from a specific OFF category."""
        params = {
            "categories_tags": category,
            "fields": _PRODUCT_FIELDS,
            "page_size": self.page_size,
            "sort_by": "nutriscore_score",
            "action": "process",
            "json": "1",
        }
        raw = self._fetch_search(params, max_results)
        return [_parse_product(p) for p in raw]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_search_params(self, query: FoodQuery) -> dict:
        params: dict = {
            "fields": _PRODUCT_FIELDS,
            "page_size": self.page_size,
            "action": "process",
            "json": "1",
        }

        # Free-text search from the original query (minus structural keywords)
        search_terms = self._query_to_search_terms(query)
        if search_terms:
            params["search_terms"] = search_terms

        # Category filter
        if query.category:
            params["categories_tags"] = query.category

        # Dietary label filters
        label_map = {
            "vegan": "en:vegan",
            "vegetarian": "en:vegetarian",
            "gluten-free": "en:gluten-free",
            "organic": "en:organic",
            "halal": "en:halal",
            "kosher": "en:kosher",
            "no-additives": "en:no-additives",
        }
        labels = [label_map[t] for t in query.dietary_tags if t in label_map]
        if labels:
            params["labels_tags"] = ",".join(labels)

        return params

    def _query_to_search_terms(self, query: FoodQuery) -> str:
        """Strip structural words from raw_text to produce a free-text search."""
        stop_words = {
            "high", "low", "under", "over", "at", "least", "most", "more", "than",
            "less", "and", "or", "with", "for", "a", "an", "the", "of", "in",
            "healthier", "alternative", "to", "instead", "replace",
            "calorie", "calories", "kcal", "gram", "grams",
            "vegan", "vegetarian", "gluten-free", "gluten", "free",
            "organic", "keto", "paleo",
        }
        # Remove nutrient words (they are not useful as text search terms)
        from .intent_parser import NUTRIENT_ALIASES
        stop_words.update(NUTRIENT_ALIASES.keys())

        words = query.raw_text.lower().split()
        kept = [w for w in words if re.sub(r"[^a-z]", "", w) not in stop_words]
        return " ".join(kept)

    def _fetch_search(self, params: dict, max_results: int) -> List[Dict]:
        """Paginate through OFF search results up to *max_results*."""
        collected: List[Dict] = []
        page = 1
        while len(collected) < max_results:
            params["page"] = page
            params["page_size"] = min(self.page_size, max_results - len(collected))
            try:
                resp = self._session.get(
                    _OFF_SEARCH_URL, params=params, timeout=self.timeout
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                logger.warning("OFF search request failed (page %d): %s", page, exc)
                break

            products = data.get("products") or []
            if not products:
                break
            collected.extend(products)
            page_count = data.get("page_count", 0)
            if page >= page_count:
                break
            page += 1
            time.sleep(self.rate_limit_delay)

        return collected[:max_results]
