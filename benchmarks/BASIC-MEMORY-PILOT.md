# Basic Memory disposable-copy pilot, 29-Sep-2026

The local open-source Basic Memory 0.23.2 CLI was run against **two synthetic
Markdown files in a disposable copy**, with `BASIC_MEMORY_CONFIG_DIR` set to a
separate temporary private directory, semantic search and auto-update disabled.
The inspected repository revision was `8a8dc7fb34f5d1bd24618b3bff5e8ee655528713`.
Basic Memory is AGPL-3.0; no source code or asset was imported into Shared Memory.

`project add` succeeded. Search initially returned zero results; an explicit
`reindex --full --search --project synthetic` reported two observed/indexed
files. A subsequent exact query found the correct path and answer. The search
CLI returned 640 JSON bytes and took about 2.7 seconds in one warm-cache run.
These numbers are illustrative, with CLI startup included and no model usage.

**The reindex modified both source files:** it added YAML frontmatter (`title`,
`type`, `permalink`) and changed their trailing newline. File count stayed at
two, which would have hidden this mutation without byte comparison. Basic
Memory must therefore remain on disposable copies during comparison; it is not
a read-only sidecar for an authoritative vault under this tested configuration.

Shared Memory v0.5's synthetic paired run currently favors direct targeted
`rg` for exact queries and the small exploration cases in `recall_pair.py`.
Both routes passed 13/13 source/answer checks, while v0.5's source hashes and
block excerpts used more retrieval-output bytes and reference tokens. This
pilot does not establish total-task token savings or authorize vault cutover.
