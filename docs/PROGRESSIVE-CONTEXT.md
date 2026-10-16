# Progressive authored context packets

Optional feature introduced in 0.7.0. See the
[source-to-target map](READINESS.md#progressive-context-selective-assimilation-development-candidate-2026-10-16).

## What this adds

`context-packet` assembles complete root `AGENTS.md`, complete root `INDEX.md`
and one explicitly selected canonical Markdown source or section in one response.
It reads original authored text, returns exact line locators and current full
source hashes, and creates no summaries, sidecars, database, model or service.

```sh
isolinear-memory context-packet . --path Wiki/Handoff.md --heading "Current handoff" --max-bytes 8192
```

This supports a small active working context with expandable original evidence.
Keep the goal, decisions, ownership, open work, stop/permission conditions and
source links in the existing authored handoff. The tool does not infer which
facts are important, authenticate authorship, decide whether a claim is true or
guarantee that a selected section contains every relevant constraint elsewhere.
Contradictory assertions in that section remain verbatim.

The command is distinct from historical coordinator `context`, whose interface
and authenticated workflow remain unchanged.

## Complete sections or no packet

All three sources are mandatory. If any source is unavailable, unsafe, missing,
empty or out of scope, no partial excerpts are returned. If the complete packet
does not fit `--max-bytes`, the command fails without trimming or dropping a
source. Increase the budget within its 65,536-byte maximum, or update the existing
canonical handoff with an accurately authored concise section. Do not shorten
it by dropping a stop condition or qualifier just to force a pass.

`--heading` is an exact, unique ATX Markdown heading. Selection includes the
heading and all nested subsections through the next equal-or-higher-level
heading. Duplicate/missing headings fail instead of guessing. Frontmatter,
fenced code, HTML comments and raw pre/script/style/textarea blocks do not create
section boundaries. Other raw HTML blocks are rejected for section selection.
Setext headings are unsupported; choose the complete source when necessary.
Original source bytes are not rewritten by this parsing.

Results are per-source verified reads, not a transactional multi-file snapshot.
`unsearched` explicitly reports unexpanded links, other sections and excluded
profile folders. No recursive discovery, link following or wider-vault access
occurs. Exact expansion uses existing `show` with the returned path/hash/lines;
its existing 80-line-per-request limit remains.

## First use, repeats and reset

- First read or after context loss: request the complete authored packet.
- Repeated reads can opt into `--with-receipts` and supply up to 32 existing
  `--known-evidence` receipts for passages still actually retained by this caller.
  All sources are read/checked before exact already-held text is omitted.
- Receipt output is also all-or-nothing: if complete required references and
  text cannot fit, the tool fails rather than omitting a source.
- After reset/compaction/uncertain retention, discard receipts and load full
  authored text again. The tool cannot detect host context loss itself.

No prompt injection hook, automatic consolidation, canonical TTL eviction,
remote memory service or generated belief store is introduced. Native targeted
reads, exact/hybrid recall and existing receipts remain valid alternatives.

## Selection and non-adoption

OpenViking's documented L0/L1 layers are generated directory sidecars. This is
an independently authored navigation/working-context adaptation using existing
Markdown, not a copy of that implementation or its vector search. Mnemosyne's
working-versus-episodic distinction informs the separation of active packet and
durable originals. Its additional semantic query cache is not adopted because
no measured gap justifies another mutable store over Isolinear's existing index
and source checks. Memori's attribution concepts reinforce the distinction
between an exact source and asserted capture authorship; existing history already
provides that provenance, so no extra attribution database is added.

The selected adaptation uses Isolinear's existing runtime. Existing Hindsight integration and holds remain. ByteRover-style authored tree
navigation overlaps INDEX/handoff conventions. Holographic/HRR machinery,
Mem0-style automatic extraction, Honcho-style broad user inference and additional
Supermemory/RetainDB services are not adopted for this bounded context task.
This records selection decisions, not a claim to have audited those entire products.

No upstream code/assets are copied and no new runtime dependency is installed.
Pinned provenance and reuse boundaries are recorded in READINESS.md.

## Verification and efficiency limits

Acceptance covers complete nested sections including a final stop condition,
fake headings inside code/comments, ambiguous/missing headings, required-source
failure, private/nested/link denial, Unicode/CRLF hashes, deadlines, output
budgets, no source/cache mutation, changed sources, repeats and reset behavior.
Tests are synthetic source-fidelity checks, not proof of agent understanding.

The benefit must be measured against the same selected evidence and task facts.
Three targeted native reads can already be efficient; do not claim a universal
token improvement by comparing only against whole-vault or whole-history loads.
One complete packet can reduce discovery/read round trips, while JSON hashes,
provenance and receipts add token overhead. First use, repeated use and reset
must be counted separately, including tool input. Reference tokenizer counts
are not actual hosted-model totals or billed credits. Detailed results belong
in VALIDATION.md. No broad default change follows from fixture measurements.

## Recorded bounded comparison

[Reproducible fixture](../benchmarks/context_packet_pair.py) and
[dated results](../benchmarks/context_packet_pair_result_20261016.json) compare
identical required facts, including a rare identifier, negation, an earlier
contradictory approval claim and its correction, ownership, pending work and a
final stop condition. All arms preserved those facts after first read, repeat,
reset and a source edit. No answering model was run.

| Stage | Three source-linked show calls | Three existing receipt queries | One authored packet |
| --- | ---: | ---: | ---: |
| First | 606 | 761 | 533 |
| Repeat with retained receipts | 606 | 749 | 505 |
| Reset, receipts discarded | 606 | 761 | 533 |
| Source edit | 613 | 811 | 581 |

Values are `o200k_base` reference tokens for logical CLI input plus actual JSON
stdout, including receipt input and all source metadata. The show baseline is
given correct hashes/ranges without discovery cost. Routing is prewarmed; index
preparation, harness/host transport envelopes and complete conversation costs
are excluded. These exclusions are explicit limits, not billing estimates.

The packet saves 12.0% versus source-linked show on the first/reset stage and
16.7% on a repeat in this fixture, with three calls reduced to one. Existing
receipt queries remain better suited to focused evidence questions than using
a whole packet for everything. Exact native targeted source content is only
84 reference tokens before native tool inputs/wrappers, so the result does not
show a universal advantage over careful native reads. Defaults remain unchanged.

## Update and removal

The runtime is `context_packet.py`, with narrow CLI registration and atomic
receipt-budget support. Omitting the command restores the existing workflow.
Removing that module and its CLI registration removes the feature; keep the
historical coordinator `context` and ordinary recall/show behavior intact.
No source, index schema, project identity, capture job or provider migration is
needed. Keep all authored originals and previous runtime versions for recovery.
