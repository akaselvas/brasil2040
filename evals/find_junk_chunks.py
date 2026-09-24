"""
find_junk_chunks.py
=====================
Varre TODA a tabela de chunks no Supabase (não só as 28 perguntas suspeitas)
procurando por chunks com sinais de serem "lixo de embedding": tabelas cruas
com pouca variedade de palavras, ou boilerplate institucional repetido em
vários lugares do corpus.

Isso é heurístico, não perfeito — o objetivo é te dar uma lista curta pra
revisão manual antes de decidir apagar/reprocessar algo.

USO:
  export SUPABASE_URL=...
  export SUPABASE_KEY=...
  python find_junk_chunks.py

Ajuste TABLE_NAME e as colunas abaixo se o nome da sua tabela/RPC for diferente.
"""

import os
import re
from collections import Counter

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
TABLE_NAME = os.getenv("CHUNKS_TABLE", "documents")  # ajuste se sua tabela tiver outro nome

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def unique_word_ratio(text: str) -> float:
    """Proporção de palavras únicas sobre o total. Tabelas repetitivas têm ratio baixo."""
    words = re.findall(r"\w+", text.lower())
    if not words:
        return 1.0
    return len(set(words)) / len(words)


def digit_ratio(text: str) -> float:
    """Proporção de caracteres que são dígitos. Tabelas numéricas têm ratio alto."""
    if not text:
        return 0.0
    digits = sum(c.isdigit() for c in text)
    return digits / len(text)


def is_boilerplate_candidate(text: str) -> bool:
    """Sinais de cabeçalho/rodapé institucional: CNPJ, endereço, telefone, sem verbo de conteúdo."""
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

    print(f"Total de chunks no corpus: {len(all_rows)}\n")

    junk_candidates = []
    for row in all_rows:
        text = row.get("text", "") or ""
        if len(text) < 20:
            continue

        uwr = unique_word_ratio(text)
        dr = digit_ratio(text)
        boilerplate = is_boilerplate_candidate(text)

        # heurística: pouquíssima variedade de palavras (tabela repetitiva)
        # OU muitos dígitos (tabela numérica) OU bate padrão de boilerplate
        is_junk = uwr < 0.35 or dr > 0.25 or boilerplate

        if is_junk:
            junk_candidates.append(
                {
                    "id": row.get("id"),
                    "file": row.get("file"),
                    "page": row.get("page"),
                    "unique_word_ratio": round(uwr, 2),
                    "digit_ratio": round(dr, 2),
                    "boilerplate": boilerplate,
                    "preview": text[:120].replace("\n", " "),
                }
            )

    print(f"Chunks suspeitos de serem 'lixo': {len(junk_candidates)} de {len(all_rows)} ({100*len(junk_candidates)/len(all_rows):.1f}%)\n")
    print("=" * 100)

    # agrupa por arquivo pra ver quais documentos concentram mais problema
    by_file = Counter(c["file"] for c in junk_candidates)
    print("Arquivos com mais chunks suspeitos:\n")
    for file, count in by_file.most_common(15):
        print(f"  {count:3d}x  {file}")

    print("\n" + "=" * 100)
    print("Amostra dos 20 piores (menor unique_word_ratio primeiro):\n")
    junk_candidates.sort(key=lambda c: c["unique_word_ratio"])
    for c in junk_candidates[:20]:
        flags = []
        if c["unique_word_ratio"] < 0.35:
            flags.append("baixa-variedade")
        if c["digit_ratio"] > 0.25:
            flags.append("muito-numérico")
        if c["boilerplate"]:
            flags.append("boilerplate")
        print(f"  id={c['id']} | {c['file']} pág.{c['page']} | {'+'.join(flags)}")
        print(f"    {c['preview']}...")

    print(
        "\nPróximo passo: revisa essa lista. Se confirmar que são mesmo lixo (tabela crua,"
        " cabeçalho institucional), decide entre (a) deletar essas linhas específicas do"
        " Supabase por id, ou (b) reprocessar o PDF de origem com extração que pule tabelas/"
        " cabeçalhos antes de rechunkar e reembedar só esses arquivos."
    )


if __name__ == "__main__":
    main()