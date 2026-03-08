"""Test various queries to understand OFF Canada data"""
import requests

url = "http://localhost:8000/nl-search"

test_queries = [
    "snacks",  # Any snacks at all
    "high calorie snacks",  # Opposite constraint
    "low calorie yogurt",  # Different category
    "chips",  # Specific snack type
]

for query_text in test_queries:
    print(f"\nQuery: '{query_text}'")
    print("-" * 60)
    response = requests.post(url, json={"query": query_text, "max_results": 5})
    result = response.json()
    
    print(f"  Products: {len(result['products'])}")
    print(f"  Relaxation: {result['relaxation_applied']}")
    if result['products']:
        print(f"  First product: {result['products'][0]['name']}")
        print(f"    Calories: {result['products'][0].get('energy_kcal_100g', 'N/A')} kcal/100g")
