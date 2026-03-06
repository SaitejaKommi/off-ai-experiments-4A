# off-ai-experiments
Open Food Facts Intelligent Search &amp; Insights Experiments

## What This Project Does

This repository explores how raw food databases can evolve into an **AI-augmented food intelligence engine**.

Three core capabilities are implemented:

### 1. Natural Language → Structured Food Queries

Users can ask complex questions and the system translates them into structured constraints over the Open Food Facts dataset.

```
User query:  "High protein vegan snack under 200 calories"

Structured interpretation:
  category = snacks
  proteins_100g >= 10 g
  vegan = true
  energy-kcal_100g <= 200 kcal
```

### 2. Automated Product Insight Engine

Product data is automatically converted into interpretable health insights:

- **Risk indicators** – High sodium, Ultra-processed (NOVA 4), Contains additive E471, …
- **Positive indicators** – High protein, High fibre, Minimally processed, Organic, …
- **Health classification** – Excellent / Good / Moderate / Risky

### 3. Intelligent Food Recommendation System

Given a reference product the system finds better-rated alternatives:

```
User: "Healthier alternative to Nutella"

Better alternatives:
1. Organic Peanut Butter
   Nutri-Score B  |  NOVA 2
   → Better Nutri-Score (B vs E)
   → 40% less sugar
   → 2 fewer additives
```

---

## Architecture

```
User Query
    ↓ IntentParser
Structured FoodQuery
    ↓ OFFDataAdapter  (Open Food Facts API)
List[Product]
    ↓ InsightEngine
List[ProductInsight]
    ↓ RecommendationEngine  (when comparison mode)
PipelineResult  →  Human-Readable Explanation
```

---

## Quick Start

### Install

```bash
pip install -e .
```

### CLI

```bash
# Search for matching products
off-ai "High protein vegan snack under 200 calories"
off-ai "Low sodium cereal for diabetics"

# Find a healthier alternative
off-ai "Healthier alternative to Nutella"

# JSON output
off-ai --json "organic high fibre cereal"

# Module form
python -m off_ai "keto low carb bread"
```

### Python API

```python
from off_ai import FoodIntelligencePipeline

pipeline = FoodIntelligencePipeline()
result = pipeline.run("High protein vegan snack under 200 calories")
print(result)
```

```python
from off_ai import IntentParser, InsightEngine, OFFDataAdapter

# Parse a query
parser = IntentParser()
query = parser.parse("low sodium cereal under 150 calories")
print(query)

# Fetch and score a single product
adapter = OFFDataAdapter()
product = adapter.get_product("3017620422003")  # Nutella barcode

engine = InsightEngine()
insight = engine.analyze(product)
print(insight)
```

---

## Project Structure

```
src/off_ai/
├── __init__.py             # public API exports
├── intent_parser.py        # NL → FoodQuery (rule-based, LLM-ready)
├── data_adapter.py         # Open Food Facts API wrapper
├── insight_engine.py       # product health scoring &amp; risk indicators
├── recommendation_engine.py # alternative product discovery
├── pipeline.py             # end-to-end orchestration
└── cli.py                  # command-line interface

tests/
├── test_intent_parser.py
├── test_data_adapter.py
├── test_insight_engine.py
└── test_recommendation_engine.py
```

---

## Running Tests

```bash
pip install pytest
pytest tests/
```

---

## Research Status

This is an experimental environment for evaluating AI-augmented food search approaches before proposing implementations within the Open Food Facts ecosystem.

Future experiments may include:
- LLM-powered intent parsing
- Embedding-based food similarity search
- Conversational nutrition assistants
- Knowledge-graph reasoning over food data

