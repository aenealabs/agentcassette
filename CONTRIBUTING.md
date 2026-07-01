# Contributing to agentcassette

Thank you for taking the time to contribute.

## Ground rules

- **Zero external dependencies.** agentcassette must remain pure Python stdlib. PRs that introduce any third-party import will not be merged.
- **Python 3.9+.** All code must run on Python 3.9 through the latest stable release.
- **Tests required.** Every new feature or bug fix must include a corresponding test. The CI matrix runs on 3 operating systems × 5 Python versions — please run tests locally before opening a PR.
- **Keep it focused.** agentcassette does one thing: record and replay agent runs deterministically. Feature requests outside that scope belong in a separate package.

## Setting up a development environment

```bash
git clone https://github.com/aenealabs/agentcassette
cd agentcassette
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Running tests

```bash
pytest tests/ -v
```

To run against a specific Python version, use `hatch`:

```bash
pip install hatch
hatch run test
```

## Architecture

agentcassette is small and layered — read the modules in this order:

1. `src/agentcassette/_errors.py` — the exception hierarchy.
2. `src/agentcassette/_tokens.py` — token accounting (exact usage blocks, else heuristic).
3. `src/agentcassette/_cassette.py` — the on-disk JSON format, load/save/redact, JSON coercion.
4. `src/agentcassette/_session.py` — the thread-local session, `intercept()` seam, `Recorder`, `Player`, and the `record`/`replay` context managers.
5. `src/agentcassette/_diff.py` — cassette comparison.
6. `src/agentcassette/__init__.py` — the public surface.

## Adding a feature

1. Implement it in the appropriate `_*.py` module.
2. Export it from `__init__.py` (and add to `__all__`) if it is public.
3. Add tests under `tests/` covering the new behavior, including edge cases.
4. Update `README.md` and `CHANGELOG.md`.

## Submitting a pull request

1. Fork the repository and create a branch: `git checkout -b fix/my-fix` or `feat/my-feature`.
2. Make your changes and add tests.
3. Run `pytest tests/ -v` — all tests must pass.
4. Open a pull request against `main` with a clear description of what changed and why.

## Reporting bugs

Open an issue using the **Bug report** template. Include the Python version, OS, a minimal agent/callable, and the full traceback.

## Suggesting features

Open an issue using the **Feature request** template. Explain the use case, not just the solution.

## Code style

agentcassette uses no formatter or linter by choice to keep contributor setup minimal. Please follow the style of the surrounding code: 4-space indentation, descriptive variable names, module-level docstrings on every file.
