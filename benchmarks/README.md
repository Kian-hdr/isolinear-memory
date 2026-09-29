# Retrieval and complete-task token benchmarks

`recall_pair.py` generates synthetic Markdown under a temporary directory and
compares the existing targeted `rg` workflow with the packaged `recall` CLI.
Its answer key checks rare details, changed facts, explicit Raw/Output scope,
missing facts, post-edit freshness, and post-deletion freshness. It reports
return bytes, optional `tiktoken` `o200k_base` reference counts, elapsed time,
and index size. It does **not** measure model usage or cost.

```bash
python3 scripts/build_product.py --output /tmp/shared-memory-benchmark.pyz
python3 benchmarks/recall_pair.py --package /tmp/shared-memory-benchmark.pyz
```

Run `paired_task_cost.py` on a **private**, manually recorded JSONL ledger to
apply the vault-by-vault acceptance gate. Each row has `vault`, `case`, `method`
(`baseline` or `v0.5`), `provider_model`, `frozen_source_sha256`, `accepted`,
`critical_regression`, `client_total_tokens`, and optional `startup`, `write`, `index`, `retrieval`,
`answer`, `retry`, and `other` objects. Each component records
client-reported nonnegative integer `uncached_input`, `cached_input`,
`cache_write`, `output`, and separately reported `reasoning` tokens. Use zero
when no model call occurred. The gate uses the client's authoritative total,
including any unallocated tokens; component counts are diagnostic and may not
exceed it. Count all retries, write/index calls, startup instructions and base
client overhead; never infer model tokens from returned bytes. Compare only
the same provider/model and frozen source. The gate
requires at least one mutually accepted pair, no lost accepted cases or
critical regressions, complete pairs, and fewer total tokens for v0.5.

Do not put real vault excerpts, absolute paths, prompts, or private ledgers in
this public repository. For real-vault cases, run offline search or an already
authorized provider, and retain evidence under private local state. The
synthetic harness alone cannot authorize a vault cutover.

See [BASIC-MEMORY-PILOT.md](BASIC-MEMORY-PILOT.md) for the disposable-copy
comparison and its observed Markdown mutation.
See [SYNTHETIC-RESULTS.md](SYNTHETIC-RESULTS.md) for the candidate paired run.
