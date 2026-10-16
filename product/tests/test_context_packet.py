"""Packaged, synthetic acceptance for complete authored context packets."""
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

REPO = Path(__file__).resolve().parents[2]
HANDOFF = '''---
name: synthetic
---
# Handoff
Introductory context.
## Current handoff
The amber source is current.
### Constraints
Preserve the camera material.
```markdown
## Current handoff
## Fake boundary
```
<!--
## Current handoff
-->
### Final safety boundary
STOP: Do not render without sequence approval.
## History
Historical action must not be replayed.
'''


class ContextPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package_dir = tempfile.TemporaryDirectory(prefix='context-package-')
        cls.addClassCleanup(cls.package_dir.cleanup)
        cls.package = Path(cls.package_dir.name) / 'isolinear.pyz'
        proc = subprocess.run([sys.executable, str(REPO / 'scripts/build_product.py'),
                               '--output', str(cls.package)], cwd=REPO,
                              capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='context-fixture-')
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base / 'project'
        for name, content in {
            'AGENTS.md': '# Rules\nDo not delete source assets.\n',
            'INDEX.md': '# Navigation\nSee [Handoff](Wiki/Handoff.md).\n',
            'Wiki/Handoff.md': HANDOFF,
            'Wiki/credentials/Hidden.md': '# Secret\nNever return this private-scope text.\n',
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        (self.root / 'Raw').mkdir()
        (self.root / 'Output').mkdir()

    def cli(self, *flags, name='Wiki/Handoff.md', root=None, expected=0, text=False):
        args = [sys.executable, str(self.package), 'context-packet', str(root or self.root),
                '--path', name, *map(str, flags)]
        if text:
            args += ['--text']
        proc = subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, expected, proc.stdout + proc.stderr)
        if expected == 0:
            cap = int(flags[flags.index('--max-bytes') + 1]) if '--max-bytes' in flags else 8192
            self.assertLessEqual(len(proc.stdout.encode('utf-8')), cap)
        result = proc.stdout if text else json.loads(proc.stdout)
        if expected and not text:
            self.assertNotIn('"excerpt":', json.dumps(result))
        return result

    def assert_sources(self, data):
        self.assertEqual(data['method'], 'context_packet')
        self.assertEqual(data['snapshot'], 'per_source')
        self.assertEqual(data['derivation'], 'authored_exact')
        self.assertFalse(data['truncated'])
        self.assertEqual(data['unavailable'], 0)
        self.assertEqual(data['unavailable_sources'], [])
        self.assertIn('linked_sources', data['unsearched'])
        self.assertIn('other_sections', data['unsearched'])
        self.assertEqual([h['path'] for h in data['hits']],
                         ['AGENTS.md', 'INDEX.md', 'Wiki/Handoff.md'])
        for hit in data['hits']:
            raw = (self.root / hit['path']).read_bytes()
            self.assertEqual(hit['sha256'], hashlib.sha256(raw).hexdigest())
            if hit['path'] in {'AGENTS.md', 'INDEX.md'}:
                self.assertEqual(hit['start'], 1)
                self.assertEqual(hit['end'], len(raw.decode('utf-8').splitlines()))
            if 'excerpt' in hit:
                expected = '\n'.join(raw.decode('utf-8').splitlines()[hit['start'] - 1:hit['end']])
                self.assertEqual(hit['excerpt'], expected)

    def test_complete_nested_section_including_final_stop_boundary(self):
        data = self.cli('--heading', 'Current handoff')['data']
        self.assert_sources(data)
        selected = data['hits'][-1]
        self.assertEqual(selected['start'], 6)
        self.assertEqual(selected['end'], 18)
        self.assertIn('### Constraints', selected['excerpt'])
        self.assertIn('STOP: Do not render without sequence approval.', selected['excerpt'])
        self.assertNotIn('Historical action', selected['excerpt'])
        self.assertNotIn('evidence_id', selected)

    def test_whole_file_and_text_preserve_all_authored_content(self):
        data = self.cli()['data']
        self.assert_sources(data)
        hit = data['hits'][-1]
        self.assertEqual(hit['start'], 1)
        self.assertEqual(hit['end'], len(HANDOFF.splitlines()))
        self.assertEqual(hit['excerpt'], '\n'.join(HANDOFF.splitlines()))
        text = self.cli('--heading', 'Current handoff', text=True)
        self.assertIn('AGENTS.md', text)
        self.assertIn('STOP: Do not render without sequence approval.', text)

    def test_frontmatter_fences_and_comments_do_not_create_headings(self):
        path = self.root / 'Wiki/Handoff.md'
        path.write_text('---\n# Selected\n---\n# Handoff\n~~~text\n## Selected\n~~~\n'
                        '<!--\n## Selected\n-->\n## Selected\nComplete true section.\n'
                        '### Child\nRetain child.\n## Other\nOmit other.\n')
        hit = self.cli('--heading', 'Selected')['data']['hits'][-1]
        self.assertEqual(hit['start'], 11)
        self.assertEqual(hit['end'], 14)
        self.assertIn('Retain child.', hit['excerpt'])
        self.assertNotIn('Omit other.', hit['excerpt'])

    def test_inline_opened_html_comment_does_not_truncate_safety_boundary(self):
        path = self.root / 'Wiki/Handoff.md'
        path.write_text('# Handoff\n## Current handoff\nText <!--\n## Fake boundary\n-->\n'
                        'STOP: Retain final approval requirement.\n## Next\nHistory.\n')
        hit = self.cli('--heading', 'Current handoff')['data']['hits'][-1]
        self.assertEqual(hit['start'], 2)
        self.assertEqual(hit['end'], 6)
        self.assertIn('STOP: Retain final approval requirement.', hit['excerpt'])

    def test_comment_removal_cannot_synthesize_a_heading_boundary(self):
        path = self.root / 'Wiki/Handoff.md'
        for body in ('<!-- inline -->## Fake boundary\n',
                     'Text <!--\n-->## Fake boundary\n'):
            with self.subTest(body=body):
                path.write_text('# Handoff\n## Current handoff\n' + body +
                                'STOP: require approval.\n## History\nOld.\n')
                hit = self.cli('--heading', 'Current handoff')['data']['hits'][-1]
                self.assertIn('STOP: require approval.', hit['excerpt'])
                self.assertNotIn('Old.', hit['excerpt'])
                self.assertEqual(hit['start'], 2)

    def test_raw_html_headings_do_not_truncate_safety_boundary(self):
        path = self.root / 'Wiki/Handoff.md'
        for tag in ('pre', 'script', 'style', 'textarea'):
            with self.subTest(tag=tag):
                path.write_text('# Handoff\n## Current handoff\n<' + tag + '>\n'
                                '## Fake boundary\n</' + tag + '>\n'
                                'STOP: Keep permission boundary.\n## Next\nHistory.\n')
                hit = self.cli('--heading', 'Current handoff')['data']['hits'][-1]
                self.assertEqual(hit['end'], 6)
                self.assertIn('STOP: Keep permission boundary.', hit['excerpt'])

    def test_missing_duplicate_and_setext_headings_fail_without_partial_packet(self):
        missing = self.cli('--heading', 'No such heading', expected=3)
        self.assertEqual(missing['code'], 'context_heading')
        path = self.root / 'Wiki/Handoff.md'
        path.write_text(HANDOFF + '\n## Current handoff\nConflicting duplicate.\n')
        duplicate = self.cli('--heading', 'Current handoff', expected=3)
        self.assertEqual(duplicate['code'], 'context_heading')
        path.write_text('Selected\n========\nNo ATX heading.\n')
        setext = self.cli('--heading', 'Selected', expected=3)
        self.assertEqual(setext['code'], 'context_heading')

    def test_missing_required_sources_fail_without_partial_packet(self):
        for name in ('AGENTS.md', 'INDEX.md', 'Wiki/Handoff.md'):
            path = self.root / name
            saved = path.read_bytes()
            path.unlink()  # disposable synthetic fixture
            try:
                result = self.cli(expected=5)
                self.assertEqual(result['code'], 'context_source')
            finally:
                path.write_bytes(saved)

    def test_duplicate_required_target_is_rejected(self):
        for name in ('AGENTS.md', 'INDEX.md'):
            result = self.cli(name=name, expected=3)
            self.assertEqual(result['code'], 'context_source')

    def test_budget_never_omits_safety_at_end_of_selected_section(self):
        path = self.root / 'Wiki/Handoff.md'
        path.write_text('# Handoff\n## Current handoff\n' + 'Synthetic detail. ' * 160 +
                        '\nSTOP: Do not render without sequence approval.\n## Other\nHistory.\n')
        data = self.cli('--heading', 'Current handoff', '--max-bytes', '8192')['data']
        self.assertIn('STOP: Do not render without sequence approval.', data['hits'][-1]['excerpt'])
        result = self.cli('--heading', 'Current handoff', '--max-bytes', '1024', expected=3)
        self.assertEqual(result['code'], 'context_budget')

    def test_unicode_crlf_and_no_workspace_mutation(self):
        path = self.root / 'Wiki/Handoff.md'
        raw = '# Handoff\r\n## Current handoff\r\nCafé 北京, retain exact source.\r\n'.encode()
        path.write_bytes(raw)
        before = {p.relative_to(self.root).as_posix(): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file()}
        data = self.cli('--heading', 'Current handoff')['data']
        self.assert_sources(data)
        self.assertEqual(data['hits'][-1]['sha256'], hashlib.sha256(raw).hexdigest())
        after = {p.relative_to(self.root).as_posix(): p.read_bytes()
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse(list(self.root.rglob('*.sqlite3')))

    def test_unsafe_private_and_nested_paths_fail_closed(self):
        for name in ('../Outside.md', 'Wiki/credentials/Hidden.md'):
            result = self.cli(name=name, expected=3)
            self.assertIn(result['code'], {'recall_path', 'recall_scope', 'context_source'})
        nested = self.root / 'Wiki/Nested'
        nested.mkdir()
        (nested / '.shared-memory.json').write_text('{}')
        (nested / 'Handoff.md').write_text('# Nested\nNot selected project authority.\n')
        result = self.cli(name='Wiki/Nested/Handoff.md', expected=3)
        self.assertIn(result['code'], {'recall_nested_project', 'recall_path', 'context_source'})

    def test_receipt_repeat_edit_reset_and_cross_root(self):
        flags = ('--heading', 'Current handoff', '--with-receipts')
        full = self.cli(*flags)['data']
        self.assert_sources(full)
        known = tuple(value for hit in full['hits']
                      for value in ('--known-evidence', hit['evidence_id']))
        repeat = self.cli('--heading', 'Current handoff', *known)['data']
        self.assertTrue(all(h['delivery'] == 'unchanged' and 'excerpt' not in h for h in repeat['hits']))
        reset = self.cli(*flags)['data']
        self.assertTrue(all(h['delivery'] == 'full' and 'excerpt' in h for h in reset['hits']))
        path = self.root / 'Wiki/Handoff.md'
        path.write_text(path.read_text().replace('17:40', '18:40') + '\nChanged source date: 2026-10-17.\n')
        edited = self.cli('--heading', 'Current handoff', *known)['data']
        self.assertEqual(edited['hits'][-1]['delivery'], 'full')
        self.assertNotEqual(edited['hits'][-1]['evidence_id'], full['hits'][-1]['evidence_id'])
        other = self.base / 'other-project'
        import shutil
        shutil.copytree(self.root, other)
        cross = self.cli('--heading', 'Current handoff', *known, root=other)['data']
        self.assertTrue(all(h['delivery'] == 'full' for h in cross['hits']))

    def test_deadline_has_no_partial_context(self):
        from product.shared_workspace import context_packet, recall
        from product.shared_workspace.errors import ProductError
        original = recall._read

        def delayed(path):
            result = original(path)
            time.sleep(.25)
            return result

        started = time.monotonic()
        with mock.patch.object(recall, '_read', side_effect=delayed):
            with self.assertRaises(ProductError) as raised:
                context_packet.context(self.root, 'Wiki/Handoff.md', deadline=.1)
            self.assertEqual(raised.exception.code, 'context_deadline')
            self.assertLess(time.monotonic() - started, .75)
            # Let the finite mocked reader complete before fixture teardown.
            import threading
            for worker in threading.enumerate():
                if worker.name == 'bounded-markdown-memory':
                    worker.join(timeout=2)

    def test_unknown_receipts_never_suppress_and_receipt_budget_is_atomic(self):
        unknown = self.cli('--known-evidence', 'f' * 32)['data']
        self.assertEqual(len(unknown['hits']), 3)
        self.assertTrue(all(h['delivery'] == 'full' for h in unknown['hits']))
        for hit in unknown['hits']:
            self.assertRegex(hit['evidence_id'], r'\A[0-9a-f]{32}\Z')
        # A small budget must fail rather than returning only mandatory files.
        result = self.cli('--with-receipts', '--max-bytes', '512', expected=3)
        self.assertEqual(result['code'], 'context_budget')


if __name__ == '__main__':
    unittest.main()
