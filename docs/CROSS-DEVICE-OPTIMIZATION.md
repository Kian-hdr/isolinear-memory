# Cross-device optimization goal and architecture

Decision and engineering goal, October 16, 2026. Sources and selective adaptations:
[research](RESEARCH-CROSS-DEVICE.md), [Scion map](READINESS.md),
[progressive context](PROGRESSIVE-CONTEXT.md). User clarified that “SciAI” meant
Anthropic Scion. This document separates intended design from tested deployment.

## Goal and constraints

Reduce the total cost of correctly finding, preserving and using memory across
local desktops, remote agents, phones and tablets. Preserve exact small facts,
negations, stop conditions, corrections, contradictory evidence and authorization
boundaries. Original Markdown, attachments and causal history remain authority.

The active implementation goal is to add a shared bounded read contract, enforce
local-mirror-first routine work, improve the existing remote connector rather than
duplicate it, update the skills and publish only reviewed public-safe changes.
No new paid service or model is required. Existing private sidecar/import and
content-preservation holds remain; this is not authority to upload every vault.

## How much can improve

Count complete task cost as instructions/history, memory discovery and evidence,
reasoning/answers, writes/indexing and retries. Backend caching does not itself
remove model tokens: only data and tool schemas actually sent to the model fill
its context. Prompt-cache discounts also do not enlarge the context window.
An MCP server cannot remove system instructions, tool schemas or earlier messages
already supplied by its host. Backend caches and smaller future responses cannot
evict that existing context. Long-running work still needs an authored durable
handoff plus the host's supported compaction/reset behavior; fresh contexts reload
instructions and exact needed evidence, rather than replaying the full chat.

If retrieval is a fraction `f` of task tokens and delivery shrinks by `r`, the
best possible total reduction before new overhead is `f * r`. For example, a
40% reduction to a 30% retrieval share could save at most 12% overall. This is a
scenario calculation, not a measured workload forecast. Current evidence is only
bounded synthetic/reference-token work: a prior long-repeat example saved 25%,
and a bootstrap fixture saved 12% versus three source-linked calls. Careful native
reads can be cheaper. Do not extrapolate vendor benchmarks or bytes into billing.

Predeclared acceptance targets for this iteration:

- Zero routine cloud-app/upload-queue checks in generated instructions and skill
  trajectories; native local readback is sufficient for normal local saves.
- Every successful bounded MCP result fits its complete serialized tool-result
  budget, including nested JSON escaping. Fetch/context fail whole if they do not
  fit. No duplicated full text in both content and structuredContent.
- All required source facts, qualifiers and stop conditions survive the declared
  same-task fixtures. Stale, missing, revoked and out-of-scope evidence never
  becomes an apparently current answer.
- Aim for at least 20% lower memory I/O reference tokens on the remote compact
  delivery slice where baseline metadata dominates. Treat this as a testable
  engineering target, not a promised total-task improvement or a gate to force
  smaller unsafe excerpts. Record a miss honestly.
- Preserve efficient native reads and optional retrieval defaults. No mandatory
  summarizer, large model, embeddings, remote service, new authoritative store or
  universal client-compatibility claim.

## One authority, separate access paths

| Situation | Access path | Completion evidence |
| --- | --- | --- |
| Desktop has a local mirror | Native files, CLI or fixed-project local MCP | Local file/hash readback; background upload state irrelevant |
| Remote agent has an authorized mounted mirror | Same local reader in that environment | Same selected-scope checks; no assumption of another device's freshness |
| Phone/tablet has no local mirror | Authenticated remote MCP over authorized provider-backed projection | Source revision/hash, scope and coverage; actual client acceptance separate |
| No Isolinear remote service connected | Existing Drive/OneDrive MCP search and bounded source fetch | Exact cited source where exposed; no pretend local path/hash equivalence |

The phone does not need a full vault on device. An always-reachable authenticated
service can maintain a private rebuildable index over the authorized Drive or
OneDrive source and return only relevant evidence. Incremental provider change
feeds belong to that service, outside the agent's prompt. This is source access
and freshness maintenance, not checking whether a desktop app finished uploading.

An existing private remote connector already implements Streamable HTTP, owner
OAuth, isolated vault caches and revision checks. Improve its bounded delivery
and selected-vault coverage; do not create another backend. The public local MCP
adapter reuses the file engine and is stdio-only. It is not a phone endpoint or an
internet service. No UI is necessary for basic memory tools. A plugin packages
the skill/connection; it does not replace the memory engine or grant source access.

## Context layers and source fidelity

1. Active working context: the explicit task, authored handoff, constraints, owner,
   open work and source locators. Load complete authored bootstrap sections only
   when needed; never silently trim a stop condition.
2. Query evidence: bounded lexical/hybrid source passages, with exact locators and
   current hashes. Expand details on demand instead of loading all related notes.
3. Durable authority: full Markdown, attachments and causal history outside model
   context. A private index or semantic sidecar is derived and rebuildable.

Hindsight's separation of search effort from returned-evidence budget is useful.
Its extraction/reflection are optional derived aids, not a reason to replace
source passages with inferred claims. Scion's sparse content-addressed retrieval
and derived caches are useful patterns; its always-online source-control storage
format and distributed fleet are unnecessary here. No new query-plan cache is
justified until an actual bottleneck remains after existing indexed retrieval.

## Shared read contract and delivery bounds

Tools expose source search, exact expansion and optional authored bootstrap. They
receive an explicit budget and retain incomplete-coverage diagnostics. A server
performs ranking and source checks; the model gets evidence, not graph dumps,
every ingestion record or complete background logs. Search depth and returned
bytes are separate controls. Keep one representation of the actual evidence.

Local caller receipts bind the physical root and exact source passage and thus
intentionally miss after moving roots/devices. A future portable remote handle
must bind stable project/vault identity, authenticated grant scope, source revision
and full hash, exact span and format version. It must be reauthorized/revalidated
on fetch. A server cache is not proof that a new chat/phone still holds evidence;
discard caller receipts after reset or uncertain compaction retention.

A remote mirror of desktop scope is not automatic. The desktop respects manifest
profiles and declared project folders. The existing remote pilot's provider-root
scope needs explicit parity certification before real-corpus admission. Do not
equate transport success, a matching file name or a synthetic namespace with
equivalent permissions, corpus coverage or physical-device acceptance.

## Phone, iPad and client acceptance

Reuse the existing authenticated remote connector with selected provider grants.
Verify tool availability in each intended host and test first read, repeat,
context reset, source edit, missing evidence, revoked grant and write conflict.
Clients differ in tool discovery, skill loading, MCP support and context control.
“MCP-compatible” is a protocol statement, not proof every app/device works.

Real provider ingestion needs its existing preservation/content-eligibility and
scope checks. Keep synthetic data until those gates are met. Hosted writes need
expected revisions, idempotent retry and immutable history; provider-confirmed
write/readback is appropriate for that explicit operation. Routine local notes
must not trigger the same remote verification workflow.

No Mac-only stdio server keeps working while the Mac is asleep. The remote
connector must run on a reachable host with durable credentials outside notes,
authenticated transport, per-vault authorization, revocation handling and no
cross-scope cache leakage. Actual iPhone/iPad behavior remains an acceptance item
unless observed in those clients; tests on a Mac do not establish it.

## This iteration's observed results

The private remote connector was changed and locally verified with 68 tests,
type checking and a build: caller-selected result/output limits, compact delivery,
selected-vault-only coverage and complete escaped tool-result bounds. A synthetic
same-evidence case used 333 reference tokens before versus 317 with compact
output including added arguments, a 4.8% reduction. The 20% engineering target
was not met on that measured case; a broader median/real-task gain is unproven.
The change is retained for bounded delivery and scope correctness, not marketed
as a large token saving. No evidence text was removed to manufacture the result.
This private patch was not deployed by these tests.

The currently connected remote memory service was separately queried for this
architecture review and still reports synthetic fixtures, no real-vault import
and no live-source recheck. It is distinct from the private connector's tested
source checkout. No public release should imply those systems are identical or
that native phone/tablet access to real notes has passed.

The new optional local MCP adapter passed 12 official-SDK tests including an
actual stdio client, single-representation output, fixed scope, stale source
rejection, atomic context/reset and complete serialized budget tests. The public
release carries that adapter, not private cloud account bindings. Remaining
release/platform results belong in VALIDATION.md.

## Evaluation and release

Use paired, public-safe synthetic cases before private-corpus evaluation. Count
tool input/output, metadata, first-use/setup overhead, retries and reference
tokens; keep model totals and billing unavailable when not measured. Check rare
facts, corrections, negations, conflicting sources and stop conditions directly.
Report cold/warm and first/repeat/reset separately. Do not use shorter output as
proof of intelligence, source completeness or answer accuracy.

Publish the reviewed core, tests, skill and sanitized documentation from an
isolated clean source tree. Exclude private connector bindings, account details,
runtime caches and unrelated unfinished sidecar work. Build release assets from
the exact clean committed revision, run relevant CI and retain rollback runtimes.
Record actual results and unresolved client/provider gates in VALIDATION.md and
the canonical project handoff. Future defaults require measured task-level gain.
