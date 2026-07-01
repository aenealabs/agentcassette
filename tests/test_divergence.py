"""Strict replay raises on drift; non-strict collects divergences."""

import os
import tempfile
import unittest

import agentcassette
from agentcassette import DivergenceError, record, replay


class TestDivergence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "run.json")

        @agentcassette.intercept(kind="llm")
        def call_model(prompt):
            return {"echo": prompt}

        self.call_model = call_model

        with record(self.path):
            self.call_model("original prompt")

    def tearDown(self):
        self.tmp.cleanup()

    def test_matching_replay_does_not_diverge(self):
        with replay(self.path, strict=True) as player:
            self.call_model("original prompt")
        self.assertEqual(player.divergences, [])

    def test_strict_replay_raises_on_argument_mismatch(self):
        with self.assertRaises(DivergenceError) as ctx:
            with replay(self.path, strict=True):
                self.call_model("a DIFFERENT prompt")
        err = ctx.exception
        self.assertEqual(err.step_index, 0)
        self.assertEqual(err.actual["arguments"]["args"], ["a DIFFERENT prompt"])

    def test_nonstrict_replay_collects_divergence_and_still_returns_recorded(self):
        with replay(self.path, strict=False) as player:
            result = self.call_model("a DIFFERENT prompt")
        # Recorded result is still served despite the mismatch.
        self.assertEqual(result, {"echo": "original prompt"})
        self.assertEqual(len(player.divergences), 1)
        self.assertEqual(player.divergences[0]["index"], 0)

    def test_strict_replay_raises_on_name_mismatch(self):
        @agentcassette.intercept
        def other_call(prompt):
            return {"echo": prompt}

        with self.assertRaises(DivergenceError):
            with replay(self.path, strict=True):
                other_call("original prompt")


if __name__ == "__main__":
    unittest.main()
