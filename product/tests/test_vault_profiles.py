"""Vault profile setup is portable, recoverable and preserves existing work."""
from pathlib import Path
import json
import shutil
from unittest import mock
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'product'))
from shared_workspace.folder import Folder
from shared_workspace import folder as folder_module
from shared_workspace.errors import ProductError


class VaultProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package_temp = tempfile.TemporaryDirectory(prefix='vault-profile-package-')
        cls.addClassCleanup(cls.package_temp.cleanup)
        cls.package = Path(cls.package_temp.name) / 'product.pyz'
        result = subprocess.run([sys.executable, str(REPO / 'scripts/build_product.py'), '--output', str(cls.package)], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vault-profile-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'vault'
        self.root.mkdir()
        self.state = self.base / 'state'

    def setup(self, *args, expected=0):
        result = subprocess.run([sys.executable, str(self.package), 'setup', str(self.root), '--state-dir', str(self.state), *args], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_default_team_structure_is_compatible(self):
        result = self.setup()['data']
        self.assertEqual(result['vault_type'], 'team')
        self.assertEqual({p.relative_to(self.root).as_posix() for p in self.root.rglob('README.md')}, {'Raw/README.md', 'Wiki/README.md', 'Output/README.md'})

    def test_personal_instructions_are_simple_and_resume_retains_profile(self):
        first = self.setup('--vault-type', 'personal')['data']
        instructions = (self.root / 'AGENTS.md').read_text()
        self.assertIn('Do not require manual', instructions)
        self.assertIn('person-agent attribution, change registers', instructions)
        self.assertIn('Keep factual accuracy', instructions)
        self.assertEqual({p.relative_to(self.root).as_posix() for p in self.root.rglob('README.md')}, {'Notes/README.md', 'Resources/README.md'})
        self.assertEqual(self.setup()['data']['vault_type'], 'personal')
        self.assertEqual(json.loads((self.root / '.shared-memory.json').read_text())['vault_profile']['type'], 'personal')
        self.assertEqual(self.setup('--vault-type', 'team', expected=3)['code'], 'vault_profile_mismatch')
        self.assertEqual(self.setup()['data']['project_id'], first['project_id'])

    def test_project_custom_nested_folders_and_resume(self):
        self.setup('--vault-type', 'project', '--project-folder', 'Engineering/Hardware', '--project-folder', 'Decisions', '--project-folder', 'Delivery')
        self.assertTrue((self.root / 'Engineering/Hardware/README.md').is_file())
        self.assertFalse((self.root / 'Wiki').exists())
        index = (self.root / 'INDEX.md').read_text()
        self.assertIn('[[Engineering/Hardware/README|Engineering/Hardware/]]', index)
        self.assertEqual(self.setup()['data']['project_folders'], ['Engineering/Hardware', 'Decisions', 'Delivery'])
        self.setup('--vault-type', 'project', '--project-folder', 'Different', expected=3)

    def test_shared_project_preserves_two_contributor_attribution(self):
        self.setup('--vault-type', 'project', '--project-folder', 'Design',
                   '--actor', 'editor-a', '--person', 'Alice', '--agent', 'Codex')
        note = self.root / 'Design/Work.md'
        note.write_text('Alice created the design.\n')
        def cli(*args):
            result = subprocess.run([sys.executable, str(self.package), *map(str, args)],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)['data']
        cli('sync', self.root, '--state-dir', self.state)
        second_state = self.base / 'second-private'
        cli('setup', self.root, '--state-dir', second_state, '--actor', 'editor-b',
            '--person', 'Bob', '--agent', 'Claude')
        note.write_text('Alice created the design.\nBob reviewed the design.\n')
        cli('sync', self.root, '--state-dir', second_state)
        events = cli('history', self.root, '--state-dir', second_state,
                     '--path', 'Design/Work.md')['events']
        authors = {(event['author']['person'], event['author']['agent']) for event in events}
        self.assertIn(('Alice', 'Codex'), authors)
        self.assertIn(('Bob', 'Claude'), authors)
        self.assertIn('Retain person/agent contribution attribution',
                      (self.root / 'AGENTS.md').read_text())

    def test_generic_project_fallback_is_explicit(self):
        result = self.setup('--vault-type', 'project')['data']
        self.assertEqual(result['project_folders'], ['Knowledge', 'Planning', 'Deliverables'])
        self.assertIn('starting point', (self.root / 'AGENTS.md').read_text())

    def test_populated_vault_keeps_hierarchy_and_content(self):
        (self.root / 'Existing').mkdir()
        (self.root / 'Existing/Note.md').write_text('Original content')
        self.setup('--vault-type', 'project', '--project-folder', 'NewDomain')
        self.assertFalse((self.root / 'NewDomain').exists())
        self.assertFalse((self.root / 'AGENTS.md').exists())
        self.assertEqual((self.root / 'Existing/Note.md').read_text(), 'Original content')

    def test_unsafe_custom_folders_fail_before_creating_state(self):
        for folder in ('../Escape', '/absolute', 'A//B', '.hidden', 'A\\B', 'CON', 'A|B', 'A/B/../../C'):
            with self.subTest(folder=folder):
                self.setup('--vault-type', 'project', '--project-folder', folder, expected=2)
                self.assertFalse(self.state.exists())
                self.assertEqual(list(self.root.iterdir()), [])
        self.setup('--vault-type', 'project', '--project-folder', 'Data', '--project-folder', 'data/Child', expected=2)
        self.setup('--vault-type', 'personal', '--project-folder', 'Data', expected=2)

    def test_personal_join_retains_profile_without_flags(self):
        first = self.setup('--vault-type', 'personal')['data']
        recipient = self.base / 'recipient'
        shutil.copytree(self.root, recipient)
        result = subprocess.run([sys.executable, str(self.package), 'setup', str(recipient),
                                 '--state-dir', str(self.base / 'recipient-state')], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)['data']
        self.assertEqual(data['vault_type'], 'personal')
        self.assertEqual(data['project_id'], first['project_id'])

    def test_interrupted_initialization_resumes_saved_profile(self):
        original_atomic = folder_module.atomic
        def interrupted(path, data, immutable=False):
            if path == self.root / '.shared-memory.json':
                raise OSError('Synthetic manifest interruption')
            return original_atomic(path, data, immutable=immutable)
        with mock.patch.object(folder_module, 'atomic', side_effect=interrupted):
            with self.assertRaises(ProductError):
                Folder.initialize(self.root, self.state, actor='device', person='Owner', agent='Agent',
                                  vault_profile={'type': 'personal', 'project_folders': []},
                                  initial_files={'Notes/README.md': '# Notes\n'}, materialize_initial=True)
        self.assertFalse((self.root / '.shared-memory.json').exists())
        result = self.setup()['data']
        self.assertEqual(result['vault_type'], 'personal')
        self.assertTrue((self.root / 'Notes/README.md').exists())

    def test_old_interrupted_initialization_remains_resumable(self):
        original_atomic = folder_module.atomic
        def interrupted(path, data, immutable=False):
            if path == self.root / '.shared-memory.json':
                raise OSError('Synthetic manifest interruption')
            return original_atomic(path, data, immutable=immutable)
        with mock.patch.object(folder_module, 'atomic', side_effect=interrupted):
            with self.assertRaises(ProductError):
                Folder.initialize(self.root, self.state, actor='device', person='Owner', agent='Agent')
        path = self.state / 'initialization.json'
        intent = json.loads(path.read_text())
        intent.pop('vault_profile')
        path.write_text(json.dumps(intent))
        self.assertEqual(self.setup()['data']['vault_type'], 'team')
        self.assertNotIn('vault_profile', json.loads((self.root / '.shared-memory.json').read_text()))

    def test_malformed_profiles_are_rejected_in_manifest_and_direct_api(self):
        malformed = ({}, {'type': 'unknown', 'project_folders': []},
                     {'type': 'project', 'project_folders': '../Escape'},
                     {'type': 'personal', 'project_folders': ['Data']},
                     {'type': 'project', 'project_folders': ['../Escape']})
        for profile in malformed:
            with self.subTest(profile=profile):
                with self.assertRaises(ProductError):
                    Folder.initialize(self.root, self.state, actor='device', person='Owner', agent='Agent', vault_profile=profile)
                self.assertFalse(self.state.exists())
        self.setup()
        path = self.root / '.shared-memory.json'
        manifest = json.loads(path.read_text())
        manifest['vault_profile'] = {'type': 'unknown', 'project_folders': []}
        path.write_text(json.dumps(manifest))
        self.assertEqual(self.setup(expected=3)['code'], 'folder_vault_profile')

    def test_old_manifest_is_not_reclassified(self):
        self.setup()
        path = self.root / '.shared-memory.json'
        manifest = json.loads(path.read_text())
        manifest.pop('vault_profile')
        path.write_text(json.dumps(manifest))
        self.setup('--vault-type', 'personal', expected=3)
        self.assertEqual(self.setup()['data']['vault_type'], 'team')
        self.assertNotIn('vault_profile', json.loads(path.read_text()))


if __name__ == '__main__':
    unittest.main()
