"""
agentcassette — Deterministic agent test recorder and replayer.

Zero dependencies. Pure Python stdlib.

Testing agents is painful: live LLM calls are expensive, non-deterministic, and
slow. agentcassette records a real run once, then replays it forever from a JSON
"cassette" — no network, no cost, fully deterministic.

Quick start
-----------
Wrap the callable(s) you want captured once (your model-call function, and
optionally your tools), then drive recording and replay with context managers::

    import agentcassette
    from agentcassette import record, replay

    call_model = agentcassette.intercept(call_model, kind="llm")

    # Record a real run:
    with record("cassettes/flight_search.json"):
        my_agent.run("Find flights to NYC under $300")

    # Replay it in a test — no API calls happen:
    def test_flight_search():
        with replay("cassettes/flight_search.json"):
            result = my_agent.run("Find flights to NYC under $300")
        assert result.success

Catch regressions with strict replay::

    from agentcassette import replay, DivergenceError

    with replay("cassettes/flight_search.json", strict=True):
        my_agent.run("Find flights to NYC under $300")   # DivergenceError on drift

Inspect and diff cassettes::

    from agentcassette import Cassette, diff_cassettes

    c = Cassette.load("cassettes/flight_search.json")
    c.num_steps, c.total_input_tokens, c.total_output_tokens
    c.redact("api_key")                       # scrub secrets before committing

    delta = diff_cassettes("cassettes/v1.json", "cassettes/v2.json")
    delta.new_calls, delta.dropped_calls, delta.token_delta

See the project README for the full cassette format and API reference.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _version

from ._cassette import Cassette
from ._diff import CassetteDiff, diff_cassettes
from ._errors import (
    AgentCassetteError,
    CassetteNotFound,
    DivergenceError,
    ReplayExhausted,
)
from ._session import Player, Recorder, intercept, record, replay

__all__ = [
    "record",
    "replay",
    "intercept",
    "Cassette",
    "Recorder",
    "Player",
    "diff_cassettes",
    "CassetteDiff",
    "AgentCassetteError",
    "CassetteNotFound",
    "ReplayExhausted",
    "DivergenceError",
]

try:
    __version__ = _version("agentcassette")
except PackageNotFoundError:  # running from a source tree without install metadata
    __version__ = "0.0.0"
