# Context-local evidence receipts

Optional feature introduced in 0.7.0. See the [Scion source-to-target map](READINESS.md#scion-selective-assimilation-development-candidate-2026-10-16).

## Purpose and contract

Use receipts to avoid sending an exact passage again when the caller still holds
its full text in the active context or an accessible host cache. Normal recall
still reads/validates current source bytes. This is selective delivery, not
source summarization, automatic conversation compaction or durable agent memory.

Defaults are unchanged. Opt in on exact or hybrid recall:

```sh
isolinear-memory recall . "launch constraints" --with-receipts --max-bytes 4096
```

Each returned hit includes `evidence_id` and `delivery: "full"` alongside its
normal exact excerpt, source hash and lines. On a later request, supply only
receipts for passages whose full text is still available to this caller:

```sh
isolinear-memory recall . "launch constraints" --known-evidence <32-hex-evidence-id> --max-bytes 4096
```

`--known-evidence` is repeatable, with at most 32 lowercase 32-hex receipts, and
implies receipt mode. An exact match returns `delivery: "unchanged"` and the
source reference without an `excerpt`. This positively confirms that the same
passage was retrieved and source-validated; it is distinct from no search hits.
Unknown valid receipts simply match nothing. Invalid/excess input is rejected.
The existing `show` command always permits full expansion against a matching
current source hash.

The 128-bit receipt locators bind version, normalized local absolute project root, relative path,
full source SHA-256, final start/end lines and exact excerpt bytes. A different
passage in an unchanged file does not match. Any source edit invalidates all old
receipts for that file. They are local-root-specific and not portable across
renamed roots/devices. Receipts are cache identifiers, not credentials or proof
of access, delivery, factual truth or agent understanding.

The delivery layer adds metadata after normal bounded search. If necessary, it
drops complete trailing hits with `truncated: true`; it never shortens a date-
qualified span or enlarges the retrieved candidate set. Source coverage and
unavailable/deadline information remain visible. A receipt does not make partial
search exhaustive. Ordinary `--max-bytes` limits still apply.

## Agent use

- Start each new chat/task/context cache without known receipts.
- Retain receipts only after the corresponding full excerpt actually arrives.
  Discard receipts for excerpts lost to compaction, reset or uncertain retention.
- Keep objective, current decisions, constraints, ownership, open work and source
  locators in the existing canonical handoff. Re-read that handoff after a reset;
  a bag of hashes cannot reconstruct missing context.
- Expand sources when exact qualifications or contradictions matter. This mode
  neither summarizes nor repairs incomplete original excerpts.
- Keep receipt lists small and context-local; do not write them into shared
  Markdown or create a second authoritative memory store.

The optional development Hindsight route is intentionally unsupported by receipt
mode pending separate boundary acceptance. Existing Hindsight changes are not
part of the clean local receipt package.

## Efficiency and evidence limits

The tradeoff is extra receipt metadata/input for fewer repeated excerpt bytes.
Short passages may cost more, and first delivery adds overhead. Use the mode for
repeated longer evidence, not as an unconditional default. It saves no initial
conversation tokens, cannot enlarge the context window or remove old messages,
and does not guarantee later recall by a model.

The packaged synthetic tests cover current-source revalidation, source edits,
different spans, root isolation, missing/excluded sources, reset behavior, text
formatting, malformed receipts, full output budgets and hybrid date qualification.
A paired warm-cache measurement used the same `fts5_cached` route, two calls per
arm, and counted both receipt responses plus added flag input, including first-
delivery overhead. The reference tokenizer was existing `tiktoken o200k_base`.

| Synthetic passage | Serialized byte reduction | Reference token reduction |
| --- | ---: | ---: |
| 767 characters | 23.4% | 3.8% |
| 2,559 characters | 39.2% | 25.0% |

For the longer fixture, ordinary responses totaled 6,026 bytes and 1,056 reference
tokens. Receipt responses plus their added flags totaled 3,663 bytes and 792
reference tokens in the measured run. Random-looking receipt text and local root
identity can slightly affect tokenization. These are fixture observations, not
predictions for a vault or model. Common prompts, previous chat history and
unrelated tool calls are excluded. No model-answer or billed usage was measured.

The first design used 256-bit locators and a smaller fixture showed 8.8% more
reference tokens over two calls despite fewer bytes. This justified 128-bit
locators and retaining opt-in use. A receipt is not a security signature; full
source hashes remain 256-bit. Even the revised design can cost more for short
passages or one-off reads. Existing context-window limits and host compaction
behavior are unchanged. Real task-level token savings and answer quality remain
unverified.

## Update or removal

No external dependency, provider/capture configuration, index schema or source
format changed. Stop using the two options to restore ordinary full delivery.
Runtime code is in `evidence_receipts.py` with narrow recall/CLI wiring. Preserve
the default path and source/scope tests when changing receipt identity or output.
Changing its version intentionally invalidates old receipts. Local package and
release evidence belong in [VALIDATION.md](../VALIDATION.md).
