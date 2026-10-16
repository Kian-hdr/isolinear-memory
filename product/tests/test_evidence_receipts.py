"""Packaged acceptance for optional, caller-held evidence receipts.

Original synthetic fixtures only. Byte savings are bounded fixture measurements,
not provider token counts, billed credits or real-workspace benchmarks.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from product.shared_workspace import recall as retrieval
from product.shared_workspace.errors import ProductError

REPO = Path(__file__).resolve().parents[2]
LONG_PASSAGE = ('The amber observation contains reproducible synthetic evidence. ' * 40).strip()


class EvidenceReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package_dir = tempfile.TemporaryDirectory(prefix='receipt-package-')
        cls.addClassCleanup(cls.package_dir.cleanup)
        cls.package = Path(cls.package_dir.name) / 'isolinear.pyz'
        process = subprocess.run([sys.executable, str(REPO / 'scripts/build_product.py'),
                                  '--output', str(cls.package)], cwd=REPO,
                                 text=True, capture_output=True)
        if process.returncode:
            raise AssertionError(process.stdout + process.stderr)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='receipt-fixture-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / 'project'
        self.state = self.base / 'private-state'
        contents = {
            'AGENTS.md': '# Rules\nUse current sources.\n',
            'INDEX.md': '# Index\nWiki contains synthetic evidence.\n',
            'Wiki/Observations.md': '# Observations\n' + LONG_PASSAGE + '\n' + '\n' * 7 +
                                    'The indigo observation is a different passage.\n',
            'Wiki/Schedule.md': '# Schedule\n2026-10-02: The quartz window opens at 17:40 UTC.\n',
            'Raw/Source.md': '# Source\nThe private-scope copper heron arrived.\n',
        }
        for name, content in contents.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        (self.root / 'Output').mkdir()

    def invoke(self, query, *flags, root=None, state=None, expected=0, text=False):
        args = [sys.executable, str(self.package), 'recall', str(root or self.root), query,
                '--state-dir', str(state or self.state), *map(str, flags)]
        if text:
            args += ['--text']
        process = subprocess.run(args, cwd=REPO, text=True, capture_output=True, timeout=20)
        self.assertEqual(process.returncode, expected, process.stdout + process.stderr)
        if expected == 0:
            cap = int(flags[flags.index('--max-bytes') + 1]) if '--max-bytes' in flags else 2048
            self.assertLessEqual(len(process.stdout.encode('utf-8')), cap)
        return process.stdout if text else json.loads(process.stdout)

    def one(self, query='amber', *flags):
        result = self.invoke(query, '--max-hits', '1', '--max-bytes', '8192', *flags)
        self.assertEqual(len(result['data']['hits']), 1, result)
        return result['data']['hits'][0]

    def assert_current(self, hit):
        content = (self.root / hit['path']).read_bytes()
        self.assertEqual(hit['sha256'], hashlib.sha256(content).hexdigest())
        if hit['delivery'] == 'full':
            span = '\n'.join(content.decode('utf-8').splitlines()[hit['start'] - 1:hit['end']])
            self.assertEqual(hit['excerpt'], span)
        else:
            self.assertNotIn('excerpt', hit)
        self.assertRegex(hit['evidence_id'], r'\A[0-9a-f]{32}\Z')

    def test_default_has_no_receipt_fields(self):
        first = self.one()
        second = self.one()
        self.assertEqual(first, second)
        self.assertNotIn('evidence_id', first)
        self.assertNotIn('delivery', first)
        self.assertEqual(first['excerpt'], LONG_PASSAGE)

    def test_full_repeat_and_source_edit(self):
        original = self.one('amber', '--with-receipts')
        self.assertEqual(original['delivery'], 'full')
        self.assert_current(original)
        repeat = self.one('amber', '--known-evidence', original['evidence_id'])
        self.assertEqual(repeat['delivery'], 'unchanged')
        self.assertEqual(repeat['evidence_id'], original['evidence_id'])
        self.assert_current(repeat)
        # A new/compacted caller with no retained passage must receive text
        # again. No process-local or persisted delivery history may suppress it.
        forgotten = self.one('amber', '--with-receipts')
        self.assertEqual(forgotten['delivery'], 'full')
        self.assertEqual(forgotten['evidence_id'], original['evidence_id'])
        self.assertEqual(forgotten['excerpt'], original['excerpt'])
        note = self.root / original['path']
        note.write_text(note.read_text() + 'A source change outside the cited span.\n')
        changed = self.one('amber', '--known-evidence', original['evidence_id'])
        self.assertEqual(changed['delivery'], 'full')
        self.assertNotEqual(changed['evidence_id'], original['evidence_id'])
        self.assert_current(changed)

    def test_new_passage_same_file_is_not_suppressed(self):
        original = self.one('amber', '--with-receipts')
        different = self.one('indigo', '--known-evidence', original['evidence_id'])
        self.assertEqual(different['path'], original['path'])
        self.assertEqual(different['sha256'], original['sha256'])
        self.assertNotEqual(different['start'], original['start'])
        self.assertEqual(different['delivery'], 'full')
        self.assertNotEqual(different['evidence_id'], original['evidence_id'])
        self.assert_current(different)

    def test_receipt_does_not_cross_roots(self):
        original = self.one('amber', '--with-receipts')
        other = self.base / 'other-project'
        shutil.copytree(self.root, other)
        result = self.invoke('amber', '--known-evidence', original['evidence_id'],
                             '--max-hits', '1', '--max-bytes', '8192', root=other,
                             state=self.base / 'other-private-state')
        hit = result['data']['hits'][0]
        self.assertEqual(hit['delivery'], 'full')
        self.assertNotEqual(hit['evidence_id'], original['evidence_id'])

    def test_receipt_cannot_restore_missing_or_excluded_source(self):
        original = self.one('amber', '--with-receipts')
        (self.root / original['path']).unlink()  # disposable fixture created by this test
        missing = self.invoke('amber', '--known-evidence', original['evidence_id'])
        self.assertFalse(missing['data']['hits'])
        included = self.one('copper', '--include-raw', '--with-receipts')
        excluded = self.invoke('copper', '--known-evidence', included['evidence_id'])
        self.assertFalse(excluded['data']['hits'])
        self.assertNotIn('private-scope', json.dumps(excluded))
        unknown = self.invoke('no-such-passage', '--known-evidence', 'f' * 32)
        self.assertFalse(unknown['data']['hits'])

    def test_text_receipt_reports_unchanged_without_repeating_evidence(self):
        original = self.one('amber', '--with-receipts')
        text = self.invoke('amber', '--known-evidence', original['evidence_id'],
                           '--max-bytes', '8192', text=True)
        self.assertIn('unchanged', text.lower())
        self.assertIn('Wiki/Observations.md', text)
        self.assertNotIn(LONG_PASSAGE, text)

    def test_invalid_and_excess_receipts_fail_closed(self):
        for value in ('abc', 'A' * 32, '0' * 31, 'z' * 32, '0' * 64):
            result = self.invoke('amber', '--known-evidence', value, expected=3)
            self.assertEqual(result['code'], 'recall_receipt')
        flags = tuple(part for index in range(33)
                      for part in ('--known-evidence', f'{index:032x}'))
        result = self.invoke('amber', *flags, expected=3)
        self.assertEqual(result['code'], 'recall_receipt')
        for value in (('bad',), tuple(f'{index:032x}' for index in range(33))):
            with self.assertRaises(ProductError) as raised:
                retrieval.recall(self.root, self.state, 'amber', known_evidence=value)
            self.assertEqual(raised.exception.code, 'recall_receipt')

    def test_receipts_do_not_enable_an_unavailable_sidecar_strategy(self):
        with self.assertRaises(ProductError) as raised:
            retrieval.recall(self.root, self.state, 'amber', strategy='hindsight', with_receipts=True)
        self.assertEqual(raised.exception.code, 'recall_strategy')

    def test_full_envelope_bounds_and_final_span_receipts(self):
        for cap in (512, 1024, 2048):
            first = self.invoke('amber', '--with-receipts', '--max-bytes', str(cap))
            for hit in first['data']['hits']:
                self.assert_current(hit)
                repeat = self.invoke('amber', '--known-evidence', hit['evidence_id'],
                                     '--max-bytes', str(cap))
                matching = [item for item in repeat['data']['hits']
                            if item['evidence_id'] == hit['evidence_id']]
                self.assertTrue(matching, repeat)
                self.assertEqual(matching[0]['delivery'], 'unchanged')
            if not first['data']['hits']:
                self.assertTrue(first['data']['truncated'])

    def test_hybrid_date_receipts_preserve_source_contract(self):
        flags = ('--strategy', 'hybrid', '--after', '2026-10-01', '--before', '2026-10-03',
                 '--max-bytes', '8192')
        first = self.invoke('quartz', '--with-receipts', *flags)
        self.assertTrue(first['data']['hits'], first)
        original = first['data']['hits'][0]
        self.assertIn('2026-10-02', original['excerpt'])
        self.assert_current(original)
        repeat = self.invoke('quartz', '--known-evidence', original['evidence_id'], *flags)
        hit = next(item for item in repeat['data']['hits']
                   if item['evidence_id'] == original['evidence_id'])
        self.assertEqual(hit['delivery'], 'unchanged')
        outside = self.invoke('quartz', '--known-evidence', original['evidence_id'],
                              '--strategy', 'hybrid', '--after', '2026-10-03',
                              '--max-bytes', '8192')
        self.assertFalse(outside['data']['hits'])

    def test_repeated_long_fixture_saves_bytes_including_receipt_input(self):
        flags = ('--max-hits', '1', '--max-bytes', '8192')
        # Warm both arms before comparing the complete two-call exchange.
        # Include first-response receipt overhead and both extra input flags.
        self.invoke('amber', *flags)
        baseline_first = self.invoke('amber', *flags)
        baseline_repeat = self.invoke('amber', *flags)
        first = self.invoke('amber', '--with-receipts', *flags)
        evidence_id = first['data']['hits'][0]['evidence_id']
        repeat = self.invoke('amber', '--known-evidence', evidence_id, *flags)
        encoded_size = lambda value: len(json.dumps(value, ensure_ascii=True).encode('utf-8'))
        baseline_bytes = encoded_size(baseline_first) + encoded_size(baseline_repeat)
        receipt_input_bytes = len(('--with-receipts --known-evidence ' + evidence_id).encode('utf-8'))
        receipt_bytes = encoded_size(first) + encoded_size(repeat) + receipt_input_bytes
        self.assertGreaterEqual(len(LONG_PASSAGE), 2000)
        self.assertEqual(repeat['data']['hits'][0]['delivery'], 'unchanged')
        self.assertLess(receipt_bytes, baseline_bytes)


if __name__ == '__main__':
    unittest.main()
