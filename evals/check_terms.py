import json, requests
gs = {q["id"]: q for q in json.load(open("evals/golden_set.json", encoding="utf-8"))}
chunks = requests.post("http://localhost:8000/search", json={"question": gs["agro_001"]["question"], "top_k": 10}, timeout=60).json()["chunks"]
for c in chunks:
    for n in ("132%", "167%"):
        i = c["text"].find(n)
        if i >= 0: print(n, c["file"], c.get("page"), repr(c["text"][max(i-60,0):i+60]))