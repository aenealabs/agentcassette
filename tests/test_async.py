"""Async callables record and replay just like sync ones."""

import asyncio
import os
import tempfile
import unittest

import agentcassette
from agentcassette import DivergenceError, record, replay


class TestAsyncInterception(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "run.json")
        self.calls = {"model": 0, "tool": 0}

        @agentcassette.intercept(kind="llm")
        async def acall_model(prompt):
            await asyncio.sleep(0)  # a real awaitable boundary
            self.calls["model"] += 1
            return {"text": f"answer-{self.calls['model']}", "prompt": prompt}

        @agentcassette.intercept(kind="tool")
        def sync_tool(x):  # sync tool mixed into an async agent
            self.calls["tool"] += 1
            return x * 2

        self.acall_model = acall_model
        self.sync_tool = sync_tool

    def tearDown(self):
        self.tmp.cleanup()

    async def _agent(self):
        a = await self.acall_model("first")
        b = self.sync_tool(21)
        c = await self.acall_model("second")
        return a["text"], b, c["text"]

    def test_intercept_returns_coroutine_function(self):
        self.assertTrue(asyncio.iscoroutinefunction(self.acall_model))
        self.assertTrue(getattr(self.acall_model, "__agentcassette_intercepted__", False))
        self.assertEqual(self.acall_model.__name__, "acall_model")

    def test_record_then_replay_async(self):
        with record(self.path):
            recorded = asyncio.run(self._agent())

        self.assertTrue(os.path.exists(self.path))
        cassette = agentcassette.Cassette.load(self.path)
        self.assertEqual([s["name"] for s in cassette.steps],
                         ["acall_model", "sync_tool", "acall_model"])

        # Reset counters — replay must not touch the real functions.
        self.calls["model"] = 0
        self.calls["tool"] = 0
        with replay(self.path):
            replayed = asyncio.run(self._agent())

        self.assertEqual(recorded, replayed)
        self.assertEqual(self.calls, {"model": 0, "tool": 0})

    def test_passthrough_async_outside_session(self):
        result = asyncio.run(self.acall_model("hi"))
        self.assertEqual(self.calls["model"], 1)
        self.assertEqual(result["text"], "answer-1")

    def test_strict_divergence_async(self):
        with record(self.path):
            asyncio.run(self.acall_model("original"))

        async def different():
            await self.acall_model("changed")

        with self.assertRaises(DivergenceError):
            with replay(self.path, strict=True):
                asyncio.run(different())

    def test_concurrent_gather_records_all_calls(self):
        async def fan_out():
            return await asyncio.gather(
                self.acall_model("a"), self.acall_model("b"), self.acall_model("c")
            )

        with record(self.path):
            asyncio.run(fan_out())

        cassette = agentcassette.Cassette.load(self.path)
        self.assertEqual(cassette.num_steps, 3)


if __name__ == "__main__":
    unittest.main()
