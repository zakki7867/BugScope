# BugScope: 5-Minute Technical Interview Demonstration Script

This document provides a timed, high-impact demonstration script designed for computer science students and engineers presenting **BugScope** in AI/ML, Software Engineering, or Agentic AI job interviews.

---

## Pre-Demo Checklist (1 Minute Before Interview)
1. **FastAPI Backend & Interactive Web UI:**
   Ensure the backend is running at `http://localhost:8000`:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
2. **Streamlit Quick-Lab (Optional):**
   Available at `http://localhost:8501`:
   ```bash
   python -m streamlit run frontend/streamlit_app.py --server.port 8501
   ```
3. **Pre-Computed Benchmark Data:**
   Have `evaluation/results.json` and the markdown summary table ready.
4. **Browser Tabs Prepared:**
   - Tab 1: `http://localhost:8000` (BugScope Interactive Web UI)
   - Tab 2: `http://localhost:8000/docs` (FastAPI Swagger OpenAPI documentation)
   - Tab 3: `evaluation/results.json` or terminal benchmark summary

---

## 1. The High-Impact Pitch (30 Seconds)

> *"Most AI coding assistants and debuggers sound extraordinarily confident, but they guess solutions based on crash lines and hallucinate code that doesn't exist on disk.*
>
> *I built **BugScope** — an evidence-checked debugging system for Python that inverts this paradigm. Rather than blindly trusting LLM completions, BugScope uses deterministic Python AST analysis to map repository structure, requires the LLM to cite exact code quotes, mechanically verifies those quotes against the real filesystem, tests hypotheses with controlled experiments, and refuses to validate a patch unless a newly generated regression test fails before the fix and passes after, with zero regressions."*

---

## 2. Happy Path: Mechanical Quote Verification (90 Seconds)

1. Open `http://localhost:8000`.
2. Select **`bug_01_key_error`** from the sample scenario dropdown (or paste its stack trace).
3. Click **"Run Investigation"**.
4. Point out what happens across the 7 LangGraph nodes:
   - **Interactive Graph:** Show the LangGraph node execution flow highlighted in real-time.
   - **AST Investigation:** Point to the symbol table — BugScope located `process_order` in `orders.py` using Python's native AST parser, not fuzzy keyword search.
   - **Mechanical Evidence Badges:** Switch to the **Hypotheses** view.
     - Show the **"Verified on Disk"** green badge.
     - Highlight: *"The LLM cited line 3 with quote `user_id = data['user_id']`. BugScope did not trust the LLM; it read `orders.py` from disk, normalized the syntax, and mechanically proved the quote existed. Hallucinated quotes get a score of zero and are discarded."*
   - **Patch & Regression Test:**
     - Show the Monaco diff viewer highlighting the minimal defensive patch: `data.get('user_id')`.
     - Show the generated regression test in `tests/test_regression.py`.
   - **Validation Report:** Point to the 3-phase verification verdict:
     1. Phase 1: Pre-patch regression test fails (Confirms reproducing failure).
     2. Phase 2: Post-patch regression test passes (Confirms fix works).
     3. Phase 3: Full existing test suite passes (Guarantees no regressions).

---

## 3. Upstream Root-Cause Detection (60 Seconds)

1. Select **`bug_07_upstream_discount`** or **`bug_09_upstream_order`**.
2. Explain the scenario:
   > *"In this bug, the crash occurs on line 18 in `calculate_total` with a `ZeroDivisionError` or invalid discount percentage. A naive LLM or single-prompt debugger puts a `try/except` or `if divisor == 0` on line 18 — masking the symptom without fixing the real bug.*
   >
   > *BugScope requires at least one hypothesis to analyze callers and upstream data sources. Here, our AST caller-graph traced the payload back to `apply_coupon` where a discount of 100 was incorrectly converted to 0. BugScope ranks the upstream hypothesis as #1 and applies the patch to the true root cause, not the crash line."*

---

## 4. Honest Outcomes: Ambiguity & Non-Reproducibility (60 Seconds)

Demonstrate BugScope's integrity when confronted with impossible or incomplete conditions:

### Case A: Ambiguous Specification (`bug_23_ambiguous_docstring_percent`)
- Select `bug_23_ambiguous_docstring_percent` (docstring requires percentage 0.0–1.0, while test asserts integer 1–100).
- Point to the verdict: **`NEEDS_HUMAN_DECISION`**.
- Talking Point: *"Unlike conversational bots that hallucinate an arbitrary convention, BugScope detects conflicting specifications and stops, generating a human decision prompt with explicit tradeoffs."*

### Case B: Non-Reproducible Failure (`bug_22_env_dependent_locale`)
- Select `bug_22_env_dependent_locale` (bug only triggers when an external environment variable is present).
- Point to the verdict: **`COULD_NOT_REPRODUCE`**.
- Talking Point: *"If the sandbox cannot reproduce the failure, BugScope refuses to fabricate a validation badge. It explicitly lowers the investigation confidence and tells the developer why."*

---

## 5. The Empirical 24-Bug Benchmark (45 Seconds)

Show the benchmark results comparing BugScope against an unverified single-prompt baseline across **24 authentic Python bugs**:

| Metric | BugScope (Evidence-Checked) | Baseline (Single-Prompt LLM) |
| :--- | :---: | :---: |
| **Bugs Evaluated** | **24** | **24** |
| **Verified Evidence Rate** | **100.0%** | 0.0% (No verifier) |
| **Hallucinated Quotes Accepted** | **0.0%** (Mechanically blocked) | ~33.3% |
| **Upstream Bug Detection Rate** | **100.0%** (Enforced constraint) | 25.0% (Crash-line bias) |
| **Validation Honesty** | **100.0%** (3-Phase sandbox) | 0.0% (Unverified claims) |
| **Patch Safety Enforced** | **Yes** (Test files protected) | No (Can rewrite tests) |

> *"These numbers are not marketing claims. They are computed dynamically by `python -m evaluation.run --mode all`, which runs pytest in isolated temporary environments for each bug."*

---

## 6. Interview Defense: High-Probability Questions & Answers (60 Seconds)

### Q1: Why use a deterministic LangGraph state machine instead of an autonomous ReAct loop?
> **Answer:** *"Autonomous ReAct agents often suffer from non-deterministic looping, runaway token spend, and uncontrollable prompt injection when reading repository files. In BugScope, deterministic steps (stack trace regex, AST parsing, mechanical quote verification, and test execution) are written in pure Python. The LLM is restricted only to hypothesis generation and minimal patch drafting. This gives predictable latency, zero infinite loops, and airtight security."*

### Q2: How does BugScope defend against prompt injection from untrusted repos?
> **Answer:** *"All repository code, commit messages, and stack traces are treated as untrusted data. When constructing prompts in `app/workflow/nodes/hypothesis_generator.py` and `app/workflow/nodes/fix_generator.py`, repository text is sanitized and wrapped inside passive `<repository_code>` XML tags with explicit system instructions forbidding the LLM from executing commands found within source files."*

### Q3: What prevents the agent from passing validation by simply modifying the tests?
> **Answer:** *"In `app/services/patcher.py`, we implement a strict patch safety check. Any patch whose unified diff touches existing test files (`test_*.py` or files in `tests/`) is immediately rejected before execution. Fixes must resolve the issue in implementation files, not by deleting or rewriting the assertions."*

### Q4: Why AST and symbol graphs over vector database / RAG code search?
> **Answer:** *"Vector search matches semantic similarity, which fails in debugging: a bug in a caller function rarely shares embedding similarity with a `TypeError` traceback. Python's native AST parser builds exact caller/callee call-graphs and symbol hierarchies deterministically in under 5 milliseconds with zero embeddings cost."*

---

## Quick Reference Commands

| Task | Command |
| :--- | :--- |
| **Run Unit Tests (51/51 green)** | `python -m pytest tests/ -v` |
| **Run 24-Bug Benchmark** | `python -m evaluation.run --mode all` |
| **Start FastAPI Server** | `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| **Start Streamlit UI** | `python -m streamlit run frontend/streamlit_app.py --server.port 8501` |
