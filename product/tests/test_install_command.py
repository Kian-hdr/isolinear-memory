import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

script = Path(__file__).resolve().parents[2]/'scripts/install_command.py'
spec = importlib.util.spec_from_file_location('install_command', script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LauncherTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "The installed command launcher is POSIX-only")
    def test_foreign_legacy_command_is_not_taken_over(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            runtime = base / 'runtime.py'
            runtime.write_text('print("verified")\n')
            digest = hashlib.sha256(runtime.read_bytes()).hexdigest()
            canonical = base / 'isolinear-memory'
            legacy = base / 'shared-memory'
            foreign = b'#!/bin/sh\necho unrelated-user-command\n'
            legacy.write_bytes(foreign)
            command = [sys.executable, str(script), '--runtime', str(runtime),
                       '--sha256', digest, '--destination', str(canonical)]
            refused = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn('not a recognized', refused.stderr)
            self.assertFalse(canonical.exists())
            self.assertEqual(legacy.read_bytes(), foreign)
            self.assertFalse(list(base.glob('*.previous-*')))
            canonical_only = subprocess.run([*command, '--no-legacy-alias'],
                                            capture_output=True, text=True)
            self.assertEqual(canonical_only.returncode, 0, canonical_only.stderr)
            self.assertEqual(legacy.read_bytes(), foreign)
            self.assertTrue(module.managed_launcher(canonical.read_bytes()))
            canonical.write_bytes(foreign)
            refused_canonical = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(refused_canonical.returncode, 0)
            self.assertEqual(canonical.read_bytes(), foreign)

    @unittest.skipIf(os.name == "nt", "The installed command launcher is POSIX-only")
    def test_canonical_launcher_and_legacy_alias_share_verified_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            runtime = base / 'runtime.py'
            runtime.write_text('print("brand-compatible")\n')
            digest = hashlib.sha256(runtime.read_bytes()).hexdigest()
            canonical = base / 'isolinear-memory'
            result = subprocess.run([sys.executable, str(script), '--runtime', str(runtime),
                                     '--sha256', digest, '--destination', str(canonical)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            legacy = base / 'shared-memory'
            self.assertEqual(canonical.read_bytes(), legacy.read_bytes())
            self.assertEqual(len(json.loads(result.stdout)['launchers']), 2)
            for command in (canonical, legacy):
                launched = subprocess.run([str(command)], capture_output=True, text=True)
                self.assertEqual(launched.returncode, 0, launched.stderr)
                self.assertEqual(launched.stdout.strip(), 'brand-compatible')
            # Updating both launchers preserves the old executable for rollback.
            previous = legacy.read_bytes()
            runtime.write_text('print("updated-runtime")\n')
            new_digest = hashlib.sha256(runtime.read_bytes()).hexdigest()
            updated = subprocess.run([sys.executable, str(script), '--runtime', str(runtime),
                                      '--sha256', new_digest, '--destination', str(canonical)],
                                     capture_output=True, text=True)
            self.assertEqual(updated.returncode, 0, updated.stderr)
            record = json.loads(updated.stdout)
            self.assertEqual(len(record['launchers']), 2)
            old_backup = Path(record['launchers'][1]['recovery'])
            self.assertEqual(old_backup.read_bytes(), previous)
            for command in (canonical, legacy):
                launched = subprocess.run([str(command)], capture_output=True, text=True)
                self.assertEqual(launched.stdout.strip(), 'updated-runtime')
            single = base / 'single' / 'isolinear-memory'
            opt_out = subprocess.run([sys.executable, str(script), '--runtime', str(runtime),
                                      '--sha256', new_digest, '--destination', str(single),
                                      '--no-legacy-alias'], capture_output=True, text=True)
            self.assertEqual(opt_out.returncode, 0, opt_out.stderr)
            self.assertTrue(single.is_file())
            self.assertFalse((single.parent / 'shared-memory').exists())

    @unittest.skipIf(os.name == "nt", "The installed command launcher is POSIX-only; Windows uses Python .pyz")
    def test_checksum_argv_and_full_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp).resolve()
            runtime=base/'runtime with spaces.py'
            runtime.write_text('import json,sys; print(json.dumps(sys.argv[1:]))')
            wrapper=base/'command.py'
            digest=hashlib.sha256(runtime.read_bytes()).hexdigest()
            wrapper.write_text(module.launcher(Path(sys.executable).resolve(),runtime,digest))
            def run(*args):
                return subprocess.run([sys.executable,str(wrapper),*args],capture_output=True,text=True)
            self.assertEqual(json.loads(run('sync','project with spaces').stdout), ['sync','project with spaces','--brief'])
            self.assertEqual(json.loads(run('folder-status','--full').stdout), ['folder-status'])
            runtime.write_text('raise RuntimeError("must not execute")')
            result=run('sync')
            self.assertEqual(result.returncode,5)
            self.assertEqual(json.loads(result.stdout)['code'],'launcher_error')

    @unittest.skipUnless(os.name == "nt", "Windows-specific installer rejection")
    def test_windows_installer_reports_supported_route(self):
        result = subprocess.run([sys.executable, str(script), '--runtime', 'unused.pyz',
                                 '--sha256', '0'*64], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('on Windows use Python with the verified .pyz directly', result.stderr)
