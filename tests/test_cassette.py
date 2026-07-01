"""Cassette inspection, persistence, and redaction."""

import os
import tempfile
import unittest

import agentcassette
from agentcassette import Cassette, record
from agentcassette._cassette import to_jsonable


class TestCassetteInspection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "run.json")

        @agentcassette.intercept(kind="llm")
        def call_model(prompt, api_key="secret-123"):
            return {"text": "ok", "usage": {"input_tokens": 30, "output_tokens": 7}}

        self.call_model = call_model

    def tearDown(self):
        self.tmp.cleanup()

    def test_token_totals_and_step_count(self):
        with record(self.path):
            self.call_model("one")
            self.call_model("two")

        c = Cassette.load(self.path)
        self.assertEqual(c.num_steps, 2)
        self.assertEqual(c.total_input_tokens, 60)   # 30 + 30
        self.assertEqual(c.total_output_tokens, 14)  # 7 + 7
        self.assertEqual(c.total_tokens, 74)
        self.assertGreaterEqual(c.duration_ms, 0.0)
        self.assertIn("Cassette(", repr(c))

    def test_save_creates_missing_directories(self):
        nested = os.path.join(self.tmp.name, "a", "b", "c", "run.json")
        with record(nested):
            self.call_model("one")
        self.assertTrue(os.path.exists(nested))

    def test_redact_scrubs_nested_keys(self):
        with record(self.path):
            self.call_model("one", api_key="super-secret")

        c = Cassette.load(self.path)
        # The secret is stored under kwargs before redaction.
        self.assertIn("super-secret", str(c.to_dict()))
        c.redact("api_key")
        self.assertNotIn("super-secret", str(c.to_dict()))

    def test_redact_at_record_time(self):
        with record(self.path, redact=["api_key"]):
            self.call_model("one", api_key="super-secret")
        c = Cassette.load(self.path)
        self.assertNotIn("super-secret", str(c.to_dict()))

    def test_round_trip_preserves_steps(self):
        with record(self.path):
            self.call_model("one")
        loaded = Cassette.load(self.path)
        again_path = os.path.join(self.tmp.name, "again.json")
        loaded.save(again_path)
        reloaded = Cassette.load(again_path)
        self.assertEqual(loaded.to_dict()["steps"], reloaded.to_dict()["steps"])


class TestToJsonable(unittest.TestCase):
    def test_primitives_pass_through(self):
        self.assertEqual(to_jsonable({"a": 1, "b": [1, 2.5, "x", None, True]}),
                         {"a": 1, "b": [1, 2.5, "x", None, True]})

    def test_sets_and_tuples_become_lists(self):
        self.assertEqual(to_jsonable((1, 2)), [1, 2])
        self.assertEqual(sorted(to_jsonable({1, 2, 3})), [1, 2, 3])

    def test_object_with_dict_is_serialized(self):
        class Point:
            def __init__(self):
                self.x = 1
                self.y = 2

        out = to_jsonable(Point())
        self.assertEqual(out["__type__"], "Point")
        self.assertEqual(out["x"], 1)

    def test_object_without_dict_falls_back_to_repr(self):
        out = to_jsonable(object())
        self.assertIn("__repr__", out)

    def test_model_dump_is_preferred(self):
        class FakeResponse:
            def model_dump(self):
                return {"text": "hi"}

        self.assertEqual(to_jsonable(FakeResponse()), {"text": "hi"})


if __name__ == "__main__":
    unittest.main()
