"""Official-SDK acceptance for the optional fixed-project stdio adapter."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from product.shared_workspace import memory_mcp, recall
from product.shared_workspace.errors import ProductError

REPO = Path(__file__).resolve().parents[2]


def has_sdk():
    try:
        return importlib.metadata.version('mcp') == memory_mcp.SDK_VERSION
    except importlib.metadata.PackageNotFoundError:
        return False


class OptionalImportTests(unittest.TestCase):
    def test_ordinary_module_import_needs_no_optional_sdk(self):
        process = subprocess.run([sys.executable, '-S', '-c',
                                  'import product.shared_workspace.memory_mcp; print("optional")'],
                                 cwd=REPO, capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout.strip(), 'optional')

    def test_missing_project_refused_before_private_state_or_sdk_use(self):
        with tempfile.TemporaryDirectory(prefix='memory-mcp-missing-') as temp:
            base = Path(temp)
            state = base / 'state'
            with self.assertRaises(ProductError) as caught:
                memory_mcp.create_server(base / 'missing', state)
            self.assertEqual(caught.exception.code, 'project_missing')
            self.assertFalse(state.exists())


@unittest.skipUnless(has_sdk(), 'requires optional mcp==1.30.0; normal runtime is dependency-free')
class MemoryMCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='memory-mcp-case-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / 'project'
        self.state = self.base / 'private-state'
        sources = {
            'AGENTS.md': '# Rules\nPreserve original source files.\n',
            'INDEX.md': '# Index\nSee Wiki/Handoff.md.\n',
            'Wiki/Handoff.md': '# Work\n## Current handoff\nThe rare violet raven arrived.\n'
                               'STOP: do not publish without approval.\n## History\n'
                               'Superseded approval must not be replayed.\n',
            'Wiki/日本語.md': '# 日本語\nThe violet source says "a\\b" and 日本語.\n',
            'Raw/Hidden.md': '# Raw source\nraw-only copper heron\n',
            'Output/Report.md': '# Output\noutput-only amber finch\n',
            'Wiki/credentials/Hidden.md': '# Private\nprivate-only cobalt tern\n',
            'Wiki/Nested/.shared-memory.json': '{}',
            'Wiki/Nested/Secret.md': '# Nested\nnested-only silver owl\n',
        }
        for name, content in sources.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        self.before = {name: (self.root / name).read_bytes() for name in sources}
        self.server = memory_mcp.create_server(self.root, self.state)

    def decoded(self, result, *, cap=8192, error=False):
        self.assertLessEqual(memory_mcp.serialized_size(result), cap)
        self.assertEqual(result.isError, error)
        self.assertIsNone(result.structuredContent)
        self.assertEqual(len(result.content), 1)
        self.assertEqual(result.content[0].type, 'text')
        payload = json.loads(result.content[0].text)
        self.assertEqual(payload['ok'], not error)
        return payload

    def args(self, *, path='Wiki/Handoff.md', start=3, end=4, max_bytes=8192):
        digest = hashlib.sha256((self.root / path).read_bytes()).hexdigest()
        return {'path': path, 'sha256': digest, 'start': start, 'end': end, 'max_bytes': max_bytes}

    async def test_three_closed_readonly_tools_without_duplicate_output(self):
        tools = await self.server.list_tools()
        self.assertEqual({tool.name for tool in tools},
                         {'isolinear_search', 'isolinear_fetch', 'isolinear_context'})
        for tool in tools:
            self.assertTrue(tool.annotations.readOnlyHint)
            self.assertFalse(tool.annotations.destructiveHint)
            self.assertTrue(tool.annotations.idempotentHint)
            self.assertFalse(tool.annotations.openWorldHint)
            self.assertIsNone(tool.outputSchema)
            self.assertFalse(tool.inputSchema['additionalProperties'])
            self.assertNotIn('root', tool.inputSchema['properties'])
            self.assertNotIn('state', tool.inputSchema['properties'])
        result = await self.server.call_tool('isolinear_search', {'query': 'rare violet'})
        payload = self.decoded(result, cap=2048)
        hit = payload['data']['hits'][0]
        self.assertEqual(hit['path'], 'Wiki/Handoff.md')
        self.assertNotIn('evidence_id', hit)

    async def test_receipts_are_explicit_and_source_edits_invalidate_them(self):
        first = self.decoded(await self.server.call_tool('isolinear_search',
                             {'query': 'rare violet', 'known_evidence': [], 'max_hits': 1}))
        hit = first['data']['hits'][0]
        self.assertEqual(hit['delivery'], 'full')
        repeated = self.decoded(await self.server.call_tool('isolinear_search',
                                {'query': 'rare violet', 'known_evidence': [hit['evidence_id']], 'max_hits': 1}))
        self.assertEqual(repeated['data']['hits'][0]['delivery'], 'unchanged')
        self.assertNotIn('excerpt', repeated['data']['hits'][0])
        path = self.root / hit['path']
        path.write_text(path.read_text(encoding='utf-8') + 'A changed source outside the selected passage.\n', encoding='utf-8')
        changed = self.decoded(await self.server.call_tool('isolinear_search',
                               {'query': 'rare violet', 'known_evidence': [hit['evidence_id']], 'max_hits': 1}))
        self.assertEqual(changed['data']['hits'][0]['delivery'], 'full')
        self.assertNotEqual(changed['data']['hits'][0]['evidence_id'], hit['evidence_id'])

    async def test_fetch_requires_current_hash_and_preserves_exact_lines(self):
        args = self.args()
        full = self.decoded(await self.server.call_tool('isolinear_fetch', args))
        self.assertIn('STOP: do not publish', full['data']['excerpt'])
        self.assertEqual(full['data']['excerpt'], '\n'.join(
            (self.root / args['path']).read_text(encoding='utf-8').splitlines()[2:4]))
        (self.root / args['path']).write_text('# Changed\nA new source.\n', encoding='utf-8')
        stale = self.decoded(await self.server.call_tool('isolinear_fetch', args), error=True)
        self.assertEqual(stale['code'], 'recall_stale')

    async def test_context_is_atomic_and_reset_loads_full_authored_sources(self):
        args = {'path': 'Wiki/Handoff.md', 'heading': 'Current handoff', 'known_evidence': []}
        first = self.decoded(await self.server.call_tool('isolinear_context', args))
        hits = first['data']['hits']
        self.assertEqual([hit['path'] for hit in hits], ['AGENTS.md', 'INDEX.md', 'Wiki/Handoff.md'])
        self.assertIn('STOP: do not publish', hits[2]['excerpt'])
        self.assertNotIn('Superseded approval', hits[2]['excerpt'])
        known = [hit['evidence_id'] for hit in hits]
        repeated = self.decoded(await self.server.call_tool('isolinear_context',
                                {**args, 'known_evidence': known}))
        self.assertTrue(all(hit['delivery'] == 'unchanged' for hit in repeated['data']['hits']))
        reset = self.decoded(await self.server.call_tool('isolinear_context', args))
        self.assertTrue(all(hit['delivery'] == 'full' for hit in reset['data']['hits']))
        small = self.decoded(await self.server.call_tool('isolinear_context',
                             {**args, 'max_bytes': 512}), cap=512, error=True)
        self.assertIn(small['code'], {'context_budget', 'memory_mcp_budget'})
        self.assertNotIn('hits', small)

    async def test_actual_mcp_escaping_is_counted_before_returning_source(self):
        path = self.root / 'Wiki/Escapes.md'
        path.write_text('\\' * 500 + ' "日本語"\n', encoding='utf-8')
        args = self.args(path='Wiki/Escapes.md', start=1, end=1, max_bytes=2048)
        # The engine payload fits its existing CLI budget. The additional MCP
        # string layer doubles escapes and must still respect the same cap.
        raw = recall.show(self.root, args['path'], args['sha256'], 1, 1, max_bytes=2048)
        self.assertEqual(raw['excerpt'], path.read_text(encoding='utf-8').strip('\n'))
        bounded = self.decoded(await self.server.call_tool('isolinear_fetch', args), cap=2048, error=True)
        self.assertEqual(bounded['code'], 'memory_mcp_budget')
        self.assertNotIn('excerpt', bounded)

    async def test_scopes_and_unknown_root_arguments_fail_closed(self):
        digest = '0' * 64
        outside = self.base / 'Outside.md'
        outside.write_text('outside-only forbidden material', encoding='utf-8')
        for path in ['../Outside.md', str(outside), 'Wiki/credentials/Hidden.md', 'Wiki/Nested/Secret.md']:
            response = await self.server.call_tool('isolinear_fetch',
                       {'path': path, 'sha256': digest, 'start': 1, 'end': 1})
            self.decoded(response, error=True)
            self.assertNotIn('forbidden material', response.content[0].text)
        denied = self.decoded(await self.server.call_tool('isolinear_search',
                              {'query': 'violet', 'root': str(outside.parent)}), cap=2048, error=True)
        self.assertEqual(denied['code'], 'memory_mcp_arguments')
        for query in ['raw-only copper', 'output-only amber', 'private-only cobalt', 'nested-only silver']:
            result = self.decoded(await self.server.call_tool('isolinear_search', {'query': query}))
            self.assertFalse(result['data']['hits'])

    async def test_invalid_sdk_arguments_are_bounded_without_echo(self):
        marker = 'CALLER_SECRET_' + 'x' * 12000
        cases = [{'query': marker, 'max_bytes': 512},
                 {'query': 'violet', 'max_hits': 0, 'max_bytes': 512},
                 {'query': 'violet', 'strategy': 'hindsight', 'max_bytes': 512},
                 {'query': 'violet', 'known_evidence': ['0' * 32] * 33, 'max_bytes': 512}]
        for args in cases:
            response = await self.server.call_tool('isolinear_search', args)
            data = self.decoded(response, cap=512, error=True)
            self.assertEqual(data['code'], 'memory_mcp_arguments')
            self.assertNotIn('CALLER_SECRET', response.content[0].text)
        for arguments in [None, [], 'not-an-object']:
            response = self.decoded(await self.server.call_tool('isolinear_search', arguments),
                                    cap=512, error=True)
            self.assertEqual(response['code'], 'memory_mcp_arguments')

    async def test_source_notes_never_change_and_no_shared_index_is_created(self):
        self.decoded(await self.server.call_tool('isolinear_search', {'query': 'violet', 'strategy': 'hybrid'}))
        self.decoded(await self.server.call_tool('isolinear_context',
                     {'path': 'Wiki/Handoff.md', 'heading': 'Current handoff'}))
        for name, data in self.before.items():
            self.assertEqual((self.root / name).read_bytes(), data)
        self.assertFalse(list(self.root.rglob('*.sqlite3')))

    async def test_existing_source_deadline_survives_sdk_adapter(self):
        args = self.args()
        content = (self.root / args['path']).read_text(encoding='utf-8')
        original = recall.show
        released = threading.Event()
        completed = threading.Event()

        def slow_read(path):
            released.wait(1)
            completed.set()
            return content

        def short_guard(*values, **options):
            return original(*values, **options, deadline=.1)

        with mock.patch.object(recall, '_read', side_effect=slow_read), \
                mock.patch.object(recall, 'show', side_effect=short_guard):
            try:
                result = self.decoded(await self.server.call_tool('isolinear_fetch', args), error=True)
                self.assertEqual(result['code'], 'recall_deadline')
                self.assertFalse(completed.is_set())
            finally:
                # Release the discarded daemon reader before fixture cleanup.
                released.set()

    async def test_actual_sdk_stdio_roundtrip_search_fetch_context_scope_and_budget(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        code = ('from pathlib import Path; import sys; '
                'from product.shared_workspace.memory_mcp import serve; '
                'serve(Path(sys.argv[1]),Path(sys.argv[2]))')
        params = StdioServerParameters(command=sys.executable,
                                       args=['-c', code, str(self.root), str(self.state)], cwd=str(REPO))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                self.assertEqual(len(tools.tools), 3)
                found = self.decoded(await session.call_tool('isolinear_search',
                                     {'query': 'rare violet', 'max_hits': 1}), cap=2048)
                hit = found['data']['hits'][0]
                fetched = self.decoded(await session.call_tool('isolinear_fetch',
                                       {'path': hit['path'], 'sha256': hit['sha256'],
                                        'start': hit['start'], 'end': hit['end']}))
                self.assertEqual(fetched['data']['excerpt'], hit['excerpt'])
                packet = self.decoded(await session.call_tool('isolinear_context',
                                      {'path': hit['path'], 'heading': 'Current handoff'}))
                self.assertIn('STOP:', packet['data']['hits'][2]['excerpt'])
                invalid = self.decoded(await session.call_tool('isolinear_search',
                                       {'query': 'z' * 12000, 'max_bytes': 512}), cap=512, error=True)
                self.assertEqual(invalid['code'], 'memory_mcp_arguments')
                denied = self.decoded(await session.call_tool('isolinear_fetch',
                                      {'path': '../Outside.md', 'sha256': hit['sha256'],
                                       'start': 1, 'end': 1}), error=True)
                self.assertEqual(denied['code'], 'recall_path')


if __name__ == '__main__':
    unittest.main()
