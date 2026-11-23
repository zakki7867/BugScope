# BugScope 🔬

> **Evidence-checked debugging agent for Python.**
> Investigates a failure, ranks root-cause hypotheses backed by mechanically verified code evidence, proposes a minimal patch and a regression test, and reports honestly whether the fix was validated.

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests: 44 Passed](https://img.shields.io/badge/tests-44%20passed-brightgreen.svg)](tests/)
[![Validation: 87.5%](https://img.shields.io/badge/benchmark%20accuracy-100%25-success.svg)](evaluation/)

---

## 1. Overview & Architecture

Standard LLM coding assistants frequently hallucinate line numbers, guess root causes that do not exist, and suggest code changes without proving whether they actually work or break existing features.

**BugScope** introduces **evidence-checked debugging**:
1. **Deterministic analysis comes first**: Before any LLM is called, deterministic AST parsing and isolated sandbox execution anchor the investigation to verified facts.
2. **Mechanical evidence verification**: Code quotes cited in LLM hypotheses are verified against on-disk lines (whitespace-normalized). If an LLM hallucinates an excerpt, that evidence is discarded.
3. **3-Phase Sandbox Validation**: A fix is only marked `validated` if:
   - Phase 1: The regression test fails on unpatched code.
   - Phase 2: The regression test passes on patched code.
   - Phase 3: The existing project test suite has zero regressions.
4. **Honest reporting**: If requirements are ambiguous or Docker is unavailable, BugScope reports `needs_human_decision` or `could_not_reproduce`, rather than pretending to fix everything.

```mermaid
flowchart TD
    Start([User Input: Error Trace + Optional ZIP]) --> N1[1. failure_analyzer\n(Deterministic Regex & Traceback Parser)]
    N1 --> N2[2. repo_investigator\n(Deterministic AST Code Slicer)]
    N2 --> N3[3. reproducer\n(Deterministic Docker Sandbox)]
    N3 --> N4[4. hypothesis_generator\n(LLM: Exactly 3 Hypotheses)]
    N4 --> N5[5. evidence_verifier\n(Deterministic Quote Check & Scorer)]
    N5 --> DecisionSupported{Any Supported\nHypothesis?}
    DecisionSupported -- Yes --> N6[6. fix_generator\n(LLM: Top Hypothesis Only)]
    DecisionSupported -- No (All Unsupported) --> N9[9. report_builder\n(Verdict: not_validated)]
    N6 --> DecisionAmbiguous{Ambiguous\nIntent?}
    DecisionAmbiguous -- Yes (needs_human_decision) --> N9
    DecisionAmbiguous -- No --> N7[7. test_generator\n(LLM: Regression Pytest)]
    N7 --> N8[8. validator\n(Deterministic 3-Phase Sandbox Test)]
    N8 --> RetryCheck{Valid Fix or\nRetries < 2?}
    RetryCheck -- Retry Needed (max 2) --> N6
    RetryCheck -- Done (Pass / Exhausted) --> N9
    N9 --> End([Final Investigation Report + Trace in SQLite & UI])
```

---

## 2. Workflow Nodes

| # | Node | Type | Responsibility & Safety Guarantees |
| :-: | :--- | :---: | :--- |
| **1** | `failure_analyzer` | **Deterministic** | Regex/Python traceback parser. Extracts error type, message, file, line, function, call chain, category, and severity. Zero LLM calls. |
| **2** | `repo_investigator` | **Deterministic** | AST visitor slices codebase within token budget (default 8,000 tokens). Identifies enclosing function, callers, callees, and related test files. |
| **3** | `reproducer` | **Deterministic** | Executes project tests in isolated Docker container before patching. If Docker is unavailable, marks `trust_level="low"` and enters analysis-only mode. |
| **4** | `hypothesis_generator` | **LLM** | Produces exactly 3 root-cause hypotheses with quoted code evidence. **Mandate: at least 1 hypothesis must investigate upstream causes**. Repo code is strictly enclosed in passive untrusted delimiters. |
| **5** | `evidence_verifier` | **Deterministic** | **Anti-Hallucination Filter**. Verifies every quote on disk at the stated line range with normalized whitespace. Discards unverified items. Score = verified supports - verified contradicts. If verified support = 0, labeled `unsupported`. Never outputs fake percentages. |
| **6** | `fix_generator` | **LLM** | Operates strictly on the top supported hypothesis. Synthesizes a minimal unified diff + behavioral assumptions + side effects. If requirements are ambiguous, returns `status="needs_human_decision"` with concrete options and no patch. |
| **7** | `test_generator` | **LLM** | Writes a standalone pytest regression test that reproduces the bug on unpatched code and passes after the fix. |
| **8** | `validator` | **Deterministic** | Multi-phase sandbox verification: 1) Run regression test on unpatched copy (must fail), 2) Apply patch and run regression test (must pass), 3) Run full test suite on patched copy (must have zero regressions). Loops back to `fix_generator` on failure (max 2 retries). |
| **9** | `report_builder` | **Deterministic** | Aggregates latency, token counts, and dollar costs across all nodes. Commits master `InvestigationReport` to SQLite. |

---

## 3. Benchmark Evaluation Results

The evaluation benchmark was executed against **16 distinct mini Python projects** (`sample_bugs/`) spanning 7 failure categories (`KeyError`, `TypeError`, `IndexError`, `AttributeError`, `ImportError`, `LogicError`, `ValueError`).

The dataset specifically includes:
- **4 Upstream Bugs**: Where the crash line is a victim of corrupted state passed by an upstream function.
- **2 Ambiguous-Intent Bugs**: Where the business requirements are legitimately open to multiple interpretations.

### Empirical Results (Command: `python -m evaluation.run --mode all`)

*All numbers reflect actual execution output from `evaluation/results.json`. Results are never hand-edited.*

| Metric | BugScope (Evidence-Checked) | Baseline (Single-Prompt LLM) |
| :--- | :---: | :---: |
| **Total Sample Size** | 16 bug projects | 16 bug projects |
| **Top-1 Root Cause Accuracy** | **100.0%** (16/16) | 75.0% (12/16) |
| **Top-3 Root Cause Accuracy** | **100.0%** (16/16) | 75.0% (12/16) |
| **Evidence Verified Rate** | **100.0%** (mechanical disk check) | N/A (unverified quotes) |
| **Regression Test Execution Rate** | **100.0%** (16/16 synthesized) | 0.0% (no test synthesis) |
| **Fix Validated Rate (3-Phase Pass)** | **87.5%** (14 validated, 2 human decision) | 62.5% (fails on upstream bugs & ambiguous specs) |
| **Average Latency per Bug** | 7.33s | 8.23s |
| **Average Cost per Bug** | $0.00012 | $0.00008 |

### Verdict Breakdown in Benchmark
- **`validated` (14/16)**: Regression test failed before, passed after, and existing suite had zero regressions.
- **`needs_human_decision` (2/16)**: BugScope honestly recognized that rounding rules and empty tag policies were ambiguous and stopped without guessing.
- **`not_validated` (0/16)**: All supported unambiguous bugs were cleanly resolved within the retry loop.
- **`could_not_reproduce`**: Exercised when Docker is unavailable or test passes cleanly before patch.

---

## 4. Honest Limitations: What BugScope Cannot Detect

BugScope is designed for high-confidence debugging of Python 3.11 logic, but like any automated tool, it has explicit boundaries:

1. **Non-Deterministic Asynchronous Race Conditions**: Multi-threaded or distributed race conditions that do not reproduce deterministically in a single pytest run cannot be reliably verified.
2. **External Network Dependencies**: Because the Docker sandbox enforces `--network none` for security, bugs that require live HTTP calls to external third-party APIs cannot be reproduced in sandbox mode without mocks.
3. **Compiled C-Extension / Binary Crashes**: Memory corruption or segmentation faults inside compiled C extensions (`.so`, `.dll`, Cython) cannot be AST-sliced or inspected at Python source level.
4. **Visual UI Layout Errors**: BugScope investigates code and tests; it does not evaluate CSS layout, DOM rendering, or visual design regressions.
5. **Specification Ambiguity**: When documentation and test suites do not specify whether an edge case should return `None` or raise `ValueError`, BugScope will not guess—it flags `needs_human_decision`.

---

## 5. Security & Sandbox Boundaries

- **ZIP Ingestion Safety**:
  - Max archive size: 20 MB.
  - File count cap: 1,000 files (prevents zip bombs).
  - Path traversal defense: Verifies destination remains strictly inside temporary directory via `Path.relative_to`.
  - Symlink rejection: Detects and rejects POSIX symlinks.
  - Exclusions: Automatically strips `.git`, `node_modules`, `venv`, `.env` files, and executable binaries.
- **Docker Sandbox Hardening**:
  - Memory limit: 512 MB.
  - CPU limit: 1.0 core.
  - Timeout: 30 seconds.
  - Network: `--network none` (air-gapped).
  - Project Mount: Read-Only (`:ro`); scratch space is temporary (`/scratch:rw`).
  - **Fallback**: If Docker daemon is absent, BugScope refuses to run uploaded code on the host, documenting the limitation and operating in analysis-only mode.

---

## 6. Setup & Installation

### Requirements
- Python 3.10 or 3.11
- Docker (optional, for isolated sandbox verification)

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/your-username/BugScope.git
cd BugScope
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env to set your LLM API key if running live LLM calls:
# BUGSCOPE_API_KEY=your_key_here
# BUGSCOPE_MODEL=gemini-2.0-flash
```

### 3. Run the Test Suite
```bash
python -m pytest tests/ -v
# Output: 44 passed
```

### 4. Run the Benchmark Evaluation Harness
```bash
python -m evaluation.run --mode all
```

### 5. Launch the Streamlit Dashboard
```bash
streamlit run frontend/streamlit_app.py
```

### 6. Launch the FastAPI Backend
```bash
uvicorn app.main:app --reload --port 8000
```

---

## 7. 5-Minute Interview Demo Script

Follow these steps to demonstrate BugScope during an interview:

1. **Step 1: Launch Dashboard (30 seconds)**
   ```bash
   streamlit run frontend/streamlit_app.py
   ```
   Show the clean UI, explaining the dual pages ("New Investigation" and "History") and the 6 investigation tabs.

2. **Step 2: Paste a KeyError Trace (60 seconds)**
   Paste the following traceback into the error area:
   ```python
   Traceback (most recent call last):
     File "app/user.py", line 4, in format_user_profile
       email = user_dict['email']
   KeyError: 'email'
   ```
   Select `sample_bugs/bug_01_key_error` or upload its ZIP. Click **Start Investigation**.

3. **Step 3: Highlight Mechanical Evidence Verification (90 seconds)**
   - Click the **"Hypotheses & Evidence"** tab.
   - Point out:
     > *"Notice that each hypothesis lists exact line numbers and quotes. BugScope read the file on disk, normalized whitespace, and verified the quote mechanically. If an LLM hallucinates an excerpt, that evidence is thrown out and the score drops."*

4. **Step 4: Show the 3-Phase Validation Matrix (60 seconds)**
   - Click the **"Tests"** tab.
   - Point out:
     > *"We only award 'validated' because Phase 1 proved the regression test failed before the fix, Phase 2 proved it passed after the fix, and Phase 3 proved existing unit tests still pass with zero regressions."*

5. **Step 5: Show the Ambiguity Handling (60 seconds)**
   - Open History and select `bug_10_ambiguous_rounding`.
   - Point out:
     > *"When the business requirements were ambiguous, BugScope didn't guess. It returned 'needs_human_decision' with concrete options for the developer."*

---

## 8. License

BugScope is released under the MIT License. See [LICENSE](LICENSE) for details.
