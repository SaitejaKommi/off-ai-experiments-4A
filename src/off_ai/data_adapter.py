"""DuckDB-backed Open Food Facts data access layer."""

from __future__ import annotations

import logging
import os
import re
import time
import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit, urlunsplit

import duckdb

from .constraint_extractor import ExtractedConstraints
from .intent_parser import FoodQuery, NutrientConstraint
from .query_builder import QueryBuilder

logger = logging.getLogger(__name__)

DEFAULT_PARQUET_FILENAME = "off_dev.parquet"
DEFAULT_DATASET_ENV_VAR = "OFF_PARQUET_PATH"
CANADA_OFF_BASE_URL = "https://ca.openfoodfacts.org"

_NUTRIENT_ALIASES: Dict[str, List[str]] = {
    "proteins_100g": ["proteins_100g", "nutriments.proteins_100g"],
    "sugars_100g": ["sugars_100g", "nutriments.sugars_100g"],
    "energy_kcal_100g": ["energy_kcal_100g", "energy-kcal_100g", "nutriments.energy_kcal_100g"],
    "fat_100g": ["fat_100g", "nutriments.fat_100g"],
    "saturated_fat_100g": ["saturated_fat_100g", "saturated-fat_100g", "nutriments.saturated_fat_100g"],
    "carbohydrates_100g": ["carbohydrates_100g", "nutriments.carbohydrates_100g"],
    "sodium_100g": ["sodium_100g", "nutriments.sodium_100g"],
    "salt_100g": ["salt_100g", "nutriments.salt_100g"],
    "fiber_100g": ["fiber_100g", "fibre_100g", "nutriments.fiber_100g", "nutriments.fibre_100g"],
}

_FIELD_CANDIDATES: Dict[str, List[str]] = {
    "code": ["code", "id"],
    "product_name": ["product_name", "product_name_en", "product_name_fr"],
    "brands": ["brands"],
    "categories": ["categories", "categories_tags"],
    "categories_tags": ["categories_tags", "categories"],
    "labels": ["labels", "labels_tags"],
    "ingredients_text": ["ingredients_text"],
    "ingredients_tags": ["ingredients_tags"],
    "nutriscore_grade": ["nutriscore_grade", "nutrition_grade_fr"],
    "nova_group": ["nova_group"],
    "ecoscore_grade": ["ecoscore_grade"],
    "image_url": ["image_url", "image_front_url"],
    "images": ["images"],
    "url": ["url"],
    "additives_tags": ["additives_tags"],
    "additives_n": ["additives_n"],
    "unique_scans_n": ["unique_scans_n"],
    "countries_tags": ["countries_tags", "country_tags"],
}

_LABEL_PATTERNS: Dict[str, List[str]] = {
    "vegan": ["%vegan%", "%plant-based%"],
    "vegetarian": ["%vegetarian%"],
    "gluten-free": ["%gluten-free%", "%gluten free%"],
    "organic": ["%organic%", "%bio%"],
    "dairy-free": ["%dairy-free%", "%dairy free%", "%lactose-free%"],
    "lactose-free": ["%lactose-free%", "%lactose free%"],
    "halal": ["%halal%"],
    "kosher": ["%kosher%"],
}


def _quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


DEFAULT_PARQUET_CANDIDATES = [
    "src/off_ai/food.parquet",
    "off_dev.parquet",
]


def _canonical_nutrient_key(key: str) -> str:
    if key == "energy-kcal_100g":
        return "energy_kcal_100g"
    if key == "saturated-fat_100g":
        return "saturated_fat_100g"
    if key == "fibre_100g":
        return "fiber_100g"
    return key.replace("-", "_")


def _expand_nutrient_aliases(key: str) -> List[str]:
    canonical = _canonical_nutrient_key(key)
    aliases = [canonical]
    if canonical == "energy_kcal_100g":
        aliases.append("energy-kcal_100g")
    if canonical == "saturated_fat_100g":
        aliases.append("saturated-fat_100g")
    if canonical == "fiber_100g":
        aliases.append("fibre_100g")
    return aliases


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

    # Ingredients
    ingredients_text: str = ""
    ingredients_tags: List[str] = field(default_factory=list)

    # Links
    image_url: str = ""
    product_url: str = ""

    def __post_init__(self) -> None:
        self.nutrients = self._normalize_nutrients(self.nutrients)
        self.categories = _normalize_list_value(self.categories)
        self.additives = _normalize_list_value(self.additives)
        self.labels = _normalize_list_value(self.labels)
        self.ingredients_tags = _normalize_list_value(self.ingredients_tags)

    # ----------------------------------------------------------------
    def nutrient(self, key: str) -> Optional[float]:
        """Return a nutrient value or *None* if absent."""
        for alias in _expand_nutrient_aliases(key):
            if alias in self.nutrients:
                return self.nutrients[alias]
        return None

    def has_label(self, label: str) -> bool:
        label_lower = label.lower()
        haystack = " ".join(self.labels).lower()
        return label_lower in haystack

    def passes_constraints(
        self,
        constraints: List[NutrientConstraint],
        allow_missing: bool = False,
    ) -> bool:
        """Return True if the product satisfies all nutrient constraints.

        Parameters
        ----------
        allow_missing:
            If True, products with missing constrained nutrient values are kept.
            If False, missing constrained nutrient values fail the constraint.
        """
        for c in constraints:
            value = self.nutrient(c.nutrient)
            if value is None:
                if allow_missing:
                    continue
                return False  # explicit constraint requires available nutrient data
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
            "ingredients_text": self.ingredients_text,
            "ingredients_tags": self.ingredients_tags,
            "image_url": self.image_url,
            "product_url": self.product_url,
        }

    def has_excluded_ingredient(self, excluded_ingredients: List[str]) -> bool:
        """Return True if product appears to contain any excluded ingredient."""
        if not excluded_ingredients:
            return False

        haystack = " ".join(self.ingredients_tags + [self.ingredients_text]).lower()
        for ingredient in excluded_ingredients:
            token = ingredient.lower().strip()
            if token and token in haystack:
                return True
        return False

    @staticmethod
    def _normalize_nutrients(nutrients: Dict[str, float]) -> Dict[str, float]:
        normalized: Dict[str, float] = {}
        for key, value in nutrients.items():
            if value is None:
                continue
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            normalized[key] = numeric_value
            canonical = _canonical_nutrient_key(key)
            normalized[canonical] = numeric_value
        return normalized


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------

def _normalize_list_value(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if not value.strip():
            return []
        if value.startswith("[") and value.endswith("]"):
            tokens = re.findall(r"'([^']+)'|\"([^\"]+)\"", value)
            extracted = [left or right for left, right in tokens]
            if extracted:
                return [re.sub(r"^[a-z]{2}:", "", item) for item in extracted]
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, Iterable):
        normalized = []
        for item in value:
            if item is None:
                continue
            normalized.append(re.sub(r"^[a-z]{2}:", "", str(item)))
        return normalized
    return [str(value)]


def _normalize_text_value(value: Any, default: str = "") -> str:
    """Normalize scalar/structured OFF text values to a user-friendly string.

    Handles variants seen in OFF parquet such as:
    - plain strings
    - dicts like {"text": "...", "lang": "en"}
    - lists of localized dicts: [{"lang": "main", "text": "..."}, ...]
    - stringified list/dict payloads produced by casts.
    """
    if value is None:
        return default

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        if stripped.startswith("[") or stripped.startswith("{"):
            try:
                parsed = ast.literal_eval(stripped)
                normalized = _normalize_text_value(parsed, default="")
                if normalized:
                    return normalized
            except (ValueError, SyntaxError):
                pass
        return stripped

    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        for candidate in value.values():
            normalized = _normalize_text_value(candidate, default="")
            if normalized:
                return normalized
        return default

    if isinstance(value, Iterable):
        entries = [entry for entry in value if entry is not None]
        if not entries:
            return default

        # Prefer English/main labels when localized values are present.
        for preferred_lang in ("en", "main", "fr"):
            for entry in entries:
                if isinstance(entry, dict) and entry.get("lang") == preferred_lang:
                    normalized = _normalize_text_value(entry.get("text"), default="")
                    if normalized:
                        return normalized

        for entry in entries:
            normalized = _normalize_text_value(entry, default="")
            if normalized:
                return normalized

    return default


def _normalize_product_url(raw_url: Any, barcode: str) -> str:
    normalized_url = _normalize_text_value(raw_url, default="")

    if normalized_url:
        parsed = urlsplit(normalized_url)
        if parsed.netloc.endswith("openfoodfacts.org"):
            path = parsed.path or (f"/product/{barcode}" if barcode else "")
            return urlunsplit(("https", "ca.openfoodfacts.org", path, parsed.query, parsed.fragment))
        return normalized_url

    if barcode:
        return f"{CANADA_OFF_BASE_URL}/product/{barcode}"
    return ""


def _barcode_to_off_path(barcode: str) -> str:
    """Convert barcode to OFF image path segments.

    OFF stores most barcodes as segmented folders (e.g. 000/010/120/9159).
    """
    cleaned = (barcode or "").strip()
    if not cleaned:
        return ""
    if not cleaned.isdigit() or len(cleaned) <= 8:
        return cleaned

    parts: List[str] = []
    remaining = cleaned
    while len(remaining) > 4:
        parts.append(remaining[:3])
        remaining = remaining[3:]
    parts.append(remaining)
    return "/".join(parts)


def _derive_image_url(raw: Dict[str, Any], barcode: str) -> str:
    direct = _normalize_text_value(raw.get("image_url") or raw.get("image_front_url"), default="")
    if direct:
        return direct

    images_payload = raw.get("images")
    if isinstance(images_payload, str):
        try:
            images_payload = ast.literal_eval(images_payload)
        except (ValueError, SyntaxError):
            images_payload = None
    if not isinstance(images_payload, list) or not images_payload:
        return ""

    image_candidates = [entry for entry in images_payload if isinstance(entry, dict)]
    if not image_candidates:
        return ""

    preferred_order = ("front_en", "front", "front_fr", "front_es")
    selected = None
    for key in preferred_order:
        selected = next((entry for entry in image_candidates if entry.get("key") == key), None)
        if selected:
            break
    if selected is None:
        selected = image_candidates[0]

    key = _normalize_text_value(selected.get("key"), default="front")
    rev = selected.get("rev")
    sizes = selected.get("sizes") if isinstance(selected.get("sizes"), dict) else {}
    size_suffix = "400" if "400" in sizes else ("200" if "200" in sizes else ("100" if "100" in sizes else "full"))

    barcode_path = _barcode_to_off_path(barcode)
    if not barcode_path:
        return ""

    if rev is not None:
        return f"https://images.openfoodfacts.org/images/products/{barcode_path}/{key}.{rev}.{size_suffix}.jpg"
    return f"https://images.openfoodfacts.org/images/products/{barcode_path}/{key}.{size_suffix}.jpg"


def _parse_product(raw: Dict[str, Any]) -> Product:
    """Convert a row or OFF-like record into a :class:`Product`."""
    nutriments = raw.get("nutriments") or {}
    nutrients: Dict[str, float] = {}

    if isinstance(nutriments, dict):
        nutrients.update(nutriments)

    for nutrient_name, aliases in _NUTRIENT_ALIASES.items():
        for alias in aliases:
            if alias in raw and raw[alias] is not None:
                nutrients[nutrient_name] = raw[alias]
                nutrients[alias] = raw[alias]

    nova_raw = raw.get("nova_group")
    nova: Optional[int] = None
    if nova_raw is not None:
        try:
            nova = int(nova_raw)
        except (ValueError, TypeError):
            nova = None

    categories = _normalize_list_value(raw.get("categories_tags") or raw.get("categories"))
    labels = _normalize_list_value(raw.get("labels_tags") or raw.get("labels"))
    ingredient_tags = _normalize_list_value(raw.get("ingredients_tags"))
    additives_raw = _normalize_list_value(raw.get("additives_tags"))
    additives = [entry.upper().replace("EN:", "") for entry in additives_raw]

    barcode = str(raw.get("code") or raw.get("barcode") or "")
    url = _normalize_product_url(raw.get("url") or raw.get("product_url"), barcode)
    image_url = _derive_image_url(raw, barcode)

    return Product(
        barcode=barcode,
        name=_normalize_text_value(raw.get("product_name") or raw.get("name"), default="Unknown"),
        brands=_normalize_text_value(raw.get("brands"), default=""),
        categories=categories,
        nutrients=nutrients,
        nutriscore=(raw.get("nutriscore_grade") or raw.get("nutriscore") or "").lower() or None,
        nova_group=nova,
        ecoscore=(raw.get("ecoscore_grade") or raw.get("ecoscore") or "").lower() or None,
        additives=additives,
        additives_count=int(raw.get("additives_n") or len(additives)),
        labels=labels,
        ingredients_text=_normalize_text_value(raw.get("ingredients_text"), default=""),
        ingredients_tags=ingredient_tags,
        image_url=image_url,
        product_url=str(url),
    )


@dataclass
class QueryExecution:
    sql: str
    parameters: List[Any]
    products: List[Product]
    execution_time_ms: float
    rows_returned: int


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class OFFDataAdapter:
    """Executes DuckDB queries over an Open Food Facts Parquet dataset."""

    def __init__(
        self,
        parquet_path: Optional[str] = None,
        database_path: str = ":memory:",
        page_size: int = 20,
    ) -> None:
        self.page_size = max(1, min(page_size, 250))
        self.parquet_path = self._resolve_parquet_path(parquet_path)
        self._con = duckdb.connect(database=database_path)
        self._source_relation = "products"
        self._view_initialized = False
        if self.parquet_path.exists():
            self._initialize_products_view()
            self._schema = self._load_schema()
            self._create_indices()
        else:
            self._schema = {}
        self._field_cache: Dict[str, Optional[str]] = {}
        self._query_builder = QueryBuilder()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def search(self, query: FoodQuery, allow_missing_nutrients: bool = False) -> List[Product]:
        execution = self.execute_search(query, allow_missing_nutrients=allow_missing_nutrients)
        return execution.products

    def execute_search(
        self,
        query: FoodQuery,
        allow_missing_nutrients: bool = False,
        candidate_limit: Optional[int] = None,
    ) -> QueryExecution:
        sql, parameters = self.build_search_sql(
            query,
            allow_missing_nutrients=allow_missing_nutrients,
            limit=candidate_limit or max(query.max_results * 5, query.max_results),
        )
        start = time.perf_counter()
        rows = self._execute_dict(sql, parameters)
        execution_time_ms = (time.perf_counter() - start) * 1000.0
        return QueryExecution(
            sql=self._render_sql(sql, parameters),
            parameters=parameters,
            products=[_parse_product(row) for row in rows],
            execution_time_ms=execution_time_ms,
            rows_returned=len(rows),
        )

    def execute_constraints(
        self,
        constraints: ExtractedConstraints,
        allow_missing_nutrients: bool = False,
        candidate_limit: Optional[int] = None,
    ) -> QueryExecution:
        sql, parameters = self.build_search_sql_from_constraints(
            constraints,
            allow_missing_nutrients=allow_missing_nutrients,
            limit=candidate_limit or max(constraints.max_results * 5, constraints.max_results),
        )
        start = time.perf_counter()
        rows = self._execute_dict(sql, parameters)
        execution_time_ms = (time.perf_counter() - start) * 1000.0
        return QueryExecution(
            sql=self._render_sql(sql, parameters),
            parameters=parameters,
            products=[_parse_product(row) for row in rows],
            execution_time_ms=execution_time_ms,
            rows_returned=len(rows),
        )

    def get_product(self, barcode: str) -> Optional[Product]:
        if not barcode:
            return None
        code_expr = self._field_expr("code")
        if code_expr is None:
            return None
        sql = self._select_clause() + f" WHERE {code_expr} = ? LIMIT 1"
        rows = self._execute_dict(sql, [barcode])
        return _parse_product(rows[0]) if rows else None

    def find_reference_product(self, free_text: str) -> Optional[Product]:
        tokens = [token for token in re.findall(r"[a-z0-9]+", free_text.lower()) if token]
        if not tokens:
            return None
        combined_expr = self._combined_text_expr()
        where_clauses = [f"{combined_expr} ILIKE ?" for _ in tokens]
        parameters: List[Any] = []
        parameters.extend([f"%{token}%" for token in tokens])
        parameters.append(1)
        sql = (
            self._select_clause()
            + " WHERE "
            + " AND ".join(where_clauses)
            + self._order_clause(FoodQuery(raw_text=free_text, search_terms=tokens))
            + " LIMIT ?"
        )
        rows = self._execute_dict(sql, parameters)
        return _parse_product(rows[0]) if rows else None

    def get_category_products(
        self,
        category: str,
        max_results: int = 30,
    ) -> List[Product]:
        query = FoodQuery(raw_text=category, category=category, max_results=max_results)
        return self.search(query)

    def build_search_sql(
        self,
        query: FoodQuery,
        allow_missing_nutrients: bool = False,
        limit: Optional[int] = None,
    ) -> Tuple[str, List[Any]]:
        constraints = ExtractedConstraints(
            raw_text=query.raw_text,
            detected_language=query.detected_language,
            normalized_text=query.normalized_text,
            category=query.category,
            nutrient_constraints=list(query.nutrient_constraints),
            dietary_tags=list(query.dietary_tags),
            keywords=list(query.search_terms),
            ranking_preferences=list(query.ranking_preferences),
            excluded_ingredients=list(query.excluded_ingredients),
            max_results=query.max_results,
        )
        return self.build_search_sql_from_constraints(
            constraints,
            allow_missing_nutrients=allow_missing_nutrients,
            limit=limit,
        )

    def build_search_sql_from_constraints(
        self,
        constraints: ExtractedConstraints,
        allow_missing_nutrients: bool = False,
        limit: Optional[int] = None,
    ) -> Tuple[str, List[Any]]:
        self._ensure_dataset_available()
        built = self._query_builder.build(
            adapter=self,
            constraints=constraints,
            allow_missing_nutrients=allow_missing_nutrients,
            limit=limit,
        )
        return built.sql, built.parameters

    def health_check(self) -> Dict[str, Any]:
        if not self.parquet_path.exists():
            return {
                "dataset_path": str(self.parquet_path),
                "dataset_available": False,
                "error": (
                    f"Parquet dataset not found. Set {DEFAULT_DATASET_ENV_VAR} or place "
                    f"{DEFAULT_PARQUET_FILENAME} in the project root."
                ),
            }

        row_count = self._con.execute(
            f"SELECT COUNT(*) FROM {self._source_relation}",
        ).fetchone()[0]
        return {
            "dataset_path": str(self.parquet_path),
            "dataset_available": True,
            "row_count": row_count,
            "relation": self._source_relation,
        }

    def inspect_schema(self) -> Dict[str, Any]:
        self._ensure_dataset_available()
        schema_rows = self._con.execute(f"DESCRIBE SELECT * FROM {self._source_relation}").fetchall()
        key_fields = [
            "product_name",
            "brands",
            "categories_tags",
            "nutriscore_grade",
            "proteins_100g",
            "sugars_100g",
            "energy_kcal_100g",
        ]
        available_fields = [row[0] for row in schema_rows]
        return {
            "relation": self._source_relation,
            "columns": [{"name": row[0], "type": row[1]} for row in schema_rows],
            "important_fields_present": [field for field in key_fields if field in available_fields],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_parquet_path(self, explicit_path: Optional[str]) -> Path:
        project_root = Path(__file__).resolve().parents[2]
        relative_candidates = [
            *DEFAULT_PARQUET_CANDIDATES,
            DEFAULT_PARQUET_FILENAME,
        ]
        candidates = [
            explicit_path,
            os.environ.get(DEFAULT_DATASET_ENV_VAR),
            *[str(Path.cwd() / rel_path) for rel_path in relative_candidates],
            *[str(project_root / rel_path) for rel_path in relative_candidates],
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return Path(candidate)
        return Path(explicit_path or os.environ.get(DEFAULT_DATASET_ENV_VAR) or DEFAULT_PARQUET_FILENAME)

    def _ensure_dataset_available(self) -> None:
        if not self.parquet_path.exists():
            raise FileNotFoundError(
                f"Parquet dataset not found at {self.parquet_path}. Set {DEFAULT_DATASET_ENV_VAR} "
                f"or add one of {DEFAULT_PARQUET_CANDIDATES + [DEFAULT_PARQUET_FILENAME]} to the project root."
            )
        if not self._view_initialized:
            self._initialize_products_view()
            self._schema = self._load_schema()
            self._field_cache.clear()

    def _initialize_products_view(self) -> None:
        parquet = str(self.parquet_path).replace("'", "''")
        self._con.execute(
            f"CREATE OR REPLACE VIEW {self._source_relation} AS SELECT * FROM read_parquet('{parquet}')"
        )
        self._view_initialized = True

    def _create_indices(self) -> None:
        """Note: DuckDB indices on views are not supported; skipping index creation.
        
        When using parquet directly as a table (not a view), indices would improve
        performance on frequently filtered columns: categories_tags, countries_tags,
        nutriscore_grade, ingredients_text.
        """
        pass

    def _load_schema(self) -> Dict[str, str]:
        rows = self._con.execute(f"DESCRIBE SELECT * FROM {self._source_relation}").fetchall()
        return {row[0]: row[1] for row in rows}

    def _field_expr(self, logical_name: str) -> Optional[str]:
        if logical_name in self._field_cache:
            return self._field_cache[logical_name]

        expression: Optional[str] = None
        if logical_name in _NUTRIENT_ALIASES:
            expression = self._resolve_nutrient_expr(logical_name)
        else:
            for candidate in _FIELD_CANDIDATES.get(logical_name, []):
                if candidate in self._schema:
                    expression = _quote_ident(candidate)
                    break

        self._field_cache[logical_name] = expression
        return expression

    def _resolve_nutrient_expr(self, nutrient_name: str) -> Optional[str]:
        if (
            "nutriments" in self._schema
            and self._schema["nutriments"].startswith("STRUCT")
            and nutrient_name in self._schema["nutriments"]
        ):
            return f"nutriments.{nutrient_name}"
        for candidate in _NUTRIENT_ALIASES[nutrient_name]:
            if candidate in self._schema:
                return _quote_ident(candidate)
        return None

    def _string_expr(self, logical_name: str) -> str:
        expr = self._field_expr(logical_name)
        if expr is None:
            return "''"
        return f"COALESCE(CAST({expr} AS VARCHAR), '')"

    def _combined_text_expr(self) -> str:
        return " || ' ' || ".join(
            [
                self._string_expr("product_name"),
                self._string_expr("brands"),
                self._string_expr("categories"),
                self._string_expr("ingredients_text"),
            ]
        )

    def _label_text_expr(self) -> str:
        return " || ' ' || ".join([self._string_expr("labels"), self._string_expr("categories")])

    def _ingredient_text_expr(self) -> str:
        return " || ' ' || ".join([self._string_expr("ingredients_text"), self._string_expr("ingredients_tags")])

    def _category_text_expr(self) -> str:
        tags_expr = self._field_expr("categories_tags")
        if tags_expr is not None:
            return f"COALESCE(CAST({tags_expr} AS VARCHAR), '')"
        return self._string_expr("categories")

    def _select_clause(self) -> str:
        columns = [
            ("code", "code"),
            ("product_name", "product_name"),
            ("brands", "brands"),
            ("categories", "categories"),
            ("labels", "labels"),
            ("ingredients_text", "ingredients_text"),
            ("ingredients_tags", "ingredients_tags"),
            ("nutriscore_grade", "nutriscore_grade"),
            ("nova_group", "nova_group"),
            ("ecoscore_grade", "ecoscore_grade"),
            ("image_url", "image_url"),
            ("images", "images"),
            ("url", "url"),
            ("additives_tags", "additives_tags"),
            ("additives_n", "additives_n"),
            ("unique_scans_n", "unique_scans_n"),
        ]

        select_parts: List[str] = []
        for logical_name, alias in columns:
            expr = self._field_expr(logical_name)
            if expr is None:
                select_parts.append(f"NULL AS {alias}")
            else:
                select_parts.append(f"{expr} AS {alias}")

        for nutrient_name in _NUTRIENT_ALIASES.keys():
            expr = self._field_expr(nutrient_name)
            if expr is None:
                select_parts.append(f"NULL AS {nutrient_name}")
            else:
                select_parts.append(f"{expr} AS {nutrient_name}")

        return "SELECT\n  " + ",\n  ".join(select_parts) + f"\nFROM {self._source_relation}"

    def _order_clause(self, query: FoodQuery | ExtractedConstraints) -> str:
        nutriscore_expr = self._string_expr("nutriscore_grade")
        nova_expr = self._field_expr("nova_group") or "NULL"
        proteins_expr = self._field_expr("proteins_100g") or "NULL"
        fiber_expr = self._field_expr("fiber_100g") or "NULL"
        sugars_expr = self._field_expr("sugars_100g") or "NULL"
        sodium_expr = self._field_expr("sodium_100g") or "NULL"
        popularity_expr = self._field_expr("unique_scans_n") or "NULL"

        order_parts = [
            f"CASE LOWER({nutriscore_expr}) WHEN 'a' THEN 5 WHEN 'b' THEN 4 WHEN 'c' THEN 3 WHEN 'd' THEN 2 WHEN 'e' THEN 1 ELSE 0 END DESC",
            f"CASE WHEN {nova_expr} IS NULL THEN 0 ELSE 5 - {nova_expr} END DESC",
            f"{self._query_builder.sql_score_expression(self)} DESC",
        ]

        if "kids" in query.ranking_preferences:
            order_parts.append(f"COALESCE({sugars_expr}, 9999) ASC")

        if "healthy" in query.ranking_preferences or query.nutrient_constraints or query.dietary_tags:
            order_parts.extend(
                [
                    f"COALESCE({proteins_expr}, 0) DESC",
                    f"COALESCE({fiber_expr}, 0) DESC",
                    f"COALESCE({sugars_expr}, 9999) ASC",
                    f"COALESCE({sodium_expr}, 9999) ASC",
                ]
            )

        order_parts.append(f"COALESCE({popularity_expr}, 0) DESC")
        order_parts.append(self._string_expr("product_name") + " ASC")
        return " ORDER BY " + ", ".join(order_parts)

    def _execute_dict(self, sql: str, parameters: Sequence[Any]) -> List[Dict[str, Any]]:
        self._ensure_dataset_available()
        cursor = self._con.execute(sql, list(parameters))
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _render_sql(self, sql: str, parameters: Sequence[Any]) -> str:
        rendered = sql
        for value in parameters:
            if isinstance(value, str):
                replacement = "'" + value.replace("'", "''") + "'"
            else:
                replacement = str(value)
            rendered = rendered.replace("?", replacement, 1)
        return rendered
