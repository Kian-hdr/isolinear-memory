#!/usr/bin/env python3
"""Paired original synthetic evidence tests; no model calls or private inputs.

This evaluates exact and hybrid Isolinear CLI evidence, not Hindsight accuracy.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

DOCS = {
    'AGENTS.md': '# Rules\nRead INDEX.md.\n',
    'INDEX.md': '# Index\nRead the Wiki.\n',
    'Wiki/Quartz.md': '# Quartz\nThe quartz relay is ready. See [[Wiki/Schedule]].\n',
    'Wiki/Schedule.md': '# Schedule\n2026-10-02: The window is 17:40 UTC.\n',
    'Wiki/History.md': '# History\n2026-09-01: The quartz relay window was 06:20 UTC.\n',
    'Wiki/Rare.md': '# Rare\nThe amber pine checksum is 8c72.\n',
    'Raw/Source.md': '# Source\nThe raw-only copper heron arrived.\n',
    'Output/Report.md': '# Report\nThe output-only satin badger arrived.\n',
}
CASES = [
    ('rare_detail', 'amber pine checksum', [], '8c72'),
    ('partial_query', 'quartz maintenance', [], 'relay is ready'),
    ('linked_answer', 'quartz', [], '17:40 UTC'),
    ('missing', 'unfindablexenon', [], None),
    ('raw_excluded', 'copper', [], None),
    ('raw_included', 'copper', ['--include-raw'], 'copper heron'),
    ('output_excluded', 'badger', [], None),
    ('output_included', 'badger', ['--include-output'], 'satin badger'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = {
        'dataset': 'hybrid-recall-synthetic-v2',
        'cases_sha256': hashlib.sha256(json.dumps(CASES, sort_keys=True).encode()).hexdigest(),
        'packages': {'baseline_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
                     'candidate_sha256': hashlib.sha256(args.candidate.read_bytes()).hexdigest()},
        'corpus_sha256': hashlib.sha256(json.dumps(DOCS, sort_keys=True).encode()).hexdigest(),
        'provenance': 'Original synthetic fixture; no private sources or model calls.',
        'rights': 'Repository MIT license; original test text.',
        'grading': 'Required evidence substring plus exact spans/current hashes and no unexpected hits for absent cases.',
        'limits': 'Eight purpose-built cases, not a prevalence sample or Hindsight benchmark; elapsed time is local CLI only.',
        'side_effects': 'Disposable private index only; original Markdown unchanged.',
        'runs': [],
    }
    with tempfile.TemporaryDirectory(prefix='hybrid-pair-') as scratch:
        base = Path(scratch)
        root = base / 'project'
        for name, content in DOCS.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        for method, package, strategy in (
            ('baseline_exact', args.baseline, []),
            ('candidate_exact', args.candidate, []),
            ('candidate_hybrid', args.candidate, ['--strategy', 'hybrid']),
        ):
            state = base / method
            for name, query, flags, expected in CASES:
                started = time.monotonic()
                proc = subprocess.run([sys.executable, str(package), 'recall', str(root), query,
                    '--state-dir', str(state), '--max-bytes', '4096'] + strategy + flags,
                    text=True, capture_output=True, timeout=15)
                result = json.loads(proc.stdout)
                hits = result.get('data', {}).get('hits', [])
                evidence = '\n'.join(hit['excerpt'] for hit in hits)
                checked = all(hit['sha256'] == hashlib.sha256(DOCS[hit['path']].encode()).hexdigest()
                    and hit['excerpt'] == '\n'.join(DOCS[hit['path']].splitlines()[hit['start']-1:hit['end']])
                    for hit in hits)
                accepted = proc.returncode == 0 and checked and (
                    expected in evidence if expected is not None else not hits)
                report['runs'].append({'method': method, 'case': name, 'accepted': accepted,
                    'source_checked': checked, 'hit_paths': sorted({h['path'] for h in hits}),
                    'returned_bytes': len(proc.stdout.encode()),
                    'elapsed_ms': round((time.monotonic()-started)*1000, 2)})
        assert all((root / n).read_text(encoding='utf-8') == c for n, c in DOCS.items())
    report['totals'] = {method: sum(r['accepted'] for r in report['runs'] if r['method'] == method)
        for method in ('baseline_exact', 'candidate_exact', 'candidate_hybrid')}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['totals']))
    return 0 if report['totals']['candidate_hybrid'] == len(CASES) and (
        report['totals']['candidate_exact'] == report['totals']['baseline_exact']) else 1

if __name__ == '__main__':
    raise SystemExit(main())
