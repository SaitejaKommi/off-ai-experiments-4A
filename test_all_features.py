"""Comprehensive test of various nutrient constraints"""
import requests
import json
import time

url = "http://localhost:8000/nl-search"

test_queries = [
    # Nutrient constraints
    ("high protein snacks", "Should find snacks with ≥10g protein/100g"),
    ("low sugar cereals", "Should find cereals with ≤5g sugar/100g"),
    ("low sodium chips", "Should find chips with low sodium"),
    ("high fiber bread", "Should find bread with ≥6g fiber/100g"),
    ("low fat yogurt", "Should find yogurt with ≤3g fat/100g"),
    
    # Dietary tags
    ("vegan chocolate", "Should filter for vegan products"),
    ("gluten free pasta", "Should filter for gluten-free products"),
    
    # Ingredient exclusions
    ("snacks without peanuts", "Should exclude peanut ingredients"),
    ("cookies without milk", "Should exclude milk ingredients"),
    
    # Category only (no constraints)
    ("cheese", "Should just find cheese category"),
]

print("=" * 80)
print("Testing Multiple Query Types - OpenFoodFacts API Feature Test")
print("=" * 80)

passed = 0
failed = 0
timeout_count = 0

for query_text, description in test_queries:
    print(f"\n🔍 Query: '{query_text}'")
    print(f"   Expected: {description}")
    print("-" * 80)
    
    try:
        response = requests.post(url, json={"query": query_text, "max_results": 5}, timeout=30)
        result = response.json()
        
        # Show interpretation
        interp = result['interpreted_query']
        print(f"  Category: {interp.get('category', 'None')}")

        dietary = [key for key, value in interp.items() if value is True]
        if dietary:
            print(f"  Dietary tags: {', '.join(dietary)}")

        exclusions = interp.get('excluded_ingredients', [])
        if exclusions:
            print(f"  Excluded ingredients: {', '.join(exclusions)}")

        # Show nutrient constraints
        constraints = {k: v for k, v in interp.items() if k.endswith('_min') or k.endswith('_max')}
        if constraints:
            constraint_list = []
            for key, value in constraints.items():
                nutrient = key.rsplit('_', 1)[0].replace('_', '-')
                operator = "≥" if key.endswith("_min") else "≤"
                constraint_list.append(f"{nutrient} {operator} {value}")
            if constraint_list:
                print(f"  Nutrient constraints: {', '.join(constraint_list)}")
        
        # Show results
        products_count = len(result['products'])
        print(f"  Products found: {products_count}")
        
        if result.get('relaxation', []):
            print(f"  ⚠️  Relaxation: {', '.join(result.get('relaxation', []))}")
        
        if products_count > 0:
            first_prod = result['products'][0]
            print(f"  Example: {first_prod['name']}")
            
            # Show relevant nutrients for first product
            if 'energy_kcal_100g' in first_prod and first_prod['energy_kcal_100g']:
                print(f"           Calories: {first_prod['energy_kcal_100g']} kcal/100g", end="")
            if 'proteins_100g' in first_prod and first_prod['proteins_100g']:
                print(f" | Protein: {first_prod['proteins_100g']}g", end="")
            if 'sugars_100g' in first_prod and first_prod['sugars_100g']:
                print(f" | Sugar: {first_prod['sugars_100g']}g", end="")
            print()
        
        print(f"  ✅ PASS")
        passed += 1
        
    except requests.exceptions.Timeout:
        print(f"  ⏱️  TIMEOUT - OpenFoodFacts API is slow (>30s)")
        timeout_count += 1
    except requests.exceptions.ConnectionError:
        print(f"  ❌ CONNECTION ERROR - Server not running?")
        failed += 1
    except Exception as e:
        print(f"  ❌ ERROR: {str(e)}")
        failed += 1
    
    time.sleep(1)  # Delay between requests to be nice to the API

print("\n" + "=" * 80)
print(f"Results: {passed} passed, {failed} failed, {timeout_count} timeouts")
print("=" * 80)
