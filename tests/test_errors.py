"""Error conditions: exhausted cassettes, missing files, nested sessions."""

import os
import tempfile
import unittest

import agentcassette
from agentcassette import (
    CassetteNotFound,
    ReplayExhausted,
    record,
    replay,
)


class TestErrors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "run.json")

        @agentcassette.intercept
        def call_model(prompt):
            return {"echo": prompt}

        self.call_model = call_model

    def tearDown(self):
        self.tmp.cleanup()

    def test_replay_missing_cassette_raises(self):
        with self.assertRaises(CassetteNotFound):
            with replay(os.path.join(self.tmp.name, "nope.json")):
                pass

    def test_replay_exhausted_when_agent_calls_more_than_recorded(self):
        with record(self.path):
            self.call_model("one")

        with self.assertRaises(ReplayExhausted):
            with replay(self.path):
                self.call_model("one")
                self.call_model("two")  # one more than recorded

    def test_nested_record_raises(self):
        with self.assertRaises(RuntimeError):
            with record(self.path):
                with record(self.path):
                    pass

    def test_record_and_replay_cannot_overlap(self):
        with record(self.path):
            self.call_model("one")
        with self.assertRaises(RuntimeError):
            with replay(self.path):
                with record(self.path):
                    pass

    def test_session_cleared_after_error_in_block(self):
        try:
            with record(self.path):
                raise ValueError("boom")
        except ValueError:
            pass
        # A subsequent session should work — thread-local must be cleared.
        with record(self.path):
            self.call_model("ok")
        self.assertTrue(os.path.exists(self.path))

    def test_exceptions_share_base_class(self):
        self.assertTrue(issubclass(ReplayExhausted, agentcassette.AgentCassetteError))
        self.assertTrue(issubclass(CassetteNotFound, agentcassette.AgentCassetteError))
        self.assertTrue(issubclass(agentcassette.DivergenceError, agentcassette.AgentCassetteError))


if __name__ == "__main__":
    unittest.main()
