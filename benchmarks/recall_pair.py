#!/usr/bin/env python3
"""Synthetic, repeatable comparison of targeted rg and Shared Memory recall.

This harness contains no private vault data. It creates its own disposable folder,
uses a supplied built product package, and writes only to a temporary directory.
The generated JSON is safe to publish; it is not a model-token or billing claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time


DOCS = {
    "AGENTS.md": "# Fixture instructions\nRead INDEX.md. Search the Wiki first.\n",
    "INDEX.md": "# Fixture index\nThe relay decision is in [[Wiki/Relay Notes]].\n",
    "Wiki/Relay Notes.md": (
        "# Relay Notes\n\n## Current handoff\n"
        "The polar quartz relay window is 17:40 UTC.\n"
        "The amber pine checksum is 8c72.\n"
    ),
    "Wiki/Zephyr Decision.md": (
        "# Zephyr Decision\n\n## Current\n"
        "For zephyr handoff, the current owner is Rowan.\n"
        "Earlier owner was Mica; see the historical note before quoting dates.\n"
    ),
    "Wiki/Zephyr History.md": (
        "# Zephyr History\n\n## Historical\n"
        "For zephyr handoff, the owner was Mica before the change.\n"
    ),
    "Wiki/Cedar Operations.md": (
        "# Cedar Operations\n\n## Cedar launch posture\n"
        "The readiness decision is green for the 06:20 review.\n"
        "The source of this decision is the synthetic review note.\n"
    ),
    "Raw/Relay Source.md": "# Relay Source\nThe raw-only phrase is copper heron nine.\n",
    "Output/Relay Report.md": "# Relay Report\nThe output-only phrase is satin otter eight.\n",
}

CASES = (
    {"name": "rare_detail", "query": "polar quartz relay", "source": "Wiki/Relay Notes.md", "answer": "17:40 UTC"},
    {"name": "second_detail", "query": "amber pine checksum", "source": "Wiki/Relay Notes.md", "answer": "8c72"},
    {"name": "changed_fact", "query": "zephyr handoff", "source": "Wiki/Zephyr Decision.md", "answer": "Rowan"},
    {"name": "adjacent_answer", "query": "cedar launch posture", "source": "Wiki/Cedar Operations.md", "answer": "06:20"},
    {"name": "out_of_order", "query": "checksum amber", "fallback_query": "checksum", "source": "Wiki/Relay Notes.md", "answer": "8c72"},
    {"name": "missing_fact", "query": "silver kestrel launch", "source": None, "answer": None},
    {"name": "raw_excluded", "query": "copper heron nine", "source": None, "answer": None},
    {"name": "raw_included", "query": "copper heron nine", "source": "Raw/Relay Source.md", "answer": "copper heron nine", "include_raw": True},
    {"name": "output_excluded", "query": "satin otter eight", "source": None, "answer": None},
    {"name": "output_included", "query": "satin otter eight", "source": "Output/Relay Report.md", "answer": "satin otter eight", "include_output": True},
    {"name": "hidden_excluded", "query": "indigo gull seven", "source": None, "answer": None},
)


def execute(args: list[str], *, cwd: Path | None = None, timeout: int = 90) -> dict:
    started = time.perf_counter()
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    return {
        "code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def write_fixture(root: Path) -> None:
    for rel, value in DOCS.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding="utf-8")


def allowed_paths(root: Path, *, raw: bool = False, output: bool = False) -> list[Path]:
    paths = [root / "AGENTS.md", root / "INDEX.md"]
    paths.extend((root / "Wiki").rglob("*.md"))
    if raw:
        paths.extend((root / "Raw").rglob("*.md"))
    if output:
        paths.extend((root / "Output").rglob("*.md"))
    return sorted(path for path in paths if path.is_file() and not path.is_symlink())


def rg_search(root: Path, case: dict) -> dict:
    paths = allowed_paths(root, raw=case.get("include_raw", False), output=case.get("include_output", False))
    result = execute(["rg", "-n", "-i", "-F", "--", case["query"], *map(str, paths)])
    if result["code"] not in {0, 1}:
        raise RuntimeError(f"rg failed: {result['stderr']}")
    calls = 1
    elapsed = result["elapsed_ms"]
    if not result["stdout"].strip() and case.get("fallback_query"):
        result = execute(["rg", "-n", "-i", "-F", "--", case["fallback_query"], *map(str, paths)])
        calls += 1
        elapsed += result["elapsed_ms"]
        if result["code"] not in {0, 1}:
            raise RuntimeError(f"rg fallback failed: {result['stderr']}")
    lines = result["stdout"].splitlines()[:5]
    # This models a bounded, manual targeted search, not an entire agent turn.
    text = "\n".join(line.replace(str(root) + os.sep, "", 1) for line in lines)
    if case["answer"] and case["answer"].casefold() not in text.casefold() and lines:
        # The agent found a heading but needs one bounded native file read.
        first = lines[0].split(":", 2)
        if len(first) == 3 and first[1].isdigit():
            target = Path(first[0])
            line = int(first[1])
            started = time.perf_counter()
            excerpt = "\n".join(target.read_text(encoding="utf-8").splitlines()[max(0, line - 3):line + 5])
            elapsed += round((time.perf_counter() - started) * 1000, 3)
            text += "\n" + excerpt
            calls += 1
    return {"text": text[:2048], "elapsed_ms": elapsed, "exit_code": result["code"], "calls": calls}


def recall(package: Path, root: Path, state: Path, case: dict) -> dict:
    args = [sys.executable, str(package), "recall", str(root), case["query"], "--state-dir", str(state), "--text"]
    if case.get("include_raw"):
        args.append("--include-raw")
    if case.get("include_output"):
        args.append("--include-output")
    result = execute(args)
    if result["code"]:
        raise RuntimeError(f"recall failed ({result['code']}): {result['stdout']} {result['stderr']}")
    text, elapsed, calls = result["stdout"], result["elapsed_ms"], 1
    if case["answer"] and case["answer"].casefold() not in text.casefold():
        # Compact recall identifies a precise hit; expand only if the answer is
        # not yet visible. This mirrors the rg + bounded native-read baseline.
        for line in text.splitlines():
            match = re.match(r"^(.+?\.md):(\d+)-(\d+) sha256=([0-9a-f]+)", line)
            if not match:
                continue
            path, start, end, digest = match.groups()
            target = root / path
            last = len(target.read_text(encoding="utf-8").splitlines())
            shown = execute([sys.executable, str(package), "show", str(root), "--state-dir", str(state),
                             "--path", path, "--sha256", digest, "--start", start,
                             "--end", str(min(last, int(end) + 1)), "--text"])
            if shown["code"]:
                raise RuntimeError(f"show failed ({shown['code']}): {shown['stdout']} {shown['stderr']}")
            text += shown["stdout"]
            elapsed += shown["elapsed_ms"]
            calls += 1
            break
    return {"text": text, "elapsed_ms": elapsed, "exit_code": result["code"], "calls": calls}


def grade(text: str, case: dict) -> dict:
    source, answer = case["source"], case["answer"]
    if source is None:
        # The text CLI prints a method/scope header even when it found no hit.
        no_hits = not any(".md:" in line for line in text.splitlines())
        return {"source_correct": no_hits, "answer_visible": no_hits}
    return {
        "source_correct": source in text,
        "answer_visible": answer.casefold() in text.casefold(),
    }


def optional_reference_tokens(text: str) -> int | None:
    try:
        import tiktoken  # type: ignore[import-not-found]
    except ImportError:
        return None
    return len(tiktoken.get_encoding("o200k_base").encode(text))


def row(name: str, text: str, elapsed_ms: float, case: dict, calls: int = 1) -> dict:
    return {
        "method": name,
        "case": case["name"],
        **grade(text, case),
        "returned_bytes": len(text.encode("utf-8")),
        "reference_tokens_o200k": optional_reference_tokens(text),
        "elapsed_ms": elapsed_ms,
        "agent_tool_calls": calls,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True, help="Built Shared Memory .pyz to exercise")
    parser.add_argument("--output", type=Path, help="Optional synthetic-only JSON result")
    args = parser.parse_args()
    package = args.package.resolve(strict=True)
    if not shutil.which("rg"):
        parser.error("rg is required for the existing targeted-search baseline")
    with tempfile.TemporaryDirectory(prefix="shared-memory-paired-") as directory:
        base = Path(directory)
        root, state = base / "fixture", base / "private-state"
        root.mkdir()
        write_fixture(root)
        setup = execute([sys.executable, str(package), "setup", str(root), "--state-dir", str(state),
                         "--actor", "benchmark", "--person", "Synthetic", "--agent", "Benchmark"])
        if setup["code"]:
            raise RuntimeError(f"setup failed: {setup['stdout']} {setup['stderr']}")
        (root / ".hidden").mkdir()
        (root / ".hidden/private.md").write_text(
            "# Private runtime\nThe hidden sentinel is indigo gull seven.\n", encoding="utf-8"
        )
        rows: list[dict] = []
        for case in CASES:
            old = rg_search(root, case)
            new = recall(package, root, state, case)
            rows.extend((row("targeted_rg", old["text"], old["elapsed_ms"], case, old["calls"]),
                         row("v0.5_recall", new["text"], new["elapsed_ms"], case, new["calls"])))
        # A source must be revalidated after indexing. No old answer may be returned.
        source = root / "Wiki/Relay Notes.md"
        source.write_text(source.read_text().replace("17:40 UTC", "18:05 UTC"), encoding="utf-8")
        changed = {"name": "post_edit", "query": "polar quartz relay", "source": "Wiki/Relay Notes.md", "answer": "18:05 UTC"}
        for method, operation in (("targeted_rg", rg_search), ("v0.5_recall", None)):
            result = operation(root, changed) if operation else recall(package, root, state, changed)
            entry = row(method, result["text"], result["elapsed_ms"], changed)
            entry["stale_answer_absent"] = "17:40 UTC" not in result["text"]
            rows.append(entry)
        source.unlink()
        missing = {"name": "post_delete", "query": "polar quartz relay", "source": None, "answer": None}
        for method, operation in (("targeted_rg", rg_search), ("v0.5_recall", None)):
            result = operation(root, missing) if operation else recall(package, root, state, missing)
            entry = row(method, result["text"], result["elapsed_ms"], missing)
            entry["deleted_source_absent"] = "Wiki/Relay Notes.md" not in result["text"]
            entry["old_fact_absent"] = "17:40 UTC" not in result["text"]
            entry["new_fact_absent"] = "18:05 UTC" not in result["text"]
            rows.append(entry)
        index_files = list(state.rglob("recall.sqlite3"))
        report = {
            "schema": "synthetic_recall_pair_v1",
            "fixture_sha256": hashlib.sha256(json.dumps(DOCS, sort_keys=True).encode()).hexdigest(),
            "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
            "index_bytes": sum(path.stat().st_size for path in index_files),
            "reference_tokenizer": "tiktoken o200k_base if installed; not GLM or billing tokens",
            "scope": "synthetic only; no private vault text or model calls",
            "rows": rows,
        }
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
