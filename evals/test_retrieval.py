import functools
import json
import re
import sys
import unicodedata
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers import PROD_TOP_K, SEARCH_ENDPOINT, get_chunks

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"
WEAK_TERM_MAX_LEN = 3
TERM_COVERAGE_THRESHOLD = 0.5

with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
    GOLDEN_SET = json.load(f)

RETRIEVAL_CASES = [q for q in GOLDEN_SET if q.get("expected_chunk_sources")]


@functools.lru_cache(maxsize=None)
def _cached_search(question: str, top_k: int) -> tuple:
    return tuple(get_chunks(question, top_k))


def search(question: str, top_k: int = PROD_TOP_K) -> list[dict]:
    return list(_cached_search(question, top_k))


def normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_filename(name: str) -> str:
    return Path(name.strip()).name.lower()


def returned_sources(chunks: list[dict]) -> set[str]:
    names = {normalize_filename(c.get("file") or "") for c in chunks}
    names.discard("")
    return names


def chunks_contain_source(chunks: list[dict], expected_sources: list[str]) -> bool:
    returned = returned_sources(chunks)
    for expected in expected_sources:
        expected_name = normalize_filename(expected)
        if not expected_name:
            continue
        for name in returned:
            if expected_name == name or expected_name in name:
                return True
    return False

SECTOR_PREFIXES = ("agricultura", "energia", "recursosh", "transportes", "infra cost")


def sector_of(filename: str) -> str:
    name = filename.lower()
    for prefix in SECTOR_PREFIXES:
        if name.startswith(prefix):
            return prefix
    return "outro"

def is_weak_term(term: str) -> bool:
    return len(re.sub(r"\W", "", term)) <= WEAK_TERM_MAX_LEN


def term_in_text(term: str, normalized_text: str) -> bool:
    normalized_term = normalize_text(term).strip()
    if not normalized_term:
        return False
    if is_weak_term(term):
        left = r"(?<!\w)" if re.match(r"\w", normalized_term) else ""
        right = r"(?!\w)" if re.search(r"\w$", normalized_term) else ""
        return re.search(left + re.escape(normalized_term) + right, normalized_text) is not None
    return normalized_term in normalized_text


def chunks_contain_terms(chunks: list[dict], expected_terms: list[str]) -> tuple[bool, list[str]]:
    all_text = normalize_text(" ".join(c.get("text", "") for c in chunks))

    numeric = [t for t in expected_terms if re.search(r"\d", t)]
    words = [t for t in expected_terms if t not in numeric]

    missing_numeric = [t for t in numeric if not term_in_text(t, all_text)]
    found_words = [t for t in words if term_in_text(t, all_text)]
    missing_words = [t for t in words if t not in found_words]

    words_ok = not words or len(found_words) >= len(words) * TERM_COVERAGE_THRESHOLD
    return (not missing_numeric) and words_ok, missing_numeric + missing_words


FACTUAL_CASES = [c for c in RETRIEVAL_CASES if c.get("difficulty") == "factual"]

RETRIEVAL_GAPS = set()

TERM_COVERAGE_PARAMS = [
    pytest.param(
        c, id=c["id"],
        marks=pytest.mark.xfail(reason="chunk relevante fica entre os rankings 11 e 20", strict=False),
    ) if c["id"] in RETRIEVAL_GAPS else pytest.param(c, id=c["id"])
    for c in RETRIEVAL_CASES
]


class TestRetrievalHitRate:
    @pytest.mark.parametrize("case", FACTUAL_CASES, ids=[c["id"] for c in FACTUAL_CASES])
    def test_factual_source_hit_rate_at_5(self, case):
        chunks = search(case["question"], top_k=5)
        assert chunks_contain_source(chunks, case["expected_chunk_sources"]), (
            f"\n[{case['id']}] SOURCE MISS (Hit Rate@5)\n"
            f"  Expected source(s): {case['expected_chunk_sources']}\n"
            f"  Got: {sorted(returned_sources(chunks))}"
        )

    @pytest.mark.parametrize("case", TERM_COVERAGE_PARAMS)
    def test_term_coverage(self, case):
        if not case.get("expected_answer_contains"):
            pytest.skip("No expected terms defined for this case")

        chunks = search(case["question"])
        ok, missing = chunks_contain_terms(chunks, case["expected_answer_contains"])
        assert ok, (
            f"\n[{case['id']}] TERM COVERAGE MISS\n"
            f"  Question: {case['question']}\n"
            f"  Missing terms in retrieved chunks: {missing}\n"
            f"  → Fix: the right chunks may not be retrieved, or chunk size may be too small"
        )


class TestRetrievalAtDifferentK:
    def test_cross_sector_query_covers_multiple_sources(self):
        question = "Considerando todos os setores analisados no Brasil 2040, qual é o setor mais vulnerável?"

        files_5 = returned_sources(search(question, top_k=5))
        files_10 = returned_sources(search(question, top_k=10))

        assert files_5 <= files_10, (
            f"Results at k=5 are not contained in results at k=10 (non-deterministic search?)\n"
            f"  k=5: {sorted(files_5)}\n"
            f"  k=10: {sorted(files_10)}"
        )
        sectors_10 = {sector_of(f) for f in files_10}
        assert len(sectors_10) >= 2, (
            f"Cross-sector question should retrieve at least 2 distinct sectors at k=10, "
            f"got {sorted(sectors_10)} from {sorted(files_10)}"
        )

    def test_english_question_matches_portuguese_retrieval(self):
        english_question = "What is the projected agricultural growth in Brazil until 2040?"
        portuguese_question = "Qual é o crescimento agrícola projetado no Brasil até 2040?"

        english_files = returned_sources(search(english_question))
        portuguese_files = returned_sources(search(portuguese_question))

        assert english_files, "English question returned zero results"
        assert portuguese_files, "Portuguese question returned zero results"

        overlap = english_files & portuguese_files
        overlap_ratio = len(overlap) / len(portuguese_files)
        assert overlap_ratio >= 0.5, (
            f"English query retrieved different sources than the equivalent Portuguese query.\n"
            f"  English: {sorted(english_files)}\n"
            f"  Portuguese: {sorted(portuguese_files)}\n"
            f"  Overlap ratio: {overlap_ratio:.2f}\n"
            f"  → The multilingual-e5-large model should handle this — check embedding normalization"
        )


class TestRetrievalEdgeCases:
    def test_empty_question_handled(self):
        try:
            response = requests.post(
                SEARCH_ENDPOINT,
                json={"question": "", "top_k": PROD_TOP_K},
                timeout=10,
            )
        except requests.exceptions.ConnectionError:
            pytest.fail(f"Server not reachable at {SEARCH_ENDPOINT}. Must not be skipped in CI.")
        assert response.status_code != 500, "Empty question caused server error 500"

    def test_very_long_question_handled(self):
        long_question = "risco climático " * 200
        try:
            response = requests.post(
                SEARCH_ENDPOINT,
                json={"question": long_question, "top_k": PROD_TOP_K},
                timeout=30,
            )
        except requests.exceptions.ConnectionError:
            pytest.fail(f"Server not reachable at {SEARCH_ENDPOINT}. Must not be skipped in CI.")
        assert response.status_code in [200, 400, 422], (
            f"Long question returned unexpected status: {response.status_code}"
        )

    def test_out_of_scope_question_still_returns_chunks(self):
        chunks = search("Qual é a receita do brigadeiro perfeito?")
        assert len(chunks) > 0, (
            "Out-of-scope question should still return some chunks (retrieval doesn't filter by relevance)"
        )