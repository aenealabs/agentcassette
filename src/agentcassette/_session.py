"""Recording and replaying of intercepted calls.

The design is a deliberate, honest seam rather than monkey-patching: you wrap
the callables you want captured once with :func:`intercept`. A thread-local
"active session" then decides what happens each time a wrapped callable runs:

* No active session  → the real function runs (production is unaffected).
* Inside ``record()`` → the real function runs and the call is taped.
* Inside ``replay()`` → the recorded result is returned; the real function is
  never called (no network, no cost, fully deterministic).

This keeps agentcassette provider-agnostic and truly zero-dependency: it works
with OpenAI, Anthropic, a raw ``requests`` call, or a local model equally.

Both synchronous and ``async def`` callables are supported — :func:`intercept`
detects coroutine functions and returns an awaitable wrapper for them.
"""

from __future__ import annotations

import functools
import inspect
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

from ._cassette import Cassette, to_jsonable
from ._errors import DivergenceError, ReplayExhausted
from ._tokens import count_tokens

_local = threading.local()


def _current_session() -> "Recorder | Player | None":
    return getattr(_local, "session", None)


def _set_session(session: "Recorder | Player | None") -> None:
    _local.session = session


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_args(args: tuple, kwargs: dict) -> dict:
    return {"args": to_jsonable(list(args)), "kwargs": to_jsonable(dict(kwargs))}


# ---------------------------------------------------------------------------
# The interception seam
# ---------------------------------------------------------------------------
def intercept(
    fn: Callable | None = None,
    *,
    name: str | None = None,
    kind: str = "call",
) -> Callable:
    """Mark a callable as recordable/replayable.

    Usable as ``intercept(fn)``, ``intercept(fn, name=..., kind="llm")``, or as a
    decorator ``@intercept`` / ``@intercept(kind="tool")``. Works on both regular
    functions and ``async def`` coroutine functions.

    Outside of a ``record``/``replay`` block the wrapped callable behaves exactly
    like the original, so it is safe to leave in production code.
    """

    def decorator(func: Callable) -> Callable:
        call_name = name or getattr(func, "__name__", "call")

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                session = _current_session()
                if session is None:
                    return await func(*args, **kwargs)
                return await session.handle_async(call_name, kind, func, args, kwargs)

            async_wrapper.__agentcassette_intercepted__ = True  # type: ignore[attr-defined]
            return async_wrapper

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            session = _current_session()
            if session is None:
                return func(*args, **kwargs)
            return session.handle(call_name, kind, func, args, kwargs)

        wrapper.__agentcassette_intercepted__ = True  # type: ignore[attr-defined]
        return wrapper

    if fn is not None:
        return decorator(fn)
    return decorator


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------
class Recorder:
    """Captures each intercepted call into an ordered list of steps."""

    def __init__(self, *, model: str | None = None) -> None:
        self.model = model
        self.steps: list[dict] = []
        self.cassette: Cassette | None = None  # populated after the block exits

    def _append(
        self, name: str, kind: str, args: tuple, kwargs: dict, result: Any, duration_ms: float
    ) -> Any:
        arguments = _normalize_args(args, kwargs)
        jresult = to_jsonable(result)
        input_tokens, output_tokens = count_tokens(arguments, jresult)
        self.steps.append(
            {
                "index": len(self.steps),
                "type": kind,
                "name": name,
                "arguments": arguments,
                "result": jresult,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "duration_ms": round(duration_ms, 3),
            }
        )
        return result  # the live run still gets the real object

    def handle(self, name: str, kind: str, func: Callable, args: tuple, kwargs: dict) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        return self._append(name, kind, args, kwargs, result, (time.perf_counter() - start) * 1000)

    async def handle_async(
        self, name: str, kind: str, func: Callable, args: tuple, kwargs: dict
    ) -> Any:
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        return self._append(name, kind, args, kwargs, result, (time.perf_counter() - start) * 1000)


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------
class Player:
    """Serves recorded results back in order, without calling the real function."""

    def __init__(self, steps: list[dict], *, strict: bool = False) -> None:
        self._steps = steps
        self.strict = strict
        self._cursor = 0
        self.divergences: list[dict] = []

    @property
    def cursor(self) -> int:
        return self._cursor

    @property
    def remaining(self) -> int:
        return len(self._steps) - self._cursor

    def _serve(self, name: str, kind: str, args: tuple, kwargs: dict) -> Any:
        if self._cursor >= len(self._steps):
            raise ReplayExhausted(
                f"cassette recorded {len(self._steps)} calls but the agent asked for more "
                f"(next was {name!r})"
            )
        step = self._steps[self._cursor]
        self._cursor += 1

        actual = {"name": name, "arguments": _normalize_args(args, kwargs)}
        expected = {"name": step.get("name"), "arguments": step.get("arguments")}
        if expected != actual:
            if self.strict:
                raise DivergenceError(step.get("index", self._cursor - 1), expected, actual)
            self.divergences.append(
                {"index": step.get("index"), "expected": expected, "actual": actual}
            )
        return step.get("result")

    def handle(self, name: str, kind: str, func: Callable, args: tuple, kwargs: dict) -> Any:
        return self._serve(name, kind, args, kwargs)

    async def handle_async(
        self, name: str, kind: str, func: Callable, args: tuple, kwargs: dict
    ) -> Any:
        return self._serve(name, kind, args, kwargs)


# ---------------------------------------------------------------------------
# Context managers
# ---------------------------------------------------------------------------
@contextmanager
def record(
    path,
    *,
    model: str | None = None,
    redact: "list[str] | None" = None,
) -> Iterator[Recorder]:
    """Record every intercepted call made inside the block to a cassette file.

    The cassette is written on clean exit only; if the block raises, nothing is
    saved. Pass ``redact=["api_key", ...]`` to scrub those keys before writing.
    """
    if _current_session() is not None:
        raise RuntimeError("agentcassette: a record/replay session is already active")
    recorder = Recorder(model=model)
    _set_session(recorder)
    start = time.perf_counter()
    try:
        yield recorder
    except BaseException:
        _set_session(None)
        raise
    _set_session(None)

    duration_ms = (time.perf_counter() - start) * 1000
    cassette = Cassette(
        steps=recorder.steps,
        model=model,
        recorded_at=_now_iso(),
        duration_ms=round(duration_ms, 3),
    )
    for key in redact or []:
        cassette.redact(key)
    cassette.save(path)
    recorder.cassette = cassette


@contextmanager
def replay(path, *, strict: bool = False) -> Iterator[Player]:
    """Replay a cassette: intercepted calls return recorded results, no real work.

    With ``strict=True`` any call whose name or arguments differ from the
    recording raises :class:`DivergenceError`. With ``strict=False`` (default)
    divergences are collected on the yielded player's ``divergences`` list.
    """
    if _current_session() is not None:
        raise RuntimeError("agentcassette: a record/replay session is already active")
    cassette = Cassette.load(path)
    player = Player(cassette.steps, strict=strict)
    _set_session(player)
    try:
        yield player
    finally:
        _set_session(None)
