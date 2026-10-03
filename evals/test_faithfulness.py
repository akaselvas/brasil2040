"""
test_faithfulness.py
====================
Tests whether the AI's answers are grounded in the retrieved context.

As respostas vêm do /chat REAL (mesmo SYSTEM_PROMPT, temperatura e top_k de
produção). Mudar o SYSTEM_PROMPT no main.py afeta estes testes.
"""

import json
import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from judges.llm_judge import run_full_eval, JudgeVerdict
from helpers import get_chunks, get_production_answer, PROD_TOP_K

# ── CONFIG ────────────────────────────────────────────────────────────────────
GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"

FAITHFULNESS_THRESHOLD  = float(os.getenv("FAITHFULNESS_THRESHOLD",  "0.7"))
HALLUCINATION_THRESHOLD = float(os.getenv("HALLUCINATION_THRESHOLD", "0.7"))

with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
    GOLDEN_SET = json.load(f)

GOLDEN_BY_ID = {q["id"]: q for q in GOLDEN_SET}

# ── Slice the golden set by role ───────────────────────────────────────────────
FAITHFULNESS_CASES  = [q for q in GOLDEN_SET if q["category"] not in ["out_of_scope"]]
HALLUCINATION_TRAPS = [q for q in GOLDEN_SET if q["category"] == "hallucination_trap"]
OUT_OF_SCOPE_CASES  = [q for q in GOLDEN_SET if q["category"] == "out_of_scope"]

# Difficulties that the original parametrize filters missed entirely
TESTED_DIFFICULTIES  = {"factual", "synthesis"}
EXTENDED_DIFFICULTIES = {"conceptual", "reasoning", "comparison", "language", "hard"}
EXTENDED_CASES = [
    q for q in FAITHFULNESS_CASES
    if q.get("difficulty") in EXTENDED_DIFFICULTIES
]

# ── Refusal detection ─────────────────────────────────────────────────────────
REFUSAL_MARKERS = [
    "não encontrei",
    "não encontramos",
    "não contém",
    "não contêm",
    "não consta",
    "não constam",
    "não menciona",
    "não mencionam",
    "não refere",
    "não referem",
    "não cita",
    "não citam",
    "não há",
    "inexiste",
    "inexistem",
    "não foi encontrado",
    "não foram encontrados",
    "informação não",
    "desculpe",
    "não está nos trechos",
]

def _is_refusal(answer: str) -> bool:
    if not answer:
        return True
    a = answer.lower()
    return any(m in a for m in REFUSAL_MARKERS)


def _is_error_answer(answer: str) -> bool:
    """Return True when the answer string is an error/mock placeholder."""
    if not answer:
        return True
    error_prefixes = ("[error", "[mock", "[mock -")
    return answer.lower().strip().startswith(error_prefixes)


# ── Robust out-of-scope hedge check ───────────────────────────────────────────
SPECIFIC_HEDGE_PHRASES = [
    "fora do escopo",
    "fora do meu escopo",
    "brasil 2040",
    "não posso ajudar com",
    "não consigo ajudar com",
    "não está no escopo",
    "não aborda",
    "não trata",
    "não cobre",
    "posso ajudar com",
    "só posso responder",
    "apenas respondo",
    "assistente do brasil 2040",
]

def _count_hedge_matches(answer: str) -> int:
    if not answer:
        return 0
    a = answer.lower()
    return sum(1 for phrase in SPECIFIC_HEDGE_PHRASES if phrase in a)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_chunks_and_answer(question: str, top_k: int = PROD_TOP_K) -> tuple[list[dict], str]:
    """Usa o /chat REAL. O top_k é sempre o de produção, ignorando overrides dos testes."""
    chunks = get_chunks(question, PROD_TOP_K)
    answer = get_production_answer(question, PROD_TOP_K)
    return chunks, answer


def _assert_not_blanket_refusal(case_id: str, answer: str, chunks: list[dict]) -> None:
    """Recusa seca com chunks recuperados = bug (prompt/retrieval) ou lacuna real do corpus."""
    case = GOLDEN_BY_ID[case_id]
    if case.get("allow_refusal") or case["category"] in ("hallucination_trap", "out_of_scope"):
        return
    if "fora do escopo do assistente" in answer.lower():
        pytest.fail(
            f"\n[{case_id}] FALSE OUT-OF-SCOPE: pergunta do domínio recebeu a recusa de fora de escopo\n"
            f"  Answer: {answer[:300]}\n"
            f"  → Ajuste o SYSTEM_PROMPT em main.py"
        )
    if chunks and _is_refusal(answer) and len(answer) < 300:
        pytest.fail(
            f"\n[{case_id}] BLANKET REFUSAL with {len(chunks)} chunks retrieved\n"
            f"  Answer: {answer[:300]}\n"
            f"  → Prompt bug, retrieval bug, or a real corpus gap (then set allow_refusal=true in golden_set.json)"
        )


def _assert_judge_ok(score, threshold, case_id, extra=""):
    """Veredito do juiz E score precisam passar. Erros de infraestrutura do juiz viram skip."""
    if score.evidence in ("empty_response", "parse_error"):
        pytest.skip(f"[{case_id}] judge infrastructure error: {score.reasoning[:150]}")
    assert score.verdict != JudgeVerdict.FAIL and score.score >= threshold, (
        f"\n[{case_id}] {score.dimension.upper()} FAIL\n"
        f"  Verdict: {score.verdict} | Score: {score.score:.2f} (threshold {threshold})\n"
        f"  Evidence: {score.evidence}\n  Reasoning: {score.reasoning}\n{extra}"
    )


# ── TESTS ─────────────────────────────────────────────────────────────────────

class TestFaithfulness:
    """Core faithfulness: is every answer grounded in retrieved chunks?"""

    @pytest.mark.parametrize(
        "case",
        [q for q in FAITHFULNESS_CASES if q["difficulty"] == "factual"],
        ids=[q["id"] for q in FAITHFULNESS_CASES if q["difficulty"] == "factual"],
    )
    def test_factual_answers_are_faithful(self, case):
        chunks, answer = get_chunks_and_answer(case["question"])

        if _is_error_answer(answer):
            pytest.skip(f"[{case['id']}] Gemini call failed — check GEMINI_API_KEY. Got: {str(answer)[:120]}")

        _assert_not_blanket_refusal(case["id"], answer, chunks)

        chunk_texts = [c.get("text", "") for c in chunks]
        result = run_full_eval(
            question_id=case["id"],
            question=case["question"],
            answer=answer,
            context_chunks=chunk_texts,
            dimensions=["faithfulness"],
        )
        faith_score = result.scores[0]

        print(f"\n[{case['id']}] Faithfulness: {faith_score.score:.2f}")
        print(f"  Answer (first 150 chars): {answer[:150]}")
        print(f"  Reasoning: {faith_score.reasoning[:200]}")

        _assert_judge_ok(
            faith_score, FAITHFULNESS_THRESHOLD, case["id"],
            extra=f"  Answer: {answer[:300]}\n  → Fix: tighten the SYSTEM_PROMPT in main.py\n",
        )

    @pytest.mark.parametrize(
        "case",
        [q for q in FAITHFULNESS_CASES if q["difficulty"] == "synthesis"],
        ids=[q["id"] for q in FAITHFULNESS_CASES if q["difficulty"] == "synthesis"],
    )
    def test_synthesis_answers_are_faithful(self, case):
        chunks, answer = get_chunks_and_answer(case["question"])

        if _is_error_answer(answer):
            pytest.skip(f"[{case['id']}] Gemini call failed — check GEMINI_API_KEY. Got: {str(answer)[:120]}")

        _assert_not_blanket_refusal(case["id"], answer, chunks)

        chunk_texts = [c.get("text", "") for c in chunks]
        result = run_full_eval(
            question_id=case["id"],
            question=case["question"],
            answer=answer,
            context_chunks=chunk_texts,
            dimensions=["faithfulness", "relevance"],
        )
        faith_score = next(s for s in result.scores if s.dimension == "faithfulness")
        synthesis_threshold = FAITHFULNESS_THRESHOLD - 0.1

        _assert_judge_ok(
            faith_score, synthesis_threshold, case["id"],
            extra="  → For synthesis questions, check retrieval diversity (top_k)\n",
        )


# ── Extended difficulties ─────────────────────────────────────────────

class TestExtendedDifficulties:
    """
    Covers the golden-set cases that the original parametrize filters missed.
    """

    EXTENDED_THRESHOLD = FAITHFULNESS_THRESHOLD - 0.1

    @pytest.mark.parametrize(
        "case",
        EXTENDED_CASES,
        ids=[c["id"] for c in EXTENDED_CASES],
    )
    def test_extended_difficulty_answers_are_faithful(self, case):
        chunks, answer = get_chunks_and_answer(case["question"])

        if _is_error_answer(answer):
            pytest.skip(
                f"[{case['id']}] Gemini call failed — check GEMINI_API_KEY. Got: {str(answer)[:120]}"
            )

        _assert_not_blanket_refusal(case["id"], answer, chunks)

        chunk_texts = [c.get("text", "") for c in chunks]
        result = run_full_eval(
            question_id=case["id"],
            question=case["question"],
            answer=answer,
            context_chunks=chunk_texts,
            dimensions=["faithfulness", "relevance"],
        )
        faith_score = next(s for s in result.scores if s.dimension == "faithfulness")

        print(f"\n[{case['id']}] difficulty={case['difficulty']} faithfulness={faith_score.score:.2f}")
        print(f"  Answer: {answer[:150]}")

        _assert_judge_ok(
            faith_score, self.EXTENDED_THRESHOLD, case["id"],
            extra=f"  difficulty: {case['difficulty']}\n  Notes: {case.get('notes', '')}\n",
        )


# ── Hallucination traps ────────────────────────────────────────────────────────

class TestHallucinationTraps:
    """Questions designed to elicit hallucination — model must hedge, not invent."""

    @pytest.mark.parametrize(
        "case",
        HALLUCINATION_TRAPS,
        ids=[c["id"] for c in HALLUCINATION_TRAPS],
    )
    def test_trap_questions_are_not_hallucinated(self, case):
        chunks, answer = get_chunks_and_answer(case["question"])

        if _is_error_answer(answer):
            pytest.skip(f"[{case['id']}] Gemini call failed. Got: {str(answer)[:120]}")

        # Só executa must_not_contain se a resposta não for uma recusa de contexto legítima
        forbidden_terms = case.get("must_not_contain", [])
        if forbidden_terms and not _is_refusal(answer):
            answer_lower = answer.lower()
            found_forbidden = [t for t in forbidden_terms if t.lower() in answer_lower]
            assert not found_forbidden, (
                f"\n[{case['id']}] HARD HALLUCINATION DETECTED (must_not_contain)\n"
                f"  Forbidden term(s) found in answer: {found_forbidden}\n"
                f"  Answer: {answer[:300]}\n"
                f"  Notes: {case.get('notes', '')}\n\n"
                f"  → Fix: tighten system prompt; the model is fabricating forbidden content."
            )

        chunk_texts = [c.get("text", "") for c in chunks]
        result = run_full_eval(
            question_id=case["id"],
            question=case["question"],
            answer=answer,
            context_chunks=chunk_texts,
            is_trap=True,
            dimensions=["hallucination"],
        )
        hall_score = result.scores[0]

        print(f"\n[{case['id']}] Hallucination verdict: {hall_score.verdict}")
        print(f"  Answer: {answer[:200]}")
        print(f"  Reasoning: {hall_score.reasoning[:200]}")

        _assert_judge_ok(
            hall_score, HALLUCINATION_THRESHOLD, case["id"],
            extra=f"  Notes: {case.get('notes', '')}\n  → Fix: tighten the SYSTEM_PROMPT in main.py\n",
        )


# ── Out-of-scope ───────────────────────────────────────────────────────────────

class TestOutOfScope:
    """Out-of-scope questions must be redirected, not fabricated."""

    @pytest.mark.parametrize(
        "case",
        OUT_OF_SCOPE_CASES,
        ids=[c["id"] for c in OUT_OF_SCOPE_CASES],
    )
    def test_out_of_scope_questions_are_redirected(self, case):
        chunks, answer = get_chunks_and_answer(case["question"])

        if _is_error_answer(answer):
            pytest.skip(f"[{case['id']}] Gemini call failed. Got: {str(answer)[:120]}")

        chunk_texts = [c.get("text", "") for c in chunks]
        result = run_full_eval(
            question_id=case["id"],
            question=case["question"],
            answer=answer,
            context_chunks=chunk_texts,
            dimensions=["safety", "hallucination"],
        )
        safety_score = next(s for s in result.scores if s.dimension == "safety")

        hedge_count = _count_hedge_matches(answer)
        has_specific_hedge = hedge_count >= 2

        assert safety_score.passed() or safety_score.score >= 0.6 or has_specific_hedge, (
            f"\n[{case['id']}] OUT-OF-SCOPE HANDLING FAIL\n"
            f"  Answer: {answer[:200]}\n"
            f"  Safety score: {safety_score.score:.2f}\n"
            f"  Specific hedge phrases matched: {hedge_count} (need ≥ 2)\n\n"
            f"  → Fix: update SYSTEM_PROMPT in main.py"
        )


# ── Response quality ───────────────────────────────────────────────────────────

class TestResponseQuality:
    """Broader quality checks — cheap heuristics run before the LLM judge."""

    def test_expected_numbers_appear_in_factual_answers(self):
        """
        Key terms from golden_set expected_answer_contains must appear in answers.
        """
        factual_cases = [q for q in GOLDEN_SET if q["difficulty"] == "factual"]
        failures = []
        skipped = []

        for case in factual_cases[:5]:
            if not case.get("expected_answer_contains"):
                continue

            chunks, answer = get_chunks_and_answer(case["question"])

            if _is_error_answer(answer):
                skipped.append(case["id"])
                continue

            if _is_refusal(answer):
                continue

            answer_lower = answer.lower()
            missing = [
                t for t in case["expected_answer_contains"]
                if t.lower() not in answer_lower
            ]

            if len(missing) > len(case["expected_answer_contains"]) * 0.6:
                failures.append({
                    "id": case["id"],
                    "question": case["question"][:80],
                    "missing_terms": missing,
                    "answer_preview": answer[:150],
                })

        if skipped:
            print(f"\n  Skipped {len(skipped)} cases due to Gemini errors: {skipped}")

        if failures:
            msg = "\n".join(
                f"  [{f['id']}] Missing: {f['missing_terms']}\n"
                f"    Q: {f['question']}\n"
                f"    A: {f['answer_preview']}"
                for f in failures
            )
            pytest.fail(
                f"\nFACTUAL ANSWERS MISSING EXPECTED TERMS ({len(failures)} cases):\n{msg}\n\n"
                f"→ Check: (1) retrieval precision, (2) SYSTEM_PROMPT, (3) top_k value"
            )

    def test_answer_language_is_portuguese(self):
        """All answers should be in Portuguese (pt-BR)."""
        portuguese_markers = [
            "que", "com", "para", "não", "uma", "os", "das", "do", "no",
            "nos", "essa", "esta", "em", "de", "da", "se", "por", "um",
            "encontrei", "informação", "trechos", "fornecidos", "a", "o",
            "e", "é", "cenário", "probabilidade", "chega", "ficar", "acima"
        ]
        test_question = "Qual o risco de déficit no cenário HadGEM 8.5?"

        chunks, answer = get_chunks_and_answer(test_question)

        if _is_error_answer(answer):
            pytest.skip("Gemini error — cannot check language.")

        found_markers = [w for w in portuguese_markers if w in answer.lower().split()]

        assert len(found_markers) >= 3, (
            f"Answer does not appear to be in Portuguese.\n"
            f"  Answer: {answer[:200]}\n"
            f"  Found PT markers: {found_markers}\n"
        )