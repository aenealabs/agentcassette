# agentcassette

[![PyPI](https://img.shields.io/pypi/v/agentcassette?color=blue)](https://pypi.org/project/agentcassette/)
[![Python](https://img.shields.io/pypi/pyversions/agentcassette)](https://pypi.org/project/agentcassette/)
[![CI](https://img.shields.io/github/actions/workflow/status/aenealabs/agentcassette/ci.yml?label=CI)](https://github.com/aenealabs/agentcassette/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Zero dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)](pyproject.toml)

**Deterministic agent test recorder and replayer.**

Record a real agent run once, replay it forever as a mock — no network, no cost, fully deterministic. Like VCR/pytest-recording, but purpose-built for LLM agents and with zero dependencies.

```python
import agentcassette
from agentcassette import record, replay

call_model = agentcassette.intercept(call_model, kind="llm")

# Record a real run once:
with record("cassettes/flight_search.json"):
    my_agent.run("Find flights to NYC under $300")

# Replay it in tests — no API calls, no tokens spent, same result every time:
def test_flight_search():
    with replay("cassettes/flight_search.json"):
        result = my_agent.run("Find flights to NYC under $300")
    assert result.success
```

## Why agentcassette?

Testing agents is painful. Live LLM calls are **expensive** (every test run costs money), **non-deterministic** (a different answer each time), and **slow** (seconds per call). So most teams either skip agent testing or maintain a costly, flaky integration suite.

agentcassette records the real calls an agent makes into a plain-JSON **cassette**, then replays them on demand. Your tests become fast, free, and deterministic — and you can assert on exactly what the agent did.

Unlike VCR-style tools that monkey-patch the HTTP layer, agentcassette uses an explicit, honest seam: you wrap the callables you want captured. That keeps it **provider-agnostic** (OpenAI, Anthropic, Gemini, a raw `requests` call, or a local model all work identically) and **truly zero-dependency**.

## Installation

```bash
pip install agentcassette
```

Requires Python 3.9+. No other dependencies, ever.

## Quick Start

### 1. Wrap what you want captured

Wrap your model-call function once (and any tools you want taped). Outside a record/replay block, wrapped callables behave exactly like the original — safe to leave in production code.

```python
import agentcassette

# As a wrapper:
call_model = agentcassette.intercept(call_model, kind="llm")

# Or as a decorator:
@agentcassette.intercept(kind="tool")
def search_web(query: str) -> list[str]:
    ...
```

### 2. Record a real run

```python
from agentcassette import record

with record("cassettes/flight_search.json", model="claude-sonnet-4-6"):
    my_agent.run("Find flights to NYC under $300")
# Cassette is written on clean exit.
```

### 3. Replay it in your tests

```python
from agentcassette import replay

def test_flight_search():
    with replay("cassettes/flight_search.json"):
        result = my_agent.run("Find flights to NYC under $300")
    assert result.success
```

During replay, every intercepted call returns its recorded result and the real function is **never called**.

## Async agents

`intercept` detects `async def` callables and returns an awaitable wrapper, so async agents work the same way — including a mix of async and sync tools in one run:

```python
import agentcassette
from agentcassette import record, replay

acall_model = agentcassette.intercept(acall_model, kind="llm")  # an async def

async def agent(task):
    plan = await acall_model(f"plan: {task}")
    ...

with record("cassettes/run.json"):
    asyncio.run(agent("book a trip"))

with replay("cassettes/run.json"):
    asyncio.run(agent("book a trip"))   # awaited calls served from the cassette
```

## Catching regressions with strict replay

By default, replay serves recorded results best-effort and collects any divergences. With `strict=True`, a call whose name or arguments differ from the recording raises `DivergenceError` — turning your cassette into a behavioral contract.

```python
from agentcassette import replay, DivergenceError

with replay("cassettes/flight_search.json", strict=True):
    my_agent.run("Find flights to NYC under $300")   # raises on drift
```

Best-effort mode exposes what changed without failing:

```python
with replay("cassettes/flight_search.json") as player:
    my_agent.run("Find flights to NYC under $300")

for d in player.divergences:
    print(d["index"], d["expected"], "->", d["actual"])
```

## Inspecting cassettes

```python
from agentcassette import Cassette

c = Cassette.load("cassettes/flight_search.json")
c.num_steps            # number of intercepted calls
c.total_input_tokens   # summed across steps
c.total_output_tokens
c.total_tokens
c.duration_ms          # wall time of the original run

c.redact("api_key")    # scrub secrets before committing to git
c.save("cassettes/flight_search.json")
```

Token counts use exact usage blocks when the recorded response carries one (OpenAI `usage.prompt_tokens`, Anthropic `usage.input_tokens`, …), falling back to a deterministic ~4-chars-per-token heuristic otherwise.

## Redacting secrets

Scrub sensitive keys either when recording or after loading:

```python
# At record time:
with record("cassettes/run.json", redact=["api_key", "authorization"]):
    my_agent.run(task)

# Or later:
Cassette.load("cassettes/run.json").redact("api_key").save("cassettes/run.json")
```

## Diffing runs

Compare two cassettes to see how an agent's behavior drifted between versions:

```python
from agentcassette import diff_cassettes

delta = diff_cassettes("cassettes/v1.json", "cassettes/v2.json")
delta.new_calls          # call names in v2 but not v1
delta.dropped_calls      # call names in v1 but not v2
delta.changed_calls      # same-position steps whose args/results changed
delta.token_delta        # total token change (v2 - v1)
delta.identical          # True if nothing changed
```

## Cassette format

Cassettes are plain, human-readable JSON — diffable and safe to commit:

```json
{
  "version": 1,
  "recorded_at": "2026-06-30T12:00:00Z",
  "model": "claude-sonnet-4-6",
  "duration_ms": 1832.4,
  "steps": [
    {
      "index": 0,
      "type": "llm",
      "name": "call_model",
      "arguments": {"args": ["plan the task"], "kwargs": {}},
      "result": {"text": "...", "usage": {"input_tokens": 420, "output_tokens": 88}},
      "input_tokens": 420,
      "output_tokens": 88,
      "duration_ms": 512.0
    }
  ]
}
```

Every intercepted call becomes one step, in the exact order it happened.

## API Reference

### `intercept(fn=None, *, name=None, kind="call")`

Marks a callable as recordable/replayable. Usable as `intercept(fn)`, `intercept(fn, kind="llm")`, or as a decorator. Works on both regular functions and `async def` coroutine functions (async callables get an awaitable wrapper). `kind` is a free-form label stored on each step (e.g. `"llm"`, `"tool"`). Outside a session, the wrapped callable is a transparent pass-through.

### `record(path, *, model=None, redact=None)`

Context manager. Records every intercepted call made inside the block to `path`, written on clean exit only. `redact` is a list of key names to scrub before saving. Yields the `Recorder`.

### `replay(path, *, strict=False)`

Context manager. Serves recorded results for intercepted calls without running the real functions. `strict=True` raises `DivergenceError` on any mismatch. Yields the `Player` (with `.divergences`, `.remaining`, `.cursor`).

### `Cassette`

| Member | Description |
|---|---|
| `Cassette.load(path)` | Load from disk (raises `CassetteNotFound`) |
| `.save(path)` | Write pretty-printed JSON, creating parent dirs |
| `.num_steps` | Number of recorded steps |
| `.total_input_tokens` / `.total_output_tokens` / `.total_tokens` | Token totals |
| `.duration_ms` | Wall time of the recorded run |
| `.redact(key, replacement="****")` | Scrub every value under `key`, at any depth |

### `diff_cassettes(a, b) -> CassetteDiff`

Compare two cassettes (paths or `Cassette` objects). Returns a `CassetteDiff` with `new_calls`, `dropped_calls`, `changed_calls`, `token_delta`, `input_token_delta`, `output_token_delta`, `step_delta`, and `identical`.

### Exceptions

All inherit from `AgentCassetteError`:

| Exception | Raised when |
|---|---|
| `CassetteNotFound` | Replaying a path that doesn't exist |
| `ReplayExhausted` | The agent makes more calls than the cassette recorded |
| `DivergenceError` | A strict replay sees a call that differs from the recording |

## Notes & limitations

- **Replayed results are JSON.** Recorded values round-trip through JSON, so on replay you get plain dicts/lists/primitives, not the original SDK objects. For typical LLM responses (dicts) this is exactly what you want.
- **Ordering matters.** Calls replay in the order they were recorded. agentcassette matches sequentially, which is deterministic and mirrors how an agent actually executes. Truly concurrent calls (e.g. `asyncio.gather`) are recorded in completion order; if that order isn't stable across runs, replay matching is best-effort — record such sections sequentially if you need strict determinism.
- **Sync and async.** Both `def` and `async def` callables are supported. `record`/`replay` are thread-local and cover the event loop running on that thread; wrap per-thread if your agent fans out across OS threads.
- **Streaming responses** (token iterators) are not specially handled yet — wrap at a boundary where the response is already materialized.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).

---

Part of the [aenealabs](https://github.com/aenealabs) AI agent toolkit.
