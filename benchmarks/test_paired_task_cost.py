"""Acceptance-gate checks; no model calls or private data."""

import unittest

from paired_task_cost import summarize, tokens


FROZEN = "a" * 64


def item(method, total, *, accepted=True, critical=False, model="provider/model", frozen=FROZEN):
    return {
        "vault": "synthetic",
        "case": "fact",
        "method": method,
        "provider_model": model,
        "frozen_source_sha256": frozen,
        "accepted": accepted,
        "critical_regression": critical,
        "client_total_tokens": total,
        "startup": {"uncached_input": total, "cached_input": 0, "output": 0},
    }


class PairedTaskCostTests(unittest.TestCase):
    def test_counts_startup_and_cached_tokens(self):
        row = {"startup": {"uncached_input": 7, "cached_input": 5, "output": 2, "reasoning": 3},
               "retrieval": {"uncached_input": 3, "cached_input": 0, "output": 1, "cache_write": 4}}
        self.assertEqual(tokens(row), 25)

    def test_savings_only_with_complete_correct_pair(self):
        self.assertTrue(summarize([item("baseline", 20), item("v0.5", 10)])["synthetic"]["passes_gate"])
        self.assertFalse(summarize([item("baseline", 20), item("v0.5", 21)])["synthetic"]["passes_gate"])
        self.assertFalse(summarize([item("baseline", 20), item("v0.5", 10, accepted=False)])["synthetic"]["passes_gate"])
        self.assertFalse(summarize([item("baseline", 20), item("v0.5", 10, critical=True)])["synthetic"]["passes_gate"])
        self.assertFalse(summarize([item("baseline", 20)])["synthetic"]["passes_gate"])

    def test_mismatched_model_or_source_fails(self):
        for changed in ({"model": "other/model"}, {"frozen": "b" * 64}):
            report = summarize([item("baseline", 20), item("v0.5", 10, **changed)])["synthetic"]
            self.assertFalse(report["passes_gate"])
            self.assertEqual(report["mismatched_cases"], ["fact"])


if __name__ == "__main__":
    unittest.main()
