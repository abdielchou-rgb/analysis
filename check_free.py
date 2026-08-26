import requests

key = ""
for line in open(r"D:\Claude\projects\2hao-analyst\.env", encoding="utf-8-sig"):
    if line.startswith("OPENROUTER_API_KEY="):
        key = line.split("=", 1)[1].strip().strip('"')
        break
r = requests.get("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
free = [
    m["id"]
    for m in r.json()["data"]
    if m.get("pricing", {}).get("prompt") == "0" and m.get("pricing", {}).get("completion") == "0"
]
print(f"Free models now: {len(free)}")
for m in free:
    print(f"  {m}")
