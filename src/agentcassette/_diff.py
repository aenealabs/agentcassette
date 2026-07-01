"""Diff two cassettes to spot behavioral drift between agent versions."""

from __future__ import annotations

import os
from collections import Counter
from typing import Union

from ._cassette import Cassette


class CassetteDiff:
    """The delta between two cassettes (``a`` = baseline, ``b`` = new).

    Attributes:
        new_calls: Call names that appear more often in ``b`` than ``a``.
        dropped_calls: Call names that appear more often in ``a`` than ``b``.
        changed_calls: Steps at the same index whose name/arguments/result differ.
        token_delta: ``b`` total tokens minus ``a`` total tokens.
        input_token_delta / output_token_delta: the same, split by direction.
        step_delta: ``b`` step count minus ``a`` step count.
    """

    def __init__(self, a: Cassette, b: Cassette) -> None:
        names_a = Counter(s.get("name") for s in a.steps)
        names_b = Counter(s.get("name") for s in b.steps)

        self.new_calls: list[str] = sorted((names_b - names_a).elements())
        self.dropped_calls: list[str] = sorted((names_a - names_b).elements())

        self.changed_calls: list[dict] = []
        for i in range(min(len(a.steps), len(b.steps))):
            sa, sb = a.steps[i], b.steps[i]
            if (
                sa.get("name") != sb.get("name")
                or sa.get("arguments") != sb.get("arguments")
                or sa.get("result") != sb.get("result")
            ):
                self.changed_calls.append({"index": i, "a": sa, "b": sb})

        self.input_token_delta = b.total_input_tokens - a.total_input_tokens
        self.output_token_delta = b.total_output_tokens - a.total_output_tokens
        self.token_delta = b.total_tokens - a.total_tokens
        self.step_delta = b.num_steps - a.num_steps

    @property
    def identical(self) -> bool:
        """True when the two cassettes have the same calls, args, and results."""
        return (
            not self.new_calls
            and not self.dropped_calls
            and not self.changed_calls
            and self.step_delta == 0
        )

    def __repr__(self) -> str:
        return (
            f"CassetteDiff(new={self.new_calls}, dropped={self.dropped_calls}, "
            f"changed={len(self.changed_calls)}, token_delta={self.token_delta})"
        )


def diff_cassettes(
    a: Union[str, os.PathLike, Cassette],
    b: Union[str, os.PathLike, Cassette],
) -> CassetteDiff:
    """Compare two cassettes given as paths or already-loaded :class:`Cassette`s."""
    cassette_a = a if isinstance(a, Cassette) else Cassette.load(a)
    cassette_b = b if isinstance(b, Cassette) else Cassette.load(b)
    return CassetteDiff(cassette_a, cassette_b)
