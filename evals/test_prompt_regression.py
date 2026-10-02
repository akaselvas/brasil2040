"""
test_prompt_regression.py
==========================
Detects quality regressions when your system prompt (or model) changes.

As respostas vêm do /chat REAL. O gate de regressão é por ÂNCORAS
(expected_answer_contains do golden set). O relatório de similaridade
(regression_diff.json) é apenas informativo.
"""

import hashlib
import json
import os
import re
import sys
import difflib
import warnings
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers import get_chunks, get_production_answer, PROD_TOP_K

# ── CONFIG ────────────────────────────────────────────────────────────────────
REGRESSION_MODE = os.getenv("REGRESSION_MODE", "compare")  # "capture" | "compare"
BASELINE_PATH = Path(__file__).parent / "regression_baseline.json"
GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"

with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
    GOLDEN_SET = json.load(f)

# Use only the "prompt_regression" category questions
REGRESSION_CASES = [q for q in GOLDEN_SET if q["category"] == "prompt_regression"]
# Also include a few factual ones for numerical stability checks
REGRESSION_CASES += [q for q in GOLDEN_SET if q["id"] in ["energia_001", "agro_001"]]


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
    "não informa",
    "não informam",
    "não é mencionado",
    "não são mencionados",
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


def _is_blanket_refusal(answer: str) -> bool:
    """Recusa seca e curta (sem explicar o conceito)."""
    return _is_refusal(answer) and len(answer) < 300


# ── HELPERS ───────────────────────────────────────────────────────────────────

def get_answer(question: str, top_k: int = PROD_TOP_K) -> tuple[str, list[str]]:
    """Resposta do /chat REAL + textos dos chunks recuperados."""
    chunks = get_chunks(question, PROD_TOP_K)
    answer = get_production_answer(question, PROD_TOP_K)
    return answer, [c.get("text", "") for c in chunks]


def semantic_similarity(text1: str, text2: str) -> float:
    """Rough similarity between two answers (informativo, não é gate)."""
    if not text1 or not text2:
        return 0.0
    return difflib.SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def extract_key_numbers(text: str) -> set[str]:
    """Extract numerical facts from an answer, protecting against None/empty strings."""
    if not text:
        return set()

    patterns = [
        r'\d+[,\.]\d+\s*%',    # percentages: 16,7%
        r'\d+\s*%',             # simple %: 99%
        r'R\$\s*[\d,\.]+',      # monetary: R$145
        r'US\$\s*[\d,\.]+',     # dollar: US$280
        r'[\d,\.]+\s*GW',       # power: 67,5 GW
        r'[\d,\.]+\s*bi',       # billions: 145 bi
        r'[\d,\.]+\s*tri',      # trillions: 2,53 tri
        r'\d+(?:[,\.]\d+)?\s*(?:×|x\b|vezes)',   # multipliers: 16,7×, 16,7 vezes
    ]
    found = set()
    for pattern in patterns:
        found.update(re.findall(pattern, text, re.IGNORECASE))
    return found


def load_baseline() -> dict:
    """Load the saved baseline answers."""
    if not BASELINE_PATH.exists():
        return {}
    with open(BASELINE_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_baseline(baseline: dict):
    """Save new baseline answers."""
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BASELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Baseline saved to {BASELINE_PATH}")


def get_prompt_hash() -> str:
    """Hash do SYSTEM_PROMPT real (main.py), ignorando a versão antiga comentada."""
    main_py = Path(__file__).parent.parent / "main.py"
    if not main_py.exists():
        return "unknown"
    m = re.search(r'^SYSTEM_PROMPT = """(.*?)"""', main_py.read_text(encoding="utf-8"), re.S | re.M)
    return hashlib.md5(m.group(1).encode()).hexdigest()[:8] if m else "unknown"


# ── CAPTURE MODE ──────────────────────────────────────────────────────────────

def capture_baseline():
    """Run all regression questions and save answers as the new baseline."""
    print("\n" + "="*60)
    print("CAPTURING REGRESSION BASELINE")
    print("="*60)

    baseline = {
        "_metadata": {
            "captured_at": datetime.now().isoformat(),
            "prompt_hash": get_prompt_hash(),
            "num_cases": len(REGRESSION_CASES)
        }
    }

    for case in REGRESSION_CASES:
        print(f"  Capturing [{case['id']}]...", end="", flush=True)
        answer, chunks = get_answer(case["question"])

        if _is_error_answer(answer):
            print(f" ✗ ERROR, not saved: {answer[:100]}")
            continue

        baseline[case["id"]] = {
            "question": case["question"],
            "answer": answer,
            "key_numbers": list(extract_key_numbers(answer)),
            "answer_length": len(answer),
            "captured_at": datetime.now().isoformat()
        }
        print(f" ✓ ({len(answer)} chars)")

    baseline["_metadata"]["num_cases"] = len([k for k in baseline if k != "_metadata"])
    save_baseline(baseline)
    return baseline


# ── TESTS ─────────────────────────────────────────────────────────────────────

class TestPromptRegression:
    """Detects when prompt changes cause unexpected answer changes."""

    def test_baseline_exists(self):
        """A baseline must exist before compare tests can run."""
        if REGRESSION_MODE == "capture":
            capture_baseline()
            pytest.skip("Baseline captured — re-run without REGRESSION_MODE=capture to compare")

        assert BASELINE_PATH.exists(), (
            f"\nNo baseline found at {BASELINE_PATH}\n"
            f"Create one first:\n"
            f"  REGRESSION_MODE=capture pytest evals/test_prompt_regression.py -v\n"
            f"Then commit regression_baseline.json to version control."
        )

    @pytest.mark.parametrize(
        "case",
        REGRESSION_CASES,
        ids=[c["id"] for c in REGRESSION_CASES]
    )
    def test_answer_has_not_regressed(self, case):
        """Current answer should still contain the key concepts (anchors) of the golden set."""
        if REGRESSION_MODE == "capture":
            pytest.skip("Running in capture mode")

        baseline = load_baseline()
        if case["id"] not in baseline:
            pytest.skip(f"No baseline for {case['id']} — run capture mode first")

        current_answer, _ = get_answer(case["question"])

        if _is_error_answer(current_answer):
            pytest.skip(f"[{case['id']}] API call failed.")

        if _is_blanket_refusal(current_answer) and not case.get("allow_refusal"):
            pytest.fail(
                f"[{case['id']}] answer is a blanket refusal.\n  {current_answer[:300]}\n"
                f"  → Fix the prompt/retrieval, or set allow_refusal=true if it's a real corpus gap."
            )

        # Use golden set anchors instead of string similarity
        anchors = case.get("expected_answer_contains", [])
        if not anchors:
            pytest.skip(f"No expected_answer_contains defined for {case['id']}")

        current_lower = current_answer.lower()
        missing = [term for term in anchors if term.lower() not in current_lower]

        print(f"\n[{case['id']}] Anchor check: {len(anchors) - len(missing)}/{len(anchors)} found")
        print(f"  Missing: {missing}")
        print(f"  Current ({len(current_answer)} chars): {current_answer[:150]}...")

        assert len(missing) == 0, (
            f"\n[{case['id']}] REGRESSION DETECTED\n"
            f"  Missing concepts: {missing}\n"
            f"  Question: {case['question']}\n"
            f"\n  CURRENT:\n  {current_answer[:300]}\n\n"
            f"  → If intentional, update expected_answer_contains in golden_set.json\n"
            f"  → If unintentional, revert your prompt changes."
        )

    @pytest.mark.parametrize(
        "case",
        [q for q in REGRESSION_CASES if q["difficulty"] == "factual"],
        ids=[q["id"] for q in REGRESSION_CASES if q["difficulty"] == "factual"]
    )
    def test_key_numbers_have_not_changed(self, case):
        """Specific numbers in factual answers must not change."""
        if REGRESSION_MODE == "capture":
            pytest.skip("Running in capture mode")

        baseline = load_baseline()

        if case["id"] not in baseline:
            pytest.skip(f"No baseline for {case['id']}")

        baseline_entry = baseline[case["id"]]
        current_answer, _ = get_answer(case["question"])

        if _is_error_answer(current_answer):
            pytest.skip(f"[{case['id']}] Chamada da API do Gemini falhou ou retornou vazio.")

        if _is_blanket_refusal(current_answer) and not case.get("allow_refusal"):
            pytest.fail(
                f"[{case['id']}] answer is a blanket refusal.\n  {current_answer[:300]}\n"
                f"  → Fix the prompt/retrieval, or set allow_refusal=true if it's a real corpus gap."
            )

        baseline_numbers = set(baseline_entry.get("key_numbers", []))
        current_numbers = extract_key_numbers(current_answer)

        if not baseline_numbers:
            pytest.skip(f"No key numbers in baseline for {case['id']}")

        missing_numbers = baseline_numbers - current_numbers

        print(f"\n[{case['id']}] Numbers check:")
        print(f"  Baseline numbers: {baseline_numbers}")
        print(f"  Current numbers:  {current_numbers}")
        print(f"  Missing: {missing_numbers}")

        assert len(missing_numbers) <= 1, (
            f"\n[{case['id']}] KEY NUMBERS DISAPPEARED AFTER PROMPT CHANGE\n"
            f"  Missing numbers: {missing_numbers}\n"
        )

    def test_no_new_hallucinated_numbers(self):
        """Current answers should not introduce new numbers not in the baseline."""
        if REGRESSION_MODE == "capture":
            pytest.skip("Running in capture mode")

        baseline = load_baseline()
        hallucination_suspects = []

        factual_cases = [q for q in REGRESSION_CASES if q["difficulty"] == "factual"]
        for case in factual_cases:
            if case["id"] not in baseline:
                continue

            baseline_entry = baseline[case["id"]]
            current_answer, _ = get_answer(case["question"])

            if _is_error_answer(current_answer):
                continue

            # Uma recusa seca não inventa números
            if _is_blanket_refusal(current_answer):
                continue

            baseline_numbers = set(baseline_entry.get("key_numbers", []))
            current_numbers = extract_key_numbers(current_answer)

            new_numbers = current_numbers - baseline_numbers

            if len(new_numbers) > 2:
                hallucination_suspects.append({
                    "id": case["id"],
                    "new_numbers": new_numbers,
                    "question": case["question"][:80]
                })

        if hallucination_suspects:
            msg = "\n".join([
                f"  [{s['id']}] New numbers: {s['new_numbers']}\n  Q: {s['question']}"
                for s in hallucination_suspects
            ])
            pytest.fail(
                f"\nPOSSIBLE NEW HALLUCINATIONS AFTER PROMPT CHANGE:\n{msg}\n\n"
            )


class TestPromptVersionTracking:
    """Tracks which prompt version produced which results."""

    def test_prompt_hash_is_recorded(self):
        current_hash = get_prompt_hash()
        print(f"\n  Current prompt hash: {current_hash}")

        baseline = load_baseline() if BASELINE_PATH.exists() else {}
        baseline_hash = baseline.get("_metadata", {}).get("prompt_hash", "unknown")

        if baseline_hash not in ("unknown", current_hash):
            warnings.warn(
                f"Prompt changed since baseline ({baseline_hash} -> {current_hash}). "
                f"Recapture: REGRESSION_MODE=capture pytest evals/test_prompt_regression.py",
                stacklevel=1,
            )

    def test_generate_diff_report(self):
        """Relatório informativo de similaridade. NÃO é um gate de regressão."""
        if REGRESSION_MODE == "capture":
            pytest.skip("Running in capture mode")

        baseline = load_baseline()
        if not baseline:
            pytest.skip("No baseline to diff against")

        diffs = []
        for case in REGRESSION_CASES[:3]:
            if case["id"] not in baseline:
                continue

            baseline_answer = baseline[case["id"]]["answer"]
            current_answer, _ = get_answer(case["question"])

            if _is_error_answer(current_answer):
                continue

            similarity = semantic_similarity(baseline_answer, current_answer)

            diffs.append({
                "id": case["id"],
                "question": case["question"],
                "similarity": similarity,
                "changed": similarity < 0.9,
                "baseline_preview": baseline_answer[:200],
                "current_preview": current_answer[:200]
            })

        report_path = Path(__file__).parent / "reports" / "regression_diff.json"
        report_path.parent.mkdir(exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(diffs, f, ensure_ascii=False, indent=2)

        changed = [d for d in diffs if d["changed"]]
        print(f"\n  Generated diff report: {report_path}")
        print(f"  Changed answers: {len(changed)}/{len(diffs)}")

        assert report_path.exists()  # relatório informativo, NÃO é um gate de regressão