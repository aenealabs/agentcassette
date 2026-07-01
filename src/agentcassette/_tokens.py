"""Token accounting for recorded steps.

agentcassette has zero dependencies, so it cannot call a real tokenizer
(``tiktoken`` and friends are third-party). Instead it:

1. Prefers exact counts when the recorded response carries a usage block
   (OpenAI ``usage.prompt_tokens`` / Anthropic ``usage.input_tokens`` etc.).
2. Falls back to a character-length heuristic (~4 chars per token), which is
   accurate enough for budgeting and regression comparisons.

The heuristic is intentionally simple and deterministic so cassettes recorded
on one machine reproduce identical counts on another.
"""

from __future__ import annotations

import json
from typing import Any

# Common usage-block key spellings across providers, mapped to (input, output).
_INPUT_KEYS = ("input_tokens", "prompt_tokens")
_OUTPUT_KEYS = ("output_tokens", "completion_tokens")

_CHARS_PER_TOKEN = 4


def estimate_tokens(obj: Any) -> int:
    """Estimate token count for an arbitrary JSON-able object via char heuristic."""
    if obj is None:
        return 0
    if isinstance(obj, str):
        text = obj
    else:
        try:
            text = json.dumps(obj, sort_keys=True, default=str)
        except (TypeError, ValueError):
            text = str(obj)
    if not text:
        return 0
    # Round up so any non-empty payload counts as at least one token.
    return max(1, -(-len(text) // _CHARS_PER_TOKEN))


def _find_usage(obj: Any) -> dict | None:
    """Return the first dict named 'usage' found anywhere in a nested structure."""
    if isinstance(obj, dict):
        usage = obj.get("usage")
        if isinstance(usage, dict):
            return usage
        for value in obj.values():
            found = _find_usage(value)
            if found is not None:
                return found
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            found = _find_usage(item)
            if found is not None:
                return found
    return None


def _pick(usage: dict, keys: tuple) -> int | None:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return None


def count_tokens(request: Any, response: Any) -> tuple[int, int]:
    """Return ``(input_tokens, output_tokens)`` for a recorded call.

    Uses an exact usage block from the response when present, otherwise falls
    back to the character heuristic over the request (input) and response
    (output) payloads.
    """
    usage = _find_usage(response)
    if usage is not None:
        input_tokens = _pick(usage, _INPUT_KEYS)
        output_tokens = _pick(usage, _OUTPUT_KEYS)
        if input_tokens is not None or output_tokens is not None:
            return (
                input_tokens if input_tokens is not None else estimate_tokens(request),
                output_tokens if output_tokens is not None else estimate_tokens(response),
            )
    return estimate_tokens(request), estimate_tokens(response)
