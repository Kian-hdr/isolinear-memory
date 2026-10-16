# Cross-device memory efficiency: source-led research

Checked October 17, 2026. This is a research and adaptation record, not a claim
that phone/iPad clients, provider accounts or a deployed real-data bridge have
passed acceptance. No private corpus was uploaded, no engine was installed and
no external service or model was started for this research.

## Decision

Keep one source-preserving memory contract over separate storage adapters.
Optimize the evidence that crosses the tool/model boundary before adding another
memory engine. Local mirrors should support normal work without provider-app or
upload-queue inspection. A phone without that mirror needs an authorized remote
read/write path, not an imitation of a desktop filesystem.

The strongest additional ideas are independently adjustable search effort and
delivered-context budgets, compact source handles with exact expansion, explicit
provenance for derived observations, and permission/freshness-aware remote
retrieval. These can fit Isolinear's existing authored context packet, exact and
hybrid recall, full source hashes and optional retained-evidence receipts.

## Verified adoption decision, October 17, 2026

The relevant upstream heads still match the pins below. Version labels and
availability were checked against their first-party repository/PyPI records;
those observations do not certify a product's deployment maturity or establish
an Isolinear performance gain. The distinction is **independent design adoption**
versus **an installed upstream dependency**.

| Source | Evidence and license scope | Current decision |
| --- | --- | --- |
| Anthropic Scion | [Official architecture article](https://www.anthropic.com/engineering/redesigning-source-control), October 13, updated October 15; describes an internal system, not an installable public offering | Independently adapt selective delivery, source hashes, derived indexes and incremental evidence reuse. No Scion code, service or protocol dependency. |
| OpenScion | [`00e92ab9c2a9985f39a64636b4b6c5c4bb583916`](https://github.com/tinyhumansai/openscion/tree/00e92ab9c2a9985f39a64636b4b6c5c4bb583916), GPL-3.0; [server README](https://github.com/tinyhumansai/openscion/blob/00e92ab9c2a9985f39a64636b4b6c5c4bb583916/crates/openscion-server/README.md) still says restart starts empty; persistence and essential collaboration remain future work in its [roadmap](https://github.com/tinyhumansai/openscion/blob/00e92ab9c2a9985f39a64636b4b6c5c4bb583916/ROADMAP.md). No GitHub tags/releases at this check. | No dependency or migration. Its prototype is not a suitable durable source of truth and does not replace Git. |
| Hindsight | [`5331da2f4db369528bb122075341a7de9c3df6df`](https://github.com/vectorize-io/hindsight/tree/5331da2f4db369528bb122075341a7de9c3df6df), MIT; current latest GitHub release is v1.0.0 | Existing independent hybrid-retrieval ideas remain. Keep response/evidence budgeting and optional source expansion. The separate experimental sidecar targets v0.10.2; v1 availability is not a compatibility result or authorization to upgrade a held service. It is not a public-core dependency. |
| OpenViking | [`8d28ffcdbb646a2f8cc1d8176d37d3c0185bc596`](https://github.com/volcengine/OpenViking/tree/8d28ffcdbb646a2f8cc1d8176d37d3c0185bc596), AGPL-3.0; latest GitHub release v0.5.0 | Independently adapt overview-to-detail access into authored `context-packet` and exact expansion. Do not import its generated directory sidecars, vector stack or runtime. |
| Mnemosyne | [`87a86a28ac00ee5c9fe26dfa7c2117a96fce4e8f`](https://github.com/mnemosyne-oss/mnemosyne/tree/87a86a28ac00ee5c9fe26dfa7c2117a96fce4e8f), MIT; latest GitHub release v0.7.4 | Keep the small-active-context versus durable-originals distinction. Another fuzzy query cache, TTL policy or consolidation process has no demonstrated need here and remains deferred. |
| Memori | [`574b1ea3e876f100ef82c37817d603eb7e258e59`](https://github.com/MemoriLabs/Memori/tree/574b1ea3e876f100ef82c37817d603eb7e258e59); the actual pinned [LICENSE](https://github.com/MemoriLabs/Memori/blob/574b1ea3e876f100ef82c37817d603eb7e258e59/LICENSE) contains Apache-2.0 text, although GitHub's classifier returned NOASSERTION; latest GitHub release v3.3.6 | Preserve explicit source/observer/session distinctions using existing hashes and asserted causal-history provenance. No additional attribution store or backend SDK. The repository license does not establish hosted-service rights or availability. |
| TurboVec | [`c3b043b992290ff223b903046af7f6683768241c`](https://github.com/RyanCodrai/turbovec/tree/c3b043b992290ff223b903046af7f6683768241c), MIT; [PyPI v1.1.2](https://pypi.org/project/turbovec/1.1.2/) is available but package metadata still declares Alpha | Deferred optional semantic-index experiment only. It compresses backend embeddings, not the text in a model's context. No installation, dependency or benchmark was added by this verification. |

The optional public MCP adapter uses the official Python MCP SDK to expose the
existing read-only search, fetch and authored-context contract over stdio. It is
not a wrapper that installs the memory engines above. See [MCP](MCP.md),
[evidence receipts](EVIDENCE-RECEIPTS.md) and
[progressive context](PROGRESSIVE-CONTEXT.md) for implementation boundaries.

### Benefit over Git

Scion/OpenScion concern source-control scaling. Isolinear concerns source-linked
memory and evidence delivery. This review establishes no reason to replace the
product's Git repository or migrate vault history into another source-control
format. Selective retrieval can improve context assembly while Git continues to
provide the product's code history, diffs and review workflow. TurboVec is also
not a source-control alternative. Infrastructure throughput or vector-storage
benchmarks are not model-token savings.

### TurboVec experiment gate

The [Python metadata](https://github.com/RyanCodrai/turbovec/blob/c3b043b992290ff223b903046af7f6683768241c/turbovec-python/pyproject.toml)
requires Python >=3.9, NumPy and a native Rust extension. Published wheels were
present for macOS arm64, Linux arm64/x86_64 and Windows amd64 at this check.
Availability is not acceptance on this product's supported hosts. A native Python
extension is not a drop-in component of a TypeScript/Workers service.

First demonstrate a useful semantic-retrieval improvement over current
lexical/title/explicit-link retrieval. No vector-memory bottleneck has been
measured in this review. Only then compare a float embedding baseline with a
4-bit candidate using the same embeddings, corpus and allowed scope. Measure
real resident memory, latency, source recall and accepted-task evidence, not
only compressed file size or maintainer microbenchmarks.

If that gate justifies an experiment, use [IdMapIndex stable external IDs](https://github.com/RyanCodrai/turbovec/blob/c3b043b992290ff223b903046af7f6683768241c/turbovec/src/id_map.rs)
with collision-checked passage identity and fresh scope/time/authorization
allowlists. Its [API documentation](https://github.com/RyanCodrai/turbovec/blob/c3b043b992290ff223b903046af7f6683768241c/docs/api.md)
warns that positional masks become invalid after mutations, including equal-size
remove/add sequences. Empty/unknown authorization sets must fail closed, never
fall back to searching all vectors. Keep source/model-version fingerprints and
current-byte checks before text delivery. Exercise edits, deletion, restart,
revocation, rare literals, negations and correction pairs. Quantization is lossy;
a smaller index may leave final tool-context cost unchanged or worsen retrieval.
This future experiment is not a blocker for the current source-preserving work.

## Hindsight: useful mechanisms and important differences

Inspected source revision:
[`5331da2f4db369528bb122075341a7de9c3df6df`](https://github.com/vectorize-io/hindsight/tree/5331da2f4db369528bb122075341a7de9c3df6df).
Its LICENSE is MIT, copyright Vectorize AI. This record recommends independent
adaptations; it copies no Hindsight implementation.

| Mechanism | Primary evidence | Isolinear adaptation or limit |
| --- | --- | --- |
| Search depth is separate from response size | [Retrieval documentation](https://hindsight.vectorize.io/developer/retrieval) distinguishes `budget` candidate/search effort from `max_tokens` returned fact text | Offer a shallow/default search effort independently of a hard serialized response cap; escalate only on missing evidence. Smaller output alone must not be advertised as cheaper backend computation. |
| Original source expansion is optional | [Pinned recall API](https://github.com/vectorize-io/hindsight/blob/5331da2f4db369528bb122075341a7de9c3df6df/hindsight-docs/docs/developer/api/recall.mdx), and [chunks-independence tests](https://github.com/vectorize-io/hindsight/blob/5331da2f4db369528bb122075341a7de9c3df6df/hindsight-api-slim/tests/test_recall_chunks_independence.py) | Return a bounded evidence passage and locator first; fetch original surrounding text only when required. Do not attach both a passage and a duplicate full chunk by default. Source expansion remains available. |
| Synthesized observations can expose contributing facts | The pinned API defines `source_fact_ids`, a deduplicated `source_facts` map and separate source-fact truncation | If optional derived observations are used, distinguish them from originals and preserve unresolved provenance IDs. A generated claim is not a new authoritative fact. Resolve its evidence before consequential use. |
| Payload fields can dominate context | [Configuration](https://hindsight.vectorize.io/developer/configuration) and [pinned reflect-budget tests](https://github.com/vectorize-io/hindsight/blob/5331da2f4db369528bb122075341a7de9c3df6df/hindsight-api-slim/tests/test_reflect_tool_token_limits.py) expose observation budget and optional entity payload | Use explicit compact result projections, preserving locator, scope, freshness and completeness. Hindsight's statement that entities can exceed half a reflect payload is a vendor observation, not an Isolinear measurement. |
| Context budgets are not necessarily complete wire budgets | [Pinned fact selector](https://github.com/vectorize-io/hindsight/blob/5331da2f4db369528bb122075341a7de9c3df6df/hindsight-api-slim/hindsight_api/engine/fact_budget.py) and [its tests](https://github.com/vectorize-io/hindsight/blob/5331da2f4db369528bb122075341a7de9c3df6df/hindsight-api-slim/tests/test_fact_budget_selection.py) | Do not copy its over-budget floor. It may return one whole fact when none fits. The API's fact-text budget excludes metadata. Isolinear should retain complete serialized-envelope bounds and return explicit expansion/insufficient-budget state instead of silently exceeding them. |
| Reflection is a separate reasoning operation | [Reflect documentation](https://hindsight.vectorize.io/developer/reflect) describes an agent using recall/expansion to formulate an answer | Keep ordinary retrieval deterministic and read-only. Optional synthesis is a separately costed operation with source checks, not a routine prerequisite to every read or save. |
| Tokenizers themselves have allocation/cost choices | [Pinned token encoding module](https://github.com/vectorize-io/hindsight/blob/5331da2f4db369528bb122075341a7de9c3df6df/hindsight-api-slim/hindsight_api/engine/token_encoding.py) separates counting from truncation and notes configured vocabulary limits | Measure response tokens with an explicit reference tokenizer or the actual client vocabulary. Do not claim a model-independent exact token cap from byte counts or one reference vocabulary. A new tokenizer dependency is justified only by measured need. |

The useful principle is selective evidence access, not that Hindsight never puts
data in a model. Its recall returns memory text; its reflect step can gather
additional material and invoke an LLM. Retention/extraction, indexing and
consolidation also have costs. Moving those costs behind an API does not remove
them from total-system accounting.

## Anthropic Scion: selective delivery, not a replacement memory engine

Source: [Redesigning source control at Anthropic](https://www.anthropic.com/engineering/redesigning-source-control), published October 13 and updated October 15, 2026. The documented system uses server-side operations, sparse materialization, changesets, derived indexes and immutable content-addressed objects. Clients request the objects they need, and caches can reuse immutable objects. These are storage and computation patterns; the article does not establish agent-token savings for Isolinear.

| Documented pattern | Isolinear fit |
| --- | --- |
| Sparse client working copy | Existing bounded recall, exact `show` expansion and authored `context-packet`; remote clients receive selected evidence rather than a whole vault. |
| Changes plus derived structures | Existing causal history remains authority. A private incremental index/projection is rebuildable derived state, not another canonical corpus. |
| Content-addressed reusable objects | Existing source hashes and explicit passage receipts. Mutable source paths still require current-version and access checks; an old immutable object is not automatically current evidence. |
| Server-side operations | A remote Isolinear adapter can perform authorized index/ranking work and return bounded source handles, without moving a full index into the phone or the model. |

Keep local offline operation. Do not import Scion's always-online assumption, distributed storage fleet, merge protocol or a new source-control format. Another cache tier is justified only by measured repeated work. The previous selective adaptation is documented in [evidence receipts](EVIDENCE-RECEIPTS.md) and [progressive authored context](PROGRESSIVE-CONTEXT.md). Scion's internal infrastructure results are not a token-efficiency or cross-device acceptance result for this product.

## One contract, two source paths

### Local mirrors

Read and write the selected local mirror, preserve causal history, and verify
saved bytes locally. Routine note work should make zero calls to provider-app UI,
upload queues or remote-delivery probes. Leave transport to background clients.
A local save is sufficient evidence of a local save; do not turn unrequested
remote-delivery verification into a completion blocker.

This policy does not mean claiming an upload occurred. Explicit sync diagnosis,
an actual local read/access error, a requested remote delivery check or the
verification of an authorized remote write are different tasks.

### Phone, iPad and hosts without the mirror

Use an authorized provider connector directly for small occasional access, or a
remote Isolinear service when it adds useful bounded retrieval, exact expansion,
source revision handling and continuity across supported clients. A skill can
describe the workflow but cannot create network access, credentials or mobile
host support by itself.

MCP defines local subprocess stdio and independent-server Streamable HTTP
[transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).
Use authenticated remote transport for a server-backed client path. Actual
ChatGPT/mobile/plugin availability must be checked against current official
OpenAI documentation and the selected account/client; a working local MCP or a
successful HTTP test is not a phone acceptance test.

Prefer existing service/adapters over a second engine. The public reusable layer
should describe interfaces and sanitized fixtures, not contain private provider
bindings, real vault data or deployment credentials.

## Remote cache and evidence identity

There are three different caches, with different invalidation rules:

1. A server's private source/index projection can reduce provider work. Track
   provider revisions, selected-root membership, per-source permissions and
   incomplete coverage. Rebuild it from authorized sources; do not promote it to
   a second canonical memory tree.
2. A query-plan cache can retain candidate IDs, not silently reuse old prose.
   Its key must include project/vault, authenticated grant scope, query/options,
   index/schema version and source versions. Existing local indexes already
   provide much of this benefit, so another cache needs a measured gap.
3. A retained-context receipt belongs to the caller. It may suppress a repeated
   exact passage only when the caller still holds the passage and the service
   revalidates source and access. A server session, earlier fetch or successful
   index update does not prove retained model context after reset or compaction.

Current local receipts intentionally include the local absolute root. They
safely stop matching across device paths. A portable remote evidence handle
should instead bind stable project/vault identity, principal/grant scope, full
source version/hash, span and protocol format. It is a locator, not an access
token: authorization must be enforced again on search, fetch and expansion.

Provider change feeds can update this projection outside the question path:
[Google Drive changes](https://developers.google.com/workspace/drive/api/guides/manage-changes)
and [Microsoft Graph delta](https://learn.microsoft.com/en-us/graph/delta-query-overview)
provide incremental change tracking. This is backend source maintenance, not
inspection of desktop upload status. Cloud-visible source watermarks cannot prove
that a different device's unuploaded local edit is already available remotely.
Removal, access loss and deletion must remain distinguishable.

Remote OAuth/grant handling should follow the MCP [authorization specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization),
with selected-vault enforcement on the server. Tool annotations and source tags
are not permission checks. A previously authorized cache entry must not survive
revocation as readable current evidence. Remote writes need expected revisions,
idempotency and truthful commit/history receipts; ordinary local saves do not
need that network workflow.

## How much could be optimized?

No defensible universal percentage follows from these products' documentation.
First separate startup/instruction tokens, useful evidence, duplicate evidence,
tool schemas/metadata, answers/retries, backend compute, provider calls and latency.

If retrieval is fraction `f` of a task's total tokens and a change reduces that
retrieval component by fraction `r`, the total saving is at most `f × r` before
new overhead. For example, halving a component that is 20% of total usage saves
10% overall, not 50%. This is arithmetic illustration, not a forecast.

The clearest immediate target is zero routine upload checks in local mode.
Further targets should follow baseline traces: full wire-response budgets,
fewer unnecessary expansions, smaller schema/metadata overhead and fewer
question-path provider calls, without losing required evidence. Preserve
contradictions, source changes, rare details and stop/approval boundaries.

A candidate engineering target can be a material reduction in median retrieval
tool tokens on the same accepted tasks, with no source/permission failure and no
loss on the critical-case slice. Choose the numerical target after baseline
measurement; do not present a desired threshold as an achieved or likely gain.

## Required evaluation before broader defaults

Compare the current local workflow, current receipts/packet and candidate remote
contract on the same immutable permitted fixtures. Include first read, repeat,
reset, changed source, a stale index, missing/oversized evidence, contradiction,
rare identifier, denied vault and revoked access. Measure complete input/output
including tool definitions and wrappers where the client exposes them. Report
reference tokenizers separately from actual model totals and billing.

For mobile, separately prove real client discovery, authenticated tool invocation,
bounded cited search, exact expansion, changed-source behavior, denial and an
authorized write/readback if writes are in scope. Synthetic server tests can
qualify mechanics; they cannot establish iPhone/iPad usability or live-provider
correctness. No numerical vendor benchmark or copied architecture substitutes
for those checks.
