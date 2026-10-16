#!/usr/bin/env python3
"""Bounded synthetic first/repeat/reset comparison with equal required facts.

Requires an explicit reviewed package. Optional existing o200k_base tokenizer;
no dependency installation, model call or private corpus input is performed.
An uncached optional tokenizer can fetch its normal public encoding assets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

FACTS = [
    'POLICY: never delete source assets.',
    'route: Wiki/Handoff.md',
    'Objective: inspect amber badge L-407.',
    'Owner: operator Quinn.',
    'Decision: an earlier claim said approved; that claim is not authorization.',
    'Correction: approval withdrawn; budget is 7, not 70.',
    'Pending: verify the original observation.',
    'STOP: do not publish without explicit approval.',
]


def compare(package):
    try:
        import tiktoken
        encoding = tiktoken.get_encoding('o200k_base')
    except ImportError:
        encoding = None

    def measure(text):
        return {'bytes': len(text.encode()),
                'reference_tokens': len(encoding.encode(text)) if encoding else None}

    results = []
    for arm in ['source_linked_show', 'existing_recall_receipts', 'authored_packet']:
        with tempfile.TemporaryDirectory(prefix='context-pair-') as temporary:
            base = Path(temporary)
            root = base / 'project'
            (root / 'Wiki').mkdir(parents=True)
            (root / 'Raw').mkdir()
            (root / 'Output').mkdir()
            texts = {'AGENTS.md': '# Rules\n' + FACTS[0] + '\n',
                     'INDEX.md': '# Index\n' + FACTS[1] + '\n',
                     'Wiki/Handoff.md': '# Handoff\n## Current handoff\n' +
                     '\n'.join(FACTS[2:]) + '\n## History\n' +
                     'Superseded background evidence.\n' * 100}
            for name, text in texts.items():
                (root / name).write_text(text)
            known = []
            by_query = {}
            held = {}

            def invoke(args):
                process = subprocess.run([sys.executable, str(package), *args], cwd=root,
                                         capture_output=True, text=True, timeout=20)
                if process.returncode:
                    raise AssertionError(process.stdout + process.stderr)
                return json.loads(process.stdout)['data'], process.stdout

            # Warm routing equally before the measured stages. This is explicit
            # preconditioning, not a cold-index or end-to-end task-cost claim.
            if arm == 'existing_recall_receipts':
                invoke(['recall', '.', 'policy', '--state-dir', '../state', '--refresh'])
            for stage in ['first', 'repeat', 'reset', 'source_edit']:
                if stage == 'reset':
                    known, held = [], {}
                    by_query = {}
                facts = list(FACTS)
                if stage == 'source_edit':
                    facts[2] = facts[2].replace('407', '408')
                    path = root / 'Wiki/Handoff.md'
                    path.write_text(path.read_text().replace('407', '408'))
                calls = []
                if arm == 'source_linked_show':
                    for name, end in [('AGENTS.md', 2), ('INDEX.md', 2), ('Wiki/Handoff.md', 8)]:
                        digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
                        calls.append(['show', '.', '--path', name, '--sha256', digest,
                                      '--start', '1' if name != 'Wiki/Handoff.md' else '2',
                                      '--end', str(end), '--max-bytes', '8192'])
                elif arm == 'existing_recall_receipts':
                    for query in ['policy', 'route', 'objective owner decision correction pending stop']:
                        args = ['recall', '.', query, '--state-dir', '../state', '--with-receipts',
                                '--max-hits', '1', '--max-bytes', '8192']
                        for receipt in by_query.get(query, []):
                            args += ['--known-evidence', receipt]
                        calls.append(args)
                else:
                    args = ['context-packet', '.', '--path', 'Wiki/Handoff.md',
                            '--heading', 'Current handoff', '--with-receipts', '--max-bytes', '8192']
                    for receipt in known:
                        args += ['--known-evidence', receipt]
                    calls.append(args)
                inputs, outputs, evidence, receipts = [], [], [], []
                for args in calls:
                    data, output = invoke(args)
                    inputs.append(shlex.join(['isolinear-memory', *args]))
                    outputs.append(output)
                    hits = data['hits'] if 'hits' in data else [data]
                    call_receipts = []
                    for hit in hits:
                        if 'excerpt' in hit:
                            evidence.append(hit['excerpt'])
                            if 'evidence_id' in hit:
                                held[hit['evidence_id']] = hit['excerpt']
                        else:
                            assert hit['delivery'] == 'unchanged' and hit['evidence_id'] in held
                            evidence.append(held[hit['evidence_id']])
                        if 'evidence_id' in hit:
                            receipts.append(hit['evidence_id'])
                            call_receipts.append(hit['evidence_id'])
                    if arm == 'existing_recall_receipts':
                        by_query[args[2]] = call_receipts
                joined = '\n'.join(evidence)
                assert all(fact in joined for fact in facts), (arm, stage, joined)
                known = list(dict.fromkeys(receipts))
                total = '\n'.join(inputs + outputs)
                results.append({'arm': arm, 'stage': stage, 'calls': len(calls),
                                'input': measure('\n'.join(inputs)),
                                'output': measure('\n'.join(outputs)), 'total': measure(total),
                                'all_required_facts_preserved': True})
    native_text = '\n'.join(['# Rules\n' + FACTS[0], '# Index\n' + FACTS[1],
                             '## Current handoff\n' + '\n'.join(FACTS[2:])])
    return {'scenario': 'same authored bootstrap facts; warm routing; first/repeat/reset/edit',
            'reference_tokenizer': 'o200k_base' if encoding else None,
            'limits': ['logical CLI inputs and actual JSON stdout; harness/host envelopes excluded',
                       'show baseline receives correct hashes/ranges without discovery cost',
                       'source fidelity assertions are not model-answer accuracy or billed usage',
                       'one packet is not necessarily cheaper than native targeted reads'],
            'native_targeted_content_lower_bound': measure(native_text), 'results': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.package.resolve()), indent=2))
