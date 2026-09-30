"""The CI fixture mirror keeps the same exact archive integrity gate."""
from __future__ import annotations

import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import zipfile


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/prepare_rclone_fixture.py'
spec = importlib.util.spec_from_file_location('rclone_fixture', SCRIPT)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class RcloneFixtureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='isolinear-rclone-fixture-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.name = 'rclone-v' + fixture.VERSION + '-osx-arm64'
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr(self.name + '/rclone', b'synthetic executable')
        self.archive = stream.getvalue()

    def test_official_github_mirror_uses_same_pinned_archive_hash(self):
        calls = []

        def fetch(url, timeout):
            calls.append(url)
            if len(calls) == 1:
                raise HTTPError(url, 403, 'Forbidden', None, None)
            return io.BytesIO(self.archive)

        with patch.object(fixture.platform, 'system', return_value='Darwin'), \
             patch.object(fixture.platform, 'machine', return_value='arm64'), \
             patch.dict(fixture.HASHES, {'osx-arm64': hashlib.sha256(self.archive).hexdigest()}), \
             patch.object(fixture.urllib.request, 'urlopen', side_effect=fetch):
            result = fixture.prepare(self.root / 'out')
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0].startswith('https://downloads.rclone.org/'))
        self.assertTrue(calls[1].startswith('https://github.com/rclone/rclone/releases/download/'))
        self.assertEqual((self.root / 'out/rclone').read_bytes(), b'synthetic executable')
        self.assertEqual(result['archive_sha256'], hashlib.sha256(self.archive).hexdigest())

    def test_hash_mismatch_never_triggers_mirror(self):
        calls = []

        def fetch(url, timeout):
            calls.append(url)
            return io.BytesIO(self.archive)

        with patch.object(fixture.platform, 'system', return_value='Darwin'), \
             patch.object(fixture.platform, 'machine', return_value='arm64'), \
             patch.dict(fixture.HASHES, {'osx-arm64': '0' * 64}), \
             patch.object(fixture.urllib.request, 'urlopen', side_effect=fetch):
            with self.assertRaisesRegex(ValueError, 'did not match'):
                fixture.prepare(self.root / 'out')
        self.assertEqual(len(calls), 1)
        self.assertFalse((self.root / 'out').exists())


if __name__ == '__main__':
    unittest.main()
