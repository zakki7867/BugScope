# Contributing to BugScope

Thank you for your interest in contributing to BugScope! We welcome community contributions, bug reports, and enhancements.

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/BugScope.git
   cd BugScope
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   ```

## Running Tests

Before submitting any code changes, verify that all automated unit and integration tests pass cleanly:

```bash
python -m pytest tests/ -v
```

## Running Benchmarks

BugScope maintains a 24-case benchmark in `sample_bugs/`. You can evaluate the full benchmark locally:

```bash
python -m evaluation.run --mode all
```

## Contribution Guidelines

- **Code Quality**: Keep functions modular and preserve the typed Pydantic models.
- **Evidence Verification**: Any new hypothesis or fix generation logic must respect on-disk evidence verification without assuming LLM accuracy.
- **Test Invariants**: Proposed patches must never edit existing unit tests (`test_*.py`).
- **Safety First**: Maintain strict sandbox boundaries and safe file extraction mechanisms.
- **Pull Requests**: Provide a clear description of the bug or improvement, including reproduction steps and test results.
