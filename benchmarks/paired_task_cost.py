#!/usr/bin/env python3
"""Evaluate paired, manually recorded complete-task token usage without note text.

Input is JSONL with one row per case and method. Keep real-vault ledgers private;
the schema is deliberately numeric and does not require prompts or excerpts.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path


COMPONENTS = ("startup", "write", "index", "retrieval", "answer", "retry", "other")
METHODS = ("baseline", "v0.5")
BUCKETS = ("uncached_input", "cached_input", "cache_write", "output", "reasoning")


def tokens(row: dict) -> int:
    total = 0
    for component in COMPONENTS:
        item = row.get(component, {})
        if not isinstance(item, dict):
            raise ValueError(f"{component} must be an object")
        for field in BUCKETS:
            value = item.get(field, 0)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{component}.{field} must be a nonnegative integer")
            total += value
    return total


def read_rows(path: Path) -> list[dict]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            vault, case, method = row["vault"], row["case"], row["method"]
            model, frozen = row["provider_model"], row["frozen_source_sha256"]
            if not all(isinstance(value, str) and value.strip() for value in (vault, case, model)) or method not in METHODS:
                raise ValueError("invalid vault, case, method or provider_model")
            if not isinstance(frozen, str) or len(frozen) != 64 or any(c not in "0123456789abcdef" for c in frozen):
                raise ValueError("frozen_source_sha256 must be a lowercase SHA-256")
            if type(row["accepted"]) is not bool or type(row["critical_regression"]) is not bool:
                raise ValueError("accepted and critical_regression must be booleans")
            observed = row["client_total_tokens"]
            if not isinstance(observed, int) or observed < 0:
                raise ValueError("client_total_tokens must be a nonnegative integer")
            if tokens(row) > observed:
                raise ValueError("component token breakdown exceeds client_total_tokens")
            row["total_tokens"] = observed
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError(f"line {number}: {error}") from error
        rows.append(row)
    return rows


def summarize(rows: list[dict]) -> dict:
    groups: dict[str, dict[str, dict[str, dict]]] = defaultdict(lambda: defaultdict(dict))
    for row in rows:
        row = dict(row)
        observed = row.get("client_total_tokens")
        if not isinstance(observed, int) or observed < 0 or tokens(row) > observed:
            raise ValueError("client_total_tokens must include all reported component tokens")
        row["total_tokens"] = observed
        methods = groups[row["vault"]][row["case"]]
        if row["method"] in methods:
            raise ValueError(f"duplicate: {row['vault']}/{row['case']}/{row['method']}")
        methods[row["method"]] = row
    result = {}
    for vault, cases in sorted(groups.items()):
        incomplete = sorted(case for case, methods in cases.items() if set(methods) != set(METHODS))
        mismatched = sorted(case for case, methods in cases.items() if set(methods) == set(METHODS)
                            and (methods["baseline"]["provider_model"] != methods["v0.5"]["provider_model"]
                                 or methods["baseline"]["frozen_source_sha256"] != methods["v0.5"]["frozen_source_sha256"]))
        accepted = [methods for methods in cases.values() if set(methods) == set(METHODS)
                    and methods["baseline"]["accepted"] and methods["v0.5"]["accepted"]
                    and methods["baseline"]["provider_model"] == methods["v0.5"]["provider_model"]
                    and methods["baseline"]["frozen_source_sha256"] == methods["v0.5"]["frozen_source_sha256"]]
        baseline = sum(pair["baseline"]["total_tokens"] for pair in accepted)
        new = sum(pair["v0.5"]["total_tokens"] for pair in accepted)
        critical = any(pair["v0.5"]["critical_regression"] for pair in cases.values() if "v0.5" in pair)
        failed = sorted(case for case, pair in cases.items() if "baseline" in pair and "v0.5" in pair
                        and pair["baseline"]["accepted"] and not pair["v0.5"]["accepted"])
        result[vault] = {
            "paired_cases": len(cases) - len(incomplete),
            "incomplete_cases": incomplete,
            "mismatched_cases": mismatched,
            "lost_accepted_cases": failed,
            "critical_regression": critical,
            "baseline_tokens_on_mutually_accepted_cases": baseline,
            "v0_5_tokens_on_mutually_accepted_cases": new,
            "reduction_fraction": round((baseline - new) / baseline, 4) if baseline else None,
            "passes_gate": bool(accepted) and not incomplete and not mismatched and not failed and not critical and new < baseline,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path, help="Private JSONL ledger with actual client-reported usage")
    args = parser.parse_args()
    print(json.dumps(summarize(read_rows(args.ledger)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
