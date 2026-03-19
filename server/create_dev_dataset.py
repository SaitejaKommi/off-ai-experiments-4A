#!/usr/bin/env python3
"""
create_dev_dataset.py - Generate a realistic synthetic OFF dev dataset.

Creates off_dev.parquet in the project root with ~500 sample Canadian products
covering diverse categories, nutrients, and dietary tags.

Use this when you cannot reach the internet.  Replace off_dev.parquet with
the real OFF dataset when network access is available.

Usage:
    python create_dev_dataset.py
"""

from __future__ import annotations

import random
import sys
import time

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyarrow", "-q"])
    import pyarrow as pa
    import pyarrow.parquet as pq

OUTPUT_FILE = "off_dev.parquet"
random.seed(42)

# ---------------------------------------------------------------------------
# Product templates per category
# ---------------------------------------------------------------------------

PRODUCTS = [
    # --- Breakfast cereals ---
    ("Honey Nut Cheerios", "General Mills", "en:breakfast-cereals", "B", 3,
     {"proteins_100g": 8.0, "sugars_100g": 25.0, "energy_kcal_100g": 380, "fat_100g": 5.0,
      "saturated_fat_100g": 0.8, "carbohydrates_100g": 72.0, "sodium_100g": 0.4,
      "salt_100g": 1.0, "fiber_100g": 4.5},
     ["en:gluten-free:no"], []),
    ("Nature's Path Flax Plus", "Nature's Path", "en:breakfast-cereals", "A", 2,
     {"proteins_100g": 10.0, "sugars_100g": 8.0, "energy_kcal_100g": 350, "fat_100g": 6.0,
      "saturated_fat_100g": 0.6, "carbohydrates_100g": 65.0, "sodium_100g": 0.15,
      "salt_100g": 0.37, "fiber_100g": 9.0},
     ["en:organic", "en:vegan"], ["milk"]),
    ("Kellogg's Special K", "Kellogg's", "en:breakfast-cereals", "B", 3,
     {"proteins_100g": 14.0, "sugars_100g": 17.0, "energy_kcal_100g": 375, "fat_100g": 1.5,
      "saturated_fat_100g": 0.3, "carbohydrates_100g": 75.0, "sodium_100g": 0.6,
      "salt_100g": 1.5, "fiber_100g": 2.0},
     [], []),
    ("Oatmeal Crisp Almond", "General Mills", "en:breakfast-cereals", "B", 3,
     {"proteins_100g": 9.0, "sugars_100g": 19.0, "energy_kcal_100g": 395, "fat_100g": 7.0,
      "saturated_fat_100g": 1.0, "carbohydrates_100g": 70.0, "sodium_100g": 0.35,
      "salt_100g": 0.88, "fiber_100g": 5.0},
     [], ["tree nuts"]),
    ("Red River Cereal", "Smuckers", "en:breakfast-cereals", "A", 2,
     {"proteins_100g": 12.0, "sugars_100g": 2.0, "energy_kcal_100g": 330, "fat_100g": 4.0,
      "saturated_fat_100g": 0.5, "carbohydrates_100g": 60.0, "sodium_100g": 0.0,
      "salt_100g": 0.0, "fiber_100g": 11.0},
     ["en:vegan", "en:organic"], []),

    # --- Chips & Snacks ---
    ("Lay's Classic", "PepsiCo", "en:chips-and-crisps", "D", 4,
     {"proteins_100g": 6.5, "sugars_100g": 0.5, "energy_kcal_100g": 536, "fat_100g": 35.0,
      "saturated_fat_100g": 5.0, "carbohydrates_100g": 50.0, "sodium_100g": 0.55,
      "salt_100g": 1.4, "fiber_100g": 4.5},
     [], []),
    ("Doritos Nacho Cheese", "PepsiCo", "en:chips-and-crisps", "D", 4,
     {"proteins_100g": 7.5, "sugars_100g": 3.0, "energy_kcal_100g": 506, "fat_100g": 26.0,
      "saturated_fat_100g": 4.0, "carbohydrates_100g": 60.0, "sodium_100g": 0.75,
      "salt_100g": 1.88, "fiber_100g": 3.0},
     [], ["milk"]),
    ("Popchips Sea Salt", "Popchips", "en:chips-and-crisps", "C", 3,
     {"proteins_100g": 3.0, "sugars_100g": 2.0, "energy_kcal_100g": 390, "fat_100g": 14.0,
      "saturated_fat_100g": 1.0, "carbohydrates_100g": 60.0, "sodium_100g": 0.42,
      "salt_100g": 1.06, "fiber_100g": 2.0},
     ["en:vegan"], []),
    ("Pringles Original", "Kellogg's", "en:chips-and-crisps", "D", 4,
     {"proteins_100g": 5.0, "sugars_100g": 2.0, "energy_kcal_100g": 521, "fat_100g": 33.0,
      "saturated_fat_100g": 9.0, "carbohydrates_100g": 52.0, "sodium_100g": 0.58,
      "salt_100g": 1.45, "fiber_100g": 3.0},
     [], []),
    ("Kettle Brand Sea Salt", "Kettle Brand", "en:chips-and-crisps", "C", 4,
     {"proteins_100g": 7.0, "sugars_100g": 0.0, "energy_kcal_100g": 536, "fat_100g": 35.0,
      "saturated_fat_100g": 3.5, "carbohydrates_100g": 50.0, "sodium_100g": 0.32,
      "salt_100g": 0.8, "fiber_100g": 5.0},
     ["en:vegan", "en:gluten-free"], []),

    # --- Protein Bars ---
    ("Quest Bar Chocolate Chip", "Quest Nutrition", "en:protein-bars", "B", 4,
     {"proteins_100g": 41.0, "sugars_100g": 3.5, "energy_kcal_100g": 377, "fat_100g": 14.0,
      "saturated_fat_100g": 5.0, "carbohydrates_100g": 39.0, "sodium_100g": 0.35,
      "salt_100g": 0.88, "fiber_100g": 25.0},
     ["en:gluten-free", "en:high-protein"], ["milk"]),
    ("Clif Bar Chocolate Chip", "Clif Bar", "en:protein-bars", "C", 3,
     {"proteins_100g": 11.0, "sugars_100g": 22.0, "energy_kcal_100g": 405, "fat_100g": 9.0,
      "saturated_fat_100g": 2.0, "carbohydrates_100g": 65.0, "sodium_100g": 0.17,
      "salt_100g": 0.43, "fiber_100g": 5.0},
     ["en:organic"], ["oats", "soy"]),
    ("Kind Bar Almond & Coconut", "Kind", "en:protein-bars", "C", 4,
     {"proteins_100g": 7.0, "sugars_100g": 19.0, "energy_kcal_100g": 470, "fat_100g": 31.0,
      "saturated_fat_100g": 8.0, "carbohydrates_100g": 45.0, "sodium_100g": 0.09,
      "salt_100g": 0.22, "fiber_100g": 7.0},
     ["en:gluten-free", "en:vegan"], ["tree nuts"]),
    ("RxBar Blueberry", "RxBar", "en:protein-bars", "B", 4,
     {"proteins_100g": 21.0, "sugars_100g": 17.0, "energy_kcal_100g": 365, "fat_100g": 9.0,
      "saturated_fat_100g": 1.5, "carbohydrates_100g": 45.0, "sodium_100g": 0.12,
      "salt_100g": 0.3, "fiber_100g": 5.0},
     ["en:gluten-free", "en:high-protein"], ["egg", "tree nuts"]),
    ("Larabar Apple Pie", "Larabar", "en:protein-bars", "B", 4,
     {"proteins_100g": 6.0, "sugars_100g": 38.0, "energy_kcal_100g": 400, "fat_100g": 16.0,
      "saturated_fat_100g": 1.5, "carbohydrates_100g": 62.0, "sodium_100g": 0.0,
      "salt_100g": 0.0, "fiber_100g": 7.0},
     ["en:vegan", "en:gluten-free"], ["dates", "almonds"]),

    # --- Dairy ---
    ("Activia Strawberry Yogurt", "Danone", "en:yogurts", "B", 2,
     {"proteins_100g": 5.0, "sugars_100g": 14.0, "energy_kcal_100g": 94, "fat_100g": 1.5,
      "saturated_fat_100g": 1.0, "carbohydrates_100g": 16.0, "sodium_100g": 0.06,
      "salt_100g": 0.15, "fiber_100g": 0.5},
     ["en:vegetarian"], ["milk"]),
    ("Greek Gods Plain Greek Yogurt", "Greek Gods", "en:yogurts", "A", 2,
     {"proteins_100g": 9.0, "sugars_100g": 5.0, "energy_kcal_100g": 100, "fat_100g": 2.5,
      "saturated_fat_100g": 1.5, "carbohydrates_100g": 7.0, "sodium_100g": 0.04,
      "salt_100g": 0.1, "fiber_100g": 0.0},
     ["en:vegetarian", "en:high-protein"], ["milk"]),
    ("Oikos Triple Zero Vanilla", "Danone", "en:yogurts", "A", 2,
     {"proteins_100g": 15.0, "sugars_100g": 0.0, "energy_kcal_100g": 90, "fat_100g": 0.0,
      "saturated_fat_100g": 0.0, "carbohydrates_100g": 8.0, "sodium_100g": 0.05,
      "salt_100g": 0.12, "fiber_100g": 0.0},
     ["en:vegetarian", "en:high-protein", "en:no-added-sugar"], ["milk"]),

    # --- Beverages ---
    ("Coca-Cola Classic", "Coca-Cola", "en:sodas", "E", 4,
     {"proteins_100g": 0.0, "sugars_100g": 10.6, "energy_kcal_100g": 42, "fat_100g": 0.0,
      "saturated_fat_100g": 0.0, "carbohydrates_100g": 10.6, "sodium_100g": 0.01,
      "salt_100g": 0.025, "fiber_100g": 0.0},
     [], []),
    ("Tropicana Orange Juice", "PepsiCo", "en:fruit-juices", "C", 4,
     {"proteins_100g": 0.7, "sugars_100g": 8.4, "energy_kcal_100g": 45, "fat_100g": 0.2,
      "saturated_fat_100g": 0.0, "carbohydrates_100g": 10.4, "sodium_100g": 0.001,
      "salt_100g": 0.003, "fiber_100g": 0.4},
     ["en:vegan"], []),
    ("V8 Vegetable Juice", "Campbell's", "en:vegetable-juices", "B", 4,
     {"proteins_100g": 0.7, "sugars_100g": 3.0, "energy_kcal_100g": 17, "fat_100g": 0.0,
      "saturated_fat_100g": 0.0, "carbohydrates_100g": 3.5, "sodium_100g": 0.23,
      "salt_100g": 0.58, "fiber_100g": 0.0},
     ["en:vegan", "en:low-calorie"], []),
    ("Oat & Mill Oat Milk", "Oat & Mill", "en:plant-milks", "B", 2,
     {"proteins_100g": 1.0, "sugars_100g": 7.0, "energy_kcal_100g": 47, "fat_100g": 1.5,
      "saturated_fat_100g": 0.2, "carbohydrates_100g": 7.5, "sodium_100g": 0.05,
      "salt_100g": 0.125, "fiber_100g": 0.3},
     ["en:vegan", "en:dairy-free", "en:lactose-free"], []),

    # --- Frozen foods ---
    ("Amy's Veggie Burger", "Amy's Kitchen", "en:veggie-burgers", "B", 2,
     {"proteins_100g": 14.0, "sugars_100g": 2.0, "energy_kcal_100g": 185, "fat_100g": 7.0,
      "saturated_fat_100g": 1.0, "carbohydrates_100g": 18.0, "sodium_100g": 0.45,
      "salt_100g": 1.13, "fiber_100g": 4.0},
     ["en:vegan", "en:organic"], ["gluten", "soy"]),
    ("PC Blue Menu Salmon Burgers", "President's Choice", "en:fish-products", "A", 2,
     {"proteins_100g": 23.0, "sugars_100g": 1.0, "energy_kcal_100g": 165, "fat_100g": 7.0,
      "saturated_fat_100g": 1.5, "carbohydrates_100g": 3.0, "sodium_100g": 0.32,
      "salt_100g": 0.8, "fiber_100g": 0.0},
     ["en:high-protein", "en:omega-3"], ["fish"]),

    # --- Bread & Grains ---
    ("Dave's Killer Bread 21 Whole Grains", "Dave's Killer Bread", "en:breads", "A", 2,
     {"proteins_100g": 12.0, "sugars_100g": 5.0, "energy_kcal_100g": 267, "fat_100g": 4.5,
      "saturated_fat_100g": 0.5, "carbohydrates_100g": 45.0, "sodium_100g": 0.28,
      "salt_100g": 0.7, "fiber_100g": 6.0},
     ["en:vegan", "en:organic"], ["gluten", "soy"]),
    ("Wonder White Bread", "Wonder", "en:breads", "C", 4,
     {"proteins_100g": 8.0, "sugars_100g": 4.0, "energy_kcal_100g": 265, "fat_100g": 3.0,
      "saturated_fat_100g": 0.5, "carbohydrates_100g": 49.0, "sodium_100g": 0.42,
      "salt_100g": 1.05, "fiber_100g": 2.0},
     [], ["gluten", "soy"]),

    # --- Cookies & Crackers ---
    ("Oreo Chocolate Sandwich Cookies", "Mondelez", "en:cookies", "E", 4,
     {"proteins_100g": 5.0, "sugars_100g": 43.0, "energy_kcal_100g": 473, "fat_100g": 20.0,
      "saturated_fat_100g": 6.0, "carbohydrates_100g": 70.0, "sodium_100g": 0.39,
      "salt_100g": 0.98, "fiber_100g": 2.0},
     ["en:vegan"], ["gluten", "soy"]),
    ("Ritz Crackers Original", "Mondelez", "en:crackers", "D", 4,
     {"proteins_100g": 7.0, "sugars_100g": 6.0, "energy_kcal_100g": 480, "fat_100g": 23.0,
      "saturated_fat_100g": 4.0, "carbohydrates_100g": 62.0, "sodium_100g": 0.63,
      "salt_100g": 1.58, "fiber_100g": 2.0},
     [], ["gluten"]),
    ("Mary's Gone Crackers Original", "Mary's Gone Crackers", "en:crackers", "B", 2,
     {"proteins_100g": 9.0, "sugars_100g": 3.0, "energy_kcal_100g": 430, "fat_100g": 22.0,
      "saturated_fat_100g": 2.5, "carbohydrates_100g": 53.0, "sodium_100g": 0.28,
      "salt_100g": 0.7, "fiber_100g": 6.0},
     ["en:gluten-free", "en:vegan", "en:organic"], []),

    # --- Candy ---
    ("Skittles Original", "Mars", "en:candies", "E", 4,
     {"proteins_100g": 0.0, "sugars_100g": 76.0, "energy_kcal_100g": 400, "fat_100g": 4.0,
      "saturated_fat_100g": 1.0, "carbohydrates_100g": 91.0, "sodium_100g": 0.0,
      "salt_100g": 0.0, "fiber_100g": 0.0},
     ["en:vegan"], []),
    ("Oh Henry! Bar", "Hershey Canada", "en:chocolate-candies", "E", 4,
     {"proteins_100g": 8.0, "sugars_100g": 47.0, "energy_kcal_100g": 450, "fat_100g": 20.0,
      "saturated_fat_100g": 8.0, "carbohydrates_100g": 62.0, "sodium_100g": 0.15,
      "salt_100g": 0.38, "fiber_100g": 2.5},
     [], ["milk", "peanuts", "gluten"]),

    # --- Soups ---
    ("Campbell's Tomato Soup", "Campbell's", "en:soups", "C", 4,
     {"proteins_100g": 1.6, "sugars_100g": 8.0, "energy_kcal_100g": 60, "fat_100g": 1.5,
      "saturated_fat_100g": 0.5, "carbohydrates_100g": 10.5, "sodium_100g": 0.43,
      "salt_100g": 1.08, "fiber_100g": 0.8},
     ["en:vegan", "en:low-fat"], []),
    ("PC Organics Lentil Soup", "President's Choice", "en:soups", "A", 2,
     {"proteins_100g": 5.0, "sugars_100g": 2.0, "energy_kcal_100g": 72, "fat_100g": 0.5,
      "saturated_fat_100g": 0.1, "carbohydrates_100g": 12.0, "sodium_100g": 0.3,
      "salt_100g": 0.75, "fiber_100g": 4.0},
     ["en:vegan", "en:organic", "en:high-fiber"], []),

    # --- Sauces & Condiments ---
    ("Heinz Ketchup Original", "Heinz", "en:ketchup", "D", 4,
     {"proteins_100g": 1.3, "sugars_100g": 22.0, "energy_kcal_100g": 101, "fat_100g": 0.2,
      "saturated_fat_100g": 0.0, "carbohydrates_100g": 24.0, "sodium_100g": 0.88,
      "salt_100g": 2.2, "fiber_100g": 0.8},
     ["en:vegan"], []),
    ("PC Zero Calorie Italian Dressing", "President's Choice", "en:salad-dressings", "A", 4,
     {"proteins_100g": 0.0, "sugars_100g": 0.1, "energy_kcal_100g": 5, "fat_100g": 0.0,
      "saturated_fat_100g": 0.0, "carbohydrates_100g": 1.0, "sodium_100g": 0.35,
      "salt_100g": 0.88, "fiber_100g": 0.0},
     ["en:vegan", "en:low-calorie", "en:low-fat"], []),

    # --- Nuts & Seeds ---
    ("Planters Mixed Nuts Unsalted", "Planters", "en:nuts", "B", 4,
     {"proteins_100g": 18.0, "sugars_100g": 5.0, "energy_kcal_100g": 598, "fat_100g": 52.0,
      "saturated_fat_100g": 8.0, "carbohydrates_100g": 19.0, "sodium_100g": 0.0,
      "salt_100g": 0.0, "fiber_100g": 7.0},
     ["en:vegan", "en:gluten-free", "en:no-added-salt"], ["tree nuts", "peanuts"]),
    ("Sunflower Seeds Roasted", "Compliments", "en:seeds", "B", 4,
     {"proteins_100g": 22.0, "sugars_100g": 3.5, "energy_kcal_100g": 584, "fat_100g": 51.0,
      "saturated_fat_100g": 6.0, "carbohydrates_100g": 20.0, "sodium_100g": 0.0,
      "salt_100g": 0.0, "fiber_100g": 9.0},
     ["en:vegan", "en:gluten-free"], []),

    # --- Meat & Plant Protein ---
    ("Beyond Burger", "Beyond Meat", "en:meat-alternatives", "B", 2,
     {"proteins_100g": 17.0, "sugars_100g": 0.0, "energy_kcal_100g": 256, "fat_100g": 18.0,
      "saturated_fat_100g": 5.0, "carbohydrates_100g": 7.0, "sodium_100g": 0.39,
      "salt_100g": 0.98, "fiber_100g": 2.0},
     ["en:vegan", "en:plant-based", "en:high-protein"], ["gluten", "soy"]),
    ("Sunrise Tofu Extra Firm", "Sunrise", "en:tofu", "A", 2,
     {"proteins_100g": 15.0, "sugars_100g": 0.5, "energy_kcal_100g": 144, "fat_100g": 8.0,
      "saturated_fat_100g": 1.0, "carbohydrates_100g": 4.0, "sodium_100g": 0.01,
      "salt_100g": 0.025, "fiber_100g": 0.5},
     ["en:vegan", "en:gluten-free", "en:high-protein", "en:organic"], ["soy"]),

    # --- Instant / Ready meals ---
    ("Kraft Dinner Original", "Kraft Heinz", "en:pasta-dishes", "D", 4,
     {"proteins_100g": 13.0, "sugars_100g": 6.0, "energy_kcal_100g": 376, "fat_100g": 5.0,
      "saturated_fat_100g": 2.0, "carbohydrates_100g": 67.0, "sodium_100g": 0.71,
      "salt_100g": 1.78, "fiber_100g": 2.0},
     [], ["gluten", "milk"]),
    ("PC Blue Menu Quinoa & Brown Rice", "President's Choice", "en:grains", "A", 2,
     {"proteins_100g": 5.5, "sugars_100g": 0.0, "energy_kcal_100g": 370, "fat_100g": 3.0,
      "saturated_fat_100g": 0.5, "carbohydrates_100g": 70.0, "sodium_100g": 0.0,
      "salt_100g": 0.0, "fiber_100g": 4.0},
     ["en:vegan", "en:gluten-free", "en:organic"], []),
]

# ---------------------------------------------------------------------------
# Expand to ~500 rows by adding minor variations
# ---------------------------------------------------------------------------

def _vary(base: dict, scale: float) -> dict:
    return {k: round(v * scale, 2) for k, v in base.items()}


def _make_rows() -> list[dict]:
    rows = []
    code_counter = 100_000_000

    for tpl in PRODUCTS:
        name, brand, category_tag, nutriscore, nova, nutrients, label_tags, allergens = tpl
        category_display = category_tag.replace("en:", "").replace("-", " ").title()

        for variant_i, scale in enumerate([1.0, 0.85, 1.15]):
            code_counter += 1
            suffix = ["", " Original", " Lite", " Plus"][variant_i % 4]
            label_slug = category_tag.split(":")[-1]

            row = {
                "code": str(code_counter),
                "product_name": name + suffix if variant_i > 0 else name,
                "brands": brand,
                "categories": category_display,
                "categories_tags": [category_tag, f"en:{label_slug}"],
                "countries_tags": ["en:canada", "en:world"],
                "nutriscore_grade": nutriscore,
                "nova_group": nova,
                "ingredients_text": f"Ingredients: {', '.join(allergens) or 'various'}",
                "labels_tags": label_tags + (["en:canadian-product"] if variant_i == 0 else []),
                "image_front_url": f"https://images.openfoodfacts.org/images/products/{code_counter}/front.jpg",
                **_vary(nutrients, scale),
            }
            rows.append(row)

    # Shuffle for realism
    random.shuffle(rows)
    return rows


def main() -> None:
    print("OFF AI - Synthetic Dev Dataset Generator")
    print(f"  Output: {OUTPUT_FILE}")
    print()

    rows = _make_rows()
    print(f"Generated {len(rows)} product rows...")

    # Build pyarrow table
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, OUTPUT_FILE, compression="snappy")

    import os
    size_kb = os.path.getsize(OUTPUT_FILE) // 1024
    print(f"Saved {OUTPUT_FILE} ({size_kb} KB, {len(rows)} rows)")
    print()
    print("Categories included:")
    cats = sorted(set(r["categories"] for r in rows))
    for c in cats:
        count = sum(1 for r in rows if r["categories"] == c)
        print(f"  {c:<35} ({count} products)")
    print()
    print("API will pick this file up automatically (default: off_dev.parquet).")
    print("To override:  $env:OFF_PARQUET_PATH = 'off_dev.parquet'")


if __name__ == "__main__":
    main()
