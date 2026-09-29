"""Actual independent folder roots and immutable-history transport fixtures."""
from pathlib import Path
import hashlib
import errno
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared_workspace import folder as module
from shared_workspace.folder import Folder
from shared_workspace.errors import ProductError


def transport(source, target):
    """Synthetic file delivery only; no server or authority substitutes."""
    for path in (source.root / '.shared-memory').rglob('*'):
        if path.is_file():
            destination = target.root / path.relative_to(source.root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)


def inventory(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and not p.is_symlink()}


class FolderTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='direct-folder-')
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()

    def create(self, name='one', files=None, **kwargs):
        root = self.base / name; root.mkdir()
        for path, text in (files or {'Note.md': 'one\ntwo\nthree\n'}).items():
            destination = root / path; destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(text.encode())
        return Folder.initialize(root, self.base / (name + '-private'), name, 'Fixture person', name + ' agent', **kwargs)

    def test_sync_io_reports_phase_and_errno_without_exception_content(self):
        one = self.create()
        secret = 'private note text inside OS error'
        with patch.object(one, '_capture', side_effect=OSError(errno.ENOSPC, secret)):
            with self.assertRaises(ProductError) as caught:
                one.sync()
        self.assertEqual(caught.exception.code, 'folder_io')
        self.assertIn('sync_capture_local', str(caught.exception))
        self.assertIn('ENOSPC', str(caught.exception))
        self.assertNotIn(secret, str(caught.exception))

    def test_opt_in_private_progress_records_only_phase_and_count(self):
        one = self.create()
        marker = one.state / 'capture-progress.json'
        self.assertFalse(marker.exists())
        secret = 'private note text inside OS error'
        with patch.dict(os.environ, {'SHARED_MEMORY_CAPTURE_PHASES': '1'}):
            with patch.object(one, '_capture', side_effect=OSError(errno.ENOSPC, secret)):
                with self.assertRaises(ProductError):
                    one.sync()
        record = json.loads(marker.read_text())
        self.assertEqual(record['phase'], 'sync_capture_local')
        self.assertEqual(set(record), {'format', 'phase', 'updated_at', 'pid'})
        self.assertNotIn(secret, marker.read_text())
        with patch.dict(os.environ, {'SHARED_MEMORY_CAPTURE_PHASES': '1'}):
            self.assertEqual(one.sync()['readiness'], 'ready')
        self.assertEqual(json.loads(marker.read_text())['phase'], 'complete')

    def test_large_ignored_asset_tree_avoids_per_file_link_checks(self):
        one = self.create()
        assets = one.root / 'Raw' / 'media'
        assets.mkdir(parents=True)
        for index in range(2000):
            (assets / f'asset-{index:04}.png').write_bytes(b'fixture')
        actual = module.is_link_or_reparse
        checked = []
        def counted(path):
            checked.append(Path(path))
            if Path(path).suffix == '.png':
                raise AssertionError('Ignored binary asset triggered provider link metadata I/O')
            return actual(path)
        with patch.object(module, 'is_link_or_reparse', side_effect=counted):
            result = one._scan(set(one._baseline()))
        self.assertIn('Note.md', result)
        self.assertLess(len(checked), 20)
        outside = self.base / 'outside.md'; outside.write_text('external')
        tracked = one.root / 'Note.md'; tracked.unlink(); tracked.symlink_to(outside)
        with self.assertRaises(ProductError):
            one._scan(set(one._baseline()))

    @unittest.skipIf(os.name == 'nt', 'Windows disables metadata reuse; the separate Windows test verifies partial coverage without a false ready state')
    def test_incremental_scan_converges_over_four_thousand_new_notes(self):
        one = self.create()
        bulk = one.root / 'Wiki' / 'bulk'
        bulk.mkdir(parents=True)
        for index in range(4001):
            (bulk / f'note-{index:04}.md').write_text(f'detail {index}\n')
        coverages = []
        for _ in range(10):
            result = one.sync()
            coverage = result['scan_coverage']
            coverages.append(coverage['covered'])
            self.assertLessEqual(coverage['read_this_run'], module.SCAN_READ_LIMIT)
            if result['readiness'] == 'ready':
                break
            self.assertIn(coverage['audit'], {'in_progress', 'coverage_incomplete'})
            self.assertGreater(coverage['deferred'], 0)
        self.assertEqual(result['readiness'], 'ready')
        self.assertEqual(coverage['eligible'], 4002)
        self.assertEqual(coverage['covered'], 4002)
        self.assertEqual(coverage['deferred'], 0)
        self.assertEqual(coverage['audit'], 'current')
        self.assertEqual(sorted(coverages), coverages)
        self.assertEqual((bulk / 'note-4000.md').read_text(), 'detail 4000\n')
        index_bytes = (one.state / 'scan-index.json').read_bytes()
        self.assertNotIn(b'detail 4000', index_bytes)
        self.assertIn(b'"checksum"', index_bytes)

    def test_incremental_scan_prioritizes_fresh_edits_over_backlog(self):
        from shared_workspace import folder_workflow
        one = self.create()
        bulk = one.root / 'Wiki' / 'bulk'; bulk.mkdir(parents=True)
        for index in range(1200):
            (bulk / f'note-{index:04}.md').write_text(f'old {index}\n')
        first = one.sync()
        self.assertEqual(first['readiness'], 'partial')
        index = json.loads((one.state / 'scan-index.json').read_text())
        covered = next(name for name in index['entries'] if name.startswith('Wiki/bulk/'))
        (one.root / covered).write_text('fresh covered edit\n')
        (one.root / 'AGENTS.md').write_text('fresh agent rule\n')
        (one.root / 'INDEX.md').write_text('fresh routing detail\n')
        (bulk / 'new-fresh.md').write_text('fresh new detail\n')
        second = one.sync()
        self.assertEqual(second['readiness'], 'partial')
        self.assertLessEqual(second['scan_coverage']['read_this_run'], module.SCAN_READ_LIMIT)
        for name in (covered, 'AGENTS.md', 'INDEX.md', 'Wiki/bulk/new-fresh.md'):
            expected = (one.root / name).read_bytes().decode('utf-8')
            self.assertIn(expected, [event['changes'].get(name) for event in one.history(name)['events']])
        brief = folder_workflow.brief(second)
        self.assertEqual(brief['scan_coverage']['deferred'], second['scan_coverage']['deferred'])
        self.assertNotIn('note-', json.dumps(brief['scan_coverage']))

    def test_windows_no_reuse_prioritizes_new_and_changed_over_reaudit(self):
        one = self.create()
        bulk = one.root / 'Wiki' / 'bulk'; bulk.mkdir(parents=True)
        for index in range(700):
            (bulk / f'note-{index:04}.md').write_bytes(f'old {index}\n'.encode())
        with patch.object(module, 'scan_metadata_reuse_allowed', return_value=False):
            first = one.sync()
            self.assertEqual(first['readiness'], 'partial')
            indexed = json.loads((one.state / 'scan-index.json').read_text())['entries']
            covered = next(name for name in indexed if name.startswith('Wiki/bulk/'))
            (one.root / covered).write_bytes(b'changed covered\n')
            (one.root / 'AGENTS.md').write_bytes(b'new agent rule\n')
            (one.root / 'INDEX.md').write_bytes(b'new routing\n')
            fresh = bulk / 'new-fresh.md'; fresh.write_bytes(b'new detail\n')
            second = one.sync()
        self.assertEqual(second['readiness'], 'partial')
        self.assertEqual(second['scan_coverage']['audit'], 'metadata_unavailable')
        self.assertLessEqual(second['scan_coverage']['read_this_run'], module.SCAN_READ_LIMIT)
        for name in (covered, 'AGENTS.md', 'INDEX.md', 'Wiki/bulk/new-fresh.md'):
            expected = (one.root / name).read_bytes().decode('utf-8')
            self.assertIn(expected, [event['changes'].get(name) for event in one.history(name)['events']])

    def test_incremental_scan_detects_same_size_restored_mtime_via_ctime(self):
        one = self.create()
        path = one.root / 'Note.md'
        prior = path.stat()
        path.write_bytes(b'ONE\ntwo\nthree\n')  # exact same byte length on every OS
        os.utime(path, ns=(prior.st_atime_ns, prior.st_mtime_ns))
        if module.scan_metadata_reuse_allowed():
            self.assertNotEqual(path.stat().st_ctime_ns, prior.st_ctime_ns)
        expected = path.read_bytes().decode('utf-8')
        result = one.sync()
        self.assertEqual(result['readiness'], 'ready')
        self.assertGreaterEqual(result['scan_coverage']['read_this_run'], 1)
        self.assertEqual(self.text(one), expected)
        self.assertIn(expected, [e['changes'].get('Note.md') for e in one.history('Note.md')['events']])

    def test_incremental_scan_missing_file_remains_partial_without_delete(self):
        one = self.create()
        path = one.root / 'Note.md'
        original = path.read_bytes(); path.unlink()
        result = one.sync()
        self.assertEqual(result['readiness'], 'partial')
        self.assertGreater(result['scan_coverage']['deferred'], 0)
        self.assertFalse(any(e['kind'] == 'delete' for e in one.history('Note.md')['events']))
        path.write_bytes(original)
        self.assertEqual(one.sync()['readiness'], 'ready')

    def test_incremental_index_commit_follows_history_capture(self):
        one = self.create()
        index = one.state / 'scan-index.json'
        before = index.read_bytes()
        self.edit(one, 'changed\ntwo\nthree\n')
        with patch.object(one, '_save_scan_index', side_effect=RuntimeError('simulated index interruption')):
            with self.assertRaises(RuntimeError):
                one.sync()
        self.assertEqual(index.read_bytes(), before)
        event_count = one.status()['event_count']
        self.assertEqual(one.sync()['readiness'], 'ready')
        self.assertEqual(one.status()['event_count'], event_count)
        self.assertEqual(self.text(one), 'changed\ntwo\nthree\n')

    def test_incremental_index_rebuilds_and_periodically_audits_bytes(self):
        one = self.create()
        index = one.state / 'scan-index.json'
        with patch.object(module, 'SCAN_AUDIT_INTERVAL_SECONDS', 0):
            result = one.sync()
        self.assertEqual(result['readiness'], 'ready')
        self.assertGreaterEqual(result['scan_coverage']['read_this_run'], 1)
        index.write_text('{"private_note_text":"must not be trusted"}')
        rebuilt = one.sync()
        self.assertEqual(rebuilt['readiness'], 'ready')
        self.assertTrue(rebuilt['scan_coverage']['index_rebuilt'])
        self.assertNotIn('private_note_text', index.read_text())

    def test_second_scan_reuses_verified_bytes_after_read_deadline(self):
        import time
        one = self.create()
        (one.root / 'A.md').write_text('new detail\n')
        capture = one._capture
        def exhaust_after_first_scan(baseline):
            result = capture(baseline)
            one._scan_deadline = time.monotonic() - 1
            return result
        with patch.object(one, '_capture', side_effect=exhaust_after_first_scan):
            result = one.sync()
        self.assertEqual(result['scan_coverage']['eligible'], 2)
        if module.scan_metadata_reuse_allowed():
            self.assertEqual(result['readiness'], 'ready')
            self.assertEqual(result['scan_coverage']['covered'], 2)
            self.assertEqual(result['scan_coverage']['deferred'], 0)
        else:
            self.assertEqual(result['readiness'], 'partial')
            self.assertEqual(result['scan_coverage']['audit'], 'metadata_unavailable')
            self.assertGreater(result['scan_coverage']['deferred'], 0)

    def test_two_stuck_provider_reads_finish_partial_without_indexing_them(self):
        one = self.create()
        (one.root / 'C.md').write_text('deferred C\n')
        (one.root / 'A.md').write_text('blocked A\n')
        (one.root / 'B.md').write_text('blocked B\n')
        code = r'''
import json, sys, threading
sys.path.insert(0, sys.argv[1])
from shared_workspace import folder as module
one = module.Folder(sys.argv[2], sys.argv[3])
original = one._read
never = threading.Event()
def blocked(name):
    if name in {'A.md', 'B.md'}:
        never.wait()
    return original(name)
one._read = blocked
module.SCAN_FILE_SECONDS = 0.01
module.SCAN_WALL_SECONDS = 0.2
module.SCAN_PENDING_READ_LIMIT = 2
result = one.sync()
print(json.dumps({'readiness': result['readiness'], 'timeouts': result['scan_timeout_count'],
                  'deferred': result['scan_coverage']['deferred'],
                  'read_this_run': result['scan_coverage']['read_this_run']}))
'''
        completed = subprocess.run([sys.executable, '-c', code, str(Path(__file__).resolve().parents[1]),
                                    str(one.root), str(one.state)], capture_output=True, text=True, timeout=5)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result['readiness'], 'partial')
        self.assertGreaterEqual(result['timeouts'], 2)
        self.assertGreaterEqual(result['deferred'], 2)
        self.assertGreaterEqual(result['read_this_run'], 2)
        self.assertLessEqual(result['read_this_run'], module.SCAN_READ_LIMIT)
        index = json.loads((one.state / 'scan-index.json').read_text())
        self.assertNotIn('A.md', index['entries'])
        self.assertNotIn('B.md', index['entries'])
        self.assertFalse(one.history('A.md')['events'])

    def test_unstable_control_file_retry_is_bounded_and_labeled(self):
        one = self.create()
        original = module.read_bytes
        calls = 0
        def once(path, *args, **kwargs):
            nonlocal calls
            if Path(path).name == '.shared-memory.json':
                calls += 1
                if calls == 1:
                    raise ProductError(4, 'folder_partial_file', 'transient')
            return original(path, *args, **kwargs)
        with patch.object(module, 'read_bytes', side_effect=once):
            self.assertEqual(Folder(one.root, one.state).project_id, one.project_id)
        self.assertEqual(calls, 2)
        def always(path, *args, **kwargs):
            if Path(path).name == '.shared-memory.json':
                raise ProductError(4, 'folder_partial_file', 'transient')
            return original(path, *args, **kwargs)
        with patch.object(module, 'read_bytes', side_effect=always):
            with self.assertRaises(ProductError) as caught:
                Folder(one.root, one.state)
        self.assertEqual(caught.exception.code, 'folder_control_unstable')

    def test_recovery_defers_unstable_note_and_preserves_journal(self):
        one = self.create()
        baseline = one._baseline()
        original = self.text(one)
        operation = {'text': 'replacement\n', 'before': original, 'heads': baseline['Note.md']['heads'],
                     'baseline': baseline['Note.md'], 'evacuated': '.folder-old-' + 'a' * 32,
                     'new': '.folder-new-' + 'b' * 32, 'mode': 0o600}
        journal = {'format': module.VERSION, 'project_id': one.project_id,
                   'operations': {'Note.md': operation}}
        journal['checksum'] = module.digest(journal)
        module.atomic(one.state / 'journal.json', module.canonical(journal))
        with patch.object(one, '_read', side_effect=ProductError(4, 'folder_partial_file', 'unstable')):
            self.assertEqual(one._recover(), ['Note.md'])
        self.assertEqual(self.text(one), original)
        self.assertTrue((one.state / 'journal.json').exists())
        self.assertEqual(one._baseline(), baseline)

    def test_capture_defers_unstable_provider_event_copy(self):
        one = self.create()
        self.edit(one, 'changed\ntwo\nthree\n')
        with patch.object(one, '_emit', side_effect=ProductError(4, 'folder_partial_file', 'unstable')):
            result = one.sync()
        self.assertEqual(result['readiness'], 'partial')
        self.assertIn('Note.md', result['partial_files'])
        self.assertEqual(self.text(one), 'changed\ntwo\nthree\n')
        self.assertEqual(one.sync()['readiness'], 'ready')

    def test_windows_metadata_reuse_disabled_prevents_false_ready(self):
        one = self.create()
        bulk = one.root / 'Wiki' / 'bulk'; bulk.mkdir(parents=True)
        for index in range(600):
            (bulk / f'item-{index:04}.md').write_text('same size\n')
        with patch.object(module, 'scan_metadata_reuse_allowed', return_value=False):
            first = one.sync(); second = one.sync()
        self.assertEqual(first['readiness'], 'partial')
        self.assertEqual(second['readiness'], 'partial')
        self.assertEqual(second['scan_coverage']['audit'], 'metadata_unavailable')
        self.assertEqual(second['scan_coverage']['reuse_basis'], 'none_windows_full_byte_read_required')

    def test_bounded_enumeration_fails_safely_and_releases_lock(self):
        import threading
        one = self.create()
        baseline = (one.state / 'baseline.json').read_bytes()
        index = (one.state / 'scan-index.json').read_bytes()
        gate = threading.Event()
        with patch.object(one, '_enumerate_scan', side_effect=lambda required: gate.wait()), \
             patch.object(module, 'SCAN_METADATA_SECONDS', 0.01):
            with self.assertRaises(ProductError) as caught:
                one.sync()
        gate.set()
        self.assertEqual(caught.exception.code, 'folder_scan_timeout')
        with one._lock():
            pass
        self.assertEqual((one.state / 'baseline.json').read_bytes(), baseline)
        self.assertEqual((one.state / 'scan-index.json').read_bytes(), index)

    def test_bounded_stat_defers_one_file_without_index_or_materialization(self):
        import threading
        one = self.create()
        (one.root / 'A.md').write_text('keep A\n')
        real = module.file_stamp
        gate = threading.Event()
        def stalled(path):
            if Path(path).name == 'A.md':
                gate.wait()
            return real(path)
        with patch.object(module, 'file_stamp', side_effect=stalled), \
             patch.object(module, 'SCAN_STAT_SECONDS', 0.01):
            result = one.sync()
        gate.set()
        self.assertEqual(result['readiness'], 'partial')
        self.assertIn('A.md', result['partial_files'])
        self.assertNotIn('A.md', json.loads((one.state / 'scan-index.json').read_text())['entries'])
        self.assertEqual((one.root / 'A.md').read_text(), 'keep A\n')
        with one._lock():
            pass

    def test_bounded_provider_event_read_defers_new_history(self):
        import threading
        one = self.create()
        event_id = one.status()['heads']['Note.md'][0]
        local = one.state / 'events' / (event_id + '.json')
        provider = one.root / '.shared-memory/events' / (event_id + '.json')
        local.unlink()
        real = module.read_bytes
        gate = threading.Event()
        def stalled(path, *args, **kwargs):
            if Path(path) == provider:
                gate.wait()
            return real(path, *args, **kwargs)
        with patch.object(module, 'read_bytes', side_effect=stalled), \
             patch.object(module, 'SCAN_EVENT_SECONDS', 0.01):
            result = one.sync()
        gate.set()
        for thread in one._pending_metadata_reads:
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
        self.assertEqual(result['readiness'], 'partial')
        self.assertTrue(any(item.get('reason') == 'provider-history-read-timeout'
                            for item in result['deferred_events']))
        self.assertFalse(local.exists())
        with one._lock():
            pass

    @unittest.skipIf(os.name == 'nt', 'POSIX lock contention fixture')
    def test_folder_lock_timeout_is_bounded_without_running_sync(self):
        one = self.create()
        with one._lock(), patch.object(module, 'LOCK_TIMEOUT_SECONDS', 0.05):
            with patch.object(one, '_sync_locked') as sync:
                with self.assertRaises(ProductError) as caught:
                    one.sync()
                sync.assert_not_called()
        self.assertEqual(caught.exception.code, 'folder_lock_timeout')

    def test_provider_duplicate_uses_private_copy_but_full_status_audits_bytes(self):
        one = self.create()
        event_id = one.status()['heads']['Note.md'][0]
        provider = one.root / '.shared-memory/events' / (event_id + '.json')
        original = provider.read_bytes()
        provider.write_bytes(b'[' + original[1:])  # same size, invalid provider copy
        result = one.sync()
        self.assertEqual(result['readiness'], 'ready')
        self.assertGreater(result['provider_duplicate_bytes_unverified'], 0)
        self.assertEqual(result['provider_delivery'], 'not_applicable')
        audited = one.status()
        self.assertEqual(audited['provider_duplicate_bytes_unverified'], 0)
        self.assertTrue(audited['invalid_events'])
        self.assertEqual(audited['readiness'], 'partial')

    def test_missing_private_event_and_new_provider_event_are_still_imported(self):
        one = self.create()
        initial = one.status()['heads']['Note.md'][0]
        local = one.state / 'events' / (initial + '.json')
        local.unlink()
        self.assertEqual(one.sync()['readiness'], 'ready')
        self.assertTrue(local.exists())
        two = self.attach(one)
        self.edit(two, 'new provider detail\n')
        two.sync()
        transport(two, one)
        result = one.sync()
        self.assertEqual(result['readiness'], 'ready')
        self.assertEqual(self.text(one), 'new provider detail\n')

    def attach(self, owner, name='two', readonly=False):
        root = self.base / name; root.mkdir()
        shutil.copyfile(owner.root / module.MANIFEST, root / module.MANIFEST)
        shutil.copytree(owner.root / module.HISTORY, root / module.HISTORY)
        return Folder.attach(root, self.base / (name + '-private'), name, 'Fixture person', name + ' agent', owner.project_id, readonly)

    def edit(self, folder, text, path='Note.md'):
        (folder.root / path).write_bytes(text.encode())

    def text(self, folder, path='Note.md'):
        path = folder.root / path
        return path.read_bytes().decode() if path.exists() else None

    def exchange(self, left, right):
        transport(left, right); transport(right, left)
        a = left.sync(); b = right.sync()
        transport(left, right); transport(right, left)
        return left.sync(), right.sync()

    def test_initialization_exact_bytes_private_state_and_idempotent_resume(self):
        one = self.create(files={'Note.md': '世界\r\nMixed\nlast\rno-newline'})
        before = inventory(one.root)
        again = Folder.initialize(one.root, one.state, 'one', 'Fixture person', 'one agent')
        self.assertEqual(again.project_id, one.project_id)
        self.assertEqual(again.status()['readiness'], 'ready')
        self.assertEqual(inventory(one.root), before)
        self.assertEqual(self.text(one), '世界\r\nMixed\nlast\rno-newline')
        self.assertFalse(any(p.suffix == '.sqlite3' for p in one.root.rglob('*')))

    def test_seed_initialization_resumes_after_journal_crash_without_overwriting_editor(self):
        root = self.base / 'seeded'; root.mkdir()
        state = self.base / 'seeded-private'
        seed = {'AGENTS.md': 'Seed instructions\n', 'Wiki/README.md': 'Canonical memory\n'}
        atomic = module.atomic

        def interrupted(path, data, immutable=False):
            atomic(path, data, immutable)
            if Path(path).name == 'journal.json':
                raise RuntimeError('simulated power loss after durable journal')

        with patch.object(module, 'atomic', interrupted), self.assertRaises(RuntimeError):
            Folder.initialize(root, state, 'seed', 'Person', 'Agent',
                              initial_files=seed, materialize_initial=True)
        newer = b'Newer user instructions\r\n'
        (root / 'AGENTS.md').write_bytes(newer)
        # A retry reads its original durable intent without needing the templates.
        resumed = Folder.initialize(root, state, 'seed', 'Person', 'Agent')
        self.assertEqual((root / 'AGENTS.md').read_bytes(), newer)
        self.assertEqual((root / 'Wiki/README.md').read_text(), seed['Wiki/README.md'])
        events = resumed.history('AGENTS.md')['events']
        preserved = [e['changes'].get('AGENTS.md') for e in events]
        self.assertIn(seed['AGENTS.md'], preserved)
        self.assertIn(newer.decode('utf-8'), preserved)

    def test_nextcloud_binding_and_unverified_delivery(self):
        one = self.create(provider='nextcloud')
        self.assertEqual(one.status()['provider'], 'nextcloud')
        self.assertEqual(one.status()['provider_delivery'], 'unverified')

    def test_offline_disjoint_edits_merge_and_converge_without_pingpong(self):
        one = self.create(); two = self.attach(one)
        self.edit(one, 'ONE\ntwo\nthree\n'); self.edit(two, 'one\ntwo\nTHREE\n')
        one.sync(); two.sync()
        a, b = self.exchange(one, two)
        self.assertEqual(self.text(one), 'ONE\ntwo\nTHREE\n')
        self.assertEqual(self.text(two), self.text(one))
        self.assertEqual(a['history_hash'], b['history_hash'])
        count = a['event_count']
        self.assertEqual(one.sync()['event_count'], count)
        self.assertEqual(two.sync()['event_count'], count)
        self.assertEqual(a['readiness'], 'ready')

    def test_capture_precedes_incoming_history_and_keeps_offline_parent(self):
        one = self.create(); two = self.attach(one)
        initial = two.status()['heads']['Note.md']
        self.edit(two, 'offline\ntwo\nthree\n')
        self.edit(one, 'remote\ntwo\nthree\n'); one.sync(); transport(one, two)
        result = two.sync()
        observed = [e for e in two.history()['events'] if e['author']['actor'] == 'two']
        self.assertEqual(observed[0]['parents']['Note.md'], initial)
        self.assertTrue(result['conflicts'])
        self.assertEqual(self.text(two), 'offline\ntwo\nthree\n')

    def test_conflict_heads_and_reports_converge_then_any_editor_resolves(self):
        one = self.create(); two = self.attach(one)
        self.edit(one, 'left\n'); self.edit(two, 'right\n')
        one.sync(); two.sync(); a, b = self.exchange(one, two)
        self.assertEqual(a['conflicts'], b['conflicts'])
        self.assertEqual(self.text(one), 'left\n'); self.assertEqual(self.text(two), 'right\n')
        report = one.root / a['conflicts'][0]['report']
        self.assertTrue(report.is_file())
        self.assertEqual(report.read_bytes(), (two.root / b['conflicts'][0]['report']).read_bytes())
        two.resolve('Note.md', 'Reviewed combined answer\n', 'Compared both original versions with the supplied source')
        a, b = self.exchange(one, two)
        self.assertEqual(a['conflicts'], []); self.assertEqual(b['conflicts'], [])
        self.assertEqual(self.text(one), 'Reviewed combined answer\n')
        versions = [e['changes']['Note.md'] for e in one.history('Note.md')['events']]
        self.assertIn('left\n', versions); self.assertIn('right\n', versions)
        with self.assertRaises(ProductError):
            two.resolve('Note.md', 'x', '')

    def test_missing_file_is_not_delete_and_explicit_delete_is_durable(self):
        one = self.create(); before = one.status()['event_count']
        (one.root / 'Note.md').unlink()
        result = one.sync()
        self.assertEqual(result['event_count'], before)
        self.assertEqual(result['missing_files'], ['Note.md'])
        self.assertIsNone(self.text(one))
        result = one.delete('Note.md', 'Deliberately remove the selected note')
        self.assertEqual(result['readiness'], 'ready')
        self.assertEqual(one.delete('Note.md', 'Retry removal')['event_count'], result['event_count'])
        self.assertTrue(any(e['kind'] == 'delete' for e in one.history()['events']))

    def test_delete_edit_race_preserves_both_and_can_resolve(self):
        one = self.create(); two = self.attach(one)
        one.delete('Note.md', 'Remove explicitly')
        self.edit(two, 'offline edited version\n'); two.sync()
        a, b = self.exchange(one, two)
        self.assertTrue(a['conflicts']); self.assertEqual(a['conflicts'], b['conflicts'])
        self.assertIsNone(self.text(one)); self.assertEqual(self.text(two), 'offline edited version\n')
        one.resolve('Note.md', 'offline edited version\n', 'Keep the offline work after reviewing the deletion')
        a, b = self.exchange(one, two)
        self.assertEqual(self.text(one), self.text(two)); self.assertFalse(a['conflicts'])

    def test_rename_single_event_preserves_source_and_retries(self):
        one = self.create(); two = self.attach(one)
        original = self.text(one)
        result = one.rename('Note.md', 'Archive/Moved.md', 'Move the note explicitly')
        self.assertIsNone(self.text(one)); self.assertEqual(self.text(one, 'Archive/Moved.md'), original)
        self.assertEqual(one.rename('Note.md', 'Archive/Moved.md', 'Move the note explicitly')['event_count'], result['event_count'])
        a, b = self.exchange(one, two)
        self.assertIsNone(self.text(two)); self.assertEqual(self.text(two, 'Archive/Moved.md'), original)
        event = [e for e in one.history()['events'] if e['kind'] == 'rename'][0]
        self.assertEqual(event['changes'], {'Note.md': None, 'Archive/Moved.md': original})

    def test_rename_edit_race_is_visible_not_lost(self):
        one = self.create(); two = self.attach(one)
        one.rename('Note.md', 'Moved.md', 'Move note')
        self.edit(two, 'Offline work on old name\n'); two.sync()
        a, b = self.exchange(one, two)
        self.assertEqual(a['conflicts'][0]['path'], 'Note.md')
        self.assertEqual(self.text(two), 'Offline work on old name\n')
        self.assertTrue((two.root / 'Moved.md').exists())

    def test_missing_parent_defers_without_rolling_back_visible_file(self):
        one = self.create(); two = self.attach(one)
        self.edit(one, 'version one\n'); one.sync()
        parent = one.status()['heads']['Note.md'][0]
        self.edit(one, 'version two\n'); one.sync()
        child = one.status()['heads']['Note.md'][0]
        shutil.copyfile(one.shared / 'events' / (child + '.json'), two.shared / 'events' / (child + '.json'))
        original = self.text(two)
        result = two.sync()
        self.assertTrue(result['deferred_events']); self.assertEqual(self.text(two), original)
        shutil.copyfile(one.shared / 'events' / (parent + '.json'), two.shared / 'events' / (parent + '.json'))
        result = two.sync()
        self.assertEqual(result['deferred_events'], [])
        self.assertEqual(self.text(two), 'version two\n')
        self.assertEqual(two.sync()['event_count'], result['event_count'])

    def test_incomplete_history_file_defers_and_retry_recovers(self):
        one = self.create(); two = self.attach(one)
        self.edit(one, 'next\n'); one.sync(); newest = one.status()['heads']['Note.md'][0]
        destination = two.shared / 'events' / (newest + '.json')
        destination.write_bytes(b'{"partial":')
        result = two.sync()
        self.assertTrue(result['invalid_events']); self.assertEqual(self.text(two), 'one\ntwo\nthree\n')
        shutil.copyfile(one.shared / 'events' / (newest + '.json'), destination)
        self.assertEqual(two.sync()['readiness'], 'ready'); self.assertEqual(self.text(two), 'next\n')

    def test_partial_utf8_local_write_is_not_captured_or_replaced(self):
        one = self.create(); before = one.status()['event_count']
        (one.root / 'Note.md').write_bytes(b'\xf0\x9f')
        result = one.sync()
        self.assertEqual(result['event_count'], before)
        self.assertEqual(result['partial_files'], ['Note.md'])
        self.assertEqual((one.root / 'Note.md').read_bytes(), b'\xf0\x9f')

    def test_stable_read_checks_detect_changed_inode_stamp(self):
        path = self.base / 'text'; path.write_bytes(b'original')
        original = module.os.fstat; calls = []
        def changed(fd):
            result = original(fd); calls.append(1)
            if len(calls) == 2:
                class Different:
                    st_dev = result.st_dev; st_ino = result.st_ino; st_size = result.st_size
                    st_mtime_ns = result.st_mtime_ns + 1; st_ctime_ns = result.st_ctime_ns
                return Different()
            return result
        with patch.object(module.os, 'fstat', changed):
            with self.assertRaises(ProductError) as failure:
                module.read_bytes(path)
        self.assertEqual(failure.exception.code, 'folder_partial_file')

    def test_scope_private_trees_nested_coordination_and_binary_not_copied(self):
        root = self.base / 'one'; root.mkdir()
        originals = {'Note.md': b'# Note\n', '.env': b'PRIVATE_MARKER', '.codex/history.jsonl': b'PRIVATE_MARKER',
                     'Sub/Coordination/work.md': b'PRIVATE_MARKER', 'secrets/notes.md': b'PRIVATE_MARKER', 'image.png': b'\x00\xff'}
        for name, value in originals.items():
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(value)
        one = Folder.initialize(root, self.base / 'private', 'a', 'Person', 'Agent')
        self.assertEqual(one.status()['readiness'], 'ready')
        for name, value in originals.items(): self.assertEqual((root / name).read_bytes(), value)
        self.assertFalse(any(b'PRIVATE_MARKER' in p.read_bytes() for p in one.state.rglob('*') if p.is_file()))
        self.assertFalse(any(b'PRIVATE_MARKER' in p.read_bytes() for p in one.shared.rglob('*') if p.is_file()))

    def test_previously_imported_nonmarkdown_remains_managed(self):
        one = self.create(files={'Note.md': '# Note\n', 'data.txt': 'original'}, initial_files={'Note.md': '# Note\n', 'data.txt': 'original'})
        self.edit(one, 'updated', 'data.txt'); one.sync()
        self.assertEqual(one.history('data.txt')['events'][-1]['changes']['data.txt'], 'updated')

    def test_migration_initial_base_preserves_divergent_current_content(self):
        one = self.create(files={'Note.md': 'newer working content\r\n'}, initial_files={'Note.md': 'older accepted content\n'})
        self.assertEqual(self.text(one), 'newer working content\r\n')
        values = [e['changes']['Note.md'] for e in one.history()['events']]
        self.assertIn('older accepted content\n', values); self.assertIn('newer working content\r\n', values)

    def test_readonly_status_history_no_mutation_and_edit_operations_refused(self):
        one = self.create(); two = self.attach(one, readonly=True)
        before = inventory(self.base)
        two.status(); two.history()
        for call in (two.sync, lambda: two.resolve('Note.md', 'x', 'why'), lambda: two.delete('Note.md', 'why'), lambda: two.rename('Note.md', 'Other.md', 'why')):
            with self.assertRaises(ProductError) as failure: call()
            self.assertEqual(failure.exception.code, 'folder_readonly')
        self.assertEqual(inventory(self.base), before)

    def test_wrong_identity_private_inside_and_symlinks_refused(self):
        one = self.create(); root = self.base / 'other'; root.mkdir()
        shutil.copyfile(one.root / module.MANIFEST, root / module.MANIFEST)
        with self.assertRaises(ProductError): Folder.attach(root, self.base / 'private2', 'b', 'B', 'Agent', 'wrong')
        self.assertFalse((self.base / 'private2').exists())
        with self.assertRaises(ProductError): Folder(root, root / 'private')
        unsafe = self.base / 'unsafe'; unsafe.mkdir(); (unsafe / 'Note.md').symlink_to(one.root / 'Note.md')
        with self.assertRaises(ProductError): Folder.initialize(unsafe, self.base / 'unsafe-state', 'a', 'A', 'Agent', initial_files={'Note.md': 'required import'})
        self.assertFalse((self.base / 'unsafe-state').exists())

    def test_provider_conflict_copy_is_distinct_preserved_note(self):
        one = self.create()
        self.edit(one, 'provider divergent copy\n', 'Note (conflicted copy).md')
        result = one.sync()
        self.assertEqual(result['provider_conflict_copies'], ['Note (conflicted copy).md'])
        self.assertIn('Note (conflicted copy).md', result['heads'])
        self.assertEqual(self.text(one), 'one\ntwo\nthree\n')

    def test_real_process_crash_initialization_and_attach_resume(self):
        for route in ('initialize', 'attach'):
            with self.subTest(route=route):
                root = self.base / ('crash-' + route); root.mkdir(); state = self.base / ('state-' + route)
                if route == 'initialize': (root / 'Note.md').write_bytes(b'Keep exact bytes\r\n')
                else:
                    owner = self.create('attach-owner')
                    shutil.copyfile(owner.root / module.MANIFEST, root / module.MANIFEST)
                    shutil.copytree(owner.shared, root / module.HISTORY)
                code = '''import os,sys\nfrom pathlib import Path\nfrom shared_workspace import folder as m\nold=m.atomic\ndef interrupted(path,data,immutable=False):\n old(path,data,immutable)\n if Path(path).name == sys.argv[4]: os._exit(81)\nm.atomic=interrupted\nroot,state=Path(sys.argv[1]),Path(sys.argv[2])\nif sys.argv[3]=='initialize': m.Folder.initialize(root,state,'crash','Person','Agent')\nelse: m.Folder.attach(root,state,'crash','Person','Agent',m.parse(m.read_bytes(root/m.MANIFEST))['project_id'])\n'''
                env = dict(os.environ, PYTHONPATH=str(Path(module.__file__).parents[1]))
                result = subprocess.run([sys.executable, '-c', code, str(root), str(state), route,
                                         module.MANIFEST if route == 'initialize' else 'folder.json'], env=env, capture_output=True)
                self.assertEqual(result.returncode, 81, result.stderr)
                if route == 'initialize': ready = Folder.initialize(root, state, 'crash', 'Person', 'Agent')
                else: ready = Folder.attach(root, state, 'crash', 'Person', 'Agent', owner.project_id)
                self.assertEqual(ready.status()['readiness'], 'ready')

    def test_crash_after_evacuating_file_preserves_post_crash_edit(self):
        one = self.create(); two = self.attach(one)
        self.edit(one, 'remote revision\n'); one.sync(); transport(one, two)
        code = '''import os,sys\nfrom pathlib import Path\nfrom shared_workspace import folder as m\nold=m.os.rename\ndef stop(src,dst):\n old(src,dst)\n if Path(dst).name.startswith('.folder-old-'): os._exit(82)\nm.os.rename=stop\nm.Folder(sys.argv[1],sys.argv[2]).sync()\n'''
        env = dict(os.environ, PYTHONPATH=str(Path(module.__file__).parents[1]))
        result = subprocess.run([sys.executable, '-c', code, str(two.root), str(two.state)], env=env, capture_output=True)
        self.assertEqual(result.returncode, 82, result.stderr)
        self.assertTrue((two.state / 'journal.json').exists())
        self.edit(two, 'new local edit after crash\n')
        reopened = Folder(two.root, two.state); result = reopened.sync()
        self.assertEqual(self.text(two), 'new local edit after crash\n')
        self.assertTrue(result['conflicts'])
        values = [e['changes']['Note.md'] for e in reopened.history()['events']]
        self.assertIn('new local edit after crash\n', values); self.assertIn('remote revision\n', values)

    def test_new_file_race_never_overwrites_racing_editor(self):
        one = self.create(); two = self.attach(one)
        self.edit(one, 'remote\n', 'New.md'); one.sync(); transport(one, two)
        original = module.os.link; injected = []
        def race(src, dst, *args, **kwargs):
            if Path(dst) == two.root / 'New.md' and not injected:
                injected.append(1); Path(dst).write_bytes(b'RACING EDITOR\n')
            return original(src, dst, *args, **kwargs)
        with patch.object(module.os, 'link', race): result = two.sync()
        self.assertEqual(self.text(two, 'New.md'), 'RACING EDITOR\n')
        self.assertEqual(result['readiness'], 'partial')
        again = two.sync()
        self.assertTrue(again['conflicts'])


    def test_valid_provider_event_copies_deduplicate_or_keep_distinct_content(self):
        one = self.create(); two = self.attach(one)
        self.edit(one, 'new provider text\n'); one.sync()
        head = one.status()['heads']['Note.md'][0]
        content = (one.shared / 'events' / (head + '.json')).read_bytes()
        copies = [two.shared / 'events' / ('history (conflicted copy).json'), two.shared / 'events' / 'second-copy.json']
        for path in copies: path.write_bytes(content)
        result = two.sync()
        self.assertEqual(result['readiness'], 'ready')
        self.assertEqual(result['event_count'], 2)
        self.assertEqual(len(result['history_copies']), 2)
        self.assertEqual(self.text(two), 'new provider text\n')
        self.assertEqual(two.sync()['event_count'], 2)
        for path in copies: self.assertEqual(path.read_bytes(), content)

    def test_required_private_subtree_does_not_import_siblings(self):
        files = {'Note.md': '# Public\n', 'Coordination/Kept.md': 'Imported existing record\n',
                 'Coordination/Private.md': 'PRIVATE_SIBLING', 'Coordination/Nested/Secret.md': 'PRIVATE_SIBLING'}
        one = self.create(files=files, initial_files={k: v for k, v in files.items() if 'PRIVATE_SIBLING' not in v})
        result = one.status()
        self.assertEqual(result['readiness'], 'ready')
        self.assertNotIn('Coordination/Private.md', result['heads'])
        self.assertNotIn('Coordination/Nested/Secret.md', result['heads'])
        self.assertFalse(any(b'PRIVATE_SIBLING' in p.read_bytes() for p in one.state.rglob('*') if p.is_file()))

    def test_file_readonly_blocks_explicit_changes_and_incoming_replacement(self):
        one = self.create(); two = self.attach(one)
        path = two.root / 'Note.md'; path.chmod(0o444)
        self.addCleanup(lambda: path.chmod(0o644) if path.exists() else None)
        before = inventory(two.root)
        for call in (lambda: two.delete('Note.md', 'remove'), lambda: two.rename('Note.md', 'Other.md', 'move'),
                     lambda: two.resolve('Note.md', 'replace', 'reason')):
            with self.assertRaises(ProductError) as failure: call()
            self.assertEqual(failure.exception.code, 'folder_readonly_file')
        self.assertEqual(inventory(two.root), before)
        self.edit(one, 'new remote text\n'); one.sync(); transport(one, two)
        result = two.sync()
        self.assertEqual(self.text(two), 'one\ntwo\nthree\n')
        self.assertEqual(result['readiness'], 'partial')
        self.assertEqual(path.stat().st_mode & 0o777, 0o444)
        path.chmod(0o640); two.sync()
        self.assertEqual(self.text(two), 'new remote text\n')
        if os.name != 'nt': self.assertEqual(path.stat().st_mode & 0o777, 0o640)

    def test_corrupt_baseline_or_journal_never_materializes(self):
        one = self.create()
        original = (one.state / 'baseline.json').read_bytes()
        value = json.loads(original); value['paths']['Note.md']['text'] = 'corruption'
        (one.state / 'baseline.json').write_text(json.dumps(value))
        before = inventory(one.root)
        with self.assertRaises(ProductError): one.sync()
        self.assertEqual(inventory(one.root), before)
        (one.state / 'baseline.json').write_bytes(original)
        (one.state / 'journal.json').write_text(json.dumps({'format': 1, 'project_id': one.project_id, 'operations': {}, 'checksum': 'bad'}))
        with self.assertRaises(ProductError) as failure: one.sync()
        self.assertEqual(failure.exception.code, 'folder_journal_invalid')
        self.assertEqual(inventory(one.root), before)

    def test_concurrent_portable_case_collision_preserves_local_path(self):
        one = self.create(files={'Home.md': '# Home\n'}); two = self.attach(one)
        self.edit(one, 'first\n', 'Note.md'); self.edit(two, 'second\n', 'note.md')
        one.sync(); two.sync(); transport(one, two); transport(two, one)
        before_one = self.text(one, 'Note.md'); before_two = self.text(two, 'note.md')
        a, b = one.sync(), two.sync()
        self.assertTrue(a['path_collisions']); self.assertTrue(b['path_collisions'])
        self.assertEqual(self.text(one, 'Note.md'), before_one); self.assertEqual(self.text(two, 'note.md'), before_two)
        self.assertEqual(a['readiness'], 'partial')

    def test_resolution_retry_has_no_extra_event(self):
        one = self.create(); one.resolve('Note.md', 'reviewed\n', 'Reviewed sources')
        count = one.status()['event_count']
        self.assertEqual(one.resolve('Note.md', 'reviewed\n', 'Reviewed sources')['event_count'], count)

    def test_compatible_merge_bound_retains_large_full_versions_as_conflict(self):
        text = ''.join(str(i) + '\n' for i in range(2100))
        one = self.create(files={'Note.md': text}); two = self.attach(one)
        self.edit(one, text.replace('0\n', 'FIRST\n', 1)); self.edit(two, text + 'LAST\n')
        one.sync(); two.sync(); a, b = self.exchange(one, two)
        self.assertTrue(a['conflicts'])
        self.assertTrue(self.text(one).startswith('FIRST\n'))
        self.assertTrue(self.text(two).endswith('LAST\n'))


    def test_concurrent_renames_report_intent_and_acknowledge_without_rewrites(self):
        for operation in ('resolve', 'delete'):
            with self.subTest(operation=operation):
                one = self.create('rename-one-' + operation)
                two = self.attach(one, 'rename-two-' + operation)
                original = self.text(one)
                one.rename('Note.md', 'DifferentA.md', 'Choose A')
                two.rename('Note.md', 'DifferentB.md', 'Choose B')
                a, b = self.exchange(one, two)
                self.assertEqual(a['readiness'], 'ready')
                self.assertEqual(a['conflicts'], [])
                self.assertEqual(a['rename_divergences'], b['rename_divergences'])
                divergence = a['rename_divergences'][0]
                self.assertEqual(divergence['source'], 'Note.md')
                self.assertEqual(divergence['destinations'], ['DifferentA.md', 'DifferentB.md'])
                self.assertEqual(len(divergence['event_ids']), 2)
                self.assertEqual(a['warnings'][0]['code'], 'rename_intent_divergence')
                for device in (one, two):
                    self.assertEqual(self.text(device, 'DifferentA.md'), original)
                    self.assertEqual(self.text(device, 'DifferentB.md'), original)
                    before = inventory(device.root)
                    count = device.status()['event_count']
                    self.assertEqual(device.sync()['event_count'], count)
                    self.assertEqual(inventory(device.root), before)
                if operation == 'resolve':
                    two.resolve('Note.md', None, 'Reviewed both destinations; deliberately retain both copies')
                else:
                    two.delete('Note.md', 'Reviewed both destinations; retain both and keep source removed')
                a, b = self.exchange(one, two)
                self.assertEqual(a['rename_divergences'], [])
                self.assertEqual(b['rename_divergences'], [])
                self.assertEqual(a['warnings'], [])
                self.assertEqual(self.text(one, 'DifferentA.md'), original)
                self.assertEqual(self.text(one, 'DifferentB.md'), original)


    def test_readonly_destination_keeps_journal_and_post_crash_old_inode(self):
        one = self.create('readonly-source'); two = self.attach(one, 'readonly-recipient')
        self.edit(one, 'incoming replacement\n'); one.sync(); transport(one, two)
        class Interrupted(Exception): pass
        original = module.os.rename
        def interrupt(source, destination):
            original(source, destination)
            if Path(destination).name.startswith('.folder-old-'):
                raise Interrupted()
        with patch.object(module.os, 'rename', interrupt):
            with self.assertRaises(Interrupted): two.sync()
        journal_path = two.state / 'journal.json'
        journal = json.loads(journal_path.read_bytes())
        evacuated = two.root / journal['operations']['Note.md']['evacuated']
        old_edit = b'UNIQUE POST-CRASH OLD-INODE EDIT\n'
        evacuated.write_bytes(old_edit)
        path = two.root / 'Note.md'
        visible = b'KEEP VISIBLE READONLY CONTENT\n'
        path.write_bytes(visible); path.chmod(0o444)
        self.addCleanup(lambda: path.chmod(0o644) if path.exists() else None)
        reopened = Folder(two.root, two.state)
        first = reopened.sync()
        self.assertTrue(first['recovery_pending'])
        self.assertEqual(first['readiness'], 'partial')
        self.assertTrue(journal_path.is_file()); self.assertTrue(evacuated.is_file())
        self.assertEqual(path.read_bytes(), visible)
        self.assertTrue(any(p.read_bytes() == old_edit for p in (two.state / 'backups').iterdir()))
        changes = [e['changes'].get('Note.md') for e in reopened.history()['events']]
        self.assertIn(old_edit.decode(), changes)
        self.assertIn(visible.decode(), changes)
        second = reopened.sync()
        self.assertEqual(second['event_count'], first['event_count'])
        self.assertEqual(path.read_bytes(), visible)
        self.assertTrue(journal_path.exists())
        path.chmod(0o644)
        finished = reopened.sync()
        self.assertFalse(journal_path.exists())
        self.assertFalse(evacuated.exists())
        self.assertEqual(path.read_bytes(), visible)
        self.assertTrue(finished['conflicts'])
        reopened.resolve('Note.md', visible.decode(), 'Reviewed all retained post-crash variants')
        self.assertEqual(reopened.status()['readiness'], 'ready')


    def test_known_nextcloud_state_directory_is_refused_before_writes(self):
        root = self.base / 'local-project'; root.mkdir()
        (root / 'Note.md').write_bytes(b'# Existing note\n')
        state = self.base / 'Nextcloud/private-state'
        with self.assertRaises(ProductError) as failure:
            Folder.initialize(root, state, 'owner', 'Person', 'Agent')
        self.assertEqual(failure.exception.code, 'folder_private_path')
        self.assertFalse(state.exists())
        self.assertFalse((root / module.MANIFEST).exists())


    def test_stable_read_accepts_stable_cross_api_timestamp_differences(self):
        from types import SimpleNamespace
        path = self.base / 'windows-stat.bin'
        content = b'CRLF\r\nMixed\nCtrlZ\x1aExact'
        path.write_bytes(content)
        original = module.os.fstat
        def descriptor_metadata(fd):
            info = original(fd)
            # Windows path stat may expose creation-time ctime while fstat
            # exposes metadata-change time. Compare each API with itself.
            return SimpleNamespace(st_dev=info.st_dev, st_ino=info.st_ino, st_mode=info.st_mode,
                                   st_size=info.st_size, st_mtime_ns=info.st_mtime_ns + 17,
                                   st_ctime_ns=info.st_ctime_ns + 10_000_000_000)
        with patch.object(module.os, 'fstat', descriptor_metadata):
            self.assertEqual(module.read_bytes(path), content)

    def test_stable_read_accepts_verified_fileprovider_zero_size_metadata(self):
        from types import SimpleNamespace
        path = self.base / 'provider-zero-size.md'
        content = b'Actual source bytes\r\nwith exact content\n'
        path.write_bytes(content)
        real_stat, real_fstat = module.os.stat, module.os.fstat
        def zero(info):
            return SimpleNamespace(st_dev=info.st_dev, st_ino=info.st_ino, st_mode=info.st_mode,
                                   st_size=0, st_mtime_ns=info.st_mtime_ns, st_ctime_ns=info.st_ctime_ns)
        def named(value, *args, **kwargs):
            result = real_stat(value, *args, **kwargs)
            return zero(result) if isinstance(value, (str, os.PathLike)) and Path(value) == path else result
        with patch.object(module.os, 'stat', side_effect=named), \
             patch.object(module.os, 'fstat', side_effect=lambda fd: zero(real_fstat(fd))):
            self.assertEqual(module.read_bytes(path), content)

    def test_stable_read_rejects_different_second_fileprovider_read(self):
        from types import SimpleNamespace
        import io
        path = self.base / 'provider-race.md'; path.write_bytes(b'original bytes')
        real_stat, real_fstat, real_fdopen = module.os.stat, module.os.fstat, module.os.fdopen
        def zero(info):
            return SimpleNamespace(st_dev=info.st_dev, st_ino=info.st_ino, st_mode=info.st_mode,
                                   st_size=0, st_mtime_ns=info.st_mtime_ns, st_ctime_ns=info.st_ctime_ns)
        def named(value, *args, **kwargs):
            result = real_stat(value, *args, **kwargs)
            return zero(result) if isinstance(value, (str, os.PathLike)) and Path(value) == path else result
        reads = 0
        def changed(fd, *args, **kwargs):
            nonlocal reads
            reads += 1
            return real_fdopen(fd, *args, **kwargs) if reads == 1 else io.BytesIO(b'changed! bytes')
        with patch.object(module.os, 'stat', side_effect=named), \
             patch.object(module.os, 'fstat', side_effect=lambda fd: zero(real_fstat(fd))), \
             patch.object(module.os, 'fdopen', side_effect=changed):
            with self.assertRaises(ProductError) as caught:
                module.read_bytes(path)
        self.assertEqual(caught.exception.code, 'folder_partial_file')

    @unittest.skipIf(os.name == 'nt', 'Windows prevents unlinking an open file; replacement-before-open and identity tests still apply')
    def test_stable_read_rejects_fileprovider_path_replaced_by_symlink(self):
        from types import SimpleNamespace
        path = self.base / 'provider-link-race.md'; path.write_bytes(b'original bytes')
        outside = self.base / 'outside-provider.md'; outside.write_bytes(b'outside bytes')
        real_stat, real_fstat, real_fdopen = module.os.stat, module.os.fstat, module.os.fdopen
        def zero(info):
            return SimpleNamespace(st_dev=info.st_dev, st_ino=info.st_ino, st_mode=info.st_mode,
                                   st_size=0, st_mtime_ns=info.st_mtime_ns, st_ctime_ns=info.st_ctime_ns)
        def named(value, *args, **kwargs):
            result = real_stat(value, *args, **kwargs)
            return zero(result) if isinstance(value, (str, os.PathLike)) and Path(value) == path else result
        reads = 0
        def replace(fd, *args, **kwargs):
            nonlocal reads
            reads += 1
            if reads == 2:
                path.unlink(); path.symlink_to(outside)
            return real_fdopen(fd, *args, **kwargs)
        with patch.object(module.os, 'stat', side_effect=named), \
             patch.object(module.os, 'fstat', side_effect=lambda fd: zero(real_fstat(fd))), \
             patch.object(module.os, 'fdopen', side_effect=replace):
            with self.assertRaises(ProductError) as caught:
                module.read_bytes(path)
        self.assertEqual(caught.exception.code, 'folder_partial_file')
        self.assertEqual(outside.read_bytes(), b'outside bytes')

    def test_zero_size_metadata_never_reuses_nonempty_baseline(self):
        one = self.create()
        real_stamp = module.file_stamp
        def provider_stamp(path):
            value = real_stamp(path)
            if Path(path).name == 'Note.md':
                value[2] = 0
            return value
        with patch.object(module, 'file_stamp', side_effect=provider_stamp), \
             patch.object(one, '_read', wraps=one._read) as read:
            first = one.sync()
            calls = read.call_count
            second = one.sync()
            self.assertGreater(read.call_count, calls)
        self.assertEqual(first['readiness'], 'ready')
        self.assertEqual(second['readiness'], 'ready')

    def test_second_pass_rechecks_zero_metadata_despite_first_pass_timeouts(self):
        self._exercise_zero_metadata_second_pass(module.scan_metadata_reuse_allowed(), 'zero-native')

    @unittest.skipIf(os.name == 'nt', 'The native Windows branch runs in the main test')
    def test_second_pass_zero_metadata_forced_windows_no_reuse(self):
        self._exercise_zero_metadata_second_pass(False, 'zero-windows-mode')

    def _exercise_zero_metadata_second_pass(self, reuse_allowed, name):
        import threading
        import time
        one = self.create(name=name)
        for index in range(8):
            (one.root / f'blocked-{index}.md').write_text('provider waiting\n')
        time.sleep(0.01)
        (one.root / 'Z.md').write_text('verified source bytes\n')
        actual_read, actual_stamp = one._read, module.file_stamp
        gate = threading.Event()
        def stalled(name):
            if name.startswith('blocked-'):
                gate.wait()
            return actual_read(name)
        def zero_stamp(path):
            value = actual_stamp(path)
            if Path(path).name == 'Z.md':
                value[2] = 0
            return value
        with patch.object(one, '_read', side_effect=stalled), \
             patch.object(module, 'file_stamp', side_effect=zero_stamp), \
             patch.object(module, 'SCAN_FILE_SECONDS', 0.01), \
             patch.object(module, 'scan_metadata_reuse_allowed', return_value=reuse_allowed):
            result = one.sync()
        gate.set()
        for pending in one._pending_scan_reads:
            pending.join(timeout=1)
        self.assertEqual(result['readiness'], 'partial')
        self.assertEqual(result['scan_coverage']['covered'], 2 if reuse_allowed else 1)
        self.assertEqual(result['scan_coverage']['deferred'], 8 if reuse_allowed else 9)
        if not reuse_allowed:
            self.assertEqual(result['scan_coverage']['audit'], 'metadata_unavailable')
        entries = json.loads((one.state / 'scan-index.json').read_text())['entries']
        self.assertIn('Z.md', entries)
        self.assertIn((one.root / 'Z.md').read_bytes().decode('utf-8'),
                      [event['changes'].get('Z.md') for event in one.history('Z.md')['events']])
        for index in range(8):
            blocked = f'blocked-{index}.md'
            self.assertNotIn(blocked, entries)
            self.assertIn(blocked, result['partial_files'])
        self.assertGreaterEqual(result['scan_timeout_count'], 8)

    def test_empty_tracked_provider_placeholder_stays_partial(self):
        one = self.create()
        prior = one._baseline()['Note.md']['text']
        real_stamp = module.file_stamp
        def placeholder_stamp(path):
            value = real_stamp(path)
            if Path(path).name == 'Note.md':
                value[2] = 0
            return value
        with patch.object(module, 'file_stamp', side_effect=placeholder_stamp), \
             patch.object(one, '_read', return_value=''):
            result = one.sync()
        self.assertEqual(result['readiness'], 'partial')
        self.assertIn('Note.md', result['partial_files'])
        self.assertEqual(one._baseline()['Note.md']['text'], prior)

    def test_stable_read_rejects_real_replacement_between_path_check_and_open(self):
        path = self.base / 'replace-during-read.txt'; path.write_bytes(b'original')
        replacement = self.base / 'replacement.txt'; replacement.write_bytes(b'replaced')
        before = path.stat()
        os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
        original = module.os.open
        changed = []
        def replace_before_open(name, flags, *args, **kwargs):
            if Path(name) == path and not changed:
                changed.append(True); os.replace(replacement, path)
            return original(name, flags, *args, **kwargs)
        with patch.object(module.os, 'open', replace_before_open):
            with self.assertRaises(ProductError) as failure:
                module.read_bytes(path)
        self.assertEqual(failure.exception.code, 'folder_partial_file')
        self.assertEqual(path.read_bytes(), b'replaced')

    def test_stable_read_rejects_actual_inplace_write_during_read(self):
        path = self.base / 'inplace.txt'; path.write_bytes(b'original')
        before = path.stat(); original = module.os.fstat; calls = []
        def edit_before_after_stat(fd):
            calls.append(True)
            if len(calls) == 2:
                path.write_bytes(b'MODIFIED')
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000))
            return original(fd)
        with patch.object(module.os, 'fstat', edit_before_after_stat):
            with self.assertRaises(ProductError) as failure:
                module.read_bytes(path)
        self.assertEqual(failure.exception.code, 'folder_partial_file')
        self.assertEqual(path.read_bytes(), b'MODIFIED')

    def test_stable_read_explicitly_requests_binary_descriptor(self):
        path = self.base / 'binary.txt'; content = b'one\r\ntwo\x1athree\r'
        path.write_bytes(content)
        original = module.os.open
        binary_flag = getattr(module.os, 'O_BINARY', 0x40000000)
        observed = []
        def capture_flags(name, flags, *args, **kwargs):
            observed.append(flags)
            forwarded = flags if os.name == 'nt' else flags & ~binary_flag
            return original(name, forwarded, *args, **kwargs)
        with patch.object(module.os, 'O_BINARY', binary_flag, create=True), patch.object(module.os, 'open', capture_flags):
            self.assertEqual(module.read_bytes(path), content)
        self.assertTrue(observed[0] & binary_flag)


if __name__ == '__main__': unittest.main()
