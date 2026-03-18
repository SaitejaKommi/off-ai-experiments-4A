"""Semantic re-ranking utilities for candidate product lists.

This module adds an embedding-based ranking signal (SentenceTransformers)
on top of the SQL-filtered candidate set. If the embedding model is not
available, it falls back to a lightweight lexical similarity so the pipeline
remains functional in constrained environments.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Dict, List

from .data_adapter import Product

logger = logging.getLogger(__name__)


class SemanticReranker:
    """Compute semantic similarity scores for query/product pairs."""

    def __init__(self) -> None:
        enabled_raw = os.environ.get("OFF_SEMANTIC_RERANK", "1").strip().lower()
        self._enabled = enabled_raw not in {"0", "false", "no", "off"}
        self._model_name = os.environ.get("OFF_SEMANTIC_MODEL", "all-MiniLM-L6-v2").strip()
        self._model = None
        self._available = False

    def product_text(self, product: Product) -> str:
        fields = [
            product.name,
            product.brands,
            " ".join(product.categories),
            product.ingredients_text,
        ]
        return " ".join(part.strip() for part in fields if part and part.strip())

    def score_products(self, query_text: str, products: List[Product]) -> Dict[str, float]:
        if not products:
            return {}
        if not self._enabled:
            return {product.barcode: 0.0 for product in products}

        if self._ensure_model_loaded():
            return self._embedding_similarity(query_text, products)

        # Fallback: lexical token overlap (bounded [0, 1])
        return self._lexical_similarity(query_text, products)

    def _ensure_model_loaded(self) -> bool:
        if self._available and self._model is not None:
            return True
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
            self._available = True
            logger.info("Semantic reranker model loaded: %s", self._model_name)
            return True
        except Exception as exc:  # pragma: no cover - environment dependent
            self._available = False
            self._model = None
            logger.warning(
                "Semantic reranker unavailable (%s). Falling back to lexical similarity.",
                exc,
            )
            return False

    def _embedding_similarity(self, query_text: str, products: List[Product]) -> Dict[str, float]:
        try:
            from sentence_transformers import util

            query_emb = self._model.encode(query_text, convert_to_tensor=True, normalize_embeddings=True)
            texts = [self.product_text(product) for product in products]
            product_embs = self._model.encode(texts, convert_to_tensor=True, normalize_embeddings=True)
            similarities = util.cos_sim(query_emb, product_embs)[0]
            scores: Dict[str, float] = {}
            for idx, product in enumerate(products):
                # convert [-1, 1] to [0, 1] for easier weighting
                raw = float(similarities[idx].item())
                scores[product.barcode] = max(0.0, min(1.0, (raw + 1.0) / 2.0))
            return scores
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("Semantic embedding scoring failed, using lexical fallback: %s", exc)
            return self._lexical_similarity(query_text, products)

    def _lexical_similarity(self, query_text: str, products: List[Product]) -> Dict[str, float]:
        query_tokens = set(re.findall(r"[a-z0-9]+", query_text.lower()))
        if not query_tokens:
            return {product.barcode: 0.0 for product in products}

        scores: Dict[str, float] = {}
        for product in products:
            text_tokens = set(re.findall(r"[a-z0-9]+", self.product_text(product).lower()))
            if not text_tokens:
                scores[product.barcode] = 0.0
                continue
            intersection = len(query_tokens.intersection(text_tokens))
            union = len(query_tokens.union(text_tokens))
            scores[product.barcode] = (intersection / union) if union else 0.0
        return scores
