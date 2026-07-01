"""pytest integration for agentcassette.

This module is loaded by pytest through the ``pytest11`` entry point declared
in ``pyproject.toml`` — it is **never** imported by ``agentcassette/__init__``,
so ``import agentcassette`` remains dependency-free. This is the one file in the
package permitted to import ``pytest`` (a test-time dependency).

Usage
-----
Wrap the callable(s) you want captured with ``agentcassette.intercept`` once,
then request the ``cassette`` fixture in a test::

    import agentcassette

    call_model = agentcassette.intercept(call_model, kind="llm")

    def test_agent(cassette):
        result = my_agent.run("find flights")
        assert result.ok

The first run records a cassette (under ``<testdir>/cassettes/``); later runs
replay it with no network or cost.

Record modes (``--record-mode`` or the ``cassette`` marker):
    once  — replay if a cassette exists, otherwise record it (default)
    none  — replay only; fail if the cassette is missing
    all   — always re-record, overwriting any existing cassette

Per-test overrides via marker::

    @pytest.mark.cassette(path="custom.json", record_mode="all",
                          strict=True, redact=["api_key"])
    def test_agent(cassette):
        ...
"""

from __future__ import annotations

import os

import pytest

from . import record, replay

RECORD_MODES = ("once", "none", "all")


def pytest_addoption(parser):
    group = parser.getgroup("agentcassette")
    group.addoption(
        "--record-mode",
        action="store",
        default=None,
        choices=list(RECORD_MODES),
        help="agentcassette record mode: once (default), none, all",
    )
    parser.addini(
        "agentcassette_dir",
        "Directory for cassette files (default: <test file dir>/cassettes)",
        default=None,
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "cassette(path=None, record_mode=None, strict=False, redact=None): "
        "configure the agentcassette `cassette` fixture for a test.",
    )


def _marker_kwargs(request) -> dict:
    marker = request.node.get_closest_marker("cassette")
    return dict(marker.kwargs) if marker is not None else {}


def _resolve_mode(request, kwargs: dict) -> str:
    mode = kwargs.get("record_mode") or request.config.getoption("--record-mode") or "once"
    if mode not in RECORD_MODES:
        raise pytest.UsageError(
            f"agentcassette: invalid record_mode {mode!r}; expected one of {RECORD_MODES}"
        )
    return mode


def _sanitize(name: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)


def _resolve_path(request, kwargs: dict) -> str:
    test_dir = os.path.dirname(str(request.node.fspath))
    custom = kwargs.get("path")
    if custom:
        return custom if os.path.isabs(custom) else os.path.join(test_dir, custom)
    base = request.config.getini("agentcassette_dir") or os.path.join(test_dir, "cassettes")
    return os.path.join(base, _sanitize(request.node.name) + ".json")


@pytest.fixture
def cassette(request):
    """Record on first run, replay afterwards.

    Yields the active :class:`agentcassette.Recorder` (while recording) or
    :class:`agentcassette.Player` (while replaying), so a test can inspect
    ``player.divergences`` etc.
    """
    kwargs = _marker_kwargs(request)
    path = _resolve_path(request, kwargs)
    mode = _resolve_mode(request, kwargs)
    strict = bool(kwargs.get("strict", False))
    redact = kwargs.get("redact")
    exists = os.path.exists(path)

    if mode == "all" or (mode == "once" and not exists):
        with record(path, redact=redact) as recorder:
            yield recorder
    elif not exists:  # mode == "none" and cassette missing
        pytest.fail(
            f"agentcassette: no cassette at {path!r} and --record-mode=none "
            f"(run once without --record-mode to create it)"
        )
    else:
        with replay(path, strict=strict) as player:
            yield player
