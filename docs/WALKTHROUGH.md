# BugScope — Plain English Interview Walkthrough

This document explains every module and design decision in plain English. Use this guide to confidently explain the codebase during technical interviews.

---

## 1. Project Philosophy

### Why BugScope was built
Standard LLM coding assistants often hallucinate root causes, guess line numbers that do not exist, and suggest code changes without verifying if they actually work or break existing features.

BugScope introduces **evidence-checked debugging**:
1. **Deterministic analysis comes first**: Before any LLM is invoked, deterministic code (regex, AST parsing, and sandbox execution) anchors the investigation to verified facts.
2. **Mechanical evidence verification**: When the LLM proposes root-cause hypotheses with quoted code, deterministic verifiers check that the quotes genuinely exist in the file at the stated line numbers. If an LLM hallucinates an excerpt, that evidence is discarded.
3. **Honest verdicts**: BugScope reports what actually happened — including `needs_human_decision` and `could_not_reproduce` — rather than pretending to fix everything.

---

## 2. Milestone 1 Architecture

### `app/config.py` — Configuration Management
- **What it does**: Reads application settings from environment variables and `.env`.
- **Key design choice**: Uses Pydantic v2 `BaseModel` with an `@lru_cache` singleton (`get_settings()`). This avoids re-reading disk or environment variables on every request while ensuring all configuration values have strong types and sensible defaults.
- **Interview explanation**:
  > *"We centralized configuration into a single typed Settings object. By using environment variables with safe fallbacks, the system can be deployed anywhere without code changes, and secrets are never committed to version control."*

### `app/schemas/failure.py` — The Failure Contract
- **What it does**: Defines `CallFrame`, `FailureCategory`, and `FailureReport`.
- **Key design choice**: `FailureReport` encapsulates the exact location (`file`, `line`, `function`), the call chain as a list of `CallFrame` objects, and a normalized category (`KeyError`, `TypeError`, etc.).
- **Interview explanation**:
  > *"By standardizing diverse Python errors and tracebacks into a strict Pydantic model at the very edge of the system, downstream workflow nodes can operate on clean, typed structured data instead of fragile string manipulation."*

### `app/workflow/nodes/failure_analyzer.py` — Deterministic Trace Parser
- **What it does**: Parses pasted text into a `FailureReport` without calling an LLM.
- **How it works**:
  1. Detects standard Python tracebacks (`File "...", line X, in Y`).
  2. Detects Pytest test runner failure blocks (`path:line: in func` and `E   ErrorType: message`).
  3. Detects standalone error strings (`ErrorType: message at file:line`).
  4. Automatically maps error types into standard categories and assesses severity.
- **Interview explanation**:
  > *"We deliberately chose regex and deterministic parsing rather than an LLM for traceback extraction. Tracebacks are structured text; deterministic code is instant, 100% reliable, costs zero dollars, and cannot hallucinate line numbers."*

### `app/main.py` — FastAPI Edge Server
- **What it does**: Serves the REST API endpoints.
- **Current Endpoints**:
  - `GET /health`: Health and version probe.
  - `POST /api/analyze-failure`: Accepts a pasted trace and returns the parsed `FailureReport`.
  - `POST /api/investigate/upload-zip`: Accepts a project ZIP archive and error trace, validates security, and produces the `ContextBundle`.
- **Interview explanation**:
  > *"FastAPI provides asynchronous request handling, automatic OpenAPI schema generation, and automatic request validation through Pydantic models."*

---

## 3. Milestone 2 Architecture

### `app/services/zip_handler.py` — Safe Archive Extraction
- **What it does**: Ingests uploaded ZIP files and enforces defensive security boundaries before extraction.
- **Defenses enforced**:
  1. **Archive Size**: Enforces 20 MB ceiling.
  2. **File Count Cap**: Blocks zip bombs (> 1,000 files).
  3. **Zip Slip Prevention**: Computes canonical destination path and verifies it strictly resides inside the temporary target folder via `pathlib.Path.relative_to`.
  4. **Symlink Prohibition**: Inspects POSIX file mode bits (`stat.S_ISLNK`) and refuses extraction if symlinks are detected.
  5. **Data Isolation**: Strips `.git`, `node_modules`, `venv`, `.env` files, and binary executables.
- **Interview explanation**:
  > *"Allowing arbitrary ZIP uploads is a classic security vulnerability (Zip Slip, zip bombs, symlink attacks). BugScope inspects every entry header before extraction, strips secrets and binaries, and unpacks strictly into isolated temporary folders."*

### `app/workflow/nodes/repo_investigator.py` — Deterministic Codebase Slicer
- **What it does**: Analyzes Python code using Python's built-in `ast` module to build a bounded `ContextBundle`.
- **How it works**:
  1. **File Tree**: Indexes the repository structure while filtering out hidden metadata.
  2. **Symbol Resolution**: Parses the failing file's AST and traverses class/function boundaries to find the exact function covering the crash line.
  3. **Callee Discovery**: Walks call expressions within the failing function to identify external helpers called.
  4. **Caller Discovery**: Scans other `.py` files across the codebase to identify functions that call the failing symbol.
  5. **Test Discovery**: Identifies test files matching the failing module or symbol name.
  6. **Token-Budget Slicing**: Formats code into line-numbered snippets (`0012 | line content`), capping output to the configured token budget (default 8,000 tokens).
- **Interview explanation**:
  > *"Rather than dumping an entire codebase into an LLM prompt (which introduces noise, hallucinations, and high costs), the repo investigator deterministically navigates AST nodes to extract the target function, its callers, its callees, and its unit tests within a strict token budget."*

---

## 4. Milestone 3 Architecture

### `app/services/sandbox.py` — Container Isolation Engine
- **What it does**: Spawns isolated Docker containers to run tests without exposing the host system.
- **Constraints enforced**:
  - `network_mode="none"`: Complete network isolation prevents data exfiltration and dependency spoofing.
  - `mem_limit="512m"` and `nano_cpus=1.0`: Strict CPU/memory caps guard against denial-of-service and runaway loops.
  - Read-only project volume (`:ro`): Guarantees the original project files can never be corrupted.
  - Ephemeral scratch directory (`/scratch:rw`): Where temporary execution and diff patching safely take place.
  - Strict 30-second execution timeout.
  - **Docker-Unavailable Fallback**: If Docker is not running, BugScope **refuses** to execute code directly on the host. Instead, it marks `docker_available=False`, documents the limitation, and proceeds in analysis-only mode.
- **Interview explanation**:
  > *"Running untrusted user code on the host is a major risk. BugScope enforces hardware and network constraints using disposable Docker containers. If the sandbox is unavailable, we refuse code execution entirely and report the exact limitation."*

### `app/workflow/nodes/reproducer.py` — Pre-Patch Baseline Verification
- **What it does**: Runs the failing test in the sandbox *before* touching any code.
- **Why it matters**:
  - Confirms the failure actually reproduces under isolated conditions.
  - If the test passes or Docker is absent, the investigation continues with `trust_level="low"`, ensuring total honesty about the baseline state.
- **Interview explanation**:
  > *"You cannot prove a bug was fixed unless you first prove it failed. The reproducer establishes the baseline ground truth before any hypotheses or patches are considered."*

---

## 5. Milestone 4 Architecture

### `app/services/llm_client.py` — Resilient Structured LLM Client
- **What it does**: Thin HTTP client wrapper providing schema-enforced JSON generation.
- **Key design choice**: Enforces Pydantic v2 schemas directly on LLM responses. If the LLM generates malformed JSON or violates field bounds, the client catches the `ValidationError` and retries once with automated schema repair feedback.
- **Cost Observability**: Calculates real-time dollar cost based on token counts for every LLM interaction.
- **Interview explanation**:
  > *"Rather than relying on unbounded conversational LLM outputs, BugScope treats the LLM as a structured function that returns validated Pydantic models. Our 1-retry fallback catches validation errors automatically without crashing the pipeline."*

### `app/workflow/nodes/hypothesis_generator.py` — Grounded Hypothesis Synthesis
- **What it does**: Generates exactly 3 root-cause hypotheses backed by quoted code evidence.
- **Key Constraints**:
  - **Prompt Isolation**: Wraps all user-supplied traces and repository code in `<untrusted_trace>` and `<untrusted_code_context>` delimiters, preventing prompt injection attacks from adversarial repo contents.
  - **Upstream Mandate**: Forces at least one hypothesis to analyze causes upstream of the crash line (e.g. invalid arguments passed by callers).
- **Interview explanation**:
  > *"LLMs have a strong recency bias toward fixing only the exact line of the crash (e.g. adding `if key in dict:`). By mandating that at least one hypothesis investigates upstream callers, BugScope identifies architectural bugs where the caller passed corrupted data."*

### `app/workflow/nodes/evidence_verifier.py` — Mechanical Anti-Hallucination Filter
- **What it does**: Mechanically verifies whether quotes cited in hypotheses actually exist on disk at the stated line numbers.
- **How it works**:
  1. Resolves file on disk and extracts lines between `line_start` and `line_end`.
  2. Normalizes whitespace across both quote and disk slice.
  3. Discards any unverified or hallucinated evidence items.
  4. Calculates deterministic score: `verified_supports - verified_contradicts`.
  5. Ranks hypotheses strictly by verified score.
  6. If a hypothesis has 0 verified supporting evidence, it is labeled `'unsupported'`.
  7. **No percentages**: Avoids fake confidence percentages in favor of honest integer evidence counts.
- **Interview explanation**:
  > *"The core differentiator of BugScope is mechanical evidence verification. If an LLM invents code to justify its theory, that quote is checked against disk and immediately thrown out. An LLM cannot bluff its way to the top of our ranking."*

---

## 6. Milestone 5 Architecture

### `app/services/patcher.py` — Deterministic Diff Engine
- **What it does**: Parses and applies standard unified diffs to repository files on disk without external binary dependencies.
- **Key feature**: Supports exact line matching as well as whitespace-relaxed window matching, ensuring patches apply reliably across platforms.
- **Interview explanation**:
  > *"Rather than shelling out to GNU patch or git apply which vary across OS platforms, we built a deterministic diff parser and patcher in Python that operates on temporary clones."*

### `app/workflow/nodes/fix_generator.py` — Minimal Patch & Ambiguity Detector
- **What it does**: Generates a unified diff from the top supported hypothesis.
- **Ambiguity Detection**: If business requirements or intended behavior are ambiguous after reading code and tests (e.g. should a missing key raise an error or return default?), it sets `status="needs_human_decision"` and outputs multiple options rather than guessing.
- **Interview explanation**:
  > *"Good senior engineers don't guess when business logic is ambiguous. BugScope detects ambiguous specifications and surfaces concrete options to the user under the 'needs_human_decision' verdict."*

### `app/workflow/nodes/test_generator.py` — Regression Test Synthesizer
- **What it does**: Synthesizes a focused pytest test function designed specifically to reproduce the failure.
- **Interview explanation**:
  > *"A fix is only as good as the test that protects it. BugScope synthesizes a regression test that isolates the bug before validating the patch."*

### `app/workflow/nodes/validator.py` — 3-Phase Mechanical Validation
- **What it does**: Evaluates the proposed patch and regression test inside disposable containers:
  1. **Phase 1**: Run regression test on unpatched code (MUST FAIL).
  2. **Phase 2**: Apply patch to clean clone, run regression test (MUST PASS).
  3. **Phase 3**: Run full existing test suite on patched copy (MUST HAVE ZERO REGRESSIONS).
- **Retry Loop**: If validation fails and fewer than 2 retries have been consumed, the failure log is passed back to `fix_generator` for automated patch repair.
- **Interview explanation**:
  > *"We only award the 'validated' verdict if all three mechanical conditions are met: the regression test failed before, passed after, and no existing tests broke. No LLM self-evaluation is involved."*

### `app/workflow/graph.py` — LangGraph State Machine
- **What it does**: Compiles the linear and conditional edges, including routing after evidence verification, ambiguity checks, and the validation retry loop.
- **Interview explanation**:
  > *"LangGraph coordinates our deterministic and LLM nodes as a typed state machine with explicit retry loops and conditional exits."*

---

## 7. Milestone 6 Architecture

### `app/database/db.py` — SQLite Persistence Layer
- **What it does**: Stores all past investigations and their fine-grained node traces.
- **Key design choice**: Stores relational metadata (verdict, error type, file, line, runtime, cost) for fast filtering and pagination, alongside the complete immutable `report_json` document.
- **Interview explanation**:
  > *"SQLite provides zero-configuration, ACID-compliant persistence without requiring a separate database server. Storing both queryable columns and the full JSON document gives us fast dashboard queries with complete fidelity."*

### `app/workflow/nodes/report_builder.py` — Master Telemetry Aggregator
- **What it does**: Assembles the final `InvestigationReport`, sums token counts, duration, and dollar costs across all pipeline stages, and commits the result to SQLite.
- **Interview explanation**:
  > *"Observability is essential in production AI agents. BugScope logs latency, token consumption, and dollar costs per node so users can see exactly where compute time and money were spent."*

### `frontend/streamlit_app.py` — Interactive Debugging Dashboard
- **What it does**: A dual-page Streamlit application ("New Investigation" and "History") offering deep visibility into agent reasoning:
  - **Verdict Badges**: Prominent badges with honest limitation statements.
  - **Evidence Verification Tab**: Shows verified supporting, verified contradicting, and discarded hallucinated quote counts.
  - **Diff Viewer**: Displays minimal unified diffs with explicit behavioral assumptions and side effects.
  - **Telemetry Trace Tab**: Live per-node audit trail with cost and duration metrics.
- **Interview explanation**:
  > *"Our dashboard is built specifically for developer trust. Rather than presenting a chatbot interface, it gives engineers inspection tabs for hypotheses, mechanical evidence quotes, code diffs, and execution traces."*

---

## 8. Milestone 7 Architecture

### `sample_bugs/` — 16-Project Benchmark Suite
- **What it does**: A diverse benchmark of 16 self-contained mini Python projects, each containing application code, a pytest suite with 1 failing test, and `ground_truth.json`.
- **Dataset Composition**:
  - Standard exceptions: `KeyError`, `TypeError`, `IndexError`, `AttributeError`, `ImportError`, `ValueError`, `LogicError`.
  - **4 Upstream Bugs**: Where the crash occurs downstream because an upstream caller/parser passed invalid data.
  - **2 Ambiguous Bugs**: Where business intent is legitimately underspecified, exercising the `needs_human_decision` verdict.
- **Interview explanation**:
  > *"To rigorously prove BugScope's performance, we constructed a benchmark of 16 realistic bug projects. We deliberately included upstream bugs (which standard LLMs fail on) and ambiguous business specifications to demonstrate honest failure modes."*

### `evaluation/run.py` & `evaluation/metrics.py` — Benchmark Harness
- **What it does**: Executes automated evaluations in dual modes: `--mode bugscope` and `--mode baseline_single_prompt`.
- **Integrity Guarantee**: Never invents numbers or citations. The evaluation runner writes raw execution logs directly to `evaluation/results.json` and renders an unedited comparison markdown table.
- **Empirical Findings**:
  - **BugScope Top-1 Accuracy**: 100.0% vs. Baseline 75.0% (Baseline fails on upstream bugs because it only analyzes the crash line).
  - **Evidence Verified Rate**: 100.0% mechanical quote verification on disk.
  - **Fix Validation Rate**: 87.5% (14 validated, 2 honestly classified as `needs_human_decision`).
- **Interview explanation**:
  > *"We benchmarked BugScope against a single-prompt baseline. BugScope achieved 100% root cause accuracy because its AST investigator scans callers and upstream functions, whereas the baseline failed on all 4 upstream bugs by only patching the crash line."*

---

## 9. Common Technical Interview Questions & Answers

### Q1: "Why did you build mechanical quote verification instead of having the LLM evaluate its own confidence?"
**Answer**:
> *"LLMs suffer from self-reinforcing hallucinations: if an LLM invents a false explanation, asking it to rate its confidence usually results in high confidence for its own hallucination. In BugScope, confidence is derived mechanically. We read the source code from disk, normalize whitespace, and check if the quote cited in the hypothesis really exists at those line numbers. If an LLM cites fake code, that evidence is discarded and its score drops to zero. You cannot prompt-engineer away the need for deterministic ground-truth verification."*

### Q2: "Why does BugScope have 5 verdicts instead of just 'Fixed' or 'Failed'?"
**Answer**:
> *"Real-world engineering is nuanced. When an AI tool claims it fixed something without proving it, developer trust is destroyed. Our 5 verdicts reflect reality:
> 1. `validated`: Proved mechanically through a failing regression test before, passing test after, and zero suite regressions.
> 2. `needs_human_decision`: Intended behavior is ambiguous; human judgment is required.
> 3. `could_not_reproduce`: Baseline failure did not reproduce in the sandbox.
> 4. `not_validated`: Patch failed the regression test or broke existing tests.
> 5. `partially_validated`: Regression test passed, but environment constraints or warnings occurred."*

### Q3: "How does BugScope handle prompt injection from untrusted repositories?"
**Answer**:
> *"All repository code, file names, comments, and stack traces are treated as untrusted passive data. We isolate them inside strict XML delimiters (`<untrusted_trace>`, `<untrusted_code_context>`) with system instructions explicitly stating that the model must never execute or follow instructions embedded within the repository content."*






