import os, re, requests
from supabase import create_client

Q = "Qual o risco de déficit (apagão) no subsistema Sudeste/Centro-Oeste no cenário HadGEM 8.5?"
PAT = re.compile(r"\b(74|99)\s*%")

# A) o que o /search devolve (top 30), com a posição de cada chunk
r = requests.post(os.getenv("SEARCH_ENDPOINT", "http://localhost:8000/search"),
                  json={"question": Q, "top_k": 30}, timeout=30)
print("== /search top 30 ==")
for i, c in enumerate(r.json()["chunks"], 1):
    hit = PAT.findall(c["text"])
    print(f"{i:2d} sim={c.get('similarity',0):.3f} {c['file']} pág.{c['page']} {'<-- ' + str(hit) if hit else ''}")

# B) existe em algum chunk de Energia no banco?
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
print("\n== banco (Energia) ==")
off = 0
while True:
    rows = sb.table("documents").select("id,file,page,text").ilike("file", "Energia%").range(off, off + 999).execute().data
    if not rows:
        break
    for row in rows:
        t = row["text"]
        if re.search(r"\b99\s*%|\b74\s*%|\b74\s*(a|e|–|-)\s*99", t):
            m = re.search(r"\b99\s*%|\b74\s*%|\b74\s*(a|e|–|-)\s*99", t)
            ini = max(m.start() - 150, 0)
            print(f"id={row['id']} {row['file']} pág.{row['page']}: ...{t[ini:m.end()+100]!r}")
    off += 1000
    if len(rows) < 1000:
        break