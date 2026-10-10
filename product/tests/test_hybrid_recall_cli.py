"""Packaged acceptance for optional source-preserving hybrid memory retrieval.

Fixtures are original synthetic data. Tests grade returned evidence and boundaries,
not answer-generation quality or real-vault token savings.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from product.shared_workspace import recall as retrieval
from product.shared_workspace.errors import ProductError

REPO = Path(__file__).resolve().parents[2]
DOCS = {
    'AGENTS.md': '# Rules\nRead the Wiki.\n',
    'INDEX.md': '# Index\nSynthetic project routes.\n',
    'Wiki/Quartz.md': '# Quartz\nThe quartz relay is ready. See [[Wiki/Schedule]].\n',
    'Wiki/Schedule.md': '# Schedule\n2026-10-02: The window opens at 17:40 UTC.\n',
    'Wiki/History.md': '# History\n2026-09-01: The quartz relay opened at 06:20 UTC.\n',
    'Raw/Source.md': '# Source\nThe raw-only copper heron arrived.\n',
    'Output/Report.md': '# Report\nThe output-only satin badger arrived.\n',
}


class HybridRecallCLITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package_dir = tempfile.TemporaryDirectory(prefix='hybrid-package-')
        cls.addClassCleanup(cls.package_dir.cleanup)
        cls.package = Path(cls.package_dir.name) / 'isolinear.pyz'
        proc = subprocess.run([sys.executable, str(REPO / 'scripts/build_product.py'),
                               '--output', str(cls.package)], cwd=REPO, capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hybrid-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'project'
        self.state = self.base / 'private'
        for name, content in DOCS.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')

    def cli(self, query, *flags, expected=0, hybrid=True):
        args = [sys.executable, str(self.package), 'recall', str(self.root), query,
                '--state-dir', str(self.state)]
        if hybrid:
            args += ['--strategy', 'hybrid']
        proc = subprocess.run(args + list(map(str, flags)), cwd=REPO,
                              capture_output=True, text=True, timeout=15)
        self.assertEqual(proc.returncode, expected, proc.stdout + proc.stderr)
        if expected == 0 and '--max-bytes' not in flags:
            self.assertLessEqual(len(proc.stdout.encode()), 2048)
        return json.loads(proc.stdout)

    def assert_sources(self, result):
        for hit in result['data']['hits']:
            content = (self.root / hit['path']).read_bytes().decode('utf-8')
            self.assertEqual(hit['excerpt'], '\n'.join(content.splitlines()[hit['start'] - 1:hit['end']]))
            self.assertEqual(hit['sha256'], hashlib.sha256(content.encode()).hexdigest())

    def test_partial_query_and_existing_exact_default(self):
        self.assertFalse(self.cli('quartz maintenance', hybrid=False)['data']['hits'])
        answer = self.cli('quartz maintenance')
        self.assertEqual(answer['data']['method'], 'hybrid')
        self.assertIn('Wiki/Quartz.md', {h['path'] for h in answer['data']['hits']})
        self.assert_sources(answer)
        self.assertFalse(answer['data']['retrieval']['semantic_model'])

    def test_crlf_source_hash_matches_original_bytes(self):
        content = b'# Windows Source\r\nThe crimson kestrel is ready.\r\n'
        note = self.root / 'Wiki/Windows Source.md'
        note.write_bytes(content)
        answer = self.cli('crimson kestrel', '--refresh')
        hit = next(item for item in answer['data']['hits'] if item['path'] == 'Wiki/Windows Source.md')
        self.assertEqual(hit['sha256'], hashlib.sha256(content).hexdigest())
        self.assert_sources(answer)

    def test_explicit_link_neighbor_without_query_words(self):
        answer = self.cli('quartz')
        schedule = [h for h in answer['data']['hits'] if h['path'] == 'Wiki/Schedule.md']
        self.assertTrue(schedule, answer)
        self.assertIn('17:40 UTC', '\n'.join(h['excerpt'] for h in schedule))
        self.assert_sources(answer)
        warm = self.cli('quartz')
        self.assertEqual(self.cli('quartz')['data'], warm['data'])
        self.assertIn('changes_since_index', warm['data']['unsearched'])

    def test_dates_filter_all_arms_and_expanded_neighbors(self):
        # Undated seed links to an out-of-window note. Neither may be quoted.
        (self.root / 'Wiki/Quartz.md').write_text('# Quartz\n2026-10-02: quartz relay [[History]].\n')
        answer = self.cli('quartz', '--after', '2026-10-01', '--before', '2026-10-03')
        names = {h['path'] for h in answer['data']['hits']}
        self.assertIn('Wiki/Quartz.md', names)
        self.assertNotIn('Wiki/History.md', names)
        self.assert_sources(answer)
        empty = self.cli('quartz', '--after', '2027-01-01')
        self.assertFalse(empty['data']['hits'])

    def test_dates_are_excerpt_dates_not_updated_metadata_or_mtime(self):
        (self.root / 'Wiki/Quartz.md').write_text(
            '---\nupdated: 2026-10-02\n---\n# Quartz\n\n\n\n\n'
            '2026-09-01: quartz window is 06:20 UTC.\n')
        result = self.cli('quartz', '--after', '2026-10-01')
        self.assertFalse(result['data']['hits'], result)

    def test_invalid_dates_and_exact_date_misuse(self):
        for flags in [('--after', 'tomorrow'), ('--before', '2026-02-30'),
                      ('--after', '2026-10-03', '--before', '2026-10-01'), ('--after', '')]:
            self.assertEqual(self.cli('quartz', *flags, expected=3)['code'], 'recall_date')
        self.assertEqual(self.cli('quartz', '--after', '2026-10-01',
                                 hybrid=False, expected=3)['code'], 'recall_date')

    def test_link_expansion_cannot_expand_scope(self):
        private = self.root / 'Wiki/credentials'
        private.mkdir()
        (private / 'Secret.md').write_text('private-only zebra')
        nested = self.root / 'Wiki/Nested'
        nested.mkdir()
        (nested / '.shared-memory.json').write_text('{}')
        (nested / 'Secret.md').write_text('nested-only zebra')
        (self.base / 'Outside.md').write_text('outside-only zebra')
        (self.root / 'Wiki/Quartz.md').write_text(
            '# Quartz\nquartz [[Raw/Source]] [[Output/Report]] [[credentials/Secret]] '
            '[[Nested/Secret]] [[../Outside]]\n')
        result = self.cli('quartz')
        self.assertEqual({h['path'] for h in result['data']['hits']},
                         {'Wiki/Quartz.md', 'Wiki/History.md'})
        raw = self.cli('copper', '--include-raw')
        self.assertIn('Raw/Source.md', {h['path'] for h in raw['data']['hits']})
        self.assertFalse(self.cli('copper')['data']['hits'])
        self.assertFalse(self.cli('badger')['data']['hits'])
        self.assertIn('Output/Report.md', {h['path'] for h in
                      self.cli('badger', '--include-output')['data']['hits']})
        self.assertFalse(list(self.root.rglob('*.sqlite3')))

    def test_ambiguous_link_is_not_arbitrarily_resolved(self):
        (self.root / 'Wiki/Other').mkdir()
        (self.root / 'Wiki/Other/Schedule.md').write_text('# Other\nAmbiguous-only 22:10.\n')
        (self.root / 'Wiki/Quartz.md').write_text('# Quartz\nquartz [[Schedule]].\n')
        result = self.cli('quartz')
        self.assertNotIn('Wiki/Schedule.md', {h['path'] for h in result['data']['hits']})
        self.assertNotIn('Wiki/Other/Schedule.md', {h['path'] for h in result['data']['hits']})

    def test_unavailable_duplicate_link_does_not_imply_unique_basename(self):
        other = self.root / 'Wiki/Other/Schedule.md'
        other.parent.mkdir()
        other.write_text('# Other\nUnavailable schedule.\n')
        (self.root / 'Wiki/Quartz.md').write_text('# Quartz\nquartz [[Schedule]].\n')
        original = retrieval._read
        with mock.patch.object(retrieval, '_read', side_effect=lambda p: None if p == other else original(p)):
            result = retrieval.recall(self.root, self.state, 'quartz', strategy='hybrid')
        self.assertNotIn('Wiki/Schedule.md', {h['path'] for h in result['hits']})
        self.assertGreater(result['unavailable'], 0)

    def test_symlink_neighbor_cannot_quote_an_outside_file(self):
        outside = self.base / 'Outside.md'
        outside.write_text('# Outside\nquartz private value\n')
        link = self.root / 'Wiki/Outside.md'
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest('Environment does not permit disposable symlinks')
        (self.root / 'Wiki/Quartz.md').write_text('# Quartz\nquartz [[Outside]].\n')
        result = self.cli('quartz')
        self.assertNotIn('Wiki/Outside.md', {h['path'] for h in result['data']['hits']})
        self.assertNotIn('private value', str(result))

    def test_deleted_and_changed_sources_do_not_survive_cached_index(self):
        result = self.cli('quartz')
        self.assert_sources(result)
        (self.root / 'Wiki/Schedule.md').unlink()  # Disposable fixture only.
        (self.root / 'Wiki/Quartz.md').write_text('# Quartz\nThe relay was cancelled.\n')
        result = self.cli('quartz')
        self.assertNotIn('Wiki/Schedule.md', {h['path'] for h in result['data']['hits']})
        self.assertNotIn('ready', '\n'.join(h['excerpt'] for h in result['data']['hits']))
        self.assert_sources(result)

    def test_budget_and_no_duplicate_passages(self):
        for size in (512, 1024, 2048):
            result = self.cli('quartz', '--max-bytes', str(size))
            self.assertLessEqual(len(json.dumps(result, ensure_ascii=True).encode()), size)
            keys = [(h['path'], h['start'], h['end']) for h in result['data']['hits']]
            self.assertEqual(len(keys), len(set(keys)))
        self.assertLessEqual(len(self.cli('quartz', '--max-hits', '1')['data']['hits']), 1)

    def test_root_qualified_links_have_consistent_root_semantics(self):
        self.cli('quartz')
        alternate = self.root / 'Wiki/Wiki/Schedule.md'
        alternate.parent.mkdir()
        alternate.write_text('# Other\nUncaptured competing relative interpretation.\n')
        for flags in ((), ('--refresh',)):
            result = self.cli('quartz', *flags)
            self.assertIn('Wiki/Schedule.md', {h['path'] for h in result['data']['hits']})
            self.assertNotIn('Wiki/Wiki/Schedule.md', {h['path'] for h in result['data']['hits']})

    def test_warm_relative_qualified_links_abstain_on_unknown_variants(self):
        (self.root / 'Wiki/Child').mkdir()
        (self.root / 'Wiki/Child/Schedule.md').write_text('# Schedule\nRelated window 17:40.\n')
        (self.root / 'Wiki/Quartz.md').write_text('# Quartz\nquartz [[Child/Schedule]].\n')
        cold = self.cli('quartz')
        self.assertIn('Wiki/Child/Schedule.md', {h['path'] for h in cold['data']['hits']})
        warm = self.cli('quartz')
        self.assertNotIn('Wiki/Child/Schedule.md', {h['path'] for h in warm['data']['hits']})

    def test_exact_current_title_survives_stale_index_and_archive_frequency(self):
        archive = self.root / 'Wiki/Archive'
        archive.mkdir()
        (archive / 'Quartz Old.md').write_text('# Old\n' + ('quartz ' * 200 + '\n') * 8)
        self.cli('quartz')
        (self.root / 'Wiki/Quartz.md').write_text('# Quartz\nCurrent quartz decision is ready.\n')
        result = self.cli('quartz')
        self.assertEqual(result['data']['hits'][0]['path'], 'Wiki/Quartz.md')
        self.assertIn('decision is ready', result['data']['hits'][0]['excerpt'])
        single = self.cli('quartz', '--max-hits', '1')
        self.assertIn('decision is ready', single['data']['hits'][0]['excerpt'])
        self.assert_sources(result)

    def test_warm_hybrid_never_enumerates_the_cloud_provider(self):
        self.cli('quartz')
        with mock.patch.object(retrieval, '_eligible', side_effect=AssertionError('provider inventory touched')):
            result = retrieval.recall(self.root, self.state, 'quartz maintenance', strategy='hybrid')
        self.assertIn('Wiki/Quartz.md', {h['path'] for h in result['hits']})
        self.assertIn('Wiki/Schedule.md', {h['path'] for h in result['hits']})
        self.assertIn('changes_since_index', result['unsearched'])

    def test_blocked_warm_source_does_not_discard_verified_hits(self):
        self.cli('quartz')
        original = retrieval._read
        history = self.root / 'Wiki/History.md'
        old = history.read_text()
        def delayed(path):
            if path == history:
                time.sleep(.5)
                return old
            return original(path)
        started = time.monotonic()
        with mock.patch.object(retrieval, '_read', side_effect=delayed):
            result = retrieval.recall(self.root, self.state, 'quartz', strategy='hybrid')
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertIn('Wiki/Quartz.md', {h['path'] for h in result['hits']})
        self.assertGreater(result['unavailable'], 0)
        self.assertTrue(result['truncated'])
        self.assertIn('source_read_budget', result['unsearched'])

    def test_warm_basename_links_abstain_when_new_paths_are_unsearched(self):
        (self.root / 'Wiki/Quartz.md').write_text('# Quartz\nquartz [[Schedule]].\n')
        self.cli('quartz')
        warm = self.cli('quartz')
        self.assertNotIn('Wiki/Schedule.md', {h['path'] for h in warm['data']['hits']})
        self.assertIn('uncaptured_paths', warm['data']['unsearched'])

    def test_missing_fts_uses_checked_lexical_fallback(self):
        with mock.patch.object(retrieval, '_connect', side_effect=OSError('unavailable')):
            result = retrieval.recall(self.root, self.state, 'quartz maintenance', strategy='hybrid')
        self.assertIn('Wiki/Quartz.md', {h['path'] for h in result['hits']})
        self.assertNotIn('fts5', result['method'])

    def test_deadline_and_invalid_bounds(self):
        with mock.patch.object(retrieval, '_bounded', side_effect=lambda op, deadline, timeout: timeout()):
            result = retrieval.recall(self.root, self.state, 'quartz', strategy='hybrid')
        self.assertEqual(result['method'], 'deadline')
        self.assertTrue(result['truncated'])
        with self.assertRaises(ProductError):
            retrieval.recall(self.root, self.state, 'quartz', strategy='unknown')


if __name__ == '__main__':
    unittest.main()
