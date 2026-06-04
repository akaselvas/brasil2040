# brasil2040-ai-evals

An AI evaluation suite for the Brasil 2040 climate risk assistant.
Built to demonstrate professional QA skills for LLM-powered features.

---

## What's in here

```
brasil2040-ai-evals/
├── evals/
│   ├── golden_set.json           # 30 Q&A pairs — your ground truth
│   ├── test_retrieval.py         # Precision@K — did right chunks come back?
│   ├── test_faithfulness.py      # LLM-judge — is the answer grounded?
│   ├── test_prompt_regression.py # Diff outputs before/after prompt changes
│   └── test_latency_cost.py      # Timing + token count thresholds
├── judges/
│   └── llm_judge.py              # Reusable judge: faithfulness, hallucination, relevance, safety
├── reports/                      # Auto-generated after each run
├── requirements.txt
└── .github/workflows/
    └── evals.yml                 # Runs on every PR that touches main.py
```

---

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set environment variables
export SUPABASE_URL=your_url
export SUPABASE_KEY=your_key
export GEMINI_API_KEY=your_key   # For the LLM judge

# 3. Start your FastAPI server
uvicorn main:app --reload

# 4. Run retrieval tests (no API keys needed)
pytest evals/test_retrieval.py -v

# 5. Run faithfulness tests with mock judge (no Gemini key needed)
JUDGE_BACKEND=mock pytest evals/test_faithfulness.py -v

# 6. Run all tests
pytest evals/ -v --html=reports/full_report.html
```

---

## What each test file does

### `golden_set.json`
Your **ground truth**. Contains 30 question/answer pairs covering:
- Factual questions (specific numbers from the reports)
- Synthesis questions (cross-sector reasoning)
- Hallucination traps (questions about things that don't exist)
- Out-of-scope questions (recipes, sports)
- Prompt regression baselines

The golden set is the most important artifact. A good golden set:
- Is **grounded in real content** (every factual case cites a source)
- Has **trap cases** that test failure modes
- Is **stable enough** to use as a regression baseline

### `test_retrieval.py` — Precision@K
Tests whether your `/search` endpoint returns relevant chunks.

Key concepts you'll learn:
- **Precision@K**: of the top-K results, how many are relevant?
- **Recall@K**: of all relevant documents, how many are in top-K?
- Why English questions work against Portuguese documents (multilingual-e5-large)

Run: `pytest evals/test_retrieval.py -v`

### `test_faithfulness.py` — LLM-as-Judge
Tests whether AI answers are grounded in the retrieved context.

Key concepts you'll learn:
- **Faithfulness** (aka groundedness): every claim must trace to a source
- **Hallucination detection**: model states facts not in context
- **Trap questions**: the model should hedge, not invent
- How to write judge prompts (the core skill for AI QA)

Run: `JUDGE_BACKEND=mock pytest evals/test_faithfulness.py -v`

### `test_prompt_regression.py` — Prompt Diff Testing
Detects when prompt changes cause unexpected quality regressions.

Key concepts:
- **Golden files**: save approved outputs, fail if they change unexpectedly
- **Semantic similarity** vs. exact string matching
- **Numerical stability**: key stats (16,7×, R$2,53 tri) must not disappear
- Capture mode vs. compare mode

First time setup:
```bash
REGRESSION_MODE=capture pytest evals/test_prompt_regression.py -v
```

Subsequent runs (CI):
```bash
pytest evals/test_prompt_regression.py -v
```

### `test_latency_cost.py` — SLA Testing
Tests performance and cost budgets.

Key concepts:
- **P50/P95 latency**: what "typical" and "worst case" performance look like
- **Token budget**: how many tokens are used per query
- **Cost estimation**: what does 1000 queries/day cost?
- Why P95 matters more than average

Run: `pytest evals/test_latency_cost.py -v -s`

### `judges/llm_judge.py` — The Judge Engine
A reusable module that scores any response on 4 dimensions:
1. **Faithfulness**: is every claim traceable to retrieved context?
2. **Hallucination**: did the model invent specific facts?
3. **Relevance**: does the answer address the question? Is it in PT-BR?
4. **Safety**: false reassurance? Misattributed stats? Wrong out-of-scope handling?

The judge uses a **different model** from your app (Gemini judges Claude, or Claude judges Gemini). This prevents self-serving bias.

---

## Mapping to the job description you found

| Job description requirement | Where it lives in this repo |
|---|---|
| Prompt regression testing | `test_prompt_regression.py` |
| Output evaluation | `test_faithfulness.py` + `llm_judge.py` |
| Hallucination detection | `test_faithfulness.py::TestHallucinationTraps` |
| Automated eval pipelines | `.github/workflows/evals.yml` |
| Golden datasets | `golden_set.json` |
| LLM-as-judge frameworks | `judges/llm_judge.py` |
| Quality metrics (accuracy, faithfulness, relevance, safety, latency, cost) | All test files |
| Thresholds for release readiness | `FAITHFULNESS_THRESHOLD`, `RETRIEVAL_P95_THRESHOLD_SEC`, etc. |
| Black-box exploratory testing | `test_retrieval.py::TestRetrievalEdgeCases` |
| Investigating AI failure modes | Judge `reasoning` and `evidence` fields |
| Distinguishing model vs. prompt vs. retrieval issues | 3 separate test files, each isolates one layer |

---

## The 3-layer mental model for RAG QA

```
User question
     │
     ▼
[LAYER 1: Retrieval]  ← tested by test_retrieval.py
Did the right chunks come back from pgvector?
Failure mode: wrong chunks → correct-looking but wrong answer
     │
     ▼
[LAYER 2: Generation]  ← tested by test_faithfulness.py
Did the LLM use only the retrieved context?
Failure mode: model adds facts not in context (hallucination)
     │
     ▼
[LAYER 3: System Prompt]  ← tested by test_prompt_regression.py
Is the prompt producing stable, high-quality outputs?
Failure mode: prompt change causes regression in factual answers
```

When an answer is wrong, this framework helps you ask:
- Did the retrieval fail? → check `test_retrieval.py` for that question
- Did the model hallucinate? → check hallucination scores in `test_faithfulness.py`
- Did a recent prompt change cause this? → check `test_prompt_regression.py`

---

## Configuring thresholds

All thresholds are configurable via environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `FAITHFULNESS_THRESHOLD` | 0.7 | Minimum faithfulness score (0-1) |
| `HALLUCINATION_THRESHOLD` | 0.7 | Minimum hallucination safety score |
| `SIMILARITY_THRESHOLD` | 0.5 | Max allowed answer drift for regression |
| `RETRIEVAL_P95_MS` | 3.0 | P95 retrieval latency in seconds |
| `MAX_TOKENS_PER_QUERY` | 4000 | Token budget per query |
| `JUDGE_BACKEND` | gemini | Judge model: gemini / anthropic / mock |
| `REGRESSION_MODE` | compare | capture (save baseline) or compare |

Start with lenient thresholds (0.6) and tighten as your system improves.

---

## Adding your own test cases

1. Open `evals/golden_set.json`
2. Add an entry following this schema:
```json
{
  "id": "your_sector_NNN",
  "question": "Your question in PT-BR",
  "expected_answer_contains": ["key", "terms", "or", "numbers"],
  "expected_chunk_sources": ["Partial filename.pdf"],
  "category": "factual|synthesis|hallucination_trap|out_of_scope",
  "difficulty": "factual|synthesis|conceptual|reasoning|trap",
  "notes": "What this case is testing"
}
```
3. For hallucination traps, set `"category": "hallucination_trap"` and `"should_hedge": true`
4. Run the retrieval test to verify your new case works: `pytest evals/test_retrieval.py -v -k "your_id"`

---

## Recommended learning path

1. **Week 1**: Read `golden_set.json` and understand why each case exists.
   Run `pytest evals/test_retrieval.py -v` and interpret failures.

2. **Week 2**: Read `judges/llm_judge.py`. Understand the 4 judge prompts.
   Run `JUDGE_BACKEND=mock pytest evals/test_faithfulness.py -v`.
   Then try with a real Gemini key and compare.

3. **Week 3**: Read `test_prompt_regression.py`. Change one word in your
   Gemini system prompt in `app.js` and run the regression test. See what breaks.

4. **Week 4**: Add 5 new golden set cases for the sectors not yet covered
   (hydro, transport, coastal). Run the full suite and interpret.

5. **Going further**: Replace `difflib.SequenceMatcher` in regression tests
   with sentence embedding similarity for better semantic comparison.
   Try `sentence-transformers` or the Gemini embedding API.
