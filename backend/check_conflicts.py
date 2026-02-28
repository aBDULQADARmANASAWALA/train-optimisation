import requests

r = requests.get('http://localhost:8010/api/v1/state/live')
data = r.json()

print(f"Current conflicts: {data['current_conflicts']}")
print(f"Total conflict objects: {len(data['conflicts'])}")
print(f"Unique conflict IDs: {len(set(c['id'] for c in data['conflicts']))}")

print("\nConflict IDs:")
for c in data['conflicts'][:10]:
    print(f"  - {c['id']} ({c['type']})")
