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
- **Interview explanation**:
  > *"FastAPI provides asynchronous request handling, automatic OpenAPI schema generation, and automatic request validation through Pydantic models."*
