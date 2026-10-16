# Optional local MCP adapter and remote-client route

Isolinear 0.7.0 can expose its existing selected-folder reader through three
read-only MCP tools. This adds a protocol adapter, not another memory store,
model or retrieval engine. Ordinary native/CLI operation remains standard-library
only. Source notes/history are not changed by the adapter; the existing private
search index can be rebuilt locally.

## Local launch

Use a private Python 3.11+ environment and the release's optional requirement:

```sh
python3 -m venv /PRIVATE/isolinear-mcp
/PRIVATE/isolinear-mcp/bin/python -m pip install -r requirements-mcp.txt
/PRIVATE/isolinear-mcp/bin/python /PRIVATE/isolinear-memory-0.7.0.pyz memory-mcp /SELECTED/PROJECT --state-dir /PRIVATE/STATE
```

The SDK is deliberately pinned to `mcp==1.30.0`, its supported 1.x maintenance
line, using the tested FastMCP API. SDK 2.x is a different API and is not silently
accepted. See the [official tagged SDK documentation](https://github.com/modelcontextprotocol/python-sdk/tree/v1.30.0).
Install the optional requirements in the interpreter used to launch the server,
not into system Python. The runtime alone does not install dependencies.

Configure a compatible local MCP client with this launch contract:

```json
{
  "command": "/PRIVATE/isolinear-mcp/bin/python",
  "args": ["/PRIVATE/isolinear-memory-0.7.0.pyz", "memory-mcp", "/SELECTED/PROJECT", "--state-dir", "/PRIVATE/STATE"]
}
```

This is a server process configuration fragment, not an assertion that every
host uses the same surrounding configuration schema. Preserve unrelated client
configuration and enable only the intended project. Official SDK interoperability
is tested separately from actual Codex/Claude/OpenCode/other client acceptance.

## Tools and output

- `isolinear_search`: exact or hybrid retrieval, explicit result/byte bounds.
- `isolinear_fetch`: exact 1–80-line source expansion against a matching hash.
- `isolinear_context`: complete authored instructions/index/selected section,
  with all-or-nothing delivery and optional retained-evidence receipts.

The server's root and private state are fixed at startup. Caller arguments cannot
select another project, invoke a shell, start a model, write notes or inspect
cloud applications. Existing profile/private/nested-project boundaries apply.
Read-only annotations describe source operations; private index writes remain
internal derived-state maintenance.

Each successful result contains one text JSON representation of the evidence,
without a duplicate full structuredContent object. `max_bytes` bounds the complete
serialized MCP CallToolResult, including nested JSON escaping; JSON-RPC request
IDs/framing are outside this tool-result cap. An oversized fetch/context returns
a bounded error with no partial source. Search can also refuse an insufficient
envelope. Byte caps are not model-independent token caps.

On search/context, omit `known_evidence` for ordinary output; send `[]` to request
receipts, then only receipts whose full text is still available to that caller.
Reset/compaction/uncertain retention means discard receipts and request full
evidence. A hash does not establish agent understanding. See
[evidence receipts](EVIDENCE-RECEIPTS.md).

## Phone/iPad and remote agents

Stdio is a local process transport. It does not create an internet endpoint or
remain reachable while its host is asleep. A phone without a local mirror uses
an authenticated remote MCP service or an existing Drive/OneDrive connector.
Do not expose this stdio adapter through an unauthenticated HTTP wrapper.

The intended remote path reuses a provider-backed, private rebuildable projection
with per-vault grants, current source revisions/hashes, coverage, revocation and
bounded fetch. The existing private pilot already supplies authenticated
Streamable HTTP; its private bindings are not part of this public release.
Desktop manifest profiles and remote provider roots need explicit parity checks
before real-corpus admission. A synthetic endpoint/SDK test does not establish
real-memory availability, physical iPhone/iPad acceptance or all-client support.

Routine desktop saves use local readback and leave cloud uploads alone. Remote
source access when no mirror exists, explicit delivery diagnosis and verification
of an authorized remote write are separate operations. No workflow should open
Drive/OneDrive apps or poll their queues after ordinary local note work.

## Update or remove

Disable/remove the selected client's server configuration to stop the adapter.
No source migration, history reset, embedding rebuild, provider change or model
restart is needed. Keep a previous verified runtime for rollback. Test a different
SDK version explicitly before updating its pin; no compatibility claim follows
from a newer version number alone.
