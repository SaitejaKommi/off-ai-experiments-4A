# OFF AI Search (Open Food Facts)

Natural-language food search powered by Open Food Facts data, DuckDB, and a Chrome extension UI.

You can type queries like:
- `high protein snack`
- `gluten free cookies`
- `give a snack which has no palm oil`
- `low sugar cereal`

The system converts plain English to filters (category, nutrients, dietary tags, exclusions), runs fast DuckDB queries, and returns ranked products with explanations.

## What We Built

This project now includes:
- Natural language query parsing for category, nutrients, dietary tags, and ingredient exclusions
- Query-to-SQL pipeline with taxonomy mapping (`snacks`, `cookies`, `bars`, `chips`, `soup`, etc.)
- Relaxation logic with transparent steps (shows exactly what changed)
- Better category handling (does not drop category too early)
- Nutri-Score-aware ranking and cleaner relevance explanations
- FastAPI backend (`/nl-search`) + Chrome extension popup UI
- Test coverage for parser, adapter, relaxation, taxonomy, and pipeline behavior

## Project Structure

- `src/off_ai/` core backend modules
- `run_api.py` start FastAPI server
- `extension/` Chrome extension popup
- `tests/` unit and behavior tests

## Requirements

- Python `3.10+`
- Windows/macOS/Linux
- Open Food Facts parquet dataset available locally

Recommended dataset path:
- `src/off_ai/food.parquet`

## Quick Start (Beginner Friendly)

### 1. Clone and open project

```bash
git clone https://github.com/SaitejaKommi/off-ai-experiments-4A.git
cd off-ai-experiments-4A
```

### 2. Create virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add dataset

Place parquet file at:
- `src/off_ai/food.parquet`

If dataset is missing, API health will report `dataset_available: false`.

### 5. Start API server

```bash
python run_api.py
```

Server URLs:
- API root: `http://localhost:8000/`
- Swagger docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

### 6. Try CLI search (optional)

```bash
python -m off_ai "gluten free cookies"
python -m off_ai "give a snack which has no palm oil"
```

### 7. Load Chrome extension

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `extension/` folder
5. Open extension popup and search

The extension calls API at `http://localhost:8000`.

## API Example

`POST /nl-search`

Request:

```json
{
  "query": "gluten free cookies",
  "max_results": 10
}
```

Response includes:
- `interpreted_query`
- `applied_filters`
- `ranking_rationale`
- `relaxation`
- `performance`
- `products`

## Testing

Run full tests:

```bash
python -m pytest tests -q
```

## Notes for New Contributors

- Keep category intent strong during relaxation
- Prefer transparent relaxation logs over hidden fallback behavior
- Keep explanations aligned with executed constraints
- Add regression tests when fixing search-quality issues

## License

MIT

