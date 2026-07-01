# Changelog

All notable changes to agentcassette are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-06-30

### Added
- **pytest plugin** (auto-registered via a `pytest11` entry point) — a `cassette` fixture that records on the first run and replays afterwards, a `--record-mode` option (`once` / `none` / `all`), and a `@pytest.mark.cassette(path=..., record_mode=..., strict=..., redact=...)` marker for per-test overrides. Cassettes default to `<test dir>/cassettes/<test name>.json`.
- `pytest` optional-dependency extra (`pip install "agentcassette[pytest]"`). Importing `agentcassette` never imports pytest, so the library stays zero-dependency.
- 6 plugin tests using pytest's `pytester`

## [0.1.0] - 2026-06-30

### Added
- `intercept()` — wrap a callable so it can be recorded and replayed; transparent pass-through outside a session. Supports both sync functions and `async def` coroutine functions
- `record()` — context manager that tapes every intercepted call to a JSON cassette (written on clean exit only)
- `replay()` — context manager that serves recorded results without running the real functions
- Strict replay (`strict=True`) raising `DivergenceError` on any name/argument mismatch; best-effort mode collects divergences on the player
- `Cassette` — load/save, `num_steps`, `total_input_tokens`, `total_output_tokens`, `total_tokens`, `duration_ms`, and `redact()` for scrubbing secrets
- Record-time redaction via `record(..., redact=[...])`
- `diff_cassettes()` / `CassetteDiff` — `new_calls`, `dropped_calls`, `changed_calls`, token deltas, and `identical`
- Token accounting that prefers exact provider usage blocks (OpenAI/Anthropic) and falls back to a deterministic character heuristic
- Exception hierarchy under `AgentCassetteError`: `CassetteNotFound`, `ReplayExhausted`, `DivergenceError`
- Zero external dependencies — pure Python stdlib (3.9+)
- 44 unit tests covering sync/async record/replay, divergence, cassette inspection, diffing, token accounting, and error handling

[Unreleased]: https://github.com/aenealabs/agentcassette/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/aenealabs/agentcassette/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/aenealabs/agentcassette/releases/tag/v0.1.0
