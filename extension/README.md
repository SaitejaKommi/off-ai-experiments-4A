# OFF AI Search Browser Extension

Natural language search interface for Open Food Facts Canada with authentic OFF design.

## ✨ Design Features

- 🍊 **Authentic OFF Branding** - Official logo and color scheme
- 🎨 **Professional UI** - Orange/brown theme matching OFF website
- ✨ **AI-Powered** - Sparkle animation on AI badge
- 🔍 **Modern Search Bar** - OFF-style unified search interface
- 📱 **Responsive Design** - Smooth animations and hover effects

See [DESIGN.md](DESIGN.md) for complete design documentation.

## Quick Start

### Prerequisites

1. **API Server Running**
   ```bash
   python run_api.py
   ```
   The API should be running at `http://localhost:8000`

2. **Browser Icons** (Optional for testing)
   - Add icon files to `extension/assets/` or remove icon references from `manifest.json`

### Loading the Extension

#### Chrome / Edge

1. Open `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `extension/` folder
5. The extension should appear in your toolbar

#### Firefox

1. Open `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on"
3. Navigate to `extension/` folder
4. Select `manifest.json`
5. The extension loads temporarily

### Usage

1. Click the extension icon in your browser toolbar
2. Type a natural language query:
   - "high protein vegan snack"
   - "low sugar cereal"
   - "céréales faibles en sucre"
3. Press Enter or click Search
4. View results with NutriScore ratings
5. Click any product card to open it on Open Food Facts

## Features

✅ Natural language query understanding  
✅ Bilingual support (English/French)  
✅ Query interpretation display  
✅ Product cards with NutriScore badges  
✅ Direct links to product pages  
✅ Loading states and error handling  

## Architecture

```
User Query (Browser Extension)
        ↓
Local FastAPI Server (localhost:8000)
        ↓
Natural Language Parser
        ↓
Open Food Facts API (ca.openfoodfacts.org)
        ↓
Filtered Results
```

## Troubleshooting

### "Failed to search" Error

**Cause:** API server not running or not accessible

**Fix:**
```bash
# Start the API server
python run_api.py

# Verify it's running
curl http://localhost:8000/
```

### Extension Not Loading

**Cause:** Missing icon files

**Fix:** Remove icon references from `manifest.json` or add placeholder images to `assets/`

### CORS Errors

**Cause:** Browser blocking localhost requests

**Fix:** The API already has CORS configured. Ensure `host_permissions` includes `http://localhost:8000/*` in `manifest.json`

## Demo Queries

Try these queries to test the system:

- "high protein snack under 200 calories"
- "low sugar cereal"
- "vegan breakfast"
- "gluten free bread"
- "céréales faibles en sucre" (French)
- "collation végétalienne riche en protéines" (French)

## Development

### File Structure

```
extension/
├── manifest.json          # Extension configuration
├── popup/
│   ├── popup.html        # Popup UI
│   ├── popup.css         # Styling
│   └── popup.js          # Logic & API calls
└── assets/
    └── README.md         # Icon requirements
```

### Modifying the Extension

After making changes:
1. Save your files
2. Go to `chrome://extensions/`
3. Click the refresh icon on the extension card
4. Reopen the popup to see changes

## Next Steps (Optional)

### Content Script Integration

Inject the AI search into Open Food Facts website:
1. Create `content/inject-search.js`
2. Add content script to `manifest.json`
3. Intercept native search on ca.openfoodfacts.org
4. Replace with AI-powered results

### Enhanced Features

- Save recent searches
- Favorite products
- Offline mode with cached results
- Dietary preference profiles
- Comparison mode
