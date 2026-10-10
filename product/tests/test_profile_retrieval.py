"""Synthetic acceptance for manifest-aware exact/hybrid recall and expansion."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from product.shared_workspace import recall as retrieval
from product.shared_workspace.errors import ProductError


class ProfileRetrievalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='profile-retrieval-')
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base / 'vault'
        self.root.mkdir()
        self.state = self.base / 'private'
        self.write('AGENTS.md', '# Instructions\nRead selected notes.\n')
        self.write('INDEX.md', '# Index\nSelected project routes.\n')

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def profile(self, kind, folders=()):
        self.write('.shared-memory.json', json.dumps({'vault_profile': {
            'type': kind, 'project_folders': list(folders)}}))

    def recall(self, query, strategy, **kwargs):
        return retrieval.recall(self.root, self.state, query, strategy=strategy,
                                max_bytes=8192, **kwargs)

    def check_show(self, hit):
        shown = retrieval.show(self.root, hit['path'], hit['sha256'], hit['start'], hit['end'])
        self.assertEqual(shown['excerpt'], hit['excerpt'])
        self.assertEqual(shown['sha256'], hashlib.sha256(
            (self.root / hit['path']).read_bytes()).hexdigest())

    def test_personal_default_sources_opt_in_cold_and_warm(self):
        self.profile('personal')
        self.write('Notes/Bird.md', '# Bird\nThe violet raven arrived.\n')
        self.write('Resources/Source.md', '# Source\nThe copper heron arrived.\n')
        self.write('Wiki/Old.md', '# Old\nThe obsolete walrus arrived.\n')
        for strategy in ('exact', 'hybrid'):
            for refresh in (True, False):
                with self.subTest(strategy=strategy, refresh=refresh):
                    answer = self.recall('violet', strategy, refresh=refresh)
                    self.assertEqual({h['path'] for h in answer['hits']}, {'Notes/Bird.md'})
                    self.assertIn('Resources', answer['unsearched'])
                    self.assertFalse(any('Wiki' in entry for entry in answer['unsearched']))
                    self.check_show(answer['hits'][0])
                    self.assertFalse(self.recall('copper', strategy, refresh=refresh)['hits'])
                    included = self.recall('copper', strategy, raw=True, refresh=refresh)
                    self.assertEqual(included['hits'][0]['path'], 'Resources/Source.md')
                    self.check_show(included['hits'][0])
                    # Previously indexed Resources must not leak to default scope.
                    self.assertFalse(self.recall('copper', strategy)['hits'])
                    self.assertFalse(self.recall('obsolete', strategy, raw=True, output=True)['hits'])

    def test_project_nested_declared_directories_and_qualified_graph(self):
        self.profile('project', ['Design/Models', 'Experiments', 'Deliverables'])
        self.write('Design/Models/Relay.md', '# Relay\nThe quartz relay is ready. See [[Experiments/Schedule]].\n')
        self.write('Experiments/Schedule.md', '# Schedule\n2026-10-02: The launch window opens.\n')
        self.write('Deliverables/Report.md', '# Report\nThe satin badger arrived.\n')
        self.write('Unlisted/Old.md', '# Old\nThe undeclared walrus arrived.\n')
        for strategy in ('exact', 'hybrid'):
            for refresh in (True, False):
                with self.subTest(strategy=strategy, refresh=refresh):
                    result = self.recall('quartz', strategy, refresh=refresh)
                    paths = {hit['path'] for hit in result['hits']}
                    self.assertIn('Design/Models/Relay.md', paths)
                    if strategy == 'hybrid':
                        self.assertIn('Experiments/Schedule.md', paths)
                    for hit in result['hits']:
                        self.check_show(hit)
                    self.assertIn('undeclared_project_folders', result['unsearched'])
                    self.assertFalse(self.recall('undeclared', strategy, raw=True, output=True)['hits'])
                    self.assertEqual(self.recall('satin', strategy)['hits'][0]['path'], 'Deliverables/Report.md')

    def test_custom_scope_rejects_private_nested_and_linked_files(self):
        self.profile('project', ['Design', 'Coordination', 'Nested/Notes'])
        self.write('Design/Good.md', '# Good\nThe visible raven arrived.\n')
        self.write('Design/Coordination/Secret.md', 'private-only otter')
        self.write('Coordination/Secret.md', 'private-only otter')
        self.write('Design/Sub/.shared-memory.json', '{}')
        self.write('Design/Sub/Secret.md', 'nested-only otter')
        self.write('Nested/.shared-memory.json', '{}')
        self.write('Nested/Notes/Secret.md', 'nested-only otter')
        outside = self.base / 'Outside.md'
        outside.write_text('linked-only otter')
        try:
            (self.root / 'Design/Link.md').symlink_to(outside)
        except OSError:
            pass
        for strategy in ('exact', 'hybrid'):
            for query in ('private-only', 'nested-only', 'linked-only'):
                self.assertFalse(self.recall(query, strategy, refresh=True)['hits'])
            self.assertEqual(self.recall('visible', strategy)['hits'][0]['path'], 'Design/Good.md')
        for name in ('Design/Coordination/Secret.md', 'Coordination/Secret.md',
                     'Design/Sub/Secret.md', 'Nested/Notes/Secret.md'):
            with self.assertRaises(ProductError):
                retrieval.show(self.root, name, 'a' * 64, 1, 1)

    def test_invalid_declaration_fails_closed(self):
        for folders in (['../Outside'], ['Design', 'Design/Sub'], ['/tmp']):
            self.profile('project', folders)
            with self.assertRaises(ProductError):
                self.recall('test', 'exact')
            with self.assertRaises(ProductError):
                self.recall('test', 'hybrid')

    def test_legacy_scope_unchanged(self):
        self.write('Wiki/Note.md', 'legacy raven')
        self.write('Notes/Note.md', 'personal otter')
        for strategy in ('exact', 'hybrid'):
            self.assertEqual(self.recall('legacy', strategy)['hits'][0]['path'], 'Wiki/Note.md')
            self.assertFalse(self.recall('personal', strategy)['hits'])


if __name__ == '__main__':
    unittest.main()
