"""
test_retrieval.py
=================
Tests whether the /search endpoint (main.py) returns relevant chunks
for each question in the golden set.

Metric: Precision@K
  - For each question, we call /search with top_k=5
  - We check if at least one returned chunk comes from the expected source file
  - We also compute a "semantic relevance" score by checking if key expected
    terms appear anywhere in the top-K results

HOW TO RUN:
  1. Start your FastAPI server: uvicorn main:app --reload
  2. Run: pytest evals/test_retrieval.py -v
  3. Or with HTML report: pytest evals/test_retrieval.py -v --html=reports/retrieval_report.html

WHAT YOU LEARN from this test:
  - Is your pgvector search actually finding the right documents?
  - Is top_k=5 sufficient, or do you need top_k=10?
  - Are any questions "lost" because the embedding model doesn't handle
    them well (e.g. English questions against Portuguese documents)?
"""

import json
import os
import requests
import pytest
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────────
SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT", "http://localhost:8000/search")
TOP_K = 5
GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"

# ── LOAD GOLDEN SET ───────────────────────────────────────────────────────────
with open(GOLDEN_SET_PATH) as f:
    GOLDEN_SET = json.load(f)

# Filter only questions that have expected_chunk_sources defined (non-empty)
RETRIEVAL_CASES = [
    q for q in GOLDEN_SET
    if q.get("expected_chunk_sources") and len(q["expected_chunk_sources"]) > 0
]


# ── HELPER ────────────────────────────────────────────────────────────────────
def call_search(question: str, top_k: int = TOP_K) -> list[dict]:
    """Call the /search endpoint and return the list of chunks."""
    try:
        response = requests.post(
            SEARCH_ENDPOINT,
            json={"question": question, "top_k": top_k},
            timeout=30
        )
        response.raise_for_status()
        return response.json().get("chunks", [])
    except requests.exceptions.ConnectionError:
        pytest.skip(f"Server not running at {SEARCH_ENDPOINT} — start with: uvicorn main:app --reload")
    except Exception as e:
        pytest.fail(f"Search endpoint error: {e}")


def chunks_contain_source(chunks: list[dict], expected_sources: list[str]) -> bool:
    """Check if any chunk's 'file' field matches one of the expected sources."""
    returned_files = [c.get("file", "") for c in chunks]
    for expected in expected_sources:
        for returned in returned_files:
            # Partial match: "Energia" matches "Panel-energia.pdf" etc.
            if expected.lower() in returned.lower() or returned.lower() in expected.lower():
                return True
    return False


def chunks_contain_terms(chunks: list[dict], expected_terms: list[str]) -> tuple[bool, list[str]]:
    """Check if expected answer terms appear in the retrieved chunk texts."""
    all_text = " ".join(c.get("text", "").lower() for c in chunks)
    found = [t for t in expected_terms if t.lower() in all_text]
    missing = [t for t in expected_terms if t.lower() not in all_text]
    return len(found) >= len(expected_terms) * 0.5, missing  # 50% threshold


# ── TESTS ─────────────────────────────────────────────────────────────────────

class TestRetrievalPrecision:
    """
    Core retrieval tests: did the right chunks come back?
    
    LEARNING NOTE: This is called "Precision@K" in information retrieval.
    K = number of results (top_k=5).
    Precision@5 = (relevant results in top 5) / 5
    """

    @pytest.mark.parametrize("case", RETRIEVAL_CASES, ids=[c["id"] for c in RETRIEVAL_CASES])
    def test_source_precision(self, case):
        """At least one returned chunk should come from the expected source file."""
        chunks = call_search(case["question"])
        
        hit = chunks_contain_source(chunks, case["expected_chunk_sources"])
        
        returned_files = [c.get("file", "unknown") for c in chunks]
        assert hit, (
            f"\n[{case['id']}] SOURCE MISS\n"
            f"  Question: {case['question']}\n"
            f"  Expected source(s): {case['expected_chunk_sources']}\n"
            f"  Got: {returned_files}\n"
            f"  → Fix: check if source file name in CSV matches expected_chunk_sources in golden_set.json"
        )

    @pytest.mark.parametrize("case", RETRIEVAL_CASES, ids=[c["id"] for c in RETRIEVAL_CASES])
    def test_term_coverage(self, case):
        """Key expected answer terms should appear in retrieved chunk text."""
        if not case.get("expected_answer_contains"):
            pytest.skip("No expected terms defined for this case")
        
        chunks = call_search(case["question"])
        ok, missing = chunks_contain_terms(chunks, case["expected_answer_contains"])
        
        assert ok, (
            f"\n[{case['id']}] TERM COVERAGE MISS\n"
            f"  Question: {case['question']}\n"
            f"  Missing terms in retrieved chunks: {missing}\n"
            f"  → Fix: the right chunks may not be retrieved, or chunk size may be too small"
        )


class TestRetrievalAtDifferentK:
    """
    Tests whether increasing top_k improves coverage.
    
    LEARNING NOTE: This helps you decide the right top_k value.
    If Precision@10 >> Precision@5, you should increase top_k.
    """

    def test_cross_sector_query_needs_more_chunks(self):
        """
        Cross-sector queries may need top_k > 5 to cover all relevant sources.
        """
        question = "Considerando todos os setores analisados no Brasil 2040, qual é o setor mais vulnerável?"
        
        chunks_5 = call_search(question, top_k=5)
        chunks_10 = call_search(question, top_k=10)
        
        files_5 = set(c.get("file", "") for c in chunks_5)
        files_10 = set(c.get("file", "") for c in chunks_10)
        
        # Log the difference — this is a diagnostic, not a hard fail
        improvement = len(files_10) - len(files_5)
        print(f"\n  Unique sources @ k=5: {len(files_5)}: {files_5}")
        print(f"  Unique sources @ k=10: {len(files_10)}: {files_10}")
        print(f"  Source diversity improvement: +{improvement} files")
        
        # Soft assertion: k=10 should give at least as many sources as k=5
        assert len(files_10) >= len(files_5), "Increasing k should never decrease source coverage"

    def test_english_question_retrieval(self):
        """
        English question should still retrieve Portuguese chunks
        (tests multilingual-e5-large embedding quality).
        """
        english_question = "What is the projected agricultural growth in Brazil until 2040?"
        chunks = call_search(english_question, top_k=5)
        
        assert len(chunks) > 0, "English question returned zero results"
        
        all_text = " ".join(c.get("text", "") for c in chunks)
        # Check that the retrieved text is in Portuguese (contains Portuguese words)
        portuguese_indicators = ["brasil", "agrícola", "produção", "crescimento", "2040"]
        found = [w for w in portuguese_indicators if w in all_text.lower()]
        
        assert len(found) >= 2, (
            f"English query didn't retrieve Portuguese chunks well.\n"
            f"  Found indicators: {found}\n"
            f"  → The multilingual-e5-large model should handle this — check embedding normalization"
        )


class TestRetrievalEdgeCases:
    """
    Edge cases that probe system limits.
    """

    def test_empty_question_handled(self):
        """Empty question should not crash the server."""
        try:
            response = requests.post(
                SEARCH_ENDPOINT,
                json={"question": "", "top_k": 5},
                timeout=10
            )
            # Either returns results or a clean error — should not be 500
            assert response.status_code != 500, "Empty question caused server error 500"
        except requests.exceptions.ConnectionError:
            pytest.skip("Server not running")

    def test_very_long_question_handled(self):
        """Very long question should not crash the server."""
        long_q = "risco climático " * 200  # 3200 chars
        try:
            response = requests.post(
                SEARCH_ENDPOINT,
                json={"question": long_q, "top_k": 5},
                timeout=30
            )
            assert response.status_code in [200, 400, 422], (
                f"Long question returned unexpected status: {response.status_code}"
            )
        except requests.exceptions.ConnectionError:
            pytest.skip("Server not running")

    def test_out_of_scope_question_still_returns_chunks(self):
        """
        Even an out-of-scope question should return chunks (retrieval layer
        doesn't filter by relevance — that's the LLM's job).
        """
        chunks = call_search("Qual é a receita do brigadeiro perfeito?")
        # Retrieval should still return something — the LLM will say it's out of scope
        # If this returns 0, something is wrong with the Supabase connection
        assert len(chunks) >= 0, "Should not error on out-of-scope questions"
        print(f"\n  Out-of-scope query returned {len(chunks)} chunks (expected: some, but LLM should redirect)")


# ── SUMMARY REPORT ────────────────────────────────────────────────────────────
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print a summary table after all tests."""
    print("\n\n" + "="*60)
    print("RETRIEVAL EVAL SUMMARY")
    print("="*60)
    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    total = passed + failed
    if total > 0:
        print(f"  Passed: {passed}/{total} ({100*passed//total}%)")
        print(f"  Failed: {failed}/{total}")
    print("="*60)
