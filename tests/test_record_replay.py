"""Record a run, then replay it and prove the real calls never happen again."""

import os
import tempfile
import unittest

import agentcassette
from agentcassette import record, replay


class TestRecordReplay(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "run.json")
        # Side-effect counter proves whether the real function actually ran.
        self.calls = {"model": 0, "tool": 0}

        @agentcassette.intercept(kind="llm")
        def call_model(prompt):
            self.calls["model"] += 1
            return {
                "text": f"answer-{self.calls['model']}",
                "usage": {"input_tokens": 12, "output_tokens": 4},
            }

        @agentcassette.intercept(kind="tool")
        def search(query):
            self.calls["tool"] += 1
            return [f"result-for-{query}"]

        self.call_model = call_model
        self.search = search

    def tearDown(self):
        self.tmp.cleanup()

    def _run_agent(self):
        plan = self.call_model("plan the task")
        hits = self.search("flights")
        final = self.call_model("summarize")
        return plan, hits, final

    def test_record_writes_cassette_with_all_steps(self):
        with record(self.path, model="test-model"):
            self._run_agent()

        self.assertTrue(os.path.exists(self.path))
        cassette = agentcassette.Cassette.load(self.path)
        self.assertEqual(cassette.num_steps, 3)
        self.assertEqual([s["name"] for s in cassette.steps], ["call_model", "search", "call_model"])
        self.assertEqual([s["type"] for s in cassette.steps], ["llm", "tool", "llm"])
        self.assertEqual(cassette.model, "test-model")

    def test_replay_returns_recorded_results_without_calling_real_functions(self):
        with record(self.path):
            recorded = self._run_agent()

        # Reset counters — during replay the real functions must NOT run.
        self.calls["model"] = 0
        self.calls["tool"] = 0

        with replay(self.path):
            replayed = self._run_agent()

        self.assertEqual(recorded, replayed)
        self.assertEqual(self.calls["model"], 0, "real model call happened during replay")
        self.assertEqual(self.calls["tool"], 0, "real tool call happened during replay")

    def test_replay_is_deterministic_even_if_real_function_would_change(self):
        with record(self.path):
            first = self.call_model("plan the task")

        # Make the real function return something different now.
        original = first["text"]
        self.calls["model"] = 99

        with replay(self.path):
            got = self.call_model("plan the task")

        self.assertEqual(got["text"], original)  # recorded value, not recomputed

    def test_passthrough_outside_session_calls_real_function(self):
        result = self.call_model("hello")  # no record/replay active
        self.assertEqual(self.calls["model"], 1)
        self.assertEqual(result["text"], "answer-1")

    def test_intercept_preserves_metadata_and_marks_wrapper(self):
        self.assertEqual(self.call_model.__name__, "call_model")
        self.assertTrue(getattr(self.call_model, "__agentcassette_intercepted__", False))

    def test_nothing_saved_when_block_raises(self):
        with self.assertRaises(ValueError):
            with record(self.path):
                self.call_model("plan")
                raise ValueError("boom")
        self.assertFalse(os.path.exists(self.path))


if __name__ == "__main__":
    unittest.main()
