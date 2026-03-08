// API Configuration
const API_BASE_URL = "http://localhost:8000";

// DOM Elements
const searchInput = document.getElementById("searchInput");
const searchButton = document.getElementById("searchButton");
const exampleTags = document.querySelectorAll(".example-tag");
const interpretationPanel = document.getElementById("interpretationPanel");
const interpretationContent = document.getElementById("interpretationContent");
const loadingState = document.getElementById("loadingState");
const resultsSection = document.getElementById("resultsSection");
const productCards = document.getElementById("productCards");
const errorState = document.getElementById("errorState");
const errorMessage = document.getElementById("errorMessage");
const emptyState = document.getElementById("emptyState");

// Event Listeners
searchButton.addEventListener("click", handleSearch);
searchInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
        handleSearch();
    }
});

// Example tags click handlers
exampleTags.forEach(tag => {
    tag.addEventListener("click", () => {
        searchInput.value = tag.textContent;
        handleSearch();
    });
});

// Main search handler
async function handleSearch() {
    const query = searchInput.value.trim();
    
    if (!query) {
        return;
    }

    // Reset UI
    hideAllStates();
    showLoading();

    try {
        const response = await fetch(`${API_BASE_URL}/nl-search`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ query })
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.status}`);
        }

        const data = await response.json();
        
        hideAllStates();
        
        // Show interpretation
        displayInterpretation(data.interpreted_query);
        
        // Show relaxation info if applied
        if (data.relaxation_applied && data.relaxation_info) {
            displayRelaxationInfo(data.relaxation_info);
        }
        
        // Show results
        if (data.products && data.products.length > 0) {
            displayResults(data.products);
        } else {
            showEmptyState();
        }

    } catch (error) {
        console.error("Search failed:", error);
        hideAllStates();
        showError(error.message || "Failed to search. Make sure the API server is running.");
    }
}

// Display query interpretation
function displayInterpretation(query) {
    let html = "";

    if (query.category) {
        html += `<div class="interpretation-item"><strong>Category:</strong> ${query.category}</div>`;
    }

    if (query.dietary_tags && query.dietary_tags.length > 0) {
        html += `<div class="interpretation-item"><strong>Tags:</strong> ${query.dietary_tags.join(", ")}</div>`;
    }

    if (query.nutrient_constraints && Object.keys(query.nutrient_constraints).length > 0) {
        const constraints = Object.entries(query.nutrient_constraints)
            .map(([key, value]) => {
                // Parse constraint key (e.g., "sugars_100g_<=")
                const parts = key.split("_");
                const operator = parts[parts.length - 1];
                const nutrient = parts.slice(0, -1).join("_").replace("_100g", "");
                
                // Determine unit based on nutrient type
                let unit = "g";
                if (nutrient === "energy-kcal") {
                    unit = "kcal";
                } else if (nutrient === "sodium" || nutrient === "salt") {
                    unit = "mg";
                }
                
                // Format nutrient name for display
                const displayName = nutrient.replace("energy-kcal", "calories").replace("-", " ");
                
                return `${displayName} ${operator} ${value}${unit}/100g`;
            })
            .join(", ");
        html += `<div class="interpretation-item"><strong>Constraints:</strong> ${constraints}</div>`;
    }

    if (query.language) {
        html += `<div class="interpretation-item"><strong>Language:</strong> ${query.language}</div>`;
    }

    interpretationContent.innerHTML = html;
    interpretationPanel.style.display = "block";
}

// Display relaxation info if constraints were adjusted
function displayRelaxationInfo(relaxationInfo) {
    if (!relaxationInfo || relaxationInfo.length === 0) return;
    
    let html = '<div class="interpretation-item" style="margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255, 135, 20, 0.2);">';
    html += '<strong style="color: var(--off-orange);">🔄 Search adjusted:</strong><br>';
    html += '<span style="font-size: 11px; color: var(--text-secondary);">No exact matches found. Showing results with relaxed criteria.</span>';
    html += '</div>';
    
    interpretationContent.innerHTML += html;
}

// Display product results
function displayResults(products) {
    productCards.innerHTML = "";

    products.forEach(product => {
        const card = createProductCard(product);
        productCards.appendChild(card);
    });

    resultsSection.style.display = "block";
}

// Create a single product card
function createProductCard(product) {
    const card = document.createElement("div");
    card.className = "product-card";
    
    // Click handler to open product page
    card.addEventListener("click", () => {
        if (product.url) {
            chrome.tabs.create({ url: product.url });
        }
    });

    // Product image
    const imageContainer = document.createElement("div");
    if (product.image) {
        const img = document.createElement("img");
        img.className = "product-image";
        img.src = product.image;
        img.alt = product.name;
        img.onerror = () => {
            // Fallback to placeholder if image fails to load
            imageContainer.innerHTML = '<div class="product-image-placeholder">🍽️</div>';
        };
        imageContainer.appendChild(img);
    } else {
        imageContainer.innerHTML = '<div class="product-image-placeholder">🍽️</div>';
    }

    // Product info
    const info = document.createElement("div");
    info.className = "product-info";

    // Product name
    const name = document.createElement("div");
    name.className = "product-name";
    name.textContent = product.name || "Unknown Product";

    // Meta (NutriScore + Category)
    const meta = document.createElement("div");
    meta.className = "product-meta";

    if (product.nutriscore) {
        const badge = document.createElement("span");
        badge.className = `nutriscore-badge nutriscore-${product.nutriscore.toLowerCase()}`;
        badge.textContent = `Nutri-Score ${product.nutriscore.toUpperCase()}`;
        meta.appendChild(badge);
    }

    if (product.category) {
        const category = document.createElement("span");
        category.className = "product-category";
        category.textContent = truncateText(product.category, 20);
        meta.appendChild(category);
    }

    // Summary
    const summary = document.createElement("div");
    summary.className = "product-summary";
    summary.textContent = product.summary || "See details";

    // Assemble info section
    info.appendChild(name);
    info.appendChild(meta);
    info.appendChild(summary);

    // Assemble card
    card.appendChild(imageContainer);
    card.appendChild(info);

    return card;
}

// Utility: Truncate text
function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + "...";
}

// UI State Management
function hideAllStates() {
    loadingState.style.display = "none";
    resultsSection.style.display = "none";
    errorState.style.display = "none";
    emptyState.style.display = "none";
    interpretationPanel.style.display = "none";
}

function showLoading() {
    loadingState.style.display = "block";
}

function showError(message) {
    errorMessage.textContent = message;
    errorState.style.display = "block";
}

function showEmptyState() {
    emptyState.style.display = "block";
}

// Check API health on load
async function checkAPIHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/`);
        if (!response.ok) {
            console.warn("API health check failed");
        }
    } catch (error) {
        console.warn("API server not reachable:", error.message);
    }
}

// Initialize
checkAPIHealth();
