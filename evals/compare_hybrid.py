import json
import os
import re
import unicodedata

from sentence_transformers import SentenceTransformer
from supabase import create_client

K = int(os.getenv("K", "10"))
model = SentenceTransformer("intfloat/multilingual-e5-large")
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
golden = json.load(open("evals/golden_set.json", encoding="utf-8"))


def norm(t):
    d = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in d if not unicodedata.combining(c))


def has(term, text):
    t = norm(term).strip()
    if re.search(r"\d", t):
        return re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", text) is not None
    return t in text


def run(question):
    emb = model.encode(["query: " + question], normalize_embeddings=True)[0].tolist()
    old = sb.rpc("match_documents", {"query_embedding": emb, "match_count": K}).execute().data
    new = sb.rpc(
        "match_documents_hybrid",
        {"query_embedding": emb, "query_text": question, "match_count": K},
    ).execute().data
    return old, new


def score(chunks, case):
    text = norm(" ".join(c["text"] for c in chunks))
    terms = case.get("expected_answer_contains", [])
    found = [t for t in terms if has(t, text)]
    sources = [s.lower() for s in case.get("expected_chunk_sources", [])]
    files = [c["file"].lower() for c in chunks]
    src_hit = (not sources) or any(s in f for s in sources for f in files)
    return len(found), len(terms), src_hit, [t for t in terms if t not in found]


better = worse = same = 0
tot_old = tot_new = tot_terms = 0
for case in golden:
    if not case.get("expected_answer_contains") and not case.get("expected_chunk_sources"):
        continue
    old, new = run(case["question"])
    o_found, n_terms, o_src, _ = score(old, case)
    n_found, _, n_src, missing = score(new, case)
    tot_old += o_found
    tot_new += n_found
    tot_terms += n_terms
    if n_found > o_found or (n_src and not o_src):
        flag = "MELHOROU"
        better += 1
    elif n_found < o_found or (o_src and not n_src):
        flag = "PIOROU"
        worse += 1
    else:
        flag = "="
        same += 1
    print(
        f"{case['id']:<24} fontes {int(o_src)}->{int(n_src)}  termos {o_found}/{n_terms} -> {n_found}/{n_terms}  {flag}"
        + (f"  faltam(novo)={missing}" if missing else "")
    )

print(f"\nK={K}  melhorou={better}  piorou={worse}  igual={same}")
print(f"termos encontrados: antigo {tot_old}/{tot_terms}  novo {tot_new}/{tot_terms}")