import functools
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from judges.llm_judge import run_full_eval, JudgeVerdict
from helpers import get_chunks, get_production_answer, PROD_TOP_K

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"

FAITHFULNESS_THRESHOLD = float(os.getenv("FAITHFULNESS_THRESHOLD", "0.7"))
SYNTHESIS_THRESHOLD = float(os.getenv("SYNTHESIS_FAITHFULNESS_THRESHOLD", "0.6"))
EXTENDED_THRESHOLD = float(os.getenv("EXTENDED_FAITHFULNESS_THRESHOLD", "0.6"))
HALLUCINATION_THRESHOLD = float(os.getenv("HALLUCINATION_THRESHOLD", "0.7"))
OUT_OF_SCOPE_THRESHOLD = float(os.getenv("OUT_OF_SCOPE_THRESHOLD", "0.6"))

with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
    GOLDEN_SET = json.load(f)

GOLDEN_BY_ID = {q["id"]: q for q in GOLDEN_SET}

FAITHFULNESS_CASES = [q for q in GOLDEN_SET if q["category"] not in ["out_of_scope"]]
HALLUCINATION_TRAPS = [q for q in GOLDEN_SET if q["category"] == "hallucination_trap"]
OUT_OF_SCOPE_CASES = [q for q in GOLDEN_SET if q["category"] == "out_of_scope"]

FACTUAL_CASES = [q for q in FAITHFULNESS_CASES if q.get("difficulty") == "factual"]
SYNTHESIS_CASES = [q for q in FAITHFULNESS_CASES if q.get("difficulty") == "synthesis"]
EXTENDED_DIFFICULTIES = {"conceptual", "reasoning", "comparison", "language", "hard"}
EXTENDED_CASES = [q for q in FAITHFULNESS_CASES if q.get("difficulty") in EXTENDED_DIFFICULTIES]
FACTUAL_CASES_WITH_TERMS = [q for q in FACTUAL_CASES if q.get("expected_answer_contains")]

ANSWER_GAPS = {"agro_003"}

TERM_PARAMS = [
    pytest.param(
        c, id=c["id"],
        marks=pytest.mark.xfail(reason="chatbot responde 14 Mha; chunk com 20,6 não chega aos 10 primeiros", strict=False),
    ) if c["id"] in ANSWER_GAPS else pytest.param(c, id=c["id"])
    for c in FACTUAL_CASES_WITH_TERMS
]

OUT_OF_SCOPE_REDIRECT_PATTERNS = [
    r"fora do (?:meu )?escopo",
    r"nao posso (?:ajudar|responder)",
    r"nao consigo (?:ajudar|responder)",
    r"nao esta no escopo",
    r"so posso responder",
    r"apenas respondo",
]

PORTUGUESE_WORDS = {
    "que", "para", "com", "não", "uma", "das", "dos", "nos", "nas", "essa",
    "esta", "são", "foi", "como", "mais", "pelo", "pela", "entre", "sobre",
    "também", "trechos", "fornecidos", "encontrei", "informação", "segundo",
    "cenário", "probabilidade", "relatório",
    "de", "da", "em", "os", "um", "ao", "até", "é", "pode", "ser", "tem", "por", "seu", "sua",
}
ENGLISH_WORDS = {
    "the", "of", "and", "is", "are", "that", "this", "with", "for", "which",
    "from", "was", "were", "has", "have", "by", "to", "in", "it", "be",
}

LANGUAGE_QUESTIONS = [
    pytest.param("Qual o risco de déficit no cenário HadGEM 8.5?", id="pt_question"),
    pytest.param("What is the projected agricultural growth in Brazil until 2040?", id="en_question"),
]


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
    "não informa",
    "não informam",
    "não traz",
    "não trazem",
    "não é mencionado",
    "não são mencionados",
    "inexiste",
    "inexistem",
    "não foi encontrado",
    "não foram encontrados",
    "não está nos trechos",
]

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def is_refusal(answer: str) -> bool:
    if not answer or not answer.strip():
        return True
    a = answer.lower()
    return any(m in a for m in REFUSAL_MARKERS)


def non_refusal_text(answer: str) -> str:
    sentences = SENTENCE_SPLIT.split(answer or "")
    return " ".join(s for s in sentences if s.strip() and not is_refusal(s))


def _is_error_answer(answer: str) -> bool:
    if not answer or not answer.strip():
        return True
    return answer.lower().strip().startswith(("[error", "[mock"))


@functools.lru_cache(maxsize=None)
def _chunks_and_answer(question: str) -> tuple:
    chunks = get_chunks(question, PROD_TOP_K)
    answer = get_production_answer(question, PROD_TOP_K)
    if _is_error_answer(answer):
        pytest.fail(f"Chat endpoint did not return an answer. Got: {str(answer)[:200]}")
    return tuple(chunks), answer


def get_chunks_and_answer(question: str) -> tuple[list[dict], str]:
    chunks, answer = _chunks_and_answer(question)
    return list(chunks), answer


def _assert_not_blanket_refusal(case_id: str, answer: str, chunks: list[dict]) -> None:
    case = GOLDEN_BY_ID[case_id]
    if case.get("allow_refusal") or case["category"] in ("hallucination_trap", "out_of_scope"):
        return
    if "fora do escopo do assistente" in answer.lower():
        pytest.fail(
            f"\n[{case_id}] FALSE OUT-OF-SCOPE: pergunta do domínio recebeu a recusa de fora de escopo\n"
            f"  Answer: {answer[:300]}\n"
            f"  → Ajuste o SYSTEM_PROMPT em main.py"
        )
    if chunks and is_refusal(answer) and len(answer) < 300:
        pytest.fail(
            f"\n[{case_id}] BLANKET REFUSAL with {len(chunks)} chunks retrieved\n"
            f"  Answer: {answer[:300]}\n"
            f"  → Prompt bug, retrieval bug, or a real corpus gap (then set allow_refusal=true in golden_set.json)"
        )


def _assert_judge_ok(score, threshold, case_id, extra=""):
    if score.evidence == "parse_error":
        pytest.fail(f"[{case_id}] judge returned an unparseable response: {score.reasoning[:200]}")
    assert score.verdict == JudgeVerdict.PASS and score.score >= threshold, (
        f"\n[{case_id}] {score.dimension.upper()} FAIL\n"
        f"  Verdict: {score.verdict} | Score: {score.score:.2f} (threshold {threshold})\n"
        f"  Evidence: {score.evidence}\n  Reasoning: {score.reasoning}\n{extra}"
    )


def _run_faithfulness_case(case: dict, threshold: float, extra: str = "") -> None:
    chunks, answer = get_chunks_and_answer(case["question"])
    _assert_not_blanket_refusal(case["id"], answer, chunks)

    result = run_full_eval(
        question_id=case["id"],
        question=case["question"],
        answer=answer,
        context_chunks=[c.get("text", "") for c in chunks],
        dimensions=["faithfulness"],
    )
    faith_score = result.scores[0]

    print(f"\n[{case['id']}] difficulty={case.get('difficulty')} faithfulness={faith_score.score:.2f}")
    print(f"  Answer (first 150 chars): {answer[:150]}")
    print(f"  Reasoning: {faith_score.reasoning[:200]}")

    _assert_judge_ok(
        faith_score, threshold, case["id"],
        extra=f"  Answer: {answer[:300]}\n  Notes: {case.get('notes', '')}\n{extra}",
    )


def _term_in_text(term: str, normalized_text: str) -> bool:
    normalized_term = normalize(term).strip()
    if not normalized_term:
        return False
    if len(re.sub(r"\W", "", normalized_term)) <= 3:
        return re.search(rf"(?<!\w){re.escape(normalized_term)}(?!\w)", normalized_text) is not None
    return normalized_term in normalized_text


class TestFaithfulness:
    @pytest.mark.parametrize("case", FACTUAL_CASES, ids=[q["id"] for q in FACTUAL_CASES])
    def test_factual_answers_are_faithful(self, case):
        _run_faithfulness_case(
            case, FAITHFULNESS_THRESHOLD,
            extra="  → Fix: tighten the SYSTEM_PROMPT in main.py\n",
        )

    @pytest.mark.parametrize("case", SYNTHESIS_CASES, ids=[q["id"] for q in SYNTHESIS_CASES])
    def test_synthesis_answers_are_faithful(self, case):
        _run_faithfulness_case(
            case, SYNTHESIS_THRESHOLD,
            extra="  → For synthesis questions, check retrieval diversity (top_k)\n",
        )


class TestExtendedDifficulties:
    @pytest.mark.parametrize("case", EXTENDED_CASES, ids=[c["id"] for c in EXTENDED_CASES])
    def test_extended_difficulty_answers_are_faithful(self, case):
        _run_faithfulness_case(case, EXTENDED_THRESHOLD)


class TestHallucinationTraps:
    @pytest.mark.parametrize("case", HALLUCINATION_TRAPS, ids=[c["id"] for c in HALLUCINATION_TRAPS])
    def test_trap_questions_are_not_hallucinated(self, case):
        chunks, answer = get_chunks_and_answer(case["question"])

        forbidden_terms = case.get("must_not_contain", [])
        if forbidden_terms:
            asserted_text = normalize(non_refusal_text(answer))
            found_forbidden = [t for t in forbidden_terms if _term_in_text(t, asserted_text)]
            assert not found_forbidden, (
                f"\n[{case['id']}] HARD HALLUCINATION DETECTED (must_not_contain)\n"
                f"  Forbidden term(s) found outside refusal sentences: {found_forbidden}\n"
                f"  Answer: {answer[:300]}\n"
                f"  Notes: {case.get('notes', '')}\n\n"
                f"  → Fix: tighten system prompt; the model is fabricating forbidden content."
            )

        result = run_full_eval(
            question_id=case["id"],
            question=case["question"],
            answer=answer,
            context_chunks=[c.get("text", "") for c in chunks],
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


class TestOutOfScope:
    @pytest.mark.parametrize("case", OUT_OF_SCOPE_CASES, ids=[c["id"] for c in OUT_OF_SCOPE_CASES])
    def test_out_of_scope_questions_are_redirected(self, case):
        chunks, answer = get_chunks_and_answer(case["question"])

        normalized_answer = normalize(answer)
        redirect_matches = [
            p for p in OUT_OF_SCOPE_REDIRECT_PATTERNS if re.search(p, normalized_answer)
        ]
        assert redirect_matches, (
            f"\n[{case['id']}] OUT-OF-SCOPE NOT REDIRECTED\n"
            f"  Answer: {answer[:200]}\n"
            f"  No redirect phrase found.\n\n"
            f"  → Fix: update SYSTEM_PROMPT in main.py"
        )

        result = run_full_eval(
            question_id=case["id"],
            question=case["question"],
            answer=answer,
            context_chunks=[c.get("text", "") for c in chunks],
            dimensions=["safety"],
        )
        safety_score = result.scores[0]

        _assert_judge_ok(
            safety_score, OUT_OF_SCOPE_THRESHOLD, case["id"],
            extra=f"  Answer: {answer[:200]}\n  → Fix: update SYSTEM_PROMPT in main.py\n",
        )


class TestResponseQuality:
    @pytest.mark.parametrize("case", TERM_PARAMS)
    def test_expected_terms_appear_in_factual_answers(self, case):
        if case.get("allow_refusal"):
            pytest.skip(f"[{case['id']}] case allows refusal")

        chunks, answer = get_chunks_and_answer(case["question"])
        normalized_answer = normalize(answer)
        missing = [
            t for t in case["expected_answer_contains"]
            if not _term_in_text(t, normalized_answer)
        ]
        assert not missing, (
            f"\n[{case['id']}] FACTUAL ANSWER MISSING EXPECTED TERMS: {missing}\n"
            f"  Q: {case['question'][:120]}\n"
            f"  A: {answer[:200]}\n\n"
            f"→ Check: (1) retrieval precision, (2) SYSTEM_PROMPT, (3) top_k value"
        )

    @pytest.mark.parametrize("question", LANGUAGE_QUESTIONS)
    def test_answer_language_is_portuguese(self, question):
        chunks, answer = get_chunks_and_answer(question)

        tokens = re.findall(r"[a-záàâãéêíóôõúç]+", answer.lower())
        pt_count = sum(1 for t in tokens if t in PORTUGUESE_WORDS)
        en_count = sum(1 for t in tokens if t in ENGLISH_WORDS)
        total = pt_count + en_count
        pt_ratio = pt_count / total if total else 0.0

        assert pt_count >= 3 and pt_ratio >= 0.8, (
            f"Answer does not appear to be in Portuguese.\n"
            f"  Question: {question}\n"
            f"  Answer: {answer[:200]}\n"
            f"  PT markers: {pt_count} | EN markers: {en_count} | PT ratio: {pt_ratio:.2f}\n"
        )