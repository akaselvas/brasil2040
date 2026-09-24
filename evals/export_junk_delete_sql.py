"""
export_junk_delete_sql.py
===========================
Roda a MESMA heurística do find_junk_chunks.py, mas em vez de só imprimir
no terminal, gera um arquivo .sql pronto com os comandos DELETE em lotes
(pra não estourar limite de query gigante), pra você rodar no SQL Editor
do Supabase depois de revisar.

USO:
  export SUPABASE_URL=...
  export SUPABASE_KEY=...
  python export_junk_delete_sql.py

Gera: junk_chunks_delete.sql
"""

import os
import re
from collections import Counter

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
TABLE_NAME = os.getenv("CHUNKS_TABLE", "documents")
BATCH_SIZE = 200  # ids por comando DELETE, pra manter a query num tamanho seguro

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def unique_word_ratio(text: str) -> float:
    words = re.findall(r"\w+", text.lower())
    if not words:
        return 1.0
    return len(set(words)) / len(words)


def digit_ratio(text: str) -> float:
    if not text:
        return 0.0
    digits = sum(c.isdigit() for c in text)
    return digits / len(text)


def is_boilerplate_candidate(text: str) -> bool:
    markers = ["cnpj", "fone", "cep ", "fundação", "universidade,", "av. da"]
    lower = text.lower()
    return any(m in lower for m in markers) and len(text) < 400


def main():
    print(f"Buscando todos os chunks na tabela '{TABLE_NAME}'...")
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        resp = (
            supabase.table(TABLE_NAME)
            .select("id, file, page, text")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = resp.data
        if not rows:
            break
        all_rows.extend(rows)
        offset += page_size
        if len(rows) < page_size:
            break

    print(f"Total de chunks no corpus: {len(all_rows)}")

    junk_ids = []
    by_file = Counter()
    for row in all_rows:
        text = row.get("text", "") or ""
        if len(text) < 20:
            continue
        uwr = unique_word_ratio(text)
        dr = digit_ratio(text)
        boilerplate = is_boilerplate_candidate(text)
        if uwr < 0.35 or dr > 0.25 or boilerplate:
            junk_ids.append(row["id"])
            by_file[row.get("file", "?")] += 1

    print(f"Chunks marcados como lixo: {len(junk_ids)}\n")
    for file, count in by_file.most_common(15):
        print(f"  {count:3d}x  {file}")

    # gera o .sql em lotes
    out_path = "junk_chunks_delete.sql"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"-- Gerado automaticamente. {len(junk_ids)} ids marcados como lixo.\n")
        f.write("-- REVISE antes de rodar. Recomendado: rode um SELECT antes do DELETE.\n\n")
        f.write("-- Passo 1 (opcional, recomendado): confira quantas linhas batem antes de apagar\n")
        f.write(f"-- select count(*) from {TABLE_NAME} where id in (...);\n\n")

        for i in range(0, len(junk_ids), BATCH_SIZE):
            batch = junk_ids[i : i + BATCH_SIZE]
            ids_str = ", ".join(str(x) for x in batch)
            f.write(f"-- lote {i // BATCH_SIZE + 1} ({len(batch)} ids)\n")
            f.write(f"delete from {TABLE_NAME} where id in ({ids_str});\n\n")

    print(f"\n✅ Arquivo gerado: {out_path}")
    print(f"   {len(junk_ids)} ids em {(len(junk_ids) + BATCH_SIZE - 1) // BATCH_SIZE} lotes de até {BATCH_SIZE}.")
    print("   Abra o arquivo, revise, e cole os comandos no SQL Editor do Supabase.")
    print("   Recomendado: rode um lote por vez, ou todos de uma vez se já confiar na heurística.")


if __name__ == "__main__":
    main()