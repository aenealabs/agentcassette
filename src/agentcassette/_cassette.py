"""The Cassette: agentcassette's on-disk recording format.

A cassette is a plain, human-readable JSON file — readable in a diff, safe to
commit to git, and portable across machines. Its shape:

    {
      "version": 1,
      "recorded_at": "2026-06-30T12:00:00Z",
      "model": "claude-sonnet-4-6",      # optional label
      "duration_ms": 1832.4,             # wall time of the whole recorded run
      "steps": [
        {
          "index": 0,
          "type": "llm",                 # "llm" | "tool" | "call"
          "name": "call_model",
          "arguments": {"args": [...], "kwargs": {...}},
          "result": {...},
          "input_tokens": 420,
          "output_tokens": 88,
          "duration_ms": 512.0
        }
      ]
    }

Every intercepted call becomes one step, in the exact order it happened.
"""

from __future__ import annotations

import json
import os
from typing import Any

from ._errors import CassetteNotFound

CASSETTE_VERSION = 1
REDACTION_PLACEHOLDER = "****"


def to_jsonable(obj: Any) -> Any:
    """Coerce an arbitrary value into something ``json.dumps`` accepts.

    JSON-native values pass through unchanged. Sets and tuples become lists.
    Objects are reduced to their ``__dict__`` when available, otherwise their
    ``repr`` wrapped in a marker so the cassette stays valid JSON.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in obj]
    # Common SDK response objects expose their fields via model_dump()/dict().
    for method in ("model_dump", "dict", "to_dict"):
        fn = getattr(obj, method, None)
        if callable(fn):
            try:
                return to_jsonable(fn())
            except Exception:  # pragma: no cover - defensive
                break
    data = getattr(obj, "__dict__", None)
    if isinstance(data, dict) and data:
        return {"__type__": type(obj).__name__, **{str(k): to_jsonable(v) for k, v in data.items()}}
    return {"__repr__": repr(obj)}


def _redact_in_place(obj: Any, key: str, replacement: str) -> None:
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            if k == key:
                obj[k] = replacement
            else:
                _redact_in_place(obj[k], key, replacement)
    elif isinstance(obj, list):
        for item in obj:
            _redact_in_place(item, key, replacement)


class Cassette:
    """An ordered recording of intercepted calls.

    Usually produced by :func:`agentcassette.record` and consumed by
    :func:`agentcassette.replay`, but can also be loaded directly for inspection.
    """

    def __init__(
        self,
        steps: list[dict] | None = None,
        *,
        model: str | None = None,
        recorded_at: str | None = None,
        duration_ms: float = 0.0,
        version: int = CASSETTE_VERSION,
    ) -> None:
        self.version = version
        self.recorded_at = recorded_at
        self.model = model
        self.duration_ms = duration_ms
        self.steps: list[dict] = steps if steps is not None else []

    # ---- persistence ----------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict) -> "Cassette":
        return cls(
            steps=list(data.get("steps", [])),
            model=data.get("model"),
            recorded_at=data.get("recorded_at"),
            duration_ms=data.get("duration_ms", 0.0),
            version=data.get("version", CASSETTE_VERSION),
        )

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "recorded_at": self.recorded_at,
            "model": self.model,
            "duration_ms": self.duration_ms,
            "steps": self.steps,
        }

    @classmethod
    def load(cls, path: str | os.PathLike) -> "Cassette":
        """Load a cassette from disk. Raises :class:`CassetteNotFound` if absent."""
        if not os.path.exists(path):
            raise CassetteNotFound(f"No cassette at {os.fspath(path)!r}")
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    def save(self, path: str | os.PathLike) -> None:
        """Write the cassette to disk as pretty-printed JSON, creating dirs."""
        parent = os.path.dirname(os.fspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    # ---- inspection -----------------------------------------------------
    @property
    def num_steps(self) -> int:
        return len(self.steps)

    @property
    def total_input_tokens(self) -> int:
        return sum(int(s.get("input_tokens", 0)) for s in self.steps)

    @property
    def total_output_tokens(self) -> int:
        return sum(int(s.get("output_tokens", 0)) for s in self.steps)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def redact(self, key: str, replacement: str = REDACTION_PLACEHOLDER) -> "Cassette":
        """Replace every value stored under ``key`` (at any depth). Returns self."""
        for step in self.steps:
            _redact_in_place(step, key, replacement)
        return self

    def __len__(self) -> int:
        return len(self.steps)

    def __repr__(self) -> str:
        return (
            f"Cassette(steps={self.num_steps}, "
            f"input_tokens={self.total_input_tokens}, "
            f"output_tokens={self.total_output_tokens})"
        )
