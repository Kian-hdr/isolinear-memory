"""Source-linked, bounded memory retrieval and targeted table writes."""
from __future__ import annotations

import hashlib
import argparse
from contextlib import closing
import errno
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from product.shared_workspace import recall as retrieval
from product.shared_workspace import folder_workflow
from product.shared_workspace.errors import ProductError


REPO = Path(__file__).resolve().parents[2]


class RecallCLITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='recall-package-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.package = Path(cls.temp.name) / 'product.pyz'
        process = subprocess.run([sys.executable, str(REPO / 'scripts/build_product.py'), '--output', str(cls.package)],
                                 text=True, capture_output=True, cwd=REPO)
        if process.returncode:
            raise AssertionError(process.stdout + process.stderr)

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='recall-case-')
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base / 'vault'
        self.root.mkdir()
        self.state = self.base / 'private-state'
        (self.root / 'Wiki').mkdir()
        (self.root / 'Raw').mkdir()
        (self.root / 'Output').mkdir()
        (self.root / 'AGENTS.md').write_text('# Instructions\nUse a source.\n')
        (self.root / 'INDEX.md').write_text('# Routing\nWiki has facts.\n')
        (self.root / 'Wiki' / 'Bird.md').write_text('# Bird\nThe rare violet raven arrived.\n', encoding='utf-8')
        (self.root / 'Wiki' / 'Register.md').write_text(
            '# Register\n\nCapture context before adding a row.\n\n| UTC | Action |\n| --- | --- |\n| before | keep |\n', encoding='utf-8')
        (self.root / 'Raw' / 'Evidence.md').write_text('# Source\nRaw-only otter.\n')
        (self.root / 'Output' / 'Report.md').write_text('# Report\nOutput-only badger.\n')
        (self.base / 'Outside.md').write_text('outside-only walrus')

    def tearDown(self):
        # A timeout returns promptly while its daemon reader finishes later.
        # Join finite mocked readers before TemporaryDirectory removes files on
        # Windows, where open SQLite and note handles prevent deletion.
        for _ in range(3):
            workers = [thread for thread in threading.enumerate()
                       if thread.name == 'bounded-markdown-memory']
            if not workers:
                break
            for thread in workers:
                thread.join(timeout=2)

    def run_cli(self, name, *args, expected=0, json_result=True):
        process = subprocess.run([sys.executable, str(self.package), name, str(self.root), *map(str, args)],
                                 text=True, capture_output=True, timeout=30)
        self.assertEqual(process.returncode, expected, process.stdout + process.stderr)
        if name == 'recall' and '--text' not in args and '--max-bytes' not in args and expected == 0:
            self.assertLessEqual(len(process.stdout.encode('utf-8')), 2048)
        return json.loads(process.stdout) if json_result else process.stdout

    def test_scope_private_index_and_source_hash(self):
        nested = self.root / 'Wiki' / 'Nested'
        nested.mkdir()
        (nested / '.shared-memory.json').write_text('{}')
        (nested / 'Secret.md').write_text('nested-only marmot')
        (self.root / 'Wiki' / 'hidden.md').symlink_to(self.base / 'Outside.md')
        response = self.run_cli('recall', 'violet', '--state-dir', self.state)
        self.assertLessEqual(len(json.dumps(response, ensure_ascii=True).encode()), 2048)
        self.assertEqual(response['data']['method'], 'fts5')
        hit = response['data']['hits'][0]
        self.assertEqual(hit['path'], 'Wiki/Bird.md')
        self.assertEqual(hit['start'], 2)
        self.assertEqual(hit['end'], 2)
        self.assertEqual(hit['excerpt'], 'The rare violet raven arrived.')
        self.assertEqual(hit['sha256'], hashlib.sha256((self.root / hit['path']).read_bytes()).hexdigest())
        self.assertTrue((self.state / 'recall.sqlite3').is_file())
        self.assertNotIn('Wiki/Nested', response['data']['unavailable_sources'])
        self.assertFalse(list(self.root.rglob('*.sqlite3')))
        with closing(retrieval._connect(self.state / 'recall.sqlite3')) as db:
            db.execute('INSERT INTO chunks(path,start,end,heading,text) VALUES(?,?,?,?,?)',
                       ('Wiki/Nested/Secret.md', 1, 1, '', 'nested-only marmot'))
            db.commit()
        hidden = self.run_cli('recall', 'marmot', '--state-dir', self.state)['data']
        self.assertFalse(hidden['hits'])
        self.assertNotIn('Wiki/Nested/Secret.md', hidden['unavailable_sources'])
        for term in ('marmot', 'walrus', 'otter', 'badger'):
            self.assertFalse(self.run_cli('recall', term, '--state-dir', self.state)['data']['hits'])
        self.assertEqual(self.run_cli('recall', 'otter', '--state-dir', self.state,
                                      '--include-raw')['data']['hits'][0]['path'], 'Raw/Evidence.md')
        self.assertFalse(self.run_cli('recall', 'otter', '--state-dir', self.state)['data']['hits'])
        self.assertEqual(self.run_cli('recall', 'badger', '--state-dir', self.state,
                                      '--include-output')['data']['hits'][0]['path'], 'Output/Report.md')
        # All query words must occur in the same source window; a navigation
        # link alone must not impersonate a removed fact.
        self.assertFalse(self.run_cli('recall', 'violet walrus', '--state-dir', self.state)['data']['hits'])
        (self.root / 'Wiki' / 'Bird.md').write_text('# Bird\nThe gold raven arrived.\n')
        self.assertFalse(self.run_cli('recall', 'violet', '--state-dir', self.state)['data']['hits'])
        self.assertEqual(self.run_cli('recall', 'gold raven', '--state-dir', self.state)['data']['hits'][0]['path'], 'Wiki/Bird.md')

    def test_same_size_reset_mtime_edit_reindexes_without_windows_ctime(self):
        path = self.root / 'Wiki' / 'Bird.md'
        self.run_cli('recall', 'violet', '--state-dir', self.state)
        old = path.stat()
        path.write_text('# Bird\nThe rare indigo raven arrived.\n')
        os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
        self.assertEqual(path.stat().st_size, old.st_size)
        self.assertEqual(path.stat().st_mtime_ns, old.st_mtime_ns)
        self.assertEqual(self.run_cli('recall', 'indigo', '--state-dir', self.state)['data']['hits'][0]['path'], 'Wiki/Bird.md')

    def test_refresh_does_not_trust_windows_creation_time(self):
        self.run_cli('recall', 'violet', '--state-dir', self.state)
        path = self.root / 'Wiki' / 'Bird.md'
        previous = path.stat()
        path.write_text('# Bird\nThe rare indigo raven arrived.\n')
        os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
        with mock.patch.object(retrieval, '_metadata_reuse_allowed', return_value=False):
            result = retrieval.recall(self.root, self.state, 'indigo', refresh=True)
        self.assertEqual(result['hits'][0]['path'], 'Wiki/Bird.md')

    def test_excerpt_prefers_matching_heading_over_filename_assisted_title(self):
        (self.root / 'Wiki' / 'Cedar Operations.md').write_text(
            '# Cedar Operations\n\n## Cedar launch posture\n'
            'The readiness decision is green for the 06:20 review.\n')
        hit = self.run_cli('recall', 'cedar launch posture', '--state-dir', self.state)['data']['hits'][0]
        self.assertEqual((hit['path'], hit['start'], hit['end']), ('Wiki/Cedar Operations.md', 3, 3))
        self.assertEqual(hit['excerpt'], '## Cedar launch posture')
        expanded = self.run_cli('show', '--path', hit['path'], '--sha256', hit['sha256'][:24],
                                '--start', 3, '--end', 4)['data']
        self.assertIn('06:20', expanded['excerpt'])

    def test_show_rejects_stale_and_private_paths(self):
        hit = self.run_cli('recall', 'violet', '--state-dir', self.state)['data']['hits'][0]
        args = ('--path', hit['path'], '--sha256', hit['sha256'], '--start', hit['start'], '--end', hit['end'])
        shown = self.run_cli('show', *args)['data']
        self.assertEqual(shown['excerpt'], hit['excerpt'])
        compact = ('--path', hit['path'], '--sha256', hit['sha256'][:24], '--start', hit['start'], '--end', hit['end'])
        self.assertEqual(self.run_cli('show', *compact)['data']['sha256'], hit['sha256'])
        text = self.run_cli('recall', 'violet', '--state-dir', self.state, '--text', json_result=False)
        self.assertIn('sha256=' + hit['sha256'][:24], text)
        self.assertNotIn(hit['sha256'], text)
        bad_prefix = ('--path', hit['path'], '--sha256', '0' * 24, '--start', hit['start'], '--end', hit['end'])
        self.assertEqual(self.run_cli('show', *bad_prefix, expected=4)['code'], 'recall_stale')
        (self.root / hit['path']).write_text('# Bird\nThe changed violet raven arrived.\n')
        self.assertEqual(self.run_cli('show', *args, expected=4)['code'], 'recall_stale')
        self.assertEqual(self.run_cli('show', '--path', '../Outside.md', '--sha256', hit['sha256'],
                                      '--start', 1, '--end', 1, expected=3)['code'], 'recall_path')
        private = self.root / 'Wiki' / 'credentials'
        private.mkdir()
        (private / 'Secret.md').write_text('secret')
        self.assertEqual(self.run_cli('show', '--path', 'Wiki/credentials/Secret.md', '--sha256', hit['sha256'],
                                      '--start', 1, '--end', 1, expected=3)['code'], 'recall_path')

    def test_budget_and_text_abstention(self):
        for n in range(12):
            (self.root / 'Wiki' / f'Term{n}.md').write_text(f'# Term {n}\n' + ('violet ' * 80) + '\n')
        response = self.run_cli('recall', 'violet', '--state-dir', self.state)
        self.assertLessEqual(len(json.dumps(response, ensure_ascii=True).encode()), 2048)
        self.assertLessEqual(len(response['data']['hits']), 5)
        self.assertTrue(response['data']['truncated'])
        output = self.run_cli('recall', 'unfindablezebra', '--state-dir', self.state, '--text', json_result=False)
        self.assertIn('unsearched=Raw,Output', output)
        self.assertEqual(len(output.splitlines()), 1)

    def test_direct_fallback_is_bounded(self):
        with mock.patch.object(retrieval, '_connect', side_effect=__import__('sqlite3').OperationalError('no fts')):
            result = retrieval.recall(self.root, self.state, 'violet')
        self.assertEqual(result['method'], 'direct')
        self.assertEqual(result['hits'][0]['path'], 'Wiki/Bird.md')

    def test_provider_stall_returns_partial_coverage_within_deadline(self):
        release = threading.Event()
        finished = threading.Event()
        def blocked(*args, **kwargs):
            release.wait(3)
            finished.set()
            return None
        try:
            with mock.patch.object(retrieval, '_eligible', side_effect=blocked):
                result = retrieval.recall(self.root, self.state, 'violet', deadline=.1, refresh=True)
            self.assertFalse(finished.is_set(), 'Recall waited for the blocked provider')
        finally:
            release.set()
        self.assertEqual(result['method'], 'deadline')
        self.assertTrue(result['truncated'])
        self.assertIn('Wiki', result['unsearched'])

    def test_show_stall_has_no_excerpt_after_deadline(self):
        path = self.root / 'Wiki' / 'Bird.md'
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        original = retrieval._read
        release = threading.Event()
        finished = threading.Event()
        def blocked(path):
            release.wait(3)
            finished.set()
            return original(path)
        try:
            with mock.patch.object(retrieval, '_read', side_effect=blocked):
                with self.assertRaises(ProductError) as caught:
                    retrieval.show(self.root, 'Wiki/Bird.md', sha, 1, 1, deadline=.1)
            self.assertFalse(finished.is_set(), 'Show waited for the blocked provider')
        finally:
            release.set()
        self.assertEqual(caught.exception.code, 'recall_deadline')
        self.assertEqual(caught.exception.data, {})

    def test_cli_root_validation_is_within_memory_deadline(self):
        args = argparse.Namespace(command='show', project=str(self.root), path='Wiki/Bird.md',
                                  sha256='0' * 64, start=1, end=1, max_bytes=8192)
        release = threading.Event()
        finished = threading.Event()
        def blocked(_):
            release.wait(3)
            finished.set()
            return self.root
        def short_bounded(operation, **kwargs):
            return retrieval._bounded(operation, .1,
                                      lambda: retrieval._error('deadline', 'No excerpt returned.', 5))
        try:
            with mock.patch.object(folder_workflow.workflow, 'selected_root', side_effect=blocked), \
                    mock.patch.object(retrieval, 'bounded_cli', side_effect=short_bounded):
                with self.assertRaises(ProductError) as caught:
                    folder_workflow.dispatch(None, args)
            self.assertFalse(finished.is_set(), 'CLI waited for selected-root validation')
        finally:
            release.set()
        self.assertEqual(caught.exception.code, 'recall_deadline')

    def test_walk_error_reports_safe_source_and_partial_coverage(self):
        def broken_walk(base, *, followlinks, onerror):
            onerror(OSError(errno.EACCES, 'unavailable', str(base / 'Denied')))
            return iter([(str(base), [], [])])
        with mock.patch.object(retrieval.os, 'walk', side_effect=broken_walk):
            paths, meta = retrieval._eligible(self.root)
        self.assertEqual(meta['unavailable_sources'], ['Wiki/Denied'])
        self.assertTrue(meta['truncated_scan'])
        self.assertEqual(meta['unavailable'], 1)
        self.assertTrue(paths)

    def test_unreadable_note_is_named_without_emitting_its_content(self):
        original = retrieval._read
        note = self.root / 'Wiki' / 'Bird.md'
        with mock.patch.object(retrieval, '_read',
                               side_effect=lambda path: None if path == note else original(path)):
            result = retrieval.recall(self.root, self.state, 'violet', refresh=True)
        self.assertFalse(result['hits'])
        self.assertIn('Wiki/Bird.md', result['unavailable_sources'])
        self.assertGreater(result['unavailable'], 0)

    def test_cold_path_match_skips_slow_full_content_index(self):
        (self.root / 'Wiki' / 'Shared Memory.md').write_text('# Shared Memory\nA current handoff is available.\n')
        with mock.patch.object(retrieval, '_refresh', side_effect=AssertionError('full refresh was called')):
            result = retrieval.recall(self.root, self.state, 'Shared Memory', deadline=.1)
        self.assertEqual(result['method'], 'path_first')
        self.assertEqual(result['hits'][0]['path'], 'Wiki/Shared Memory.md')
        self.assertIn('other Wiki content', result['unsearched'])
        self.assertTrue(result['truncated'])

    def test_warm_index_ranks_current_exact_title_before_archive(self):
        current = self.root / 'Wiki' / 'Shared Memory.md'
        current.write_text('# Shared Memory\nCurrent owner: Rowan.\n')
        archive = self.root / 'Wiki' / 'Archive'
        archive.mkdir()
        (archive / 'Shared Memory.md').write_text('# Shared Memory\n' + 'Shared Memory archive.\n' * 12)
        self.run_cli('recall', 'Shared Memory', '--state-dir', self.state, '--refresh')
        result = self.run_cli('recall', 'Shared Memory', '--state-dir', self.state,
                              '--max-hits', 1)['data']
        self.assertEqual(result['method'], 'fts5_cached')
        self.assertEqual(result['hits'][0]['path'], 'Wiki/Shared Memory.md')
        expanded = self.run_cli('recall', 'Shared Memory', '--state-dir', self.state)['data']
        self.assertEqual(sum(hit['path'] == 'Wiki/Shared Memory.md' for hit in expanded['hits']), 1)

    def test_captured_private_baseline_seeds_body_search_without_provider_sweep(self):
        self.run_cli('setup', '--state-dir', self.state, '--actor', 'indexer', '--person', 'Tester', '--agent', 'Test')
        with mock.patch.object(retrieval, '_refresh', side_effect=AssertionError('full refresh was called')):
            result = retrieval.recall(self.root, self.state, 'rare violet', deadline=5)
        self.assertEqual(result['method'], 'fts5_baseline')
        self.assertEqual(result['hits'][0]['path'], 'Wiki/Bird.md')
        self.assertIn('changes_since_capture', result['unsearched'])
        self.assertTrue((self.state / 'recall.sqlite3').exists())

    def test_atomic_row_append_validates_table_and_readonly(self):
        self.run_cli('setup', '--state-dir', self.state, '--actor', 'reader', '--person', 'Tester', '--agent', 'Test')
        appended = self.run_cli('append-row', '--path', 'Wiki/Register.md', '--heading', 'Register',
                                '--row', '| now | preserve |', '--state-dir', self.state)['data']
        self.assertEqual(appended['line'], 8)
        self.assertIn('| before | keep |\n| now | preserve |\n', (self.root / 'Wiki' / 'Register.md').read_text())
        self.assertEqual(self.run_cli('append-row', '--path', 'Wiki/Register.md', '--heading', 'Register',
                                      '--row', '| invalid |', '--state-dir', self.state, expected=3)['code'], 'recall_row')
        self.assertEqual(self.run_cli('append-row', '--path', 'AGENTS.md', '--heading', 'Instructions',
                                      '--row', '| no |', '--state-dir', self.state, expected=3)['code'], 'recall_scope')
        command = [sys.executable, str(self.package), 'append-row', str(self.root), '--path', 'Wiki/Register.md',
                   '--heading', 'Register', '--state-dir', str(self.state)]
        first = subprocess.Popen([*command, '--row', '| concurrent-a | keep |'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        second = subprocess.Popen([*command, '--row', '| concurrent-b | keep |'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for process in (first, second):
            stdout, stderr = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, stdout + stderr)
        content = (self.root / 'Wiki' / 'Register.md').read_text()
        self.assertEqual(content.count('| concurrent-a | keep |'), 1)
        self.assertEqual(content.count('| concurrent-b | keep |'), 1)
        readonly_root = self.base / 'reader-copy'
        shutil.copytree(self.root, readonly_root)
        self.root = readonly_root
        private = self.base / 'reader-state'
        self.run_cli('setup', '--state-dir', private, '--actor', 'reader2', '--person', 'Tester', '--agent', 'Test', '--read-only')
        self.assertEqual(self.run_cli('append-row', '--path', 'Wiki/Register.md', '--heading', 'Register',
                                      '--row', '| denied | no |', '--state-dir', private, expected=4)['code'], 'folder_readonly')

    def test_atomic_row_append_crosses_blank_register_batches(self):
        note = self.root / 'Wiki' / 'Register.md'
        note.write_text('# Register\n\n| Date | Action |\n| --- | --- |\n'
                        '| first | keep |\n\n| second | keep |\n\n| third | keep |\n')
        self.run_cli('setup', '--state-dir', self.state, '--actor', 'recorder',
                     '--person', 'Tester', '--agent', 'Test')
        result = self.run_cli('append-row', '--path', 'Wiki/Register.md', '--heading', 'Register',
                              '--row', '| last | keep |', '--state-dir', self.state)['data']
        self.assertEqual(result['line'], 10)
        self.assertTrue(note.read_text().endswith('| third | keep |\n| last | keep |\n'))


if __name__ == '__main__':
    unittest.main()
