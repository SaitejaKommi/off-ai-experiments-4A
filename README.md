# off-ai-experiments

AI-powered natural language search for Open Food Facts, available as:
- ✅ **CLI tool** - Command-line interface
- ✅ **REST API** - FastAPI server for web integration
- ✅ **Browser Extension** - Chrome/Firefox extension with professional OFF-branded UI

Users can ask natural-language questions like:
- `high protein snack under 200 calories`
- `healthier alternative to nutella`
- `céréales faibles en sucre`

and get structured, explainable product results.

## 🎨 New Design (v2.0)

The browser extension now features:
- 🍊 **Authentic OFF branding** with official logo and colors
- 🎨 **Orange/brown theme** matching OpenFoodFacts.org
- ✨ **AI-powered interface** with animated search
- 🔍 **Professional search bar** inspired by OFF website
- 📱 **Modern UI** with smooth animations and hover effects

See [extension/DESIGN.md](extension/DESIGN.md) for complete design documentation.

## What this project does

This project turns a plain user query into:
1. Parsed nutrition intent (constraints/tags/category)
2. Filtered products from Open Food Facts
3. Health insights for each product
4. Better alternatives (comparison mode)

## ✨ Features

### Core Functionality
- ✅ **Natural language understanding** - Converts queries into structured filters
- ✅ **Bilingual support** - English & French (EN/FR detection + normalization)
- ✅ **Smart constraint relaxation** - Progressively relaxes filters if zero results
- ✅ **Health scoring** - NutriScore and NOVA group classification
- ✅ **Explainable AI** - Shows parsed query interpretation

### Interfaces
- ✅ **CLI tool** - Command-line interface with JSON output option
- ✅ **REST API** - FastAPI server with `/nl-search` endpoint
- ✅ **Browser Extension** - Chrome/Firefox popup with product cards

### Advanced Features  
- ✅ **Comparison mode** - "healthier alternative to [product]"
- ✅ **Nutrition summaries** - Rule-based insights (High protein, Low sugar, etc.)
- ✅ **Canada-focused** - Uses ca.openfoodfacts.org API
- ✅ **Category mapping** - Recognizes cereals, snacks, beverages, etc.
- ✅ **Dietary filters** - Vegan, gluten-free, organic, low-sodium, etc.

## Data source (API used)

We use **Open Food Facts v2 API**:
- Search endpoint: `https://world.openfoodfacts.org/api/v2/search`
- Product endpoint: `https://world.openfoodfacts.org/api/v2/product/{barcode}.json`

Where in code:
- `src/off_ai/data_adapter.py`

## How data is processed (easy view)

You can think of the system as a pipeline that “segments” raw API data into useful layers:

1. **Input understanding**
    - Detect language (EN/FR)
    - Normalize terms (example: `faibles en sucre` → `low sugar`)
2. **Intent parsing**
    - Extract category, dietary tags, nutrient constraints
    - Example: `under 200 calories` → `energy-kcal_100g <= 200`
3. **API retrieval + filtering**
    - Fetch candidates from Open Food Facts
    - Apply strict nutrient/ingredient filters locally
4. **Smart fallback**
    - If no products are found, relax least-important constraints and retry
5. **Insights + recommendations**
    - Generate risk/positive indicators and health class
    - Optionally suggest better alternatives

## Input → Output (for users)

### Example 1: Search mode

Input:
```bash
python -m off_ai "high protein snack under 200 calories"
```

Output includes:
- Query interpretation (detected language + parsed constraints)
- Top matching products
- Product insights (e.g., Nutri-Score, NOVA, risk indicators)
- If needed: constraint relaxation log

### Example 2: French query

Input:
```bash
python -m off_ai "céréales faibles en sucre"
```

Typical parsed constraint:
- `sugars_100g <= 5.0 g`

### Example 3: Comparison mode

Input:
```bash
python -m off_ai "healthier alternative to nutella"
```

Output includes:
- Reference product details
- Better alternatives with improvement reasons

## Quick start

### CLI Usage

#### 1) Install

```bash
pip install -e .
```

#### 2) Run from CLI

```bash
off-ai "low sodium cereal for kids"
off-ai --json "organic high fibre cereal"
python -m off_ai "keto low carb bread"
```

### Browser Extension + API Server

#### 1) Start the API Server

```bash
python run_api.py
```

Server runs at `http://localhost:8000`

API Documentation: `http://localhost:8000/docs`

#### 2) Load the Extension

**Chrome/Edge:**
1. Open `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the `extension/` folder

**Firefox:**
1. Open `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on"
3. Select `extension/manifest.json`

#### 3) Use the Extension

1. Click the extension icon in your browser toolbar
2. Type a natural language query
3. View results with NutriScore ratings
4. Click products to open on Open Food Facts

See [extension/README.md](extension/README.md) for detailed setup instructions.

### API Endpoints

**POST /nl-search**
```bash
curl -X POST http://localhost:8000/nl-search \
  -H "Content-Type: application/json" \
  -d '{"query":"high protein vegan snack"}'
```

Response includes:
- `interpreted_query` - Parsed constraints and tags
- `products` - Product cards with name, NutriScore, summary, image, URL

**GET /health**
```bash
curl http://localhost:8000/health
```

Returns API status and OFF API connectivity check.

## Python usage

```python
from off_ai import FoodIntelligencePipeline

pipeline = FoodIntelligencePipeline(max_results=10)
result = pipeline.run("high protein vegan snack under 200 calories")
print(result)
```

## Project structure

```text
src/off_ai/
  __init__.py
  __main__.py
  cli.py
  api.py                     # 🆕 FastAPI REST wrapper
  query_preprocessor.py      # EN/FR detection + normalization
  intent_parser.py           # NL query -> FoodQuery
  data_adapter.py            # Open Food Facts API wrapper
  insight_engine.py          # product-level health insights
  recommendation_engine.py   # better alternative ranking
  pipeline.py                # orchestration end-to-end

extension/                   # 🆕 Browser Extension
  manifest.json             # Extension configuration
  popup/
    popup.html              # Popup UI
    popup.css               # Styling
    popup.js                # Search logic & API calls
  assets/                   # Extension icons
  README.md                 # Extension setup guide

tests/
  test_query_preprocessor.py
  test_intent_parser.py
  test_data_adapter.py
  test_insight_engine.py
  test_recommendation_engine.py

run_api.py                  # 🆕 API server launcher
```

## Running tests

```bash
pytest tests/
```

Current status: all tests passing.

## Notes for beginners

- This project is **rule-based and explainable** (not a black-box ML model).
- API data quality can vary (some products have missing nutrient fields).
- Filtering is strict first, then graceful fallback relaxation if needed.

