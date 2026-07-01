"""Diffing two cassettes for behavioral drift."""

import os
import tempfile
import unittest

import agentcassette
from agentcassette import Cassette, diff_cassettes, record


class TestDiff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.v1 = os.path.join(self.tmp.name, "v1.json")
        self.v2 = os.path.join(self.tmp.name, "v2.json")

        @agentcassette.intercept(kind="llm")
        def call_model(prompt):
            return {"text": prompt.upper(), "usage": {"input_tokens": 10, "output_tokens": 2}}

        @agentcassette.intercept(kind="tool")
        def search(query):
            return ["hit"]

        self.call_model = call_model
        self.search = search

    def tearDown(self):
        self.tmp.cleanup()

    def test_identical_runs_report_no_diff(self):
        with record(self.v1):
            self.call_model("a")
        with record(self.v2):
            self.call_model("a")

        delta = diff_cassettes(self.v1, self.v2)
        self.assertTrue(delta.identical)
        self.assertEqual(delta.new_calls, [])
        self.assertEqual(delta.dropped_calls, [])
        self.assertEqual(delta.token_delta, 0)
        self.assertEqual(delta.step_delta, 0)

    def test_added_tool_call_shows_as_new(self):
        with record(self.v1):
            self.call_model("a")
        with record(self.v2):
            self.call_model("a")
            self.search("flights")  # extra step in v2

        delta = diff_cassettes(self.v1, self.v2)
        self.assertFalse(delta.identical)
        self.assertEqual(delta.new_calls, ["search"])
        self.assertEqual(delta.dropped_calls, [])
        self.assertEqual(delta.step_delta, 1)

    def test_dropped_call_and_token_delta(self):
        with record(self.v1):
            self.call_model("a")
            self.call_model("bb")
        with record(self.v2):
            self.call_model("a")

        delta = diff_cassettes(self.v1, self.v2)
        self.assertEqual(delta.dropped_calls, ["call_model"])
        self.assertLess(delta.token_delta, 0)  # v2 has fewer tokens

    def test_changed_arguments_reported(self):
        with record(self.v1):
            self.call_model("a")
        with record(self.v2):
            self.call_model("b")  # same name/position, different arg + result

        delta = diff_cassettes(self.v1, self.v2)
        self.assertEqual(len(delta.changed_calls), 1)
        self.assertEqual(delta.changed_calls[0]["index"], 0)

    def test_accepts_cassette_objects(self):
        with record(self.v1):
            self.call_model("a")
        c = Cassette.load(self.v1)
        delta = diff_cassettes(c, c)
        self.assertTrue(delta.identical)
        self.assertIn("CassetteDiff(", repr(delta))


if __name__ == "__main__":
    unittest.main()
