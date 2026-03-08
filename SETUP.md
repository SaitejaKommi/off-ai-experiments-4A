# Complete Setup Guide

This guide walks you through setting up and testing the complete OFF AI Search system: CLI, API, and Browser Extension.

## Prerequisites

- Python 3.11+ installed
- Chrome or Firefox browser
- Terminal/Command Prompt access

## Step 1: Install Python Dependencies

```bash
# Navigate to project directory
cd off-ai-experiments

# Create virtual environment (if not already created)
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install packages
pip install -r requirements.txt
```

## Step 2: Test CLI (Optional)

Verify the core system works:

```bash
# Test basic search
python -m off_ai "low sugar cereal"

# Test French query
python -m off_ai "céréales faibles en sucre"

# Test multi-constraint
python -m off_ai "high protein vegan snack under 200 calories"

# Run all tests
pytest tests/ -v
```

Expected: Products should be displayed with NutriScore ratings and summaries.

## Step 3: Start the API Server

```bash
# Start the FastAPI server
python run_api.py
```

Expected output:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**Keep this terminal open!** The server must run for the extension to work.

## Step 4: Test the API

Open a **new terminal** (keep the API server running in the first one):

```bash
# Test health endpoint
curl http://localhost:8000/

# Test search endpoint (Windows PowerShell)
Invoke-RestMethod -Uri "http://localhost:8000/nl-search" `
  -Method POST `
  -Body '{"query":"low sugar cereal"}' `
  -ContentType "application/json" | ConvertTo-Json -Depth 5

# Test search endpoint (Mac/Linux/Git Bash)
curl -X POST http://localhost:8000/nl-search \
  -H "Content-Type: application/json" \
  -d '{"query":"low sugar cereal"}'
```

Expected: JSON response with `interpreted_query` and `products` array.

## Step 5: Load the Browser Extension

### Chrome / Edge

1. Open `chrome://extensions/` in your browser
2. Enable **"Developer mode"** (toggle in top-right corner)
3. Click **"Load unpacked"**
4. Navigate to and select the `extension/` folder
5. The extension should appear in your extensions list
6. Pin it to your toolbar for easy access (click puzzle icon → pin)

### Firefox

1. Open `about:debugging#/runtime/this-firefox`
2. Click **"Load Temporary Add-on..."**
3. Navigate to `extension/` folder
4. Select `manifest.json`
5. Extension loads (temporary - will disappear on browser restart)

## Step 6: Test the Extension

1. **Click the extension icon** in your browser toolbar
2. **Type a query** in the search box:
   - "high protein snack"
   - "low sugar cereal"
   - "vegan breakfast"
3. **Press Enter** or click "Search"
4. **View results:**
   - Query interpretation panel shows parsed constraints
   - Product cards display with images, NutriScore badges, summaries
5. **Click a product card** to open it on Open Food Facts website

### Example Queries to Try

**English:**
- `high protein vegan snack under 200 calories`
- `low sodium cereal for kids`
- `gluten free bread`
- `organic breakfast cereal`

**French:**
- `céréales faibles en sucre`
- `collation végétalienne riche en protéines`
- `pain sans gluten`

## Troubleshooting

### Issue: "Failed to search" error in extension

**Cause:** API server not running

**Fix:**
```bash
python run_api.py
```

Verify it's running by opening http://localhost:8000/ in your browser.

### Issue: Extension won't load

**Cause:** Browser can't find manifest.json

**Fix:** Make sure you select the `extension/` folder (not a subfolder).

### Issue: No products returned

**Cause:** Query too restrictive or OFF API connectivity issue

**Try:**
- Use simpler queries: "cereal", "snack", "bread"
- Check API health: `curl http://localhost:8000/health`
- Verify constraint relaxation is working (check console logs)

### Issue: Images not loading in extension

**Cause:** OFF image URLs may be slow or unavailable

**Fix:** This is normal; placeholders (🍽️) will appear for missing images.

### Issue: CORS errors in browser console

**Cause:** Manifest permissions not configured

**Fix:** Verify `manifest.json` includes:
```json
"host_permissions": ["http://localhost:8000/*"]
```

## Architecture Overview

```
User Types Query in Extension Popup
            ↓
Extension sends POST to localhost:8000/nl-search
            ↓
FastAPI Server (Python)
            ↓
Natural Language Parser
            ↓
Open Food Facts API (ca.openfoodfacts.org)
            ↓
Filtered Products + Nutrition Summaries
            ↓
JSON Response to Extension
            ↓
Display Product Cards with NutriScore Badges
```

## Success Criteria Checklist

Verify these work:

- [ ] CLI returns products for "low sugar cereal"
- [ ] API returns JSON for POST /nl-search
- [ ] Extension popup opens when clicking icon
- [ ] Search returns products with NutriScore badges
- [ ] Query interpretation panel shows parsed constraints
- [ ] Clicking product card opens OFF website
- [ ] French queries work ("céréales faibles en sucre")
- [ ] Loading state appears during search
- [ ] Example tag buttons populate search input

## Next Steps (Optional Enhancements)

### Content Script (Advanced)

Inject the AI search directly into ca.openfoodfacts.org:

1. Create `extension/content/inject-search.js`
2. Add to `manifest.json`:
   ```json
   "content_scripts": [{
     "matches": ["https://ca.openfoodfacts.org/*"],
     "js": ["content/inject-search.js"]
   }]
   ```
3. Intercept native search and replace with AI results

### Deployment

**API Server:**
- Deploy to Heroku, Railway, or AWS Lambda
- Update extension to use production URL

**Extension:**
- Create production build
- Submit to Chrome Web Store / Firefox Add-ons
- Add analytics and error tracking

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Chrome Extension Docs](https://developer.chrome.com/docs/extensions/)
- [Open Food Facts API](https://openfoodfacts.github.io/openfoodfacts-server/api/)
- [Extension README](extension/README.md)

## Support

For issues or questions:
1. Check API server is running (`python run_api.py`)
2. Check browser console for errors (F12 → Console)
3. Verify tests pass (`pytest tests/`)
4. Review logs in API server terminal
