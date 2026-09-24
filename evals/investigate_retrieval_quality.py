"""
investigate_retrieval_quality.py
==================================
Foca nos casos que sobraram como suspeitos depois do fix do SYSTEM_PROMPT.
Em vez de só checar "veio chunk ou não", olha a SIMILARIDADE de cada chunk
e conta com que frequência cada arquivo aparece como top-1 resultado —
isso expõe um doc "atrator" (embedding ruim) que aparece pra perguntas
sem relação nenhuma com ele.

USO:
  export SEARCH_ENDPOINT=http://localhost:8000/search
  python investigate_retrieval_quality.py
"""

import os
from collections import Counter

import requests

SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT", "http://localhost:8000/search")
TOP_K = int(os.getenv("TOP_K", "8"))

# As 28 perguntas que sobraram como suspeitas (exclui as 5 hallucination/out_of_scope
# que já confirmamos que estão corretas)
SUSPECT_QUESTIONS = [
    "Qual cultura tem maior potencial de adaptação ao aquecimento?",
    "O que o relatório recomenda para o produtor familiar?",
    "Por que a cana-de-açúcar ganha área com o aquecimento?",
    "Quanto custa implantar irrigação em 175 hectares no RS?",
    "Por que o Nordeste Cerrado ganha valor mesmo perdendo área?",
    "Como o encarecimento da ração afeta o preço do frango no mercado?",
    'Qual é o "Nível Meta" operativo e por que ele causa desvios?',
    "Por que o Sul terá mais água enquanto o Nordeste terá menos?",
    "Por que a bacia do Paraguai é exceção positiva no Sudeste?",
    "Como o aumento de evapotranspiração piora a seca mesmo sem menos chuva?",
    "Por que o Jequitinhonha pode perder quase 73% da sua ENA?",
    "Quais são os princípios de Ostrom para gestão de recursos hídricos?",
    "Qual a diferença entre adaptação incremental e transformacional?",
    "Como o calor causa fluência plástica no pavimento asfáltico?",
    "Por que as rodovias concedidas são menos vulneráveis que as do DNIT?",
    "O que é o cheap seal e como ele reduz a temperatura do pavimento?",
    "Qual é o tempo de recorrência projetado como insuficiente para os sistemas de drenagem?",
    "Como inundações em rodovias criam efeito em cascata nos demais modais?",
    "Como o assoreamento cresce proporcionalmente ao quadrado da altura das ondas?",
    "O que são eventos na-tech e por que a zona portuária de Santos representa risco industrial?",
    "O que são as curvas IDF e como as mudanças climáticas as afetam?",
    "Por que Recife apresenta o maior déficit de dados hidrológicos?",
    "O que é a premissa de estacionariedade e por que ela falha?",
    "Por que o cenário RCP 4.5 pode ser mais vulnerável à seca do que o RCP 8.5?",
    "Quais cidades costeiras brasileiras têm maior risco de inundação por elevação do nível do mar?",
    "Quais populações vulneráveis são mais afetadas pelo risco climático no Brasil segundo o relatório?",
    "Quais medidas de adaptação sem arrependimento são recomendadas para o setor de energia no Brasil 2040?",
    "Qual a demanda média do SIN projetada de 2015 para 2030?",
]


def search(question: str) -> list[dict]:
    r = requests.post(SEARCH_ENDPOINT, json={"question": question, "top_k": TOP_K}, timeout=15)
    r.raise_for_status()
    return r.json().get("chunks", [])


def main():
    top1_file_counter = Counter()
    all_file_counter = Counter()

    print(f"Investigando {len(SUSPECT_QUESTIONS)} perguntas suspeitas contra {SEARCH_ENDPOINT}\n")
    print("=" * 100)

    for q in SUSPECT_QUESTIONS:
        chunks = search(q)
        if not chunks:
            print(f"\n❓ {q}\n   🔴 zero chunks retornados")
            continue

        # ordena por similaridade decrescente pra garantir que o top-1 é o mais relevante
        chunks_sorted = sorted(chunks, key=lambda c: c.get("similarity", 0), reverse=True)
        top1 = chunks_sorted[0]
        top1_file_counter[top1.get("file", "?")] += 1
        for c in chunks:
            all_file_counter[c.get("file", "?")] += 1

        print(f"\n❓ {q}")
        print(f"   top-1: {top1.get('file','?')} (pág. {top1.get('page','?')}, sim={top1.get('similarity', 0):.3f})")
        preview = top1.get("text", "")[:150].replace("\n", " ")
        print(f"   preview: {preview}...")

        # mostra os 3 primeiros pra dar visão geral de diversidade
        print("   top-3:")
        for c in chunks_sorted[:3]:
            print(f"     - {c.get('file','?')} | sim={c.get('similarity', 0):.3f}")

    print("\n" + "=" * 100)
    print("RANKING: arquivos que mais aparecem como TOP-1 resultado nessas 28 perguntas")
    print("=" * 100)
    print("(se um arquivo aparece muitas vezes aqui para perguntas de temas bem diferentes,")
    print(" é forte sinal de embedding ruim / chunk 'atrator' nesse documento)\n")
    for file, count in top1_file_counter.most_common(10):
        pct = 100 * count / len(SUSPECT_QUESTIONS)
        print(f"  {count:2d}x ({pct:.0f}%)  {file}")

    print("\n" + "=" * 100)
    print("RANKING: arquivos que mais aparecem em QUALQUER posição do top-8")
    print("=" * 100)
    for file, count in all_file_counter.most_common(10):
        print(f"  {count:2d}x  {file}")


if __name__ == "__main__":
    main()