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
const quickSearchSection = document.querySelector(".examples");

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
    setQuickSearchVisibility(false);

    try {
        const response = await fetch(`${API_BASE_URL}/nl-search`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ query })
        });

        if (!response.ok) {
            let detail = `API Error: ${response.status}`;
            try {
                const errorBody = await response.json();
                if (errorBody && errorBody.detail) {
                    detail = errorBody.detail;
                }
            } catch {
                // Ignore JSON parse failure and fall back to status text.
            }
            throw new Error(detail);
        }

        const data = await response.json();
        
        hideAllStates();
        
        // Show interpretation
        displayInterpretation(data.interpreted_query, data.applied_filters || []);

        if (data.ranking_rationale && data.ranking_rationale.length > 0) {
            displayRankingRationale(data.ranking_rationale, data.performance || {});
        }
        
        // Show relaxation info if applied
        if (data.relaxation && data.relaxation.length > 0) {
            displayRelaxationInfo(data.relaxation);
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

function setQuickSearchVisibility(isVisible) {
    if (!quickSearchSection) return;
    quickSearchSection.style.display = isVisible ? "block" : "none";
}

// Display query interpretation
function displayInterpretation(query, appliedFilters) {
    let html = "";

    if (query.category) {
        html += `<div class="interpretation-item"><strong>Category:</strong> ${query.category}</div>`;
    }

    const booleanTags = Object.keys(query).filter((key) => query[key] === true);
    if (booleanTags.length > 0) {
        html += `<div class="interpretation-item"><strong>Tags:</strong> ${booleanTags.join(", ")}</div>`;
    }

    const numericConstraints = Object.entries(query)
        .filter(([key, value]) => (key.endsWith("_min") || key.endsWith("_max")) && typeof value === "number")
        .map(([key, value]) => {
            const op = key.endsWith("_min") ? ">=" : "<=";
            const label = key.replace(/_(min|max)$/g, "").replaceAll("_", " ");
            return `${label} ${op} ${value}`;
        });

    if (numericConstraints.length > 0) {
        const constraints = numericConstraints.join(", ");
        html += `<div class="interpretation-item"><strong>Constraints:</strong> ${constraints}</div>`;
    }

    if (query.keywords && query.keywords.length > 0) {
        html += `<div class="interpretation-item"><strong>Keywords:</strong> ${query.keywords.join(", ")}</div>`;
    }

    if (appliedFilters && appliedFilters.length > 0) {
        html += `<div class="interpretation-item"><strong>Applied Filters:</strong> ${appliedFilters.join(" | ")}</div>`;
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

function displayRankingRationale(rationale, performance) {
    if (!rationale || rationale.length === 0) return;

    let html = '<div class="interpretation-item" style="margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255, 135, 20, 0.2);">';
    html += '<strong>Why these products?</strong><br>';
    html += `<span style="font-size: 11px; color: var(--text-secondary);">${rationale.slice(0, 4).map(item => `• ${item}`).join(" ")}</span>`;
    if (performance.total_ms !== undefined) {
        html += `<br><span style="font-size: 10px; color: var(--text-light);">${performance.total_ms} ms total | ${performance.results_returned || 0} results</span>`;
    }
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

function normalizeDisplayText(value, fallback = "") {
    if (value === null || value === undefined) return fallback;
    if (typeof value === "string") {
        const trimmed = value.trim();
        return trimmed || fallback;
    }
    if (Array.isArray(value)) {
        const first = value.find(v => v !== null && v !== undefined);
        return normalizeDisplayText(first, fallback);
    }
    if (typeof value === "object") {
        if (typeof value.text === "string") return normalizeDisplayText(value.text, fallback);
        if (typeof value.name === "string") return normalizeDisplayText(value.name, fallback);
        return fallback;
    }
    return String(value);
}

// Create a single product card
function createProductCard(product) {
    const card = document.createElement("div");
    card.className = "product-card";

    const nameValue = normalizeDisplayText(product.name, "Unknown Product");
    const brandValue = normalizeDisplayText(product.brand, "Unknown brand");
    const categoryValue = normalizeDisplayText(product.category, "");
    const summaryValue = normalizeDisplayText(product.summary, "See details");
    const imageValue = normalizeDisplayText(product.image, "");
    
    // Click handler to open product page
    card.addEventListener("click", () => {
        if (product.url) {
            chrome.tabs.create({ url: product.url });
        }
    });

    // Product image
    const imageContainer = document.createElement("div");
    if (imageValue && imageValue.startsWith("http")) {
        const img = document.createElement("img");
        img.className = "product-image";
        img.src = imageValue;
        img.alt = nameValue;
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
    name.textContent = nameValue;

    const brand = document.createElement("div");
    brand.className = "product-brand";
    brand.textContent = brandValue;

    // Meta (NutriScore + Category)
    const meta = document.createElement("div");
    meta.className = "product-meta";

    if (product.nutriscore) {
        const badge = document.createElement("span");
        badge.className = `nutriscore-badge nutriscore-${product.nutriscore.toLowerCase()}`;
        badge.textContent = `Nutri-Score ${product.nutriscore.toUpperCase()}`;
        meta.appendChild(badge);
    }

    if (categoryValue) {
        const category = document.createElement("span");
        category.className = "product-category";
        category.textContent = truncateText(categoryValue, 20);
        meta.appendChild(category);
    }

    // Summary
    const summary = document.createElement("div");
    summary.className = "product-summary";
    summary.textContent = summaryValue;

    const explanation = document.createElement("div");
    explanation.className = "product-explanation";
    explanation.textContent = product.explanation && product.explanation.length > 0
        ? product.explanation.slice(0, 2).join(" • ")
        : "";

    // Assemble info section
    info.appendChild(name);
    info.appendChild(brand);
    info.appendChild(meta);
    info.appendChild(summary);
    if (explanation.textContent) {
        info.appendChild(explanation);
    }

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
