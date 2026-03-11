"""Quick test script to check relaxation behavior"""
import requests
import json

url = "http://localhost:8000/nl-search"
data = {"query": "low calorie snacks", "max_results": 10}

print("Testing query:", data["query"])
print("-" * 50)

response = requests.post(url, json=data)
result = response.json()

print(f"\nProducts found: {len(result['products'])}")
print(f"Relaxation: {result.get('relaxation', [])}")
print(f"Applied filters: {result.get('applied_filters', [])}")
print(f"\nInterpreted query:")
for key, value in result['interpreted_query'].items():
    print(f"  {key}: {value}")
