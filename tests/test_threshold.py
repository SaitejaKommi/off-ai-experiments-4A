"""Test updated calorie threshold"""
import requests
import json

url = "http://localhost:8000/nl-search"
data = {"query": "low calorie snacks", "max_results": 10}

response = requests.post(url, json=data, timeout=10)
result = response.json()

print("Interpreted calorie threshold:", result['interpreted_query'].get('energy_kcal_100g_lte', 'N/A'))
print("Expected: 400.0")
print("Products found:", len(result['products']))
print("Relaxation applied:", result['relaxation_applied'])
