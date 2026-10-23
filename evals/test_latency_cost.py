import json
import math
import os
import re
import statistics
import sys
import time
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers import CHAT_ENDPOINT, PROD_TOP_K, SEARCH_ENDPOINT, get_chunks

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"
MAIN_PY_PATH = Path(__file__).parent.parent / "main.py"

RETRIEVAL_P95_THRESHOLD_SEC = float(
    os.getenv("RETRIEVAL_P95_SEC", os.getenv("RETRIEVAL_P95_MS", "4.0"))
)
RETRIEVAL_P50_THRESHOLD_SEC = float(
    os.getenv("RETRIEVAL_P50_SEC", os.getenv("RETRIEVAL_P50_MS", "2.0"))
)
LATENCY_REPEATS_PER_QUESTION = int(os.getenv("LATENCY_REPEATS_PER_QUESTION", "5"))
MEDIAN_RUNS = int(os.getenv("LATENCY_MEDIAN_RUNS", "3"))
LONG_QUERY_MAX_RATIO = float(os.getenv("LONG_QUERY_MAX_RATIO", "2.5"))

END_TO_END_MAX_SEC = float(os.getenv("END_TO_END_MAX_SEC", "10.0"))
CHAT_TIMEOUT_SEC = float(os.getenv("CHAT_TIMEOUT_SEC", "90"))

CHARS_PER_TOKEN = float(os.getenv("CHARS_PER_TOKEN", "3.5"))
MAX_TOKENS_PER_QUERY = int(os.getenv("MAX_TOKENS_PER_QUERY", "9500"))
MAX_CHUNK_CHARS = int(os.getenv("MAX_CHUNK_CHARS", "6500"))
MAX_COST_PER_QUERY_USD = float(os.getenv("MAX_COST_PER_QUERY_USD", "0.001"))

GEMINI_INPUT_COST_PER_1M = float(os.getenv("GEMINI_INPUT_COST_PER_1M", "0.075"))
GEMINI_OUTPUT_COST_PER_1M = float(os.getenv("GEMINI_OUTPUT_COST_PER_1M", "0.30"))

ASSUMED_QUESTION_TOKENS = int(os.getenv("ASSUMED_QUESTION_TOKENS", "50"))
ASSUMED_ANSWER_TOKENS = int(os.getenv("ASSUMED_ANSWER_TOKENS", "300"))

with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
    GOLDEN_SET = json.load(f)


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    rank = max(math.ceil(p * len(ordered)), 1)
    return ordered[rank - 1]


def get_system_prompt_tokens() -> int:
    if not MAIN_PY_PATH.exists():
        pytest.fail(f"main.py not found at {MAIN_PY_PATH}; cannot measure the real SYSTEM_PROMPT size.")
    src = MAIN_PY_PATH.read_text(encoding="utf-8")
    m = re.search(r'^SYSTEM_PROMPT\s*=\s*(?:"""(.*?)"""|\'\'\'(.*?)\'\'\')', src, re.S | re.M)
    if not m:
        pytest.fail("Could not read SYSTEM_PROMPT from main.py; update get_system_prompt_tokens.")
    prompt_text = m.group(1) if m.group(1) is not None else m.group(2)
    return estimate_tokens(prompt_text)


def measure_retrieval_latency(question: str, top_k: int = PROD_TOP_K) -> tuple[float, int]:
    start = time.perf_counter()
    try:
        response = requests.post(
            SEARCH_ENDPOINT,
            json={"question": question, "top_k": top_k},
            timeout=10,
        )
        response.raise_for_status()
        elapsed = time.perf_counter() - start
    except requests.exceptions.ConnectionError:
        pytest.fail(f"Server not reachable at {SEARCH_ENDPOINT}. This must not be silently skipped in CI.")
    except requests.exceptions.Timeout:
        pytest.fail(f"/search timed out after 10s for question: {question[:80]}")

    chunks = response.json().get("chunks", [])
    all_text = " ".join(c.get("text", "") for c in chunks)
    return elapsed, estimate_tokens(all_text)


def median_retrieval_latency(question: str, runs: int = MEDIAN_RUNS) -> float:
    measure_retrieval_latency(question)  # aquecimento, descartado
    latencies = [measure_retrieval_latency(question)[0] for _ in range(runs)]
    return statistics.median(latencies)


def estimate_full_query_cost(context_tokens: int, prompt_tokens: int, answer_tokens: int) -> float:
    input_cost = ((context_tokens + prompt_tokens) / 1_000_000) * GEMINI_INPUT_COST_PER_1M
    output_cost = (answer_tokens / 1_000_000) * GEMINI_OUTPUT_COST_PER_1M
    return input_cost + output_cost


class TestRetrievalLatency:
    def test_single_query_latency_under_threshold(self):
        question = "Qual o custo operacional no cenário HadGEM 8.5?"
        median_latency = median_retrieval_latency(question)

        print(f"\n  Median latency over {MEDIAN_RUNS} runs: {median_latency:.3f}s")

        assert median_latency < RETRIEVAL_P50_THRESHOLD_SEC, (
            f"Median latency over {MEDIAN_RUNS} runs: {median_latency:.2f}s >= {RETRIEVAL_P50_THRESHOLD_SEC}s"
        )

    def test_p95_latency_over_multiple_queries(self):
        questions = [
            "O que é o ZARC?", "Qual o risco de déficit?", "Como funciona o sistema hídrico?",
            "Quais culturas têm maior risco?", "O que é RCP 8.5?", "Qual o custo de adaptação?",
            "Como a soja é afetada?", "Qual a projeção de demanda?", "O que é eficiência energética?",
            "Quais regiões têm mais risco?",
        ]
        latencies = []
        for _ in range(LATENCY_REPEATS_PER_QUESTION):
            for q in questions:
                latency, _ = measure_retrieval_latency(q)
                latencies.append(latency)
                time.sleep(0.1)

        p50 = statistics.median(latencies)
        p95 = percentile(latencies, 0.95)

        print(f"\n  Latency stats over {len(latencies)} queries:")
        print(f"    Min:  {min(latencies):.3f}s")
        print(f"    P50:  {p50:.3f}s")
        print(f"    P95:  {p95:.3f}s")
        print(f"    Max:  {max(latencies):.3f}s")

        assert p95 < RETRIEVAL_P95_THRESHOLD_SEC, (
            f"P95 latency {p95:.2f}s >= {RETRIEVAL_P95_THRESHOLD_SEC}s over {len(latencies)} samples"
        )

    def test_latency_does_not_degrade_with_longer_queries(self):
        short_question = "O que é ZARC?"
        long_question = (
            "Considerando todos os setores de infraestrutura crítica do Brasil, "
            "incluindo energia elétrica, recursos hídricos, transportes e infraestrutura costeira, "
            "quais são as principais vulnerabilidades identificadas no relatório Brasil 2040 "
            "para os cenários climáticos RCP 4.5 e RCP 8.5, e quais medidas de adaptação "
            "sem arrependimento são recomendadas para cada setor?"
        )
        short_latency = median_retrieval_latency(short_question)
        long_latency = median_retrieval_latency(long_question)

        print(f"\n  Short query ({len(short_question)} chars): {short_latency:.3f}s (median of {MEDIAN_RUNS})")
        print(f"  Long query  ({len(long_question)} chars): {long_latency:.3f}s (median of {MEDIAN_RUNS})")

        assert long_latency < short_latency * LONG_QUERY_MAX_RATIO, (
            f"Long query is {long_latency / short_latency:.1f}x slower than the short one "
            f"(max allowed {LONG_QUERY_MAX_RATIO}x)"
        )


class TestTokenCost:
    def test_context_tokens_within_budget(self):
        _, context_tokens = measure_retrieval_latency(
            "Qual o custo operacional no cenário HadGEM 8.5?", top_k=PROD_TOP_K
        )
        print(f"\n  Retrieved context tokens (approx, top_k={PROD_TOP_K}): {context_tokens}")
        assert context_tokens <= MAX_TOKENS_PER_QUERY, (
            f"Context ~{context_tokens} tokens > budget {MAX_TOKENS_PER_QUERY}"
        )

    def test_cost_per_query_estimate(self):
        _, context_tokens = measure_retrieval_latency(
            "Qual o custo operacional no cenário HadGEM 8.5?", top_k=PROD_TOP_K
        )
        system_prompt_tokens = get_system_prompt_tokens()

        cost_per_query = estimate_full_query_cost(
            context_tokens=context_tokens,
            prompt_tokens=system_prompt_tokens + ASSUMED_QUESTION_TOKENS,
            answer_tokens=ASSUMED_ANSWER_TOKENS,
        )

        print(f"\n  === COST ESTIMATE ===")
        print(f"  Context tokens:            {context_tokens}")
        print(f"  System prompt tokens:      {system_prompt_tokens}")
        print(f"  Cost per query:            ${cost_per_query:.5f}")
        print(f"  Cost at 100 queries/day:   ${cost_per_query * 100:.3f}/day")
        print(f"  Cost at 1000 queries/day:  ${cost_per_query * 1000:.3f}/day")

        assert cost_per_query < MAX_COST_PER_QUERY_USD, (
            f"Cost per query ${cost_per_query:.5f} >= limit ${MAX_COST_PER_QUERY_USD}"
        )

    def test_chunk_size_distribution(self):
        questions = [q["question"] for q in GOLDEN_SET]
        chunk_info = []
        context_tokens_per_question = []
        for question in questions:
            chunks = get_chunks(question, PROD_TOP_K)
            context_tokens_per_question.append(
                estimate_tokens(" ".join(c.get("text", "") for c in chunks))
            )
            for chunk in chunks:
                chunk_info.append((len(chunk.get("text", "")), chunk.get("file"), chunk.get("page")))

        assert chunk_info, "No chunks returned for any of the golden set questions"

        sizes = [size for size, _, _ in chunk_info]
        median = statistics.median(sizes)
        max_size = max(sizes)
        largest = sorted(set(chunk_info), key=lambda x: x[0], reverse=True)[:5]
        print(f"\n  === CHUNK SIZE ANALYSIS ({len(sizes)} chunks from {len(questions)} questions) ===")
        print(f"  Median:     {median:.0f} chars")
        print(f"  Max chars:  {max_size} chars")
        print("  Largest chunks (chars, file, page):")
        for item in largest:
            print(f"    {item}")
        print(f"  Context tokens per question (top_k={PROD_TOP_K}): "
              f"median={statistics.median(context_tokens_per_question):.0f} max={max(context_tokens_per_question)}")

        assert max_size < MAX_CHUNK_CHARS, (
            f"Chunk size {max_size} chars >= {MAX_CHUNK_CHARS} — largest: {largest[:3]}\n"
            f"  → check for parsing/chunking bugs (or raise MAX_CHUNK_CHARS if your normal chunking is larger)"
        )
        assert max(context_tokens_per_question) <= MAX_TOKENS_PER_QUERY, (
            f"Context for some question is ~{max(context_tokens_per_question)} tokens > budget {MAX_TOKENS_PER_QUERY}"
        )


class TestEndToEndLatency:
    def test_end_to_end_latency_under_threshold(self):
        question = "Qual é o risco de déficit elétrico no Brasil até 2040?"

        start = time.perf_counter()
        try:
            response = requests.post(
                CHAT_ENDPOINT,
                json={"question": question, "history": [], "top_k": PROD_TOP_K},
                timeout=CHAT_TIMEOUT_SEC,
                stream=True,
            )
            response.raise_for_status()
            text = response.content.decode("utf-8", errors="replace")
        except requests.exceptions.ConnectionError:
            pytest.fail(f"Server not reachable at {CHAT_ENDPOINT}. This must not be silently skipped in CI.")
        except requests.exceptions.Timeout:
            pytest.fail(f"/chat timed out after {CHAT_TIMEOUT_SEC}s")
        total_time = time.perf_counter() - start

        print(f"\n  === END-TO-END LATENCY (/chat, top_k={PROD_TOP_K}) ===")
        print(f"  Total:      {total_time:.3f}s")
        print(f"  Answer preview: {text[:100]}...")

        assert text.strip(), "/chat returned an empty response"
        assert total_time < END_TO_END_MAX_SEC, (
            f"End-to-end latency {total_time:.1f}s >= {END_TO_END_MAX_SEC}s"
        )