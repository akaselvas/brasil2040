"""
diagnose_chat_vs_search.py
============================
Roda TODAS as perguntas (as sugeridas na UI + o golden_set.json inteiro)
contra /search (retrieval puro) e /chat (retrieval + Gemini) lado a lado.

Se o /search traz chunks relevantes mas o /chat ainda responde
"Não encontrei essa informação nos trechos fornecidos" (ou a recusa de
fora de escopo), a causa é o SYSTEM_PROMPT de geração, não a busca.

USO:
  export SEARCH_ENDPOINT=http://localhost:8000/search
  export CHAT_ENDPOINT=http://localhost:8000/chat
  python diagnose_chat_vs_search.py

  # Pra rodar só um subconjunto (ex: só as de agro) enquanto testa algo:
  python diagnose_chat_vs_search.py --filter agro
"""

import argparse
import json
import os
import sys
from pathlib import Path
import time

import requests

SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT", "http://localhost:8000/search")
CHAT_ENDPOINT = os.getenv("CHAT_ENDPOINT", "http://localhost:8000/chat")
TOP_K = int(os.getenv("TOP_K", "8"))
GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"

REFUSAL_MARKERS = [
    "Não encontrei essa informação",
    "Não encontrei esse dado",
    "fora do escopo",
]

# ── Perguntas reais sugeridas na UI, organizadas por setor ──────────────────
UI_QUESTIONS = {
    "agro": [
        "O que são os veranicos e por que destroem a soja no Sul?",
        "Qual cultura tem maior potencial de adaptação ao aquecimento?",
        "O que o relatório recomenda para o produtor familiar?",
        "Como a irrigação pode compensar as perdas no Sul?",
        "Por que a cana-de-açúcar ganha área com o aquecimento?",
        "Quanto custa implantar irrigação em 175 hectares no RS?",
        "Como o deslocamento da soja pressiona o desmatamento da Amazônia?",
        "Por que o Nordeste Cerrado ganha valor mesmo perdendo área?",
        "O que é o gene Dreb e como ele torna a soja resistente à seca?",
        "Como o encarecimento da ração afeta o preço do frango no mercado?",
    ],
    "energia": [
        'O que é o "fator de fricção" das hidrelétricas brasileiras?',
        "Como o preço do carbono afeta a expansão elétrica no RCP 4.5?",
        "Por que o RCP 4.5 tem risco de déficit maior que o esperado?",
        "Qual seria o papel da energia solar e eólica na adaptação?",
        "Por que Sobradinho é tão vulnerável à seca?",
        "Qual o custo de operação em R$/MWh no pior cenário?",
        "O que é o critério CVaR e como o ONS o aplica?",
        "Por que o licenciamento ambiental é o maior gargalo hidrelétrico?",
        'Qual é o "Nível Meta" operativo e por que ele causa desvios?',
    ],
    "hidro": [
        "O que é Energia Natural Afluente e como ela é calculada?",
        "Por que o Sul terá mais água enquanto o Nordeste terá menos?",
        "Como a Oscilação Decadal do Pacífico afeta as vazões brasileiras?",
        "Por que a bacia do Paraguai é exceção positiva no Sudeste?",
        "O que causa a divergência extrema entre MIROC e HadGEM no Sul?",
        "Como o aumento de evapotranspiração piora a seca mesmo sem menos chuva?",
        "Por que o Jequitinhonha pode perder quase 73% da sua ENA?",
        "Quais são os princípios de Ostrom para gestão de recursos hídricos?",
        "Qual a diferença entre adaptação incremental e transformacional?",
        "Como a transposição do São Francisco protege Fortaleza mas cria novos conflitos?",
    ],
    "transporte": [
        "Como o calor causa fluência plástica no pavimento asfáltico?",
        "O que é o método SUPERPAVE e como classifica os ligantes por temperatura?",
        "Por que as rodovias concedidas são menos vulneráveis que as do DNIT?",
        "O que é o índice IVIR e como seus critérios foram ponderados?",
        "Por que Santa Catarina tem o pior IGG médio apesar de ser no Sul?",
        "Como o método MACBETH transforma julgamentos em pesos de vulnerabilidade?",
        "O que é o cheap seal e como ele reduz a temperatura do pavimento?",
        "Por que as rodovias planejadas são consideradas de alto risco ainda antes de serem construídas?",
        "Qual é o tempo de recorrência projetado como insuficiente para os sistemas de drenagem?",
        "Como inundações em rodovias criam efeito em cascata nos demais modais?",
    ],
    "costa": [
        "O que é o IVCB e quais são seus sete indicadores?",
        "Por que Santos é mais vulnerável que o Rio de Janeiro no IVCB?",
        "O que são as Storm Surge Barriers e por que Recife, Santos e Vitória foram escolhidas?",
        "Como o assoreamento cresce proporcionalmente ao quadrado da altura das ondas?",
        "Por que a incompatibilidade entre datums geodésicos limita o mapeamento costeiro?",
        "O que é borda livre de cais e quando ela se torna operacionalmente crítica?",
        "Por que a ETE Alegria é considerada de alto risco para 1,5 milhão de pessoas?",
        "Como a elevação do nível do mar afoga manguezais e intensifica o assoreamento?",
        "O que são eventos na-tech e por que a zona portuária de Santos representa risco industrial?",
        "Por que o licenciamento ambiental do IBAMA pode ser o principal instrumento de adaptação?",
    ],
    "drenagem_urbana": [
        "Por que os modelos climáticos projetam menos enchentes em SP mas a realidade piora?",
        "O que significa CN 88 e por que é crítico para drenagem urbana?",
        'Por que a "Lei das Piscininhas" não funciona na prática?',
        "O que são as curvas IDF e como as mudanças climáticas as afetam?",
        'Como os "piscinões" se comparam à detenção distribuída?',
        "Por que Recife apresenta o maior déficit de dados hidrológicos?",
        "O que é a premissa de estacionariedade e por que ela falha?",
    ],
}


def load_golden_set() -> list[dict]:
    if not GOLDEN_SET_PATH.exists():
        print(f"⚠️  golden_set.json não encontrado em {GOLDEN_SET_PATH}, pulando.")
        return []
    with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_question_list(filter_str: str | None) -> list[tuple[str, str]]:
    """Retorna lista de (categoria, pergunta), sem duplicatas, na ordem: UI primeiro, depois golden_set."""
    seen = set()
    items: list[tuple[str, str]] = []

    for category, questions in UI_QUESTIONS.items():
        for q in questions:
            if q not in seen:
                seen.add(q)
                items.append((f"ui:{category}", q))

    for case in load_golden_set():
        q = case["question"]
        if q not in seen:
            seen.add(q)
            items.append((f"golden:{case.get('category', '?')}", q))

    if filter_str:
        items = [(c, q) for c, q in items if filter_str.lower() in c.lower()]

    return items


def get_chunks(question: str) -> list[dict]:
    r = requests.post(SEARCH_ENDPOINT, json={"question": question, "top_k": TOP_K}, timeout=15)
    r.raise_for_status()
    return r.json().get("chunks", [])


def get_chat_answer(question: str, retries: int = 2) -> str:
    for attempt in range(retries + 1):
        try:
            r = requests.post(
                CHAT_ENDPOINT,
                json={"question": question, "history": [], "top_k": TOP_K},
                timeout=90,
                stream=True,
            )
            r.raise_for_status()
            return "".join(chunk.decode("utf-8", errors="ignore") for chunk in r.iter_content(chunk_size=None))
        except requests.exceptions.RequestException as e:
            if attempt < retries:
                time.sleep(5)
                continue
            return f"[ERRO após {retries+1} tentativas: {e}]"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--filter", help="só roda categorias que contenham essa string (ex: agro, energia, golden)")
    args = parser.parse_args()

    items = build_question_list(args.filter)
    print(f"Testando {len(items)} perguntas contra {SEARCH_ENDPOINT} e {CHAT_ENDPOINT} (top_k={TOP_K})\n")

    results = []  # (categoria, pergunta, n_chunks, fontes, recusou, resposta)

    for category, q in items:
        try:
            chunks = get_chunks(q)
        except requests.exceptions.ConnectionError:
            print(f"⚠️  Servidor não respondeu em {SEARCH_ENDPOINT}. Suba com: uvicorn main:app --reload")
            sys.exit(1)

        files = sorted(set(c.get("file", "?") for c in chunks))

        try:
            answer = get_chat_answer(q)
        except requests.exceptions.ConnectionError:
            print(f"⚠️  Servidor não respondeu em {CHAT_ENDPOINT}.")
            sys.exit(1)
        except requests.exceptions.RequestException as e:
            answer = f"[ERRO: {e}]"

        refused = any(marker in answer for marker in REFUSAL_MARKERS)
        errored = answer.startswith("[ERRO")
        results.append((category, q, len(chunks), files, refused, answer))

        status = "⚫ ERRO" if errored else ("🔴 RECUSOU" if refused else "🟢 ok")
        flag = "  ⚠️ chunks existem mas recusou → SYSTEM_PROMPT" if (chunks and refused) else ""
        print(f"[{category}] {status}{flag}")
        print(f"  ❓ {q}")
        print(f"  chunks: {len(chunks)} | fontes: {files}")
        print(f"  resposta: {answer[:200]}...")
        print()

        time.sleep(5)

    # ── resumo ────────────────────────────────────────────────────────────
    errored = [(c, q) for c, q, n, f, r, a in results if a.startswith("[ERRO")]
    prompt_bug = [(c, q) for c, q, n, f, r, a in results if n > 0 and r and not a.startswith("[ERRO")]
    retrieval_bug = [(c, q) for c, q, n, f, r, a in results if n == 0 and r and not a.startswith("[ERRO")]
    ok = [(c, q) for c, q, n, f, r, a in results if not r and not a.startswith("[ERRO")]

    print("=" * 90)
    print("RESUMO")
    print("=" * 90)
    print(f"Total testado: {len(results)}")
    print(f"🟢 Respondeu normalmente: {len(ok)}")
    print(f"🟠 Recusou com chunks existindo (SUSPEITO: bug de SYSTEM_PROMPT): {len(prompt_bug)}")
    for c, q in prompt_bug:
        print(f"   [{c}] {q}")
    print(f"🔴 Recusou sem nenhum chunk (SUSPEITO: bug de retrieval/embedding): {len(retrieval_bug)}")
    for c, q in retrieval_bug:
        print(f"   [{c}] {q}")
    print(f"⚫ Erro de conexão/timeout (não é bug de prompt nem de retrieval): {len(errored)}")
    for c, q in errored:
        print(f"   [{c}] {q}")


if __name__ == "__main__":
    main()