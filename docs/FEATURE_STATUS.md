# Feature status and component boundaries

Repository review: October 28, 2026. The latest packaged public runtime is
[0.7.1](https://github.com/Kian-hdr/isolinear-memory/releases/tag/v0.7.1).
Documentation on the default branch can be newer than that immutable package.

## Public runtime

| Capability | Public implementation and evidence route |
| --- | --- |
| Direct and offline Markdown editing, causal history, conflict recovery | `product/shared_workspace/folder*.py`; [folder contract](../product/FOLDER-CONTRACT.md) |
| Team, personal and custom project profiles | `profile_scope.py`; [setup](INSTALL.md) |
| Exact and optional hybrid retrieval with explicit-link ranking | `recall.py`, `hybrid_recall.py`; [retrieval design](RESEARCH-CROSS-DEVICE.md) |
| Hash-checked, bounded exact source expansion | `recall.py`; `recall` and `show` CLI help |
| Complete authored context packets | `context_packet.py`; [context packets](PROGRESSIVE-CONTEXT.md) |
| Context-local evidence receipts with source revalidation | `evidence_receipts.py`; [receipt contract](EVIDENCE-RECEIPTS.md) |
| Optional fixed-project, read-only local stdio MCP | `memory_mcp.py`; [MCP setup](MCP.md) |
| macOS automatic history capture; manual capture on other platforms | [capture setup](AUTOMATIC-CAPTURE.md) |
| Verified runtime, source kit, setup skills and icon packages | [installation](INSTALL.md); external release `SHA256SUMS` |

The local MCP exposes search, exact fetch and authored context. It does not deploy
an HTTP endpoint, provision a hosted database or grant provider access. Follow
the exact revision's CI and [validation record](../VALIDATION.md) for test results;
a supported platform is not proof of every physical client or provider workflow.

## Separate hosted component

The owner-private hosted pilot has authenticated remote search/fetch/status and a
compact provider directory with provider fallback. The agent follows the directory
using its separately authorized provider connector. The public Python package does
not include this deployment or its account bindings. [MCP guidance](MCP.md#compact-provider-directory-and-fallback)
describes the portable behavior without publishing private configuration.

The reviewed hosted pilot remains synthetic-index-only. Its directory route can
locate authorized provider sources without importing those originals into the
index. A working directory or synthetic search does not establish eligible
real-corpus indexing, current source freshness, revocation acceptance, physical
phone/tablet behavior or measured latency/token savings.

## Experiments and remaining acceptance

The optional Hindsight extraction/reflection sidecar, preservation/import tooling
and live source bridge remain separate experimental work. Their presence in a
development checkout does not make them released public-core features. Preserve
original Markdown/history and complete source-preservation and content-eligibility
gates before admitting a real corpus. No universal client or host-icon acceptance
follows from a source release.

Keep these boundaries explicit when comparing a deployed connector, an installed
runtime, a development checkout and the latest public repository. Check the
version, source revision, dirty state and package hashes independently.
