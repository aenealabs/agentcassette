"""Exception types raised by agentcassette."""

from __future__ import annotations


class AgentCassetteError(Exception):
    """Base class for all agentcassette errors."""


class CassetteNotFound(AgentCassetteError):
    """Raised when a cassette file does not exist during replay."""


class ReplayExhausted(AgentCassetteError):
    """Raised when the agent makes more intercepted calls than the cassette recorded."""


class DivergenceError(AgentCassetteError):
    """Raised during a strict replay when a call does not match the recording.

    Attributes:
        step_index: Position of the diverging call in the cassette.
        expected: The recorded ``{"name", "arguments"}`` at that position.
        actual: The ``{"name", "arguments"}`` the agent produced instead.
    """

    def __init__(self, step_index: int, expected: dict, actual: dict) -> None:
        self.step_index = step_index
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Replay diverged at step {step_index}: "
            f"expected {expected.get('name')!r} with {expected.get('arguments')!r}, "
            f"got {actual.get('name')!r} with {actual.get('arguments')!r}"
        )
