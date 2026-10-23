import difflib
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers import get_chunks, get_production_answer, PROD_TOP_K

REGRESSION_MODE = os.getenv("REGRESSION_MODE", "compare")
BASELINE_PATH = Path(__file__).parent / "regression_baseline.json"
GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"

with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
    GOLDEN_SET = json.load(f)

REGRESSION_CASES = [q for q in GOLDEN_SET if q["category"] == "prompt_regression"]
REGRESSION_CASES += [q for q in GOLDEN_SET if q["id"] in ["energia_001", "agro_001"]]
FACTUAL_REGRESSION_CASES = [q for q in REGRESSION_CASES if q["difficulty"] == "factual"]

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


def _is_refusal(answer: str) -> bool:
    if not answer or not answer.strip():
        return True
    a = answer.lower()
    return any(m in a for m in REFUSAL_MARKERS)


def _is_error_answer(answer: str) -> bool:
    if not answer or not answer.strip():
        return True
    return answer.lower().strip().startswith(("[error", "[mock"))


def _is_blanket_refusal(answer: str) -> bool:
    return _is_refusal(answer) and len(answer) < 300


def fetch_chunks_and_answer(question: str) -> tuple[list[dict], str]:
    chunks = get_chunks(question, PROD_TOP_K)
    answer = get_production_answer(question, PROD_TOP_K)
    return chunks, answer


def get_chunks_and_answer(question: str) -> tuple[list[dict], str]:
    chunks, answer = fetch_chunks_and_answer(question)
    if _is_error_answer(answer):
        pytest.fail(f"Chat endpoint did not return an answer. Got: {str(answer)[:200]}")
    return chunks, answer


def char_similarity(text1: str, text2: str) -> float:
    if not text1 or not text2:
        return 0.0
    return difflib.SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


NUM = r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?"
THOUSANDS_RE = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?")
SCALE = r"bilh(?:ões|ão)|bi|trilh(?:ões|ão)|tri"
UNIT = r"%|GW\b|bilh(?:ões|ão)\b|bi\b|trilh(?:ões|ão)\b|tri\b|×|x\b|vezes\b"

KEY_NUMBER_RE = re.compile(
    rf"(?P<cur>US\$|R\$)\s*(?P<cn>{NUM})(?:\s*(?P<scale>{SCALE})\b)?"
    rf"|(?<![\w.,$])(?P<n>{NUM})\s*(?P<unit>{UNIT})",
    re.IGNORECASE,
)
BARE_NUMBER_RE = re.compile(rf"(?<![\w.,])(?:{NUM})")

UNIT_CANON = {
    "%": "%",
    "gw": "GW",
    "bi": "bi",
    "bilhão": "bi",
    "bilhões": "bi",
    "tri": "tri",
    "trilhão": "tri",
    "trilhões": "tri",
    "×": "x",
    "x": "x",
    "vezes": "x",
}


def _canon_number(raw: str) -> str:
    if THOUSANDS_RE.fullmatch(raw):
        raw = raw.replace(".", "")
    raw = raw.replace(",", ".")
    return format(Decimal(raw).normalize(), "f")


def extract_key_numbers(text: str) -> set[str]:
    if not text:
        return set()

    found = set()
    for m in KEY_NUMBER_RE.finditer(text):
        if m.group("cur"):
            scale = UNIT_CANON.get((m.group("scale") or "").lower(), "")
            found.add(f"{m.group('cur').upper()}{_canon_number(m.group('cn'))}{scale}")
        else:
            unit = UNIT_CANON[m.group("unit").lower()]
            found.add(f"{_canon_number(m.group('n'))}{unit}")
    return found


def extract_bare_numbers(text: str) -> set[str]:
    if not text:
        return set()
    return {_canon_number(raw) for raw in BARE_NUMBER_RE.findall(text)}


def _numeric_part(key: str) -> str:
    return re.search(r"\d+(?:\.\d+)?", key).group()


def load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        return {}
    with open(BASELINE_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_baseline(baseline: dict):
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BASELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Baseline saved to {BASELINE_PATH}")


def _require_baseline_entry(case_id: str) -> dict:
    baseline = load_baseline()
    if case_id not in baseline:
        pytest.fail(
            f"[{case_id}] not found in {BASELINE_PATH.name}.\n"
            f"  → Recapture: REGRESSION_MODE=capture pytest evals/test_prompt_regression.py"
        )
    return baseline[case_id]


def get_config_fingerprint() -> dict:
    parts = {
        "prompt": "unknown",
        "model": "unknown",
        "temperature": "unknown",
        "top_k": str(PROD_TOP_K),
    }
    main_py = Path(__file__).parent.parent / "main.py"
    if main_py.exists():
        src = main_py.read_text(encoding="utf-8")

        m = re.search(r'^SYSTEM_PROMPT\s*=\s*(?:"""(.*?)"""|\'\'\'(.*?)\'\'\')', src, re.S | re.M)
        if m:
            prompt_text = m.group(1) if m.group(1) is not None else m.group(2)
            parts["prompt"] = hashlib.md5(prompt_text.encode()).hexdigest()[:8]

        m = re.search(
                        r'^\s*GEMINI_(?:ANSWER_)?MODEL\s*=\s*(?:os\.(?:getenv|environ\.get)\([^,]+,\s*)?["\']([^"\']+)["\']',
            src, re.M,
        )
        if m:
            parts["model"] = m.group(1)

        m = re.search(r"temperature\s*=\s*([0-9.]+)", src)
        if m:
            parts["temperature"] = m.group(1)

    parts["model"] = os.getenv("GEMINI_ANSWER_MODEL") or parts["model"]
    digest = hashlib.md5(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:8]
    return {"parts": parts, "hash": digest}


def capture_baseline():
    print("\n" + "=" * 60)
    print("CAPTURING REGRESSION BASELINE")
    print("=" * 60)

    fingerprint = get_config_fingerprint()
    baseline = {
        "_metadata": {
            "captured_at": datetime.now().isoformat(),
            "config_hash": fingerprint["hash"],
            "config": fingerprint["parts"],
            "num_cases": 0,
        }
    }
    failed = []

    for case in REGRESSION_CASES:
        print(f"  Capturing [{case['id']}]...", end="", flush=True)
        chunks, answer = fetch_chunks_and_answer(case["question"])

        if _is_error_answer(answer):
            print(f" ✗ ERROR: {str(answer)[:100]}")
            failed.append(case["id"])
            continue

        baseline[case["id"]] = {
            "question": case["question"],
            "answer": answer,
            "key_numbers": sorted(extract_key_numbers(answer)),
            "answer_length": len(answer),
            "captured_at": datetime.now().isoformat(),
        }
        print(f" ✓ ({len(answer)} chars)")

    if failed:
        pytest.fail(
            f"Capture failed for {failed}. The existing baseline was NOT modified.\n"
            f"  → Fix the chat endpoint and run the capture again."
        )

    baseline["_metadata"]["num_cases"] = len([k for k in baseline if k != "_metadata"])
    save_baseline(baseline)
    return baseline


class TestPromptRegression:
    def test_baseline_exists(self):
        if REGRESSION_MODE == "capture":
            capture_baseline()
            pytest.skip("Baseline captured — re-run without REGRESSION_MODE=capture to compare")

        assert BASELINE_PATH.exists(), (
            f"\nNo baseline found at {BASELINE_PATH}\n"
            f"Create one first:\n"
            f"  REGRESSION_MODE=capture pytest evals/test_prompt_regression.py -v\n"
            f"Then commit regression_baseline.json to version control."
        )

        baseline = load_baseline()
        missing_cases = [c["id"] for c in REGRESSION_CASES if c["id"] not in baseline]
        assert not missing_cases, (
            f"\nBaseline is missing cases: {missing_cases}\n"
            f"  → Recapture: REGRESSION_MODE=capture pytest evals/test_prompt_regression.py"
        )

    @pytest.mark.parametrize("case", REGRESSION_CASES, ids=[c["id"] for c in REGRESSION_CASES])
    def test_answer_has_not_regressed(self, case):
        if REGRESSION_MODE == "capture":
            pytest.skip("Running in capture mode")

        entry = _require_baseline_entry(case["id"])
        chunks, current_answer = get_chunks_and_answer(case["question"])

        if _is_blanket_refusal(current_answer) and not case.get("allow_refusal"):
            pytest.fail(
                f"[{case['id']}] answer is a blanket refusal.\n  {current_answer[:300]}\n"
                f"  → Fix the prompt/retrieval, or set allow_refusal=true if it's a real corpus gap."
            )

        anchors = case.get("expected_answer_contains", [])
        if not anchors:
            pytest.fail(f"[{case['id']}] no expected_answer_contains defined in golden_set.json")

        baseline_lower = entry["answer"].lower()
        current_lower = current_answer.lower()

        missing = [t for t in anchors if t.lower() not in current_lower]
        lost_since_baseline = [t for t in missing if t.lower() in baseline_lower]
        never_present = [t for t in missing if t.lower() not in baseline_lower]

        print(f"\n[{case['id']}] Anchor check: {len(anchors) - len(missing)}/{len(anchors)} found")
        print(f"  Lost since baseline: {lost_since_baseline}")
        print(f"  Not in baseline either: {never_present}")
        print(f"  Current ({len(current_answer)} chars): {current_answer[:150]}...")

        assert not missing, (
            f"\n[{case['id']}] REGRESSION DETECTED\n"
            f"  Lost since baseline: {lost_since_baseline}\n"
            f"  Missing in baseline too: {never_present}\n"
            f"  Question: {case['question']}\n"
            f"\n  BASELINE:\n  {entry['answer'][:300]}\n"
            f"\n  CURRENT:\n  {current_answer[:300]}\n\n"
            f"  → If intentional, update expected_answer_contains in golden_set.json\n"
            f"  → If unintentional, revert your prompt changes."
        )

    @pytest.mark.parametrize(
        "case",
        FACTUAL_REGRESSION_CASES,
        ids=[q["id"] for q in FACTUAL_REGRESSION_CASES],
    )
    def test_key_numbers_have_not_changed(self, case):
        if REGRESSION_MODE == "capture":
            pytest.skip("Running in capture mode")

        entry = _require_baseline_entry(case["id"])
        chunks, current_answer = get_chunks_and_answer(case["question"])

        if _is_blanket_refusal(current_answer) and not case.get("allow_refusal"):
            pytest.fail(
                f"[{case['id']}] answer is a blanket refusal.\n  {current_answer[:300]}\n"
                f"  → Fix the prompt/retrieval, or set allow_refusal=true if it's a real corpus gap."
            )

        baseline_numbers = extract_key_numbers(entry["answer"])
        if not baseline_numbers:
            pytest.fail(
                f"[{case['id']}] baseline answer has no key numbers to compare.\n"
                f"  Baseline answer: {entry['answer'][:300]}"
            )

        anchor_values = extract_bare_numbers(" ".join(case.get("expected_answer_contains", [])))
        required_numbers = {n for n in baseline_numbers if _numeric_part(n) in anchor_values} or baseline_numbers
        current_numbers = extract_key_numbers(current_answer)
        missing_numbers = required_numbers - current_numbers

        print(f"\n[{case['id']}] Numbers check:")
        print(f"  Baseline numbers: {sorted(baseline_numbers)}")
        print(f"  Current numbers:  {sorted(current_numbers)}")
        print(f"  Missing: {sorted(missing_numbers)}")

        assert not missing_numbers, (
            f"\n[{case['id']}] KEY NUMBERS DISAPPEARED AFTER PROMPT CHANGE\n"
            f"  Missing numbers: {sorted(missing_numbers)}\n"
            f"  Answer: {current_answer[:300]}\n"
        )

    @pytest.mark.parametrize(
        "case",
        FACTUAL_REGRESSION_CASES,
        ids=[q["id"] for q in FACTUAL_REGRESSION_CASES],
    )
    def test_answer_numbers_come_from_retrieved_chunks(self, case):
        if REGRESSION_MODE == "capture":
            pytest.skip("Running in capture mode")

        chunks, current_answer = get_chunks_and_answer(case["question"])

        chunk_text = " ".join(c.get("text", "") for c in chunks)
        chunk_keys = extract_key_numbers(chunk_text)
        chunk_values = extract_bare_numbers(chunk_text)

        answer_numbers = extract_key_numbers(current_answer)
        unsupported = sorted(
            n for n in answer_numbers
            if n not in chunk_keys and _numeric_part(n) not in chunk_values
        )

        print(f"\n[{case['id']}] Answer numbers: {sorted(answer_numbers)}")
        print(f"  Not found in retrieved chunks: {unsupported}")

        assert not unsupported, (
            f"\n[{case['id']}] NUMBERS NOT PRESENT IN RETRIEVED CHUNKS: {unsupported}\n"
            f"  Question: {case['question']}\n"
            f"  Answer: {current_answer[:300]}\n"
        )


class TestPromptVersionTracking:
    def test_config_fingerprint_matches_baseline(self):
        if REGRESSION_MODE == "capture":
            pytest.skip("Running in capture mode")

        assert BASELINE_PATH.exists(), f"No baseline found at {BASELINE_PATH}"

        current = get_config_fingerprint()
        unreadable = [k for k, v in current["parts"].items() if v == "unknown"]
        assert not unreadable, (
            f"Could not read {unreadable} from main.py, so the baseline cannot be validated.\n"
            f"  → Update get_config_fingerprint to match how main.py defines them."
        )

        metadata = load_baseline().get("_metadata", {})
        baseline_hash = metadata.get("config_hash")
        assert baseline_hash, (
            "Baseline has no config_hash (captured with an older version of this test).\n"
            "  → Recapture: REGRESSION_MODE=capture pytest evals/test_prompt_regression.py"
        )

        baseline_parts = metadata.get("config", {})
        changed = {
            k: (baseline_parts.get(k), v)
            for k, v in current["parts"].items()
            if baseline_parts.get(k) != v
        }
        assert baseline_hash == current["hash"], (
            f"Config changed since baseline ({baseline_hash} -> {current['hash']}).\n"
            f"  Changed (baseline, current): {changed}\n"
            f"  → Recapture: REGRESSION_MODE=capture pytest evals/test_prompt_regression.py"
        )

    def test_generate_diff_report(self):
        if REGRESSION_MODE == "capture":
            pytest.skip("Running in capture mode")

        baseline = load_baseline()
        assert baseline, f"No baseline found at {BASELINE_PATH}"

        diffs = []
        for case in REGRESSION_CASES[:3]:
            entry = _require_baseline_entry(case["id"])
            baseline_answer = entry["answer"]
            chunks, current_answer = get_chunks_and_answer(case["question"])

            similarity = char_similarity(baseline_answer, current_answer)
            diffs.append({
                "id": case["id"],
                "question": case["question"],
                "char_similarity": similarity,
                "changed": similarity < 0.9,
                "baseline_preview": baseline_answer[:200],
                "current_preview": current_answer[:200],
            })

        report_path = Path(__file__).parent / "reports" / "regression_diff.json"
        report_path.parent.mkdir(exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(diffs, f, ensure_ascii=False, indent=2)

        changed = [d for d in diffs if d["changed"]]
        print(f"\n  Generated diff report: {report_path}")
        print(f"  Changed answers: {len(changed)}/{len(diffs)}")

        assert report_path.exists()