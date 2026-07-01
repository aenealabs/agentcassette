"""Token accounting: exact usage blocks preferred, char heuristic as fallback."""

import unittest

from agentcassette._tokens import count_tokens, estimate_tokens


class TestEstimate(unittest.TestCase):
    def test_empty_is_zero(self):
        self.assertEqual(estimate_tokens(""), 0)
        self.assertEqual(estimate_tokens(None), 0)

    def test_nonempty_is_at_least_one(self):
        self.assertEqual(estimate_tokens("a"), 1)

    def test_roughly_four_chars_per_token(self):
        self.assertEqual(estimate_tokens("a" * 40), 10)

    def test_structures_are_serialized_before_counting(self):
        self.assertGreater(estimate_tokens({"key": "value" * 10}), 1)


class TestCountTokens(unittest.TestCase):
    def test_prefers_openai_usage_block(self):
        response = {"choices": [], "usage": {"prompt_tokens": 123, "completion_tokens": 45}}
        self.assertEqual(count_tokens({"q": "x"}, response), (123, 45))

    def test_prefers_anthropic_usage_block(self):
        response = {"content": [], "usage": {"input_tokens": 200, "output_tokens": 60}}
        self.assertEqual(count_tokens({"q": "x"}, response), (200, 60))

    def test_finds_nested_usage(self):
        response = {"data": {"meta": {"usage": {"input_tokens": 5, "output_tokens": 1}}}}
        self.assertEqual(count_tokens({}, response), (5, 1))

    def test_falls_back_to_heuristic_without_usage(self):
        inp, out = count_tokens("a" * 40, "b" * 80)
        self.assertEqual((inp, out), (10, 20))


if __name__ == "__main__":
    unittest.main()
