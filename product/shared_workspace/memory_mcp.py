"""Optional official-SDK stdio adapter over one fixed local project.

No model, hosted service, cloud upload check or Hindsight dependency is involved.
Sources remain read-only; the existing engine may rebuild its private index.
Each result has one text JSON representation and a complete MCP-result byte cap.
"""
import asyncio
import importlib.metadata
import json
from pathlib import Path
from typing import Annotated, Literal

from . import PRODUCT_VERSION, context_packet, recall, workflow
from .errors import ProductError
from .folder import private_path

SDK_VERSION = '1.30.0'
PUBLIC_ICON_BASE = f'https://raw.githubusercontent.com/Kian-hdr/isolinear-memory/v{PRODUCT_VERSION}/assets/'
ALLOWED = {
    'isolinear_search': {'query', 'strategy', 'max_hits', 'max_bytes', 'known_evidence'},
    'isolinear_fetch': {'path', 'sha256', 'start', 'end', 'max_bytes'},
    'isolinear_context': {'path', 'heading', 'max_bytes', 'known_evidence'},
}
DEFAULT_BYTES = {'isolinear_search': 2048, 'isolinear_fetch': 8192, 'isolinear_context': 8192}


def _sdk():
    """Keep ordinary CLI imports dependency-free and pin the tested wire API."""
    try:
        if importlib.metadata.version('mcp') != SDK_VERSION:
            raise ImportError('Untested SDK version')
        from mcp.server.fastmcp import FastMCP
        from mcp.types import CallToolResult, Icon, TextContent, ToolAnnotations
        from pydantic import Field
        return FastMCP, CallToolResult, TextContent, ToolAnnotations, Field, Icon
    except (ImportError, importlib.metadata.PackageNotFoundError) as error:
        raise ProductError(3, 'memory_mcp_sdk',
                           'Install optional requirements-mcp.txt in this private Python environment.') from error


def serialized_size(result):
    """Match the pinned official stdio writer's complete result serialization."""
    return len(result.model_dump_json(by_alias=True, exclude_none=True).encode('utf-8'))


def create_server(root: Path, state: Path):
    """Construct three source-read tools with no client-selectable root/state."""
    def selected():
        chosen = workflow.selected_root(root)
        return chosen, private_path(state, chosen)
    root, state = recall.bounded_cli(selected, command='show')
    FastMCP, CallToolResult, TextContent, ToolAnnotations, Field, Icon = _sdk()

    def result(data, *, error=False):
        text = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        return CallToolResult(content=[TextContent(type='text', text=text)], isError=error)

    def failure(code, message, max_bytes):
        response = result({'ok': False, 'code': code, 'message': message}, error=True)
        if serialized_size(response) > max_bytes:
            # Error details are never evidence; use a fixed bounded error rather
            # than echoing a long path, caller argument or partial source text.
            response = result({'ok': False, 'code': 'memory_mcp_budget',
                               'message': 'Complete result exceeds max_bytes.'}, error=True)
        return response

    def complete(data, max_bytes):
        response = result({'ok': True, 'data': data})
        if serialized_size(response) > max_bytes:
            return failure('memory_mcp_budget',
                           'Complete MCP result exceeds max_bytes; request fewer lines or a larger budget.',
                           max_bytes)
        return response

    async def execute(operation, max_bytes):
        try:
            return complete(await asyncio.to_thread(operation), max_bytes)
        except ProductError as error:
            return failure(error.code, str(error), max_bytes)
        except Exception:
            return failure('memory_mcp_operation',
                           'Operation could not complete safely; no source excerpt was returned.', max_bytes)

    class BoundedFastMCP(FastMCP):
        """Bound SDK validation errors too, before they can echo large inputs."""
        async def list_tools(self):
            tools = await super().list_tools()
            for tool in tools:
                tool.inputSchema['additionalProperties'] = False
            return tools

        async def call_tool(self, name, arguments):
            if not isinstance(name, str) or not isinstance(arguments, dict):
                return failure('memory_mcp_arguments', 'Use a tool name and an argument object.', 512)
            cap = arguments.get('max_bytes', DEFAULT_BYTES.get(name, 2048))
            cap = cap if type(cap) is int and 512 <= cap <= 65536 else 512
            if name not in ALLOWED or set(arguments) - ALLOWED[name]:
                return failure('memory_mcp_arguments', 'Unknown tool or arguments; inspect the tool schema.', cap)
            try:
                response = await super().call_tool(name, arguments)
            except Exception:
                return failure('memory_mcp_arguments', 'Invalid arguments; inspect the tool schema.', cap)
            if not isinstance(response, CallToolResult) or serialized_size(response) > cap:
                return failure('memory_mcp_budget', 'Complete MCP result exceeds max_bytes.', cap)
            return response

    # Initialization metadata only: public release-tag URLs avoid embedding
    # image bytes or repeating artwork metadata in every tool result/schema.
    icons = [Icon(src=PUBLIC_ICON_BASE + filename, mimeType='image/png',
                  sizes=['256x256'], theme=theme)
             for theme, filename in [('light', 'isolinear-memory-256.png'),
                                     ('dark', 'isolinear-memory-dark-256.png')]]
    server = BoundedFastMCP('isolinear_memory_mcp', log_level='ERROR', icons=icons,
                            website_url='https://github.com/Kian-hdr/isolinear-memory')
    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                           idempotentHint=True, openWorldHint=False)
    Bytes = Annotated[int, Field(ge=512, le=65536, strict=True)]
    PathName = Annotated[str, Field(min_length=1, max_length=2048, strict=True)]
    Known = Annotated[list[Annotated[str, Field(pattern=r'^[0-9a-f]{32}$', strict=True)]],
                      Field(max_length=32)]

    @server.tool(name='isolinear_search', annotations=read, structured_output=False)
    async def search(query: Annotated[str, Field(min_length=1, max_length=1024, strict=True)],
                     strategy: Literal['exact', 'hybrid'] = 'exact',
                     max_hits: Annotated[int, Field(ge=1, le=5, strict=True)] = 5,
                     max_bytes: Bytes = 2048, known_evidence: Known | None = None) -> CallToolResult:
        """Search this fixed project. Omit receipts normally; [] requests IDs for retained evidence."""
        return await execute(lambda: recall.recall(
            root, state, query, strategy=strategy, max_hits=max_hits, max_bytes=max_bytes,
            with_receipts=known_evidence is not None, known_evidence=known_evidence or ()), max_bytes)

    @server.tool(name='isolinear_fetch', annotations=read, structured_output=False)
    async def fetch(path: PathName,
                    sha256: Annotated[str, Field(pattern=r'^(?:[0-9a-f]{24}|[0-9a-f]{64})$', strict=True)],
                    start: Annotated[int, Field(ge=1, strict=True)],
                    end: Annotated[int, Field(ge=1, strict=True)],
                    max_bytes: Bytes = 8192) -> CallToolResult:
        """Expand 1–80 exact source lines only while the supplied source hash matches."""
        return await execute(lambda: recall.show(root, path, sha256, start, end,
                                                max_bytes=max_bytes), max_bytes)

    @server.tool(name='isolinear_context', annotations=read, structured_output=False)
    async def context(path: PathName,
                      heading: Annotated[str, Field(min_length=1, max_length=160, strict=True)] | None = None,
                      max_bytes: Bytes = 8192, known_evidence: Known | None = None) -> CallToolResult:
        """Read complete instructions/index/selected section, or fail without partial context. Reset receipts after context loss."""
        return await execute(lambda: context_packet.context(
            root, path, heading, max_bytes=max_bytes,
            with_receipts=known_evidence is not None, known_evidence=known_evidence or ()), max_bytes)

    return server


def serve(root: Path, state: Path):
    """Serve the fixed project through official SDK stdio only."""
    create_server(root, state).run(transport='stdio')
