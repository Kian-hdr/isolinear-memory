---
name: setup-isolinear-memory
description: Set up, update, or repair Isolinear Memory in a selected Markdown folder. Ordinary note work uses native file tools; load this skill for installation, capture, migration, or troubleshooting.
---

# Isolinear Memory setup

Set up or repair the selected Markdown folder, then leave routine work to native
file tools. Preserve `.shared-memory.json`, `.shared-memory/`, project identity,
original notes, attachments, history, private state and existing provider bindings.
`shared-memory` and `setup-shared-project-workspace` remain compatibility aliases.
A skill supplies instructions; it does not install a runtime or grant source access.

## Install or update

Read the existing selected AGENTS.md and INDEX.md before changing anything. For released
0.7 behavior, use the [installation guide](https://github.com/Kian-hdr/isolinear-memory/blob/v0.7.1/docs/INSTALL.md).
Verify the actual release asset against its external SHA256SUMS before executing
it. Verify any source/skill archives too, and use helper installers only from the
matching verified source kit. On macOS/Linux, install both command aliases against
the same verified runtime in private immutable tools storage; Windows uses Python
with the verified package directly. Retain the previous runtime for rollback. Check `version`
and only the needed command help, especially when an older runtime is installed.

## Choose the vault profile

- **Team:** shared company or organizational knowledge; default Raw/Wiki/Output,
  useful source provenance and shared ownership. Do not invent an approval queue.
- **Personal:** light single-owner Notes/Resources; no mandatory manual contributor
  tables, team change registers or verification templates. Preserve useful sources,
  dates, factual corrections, recovery and internal causal history.
- **Project:** domain-specific folders, usually shared. Derive them from the brief,
  lifecycle, sources/assets and deliverables; retain contributor attribution when
  shared. A sole-owner project can use lighter personal writing conventions.

For a new empty vault, design the smallest useful folder set, explain it in INDEX.md
and identify its canonical brief/current handoff. Run `setup PROJECT` with the
matching `--vault-type team`, `--vault-type personal` or `--vault-type project`.
Use repeatable `--project-folder RELATIVE_FOLDER` for a custom project structure.
The minimal project fallback is Knowledge/Planning/Deliverables.
Profiles exist since 0.6.0; do not assume older flags work. Preserve populated layouts
on join/resume. A profile does not authorize reorganization, remove logs/history or
change provider permissions. Keep code and large assets in their governed homes
and link them. See the [profile policy](https://github.com/Kian-hdr/isolinear-memory/blob/v0.7.1/skills/setup-shared-project-workspace/references/vault-profiles.md)
when designing a new structure or planning an explicit migration.

## Routine source-first work

For a known note or exact symbol, use a bounded native read/search first. For an
unknown location, use selected-project `recall`; choose optional `--strategy hybrid`
for related lexical/title/explicit-link discovery. Read coverage and source metadata;
relevance ranking is not factual confidence. Never widen the scope to another vault,
parent folder or undeclared corpus to obtain a hit.

Use complete relevant evidence already returned when its scope, qualifiers and
freshness satisfy the task. Do not fetch automatically after every search. Expand
heading-only, path-only, truncated or incomplete results with hash-checked `show` or
the host's source tool. A local exact hit can be just a heading; its hash does not
mean the body has been read. An indexed remote fetch is not proof of live freshness.

Save meaningful findings, decisions, corrections, deliverable links and next steps
in the existing canonical note, then read it back. Create a note/INDEX route only
when no suitable home exists. Preserve dates, sources, uncertainty and planned versus
completed status; leave a concise handoff, not a transcript. Each host agent performs
its authorized edit; no automatic conversation extraction is implied.

## Context and client routes

Released 0.7 adds optional `context-packet`: complete authored instructions/index
plus an explicit canonical file or unique handoff section, or no partial packet.
Never trim a stop condition to fit. Use native reads for focused evidence when
cheaper. Optional receipts reuse only exact passages still retained after source
revalidation; discard them after reset, compaction, a new chat or uncertain retention.
See [context packets](https://github.com/Kian-hdr/isolinear-memory/blob/v0.7.1/docs/PROGRESSIVE-CONTEXT.md)
and [receipts](https://github.com/Kian-hdr/isolinear-memory/blob/v0.7.1/docs/EVIDENCE-RECEIPTS.md)
only when those modes are needed.

Normal local-mirror work needs no MCP server. Optional 0.7 `memory-mcp` is a read-only,
fixed-project stdio adapter using the SDK environment in `requirements-mcp.txt`.
It does not itself provide a remote phone service. Without a local mirror, use an
authorized connector/service available on that host and retain scope, source ID,
revision and freshness limits. A saved skill transfers neither credentials nor
client support. Read [MCP setup](https://github.com/Kian-hdr/isolinear-memory/blob/v0.7.1/docs/MCP.md)
for that integration, not for ordinary notes.

## Local save and history capture

A native save plus local readback completes an ordinary save. Leave Drive/OneDrive
apps, menus, upload queues/status and background syncing alone: no polling, forced
sync, client restarts or sync-setting changes for routine notes/capture. Unchecked
upload state is not a completion blocker. Remote source reads and actual remote-write
receipts are appropriate without a local mirror; desktop upload checks are separate.
Investigate delivery only for an explicit request or actual recipient/delivery task.

The supplied automatic-capture installer is macOS-only; other hosts can use an
existing scheduler or manual capture. Use verified configured automatic capture,
or one `sync PROJECT --brief` after
material edits when no capture job exists. Verify job configuration once during setup;
keep its readiness hint in device-local guidance and recheck only when health changes.
Do not place device/runtime state in shared AGENTS.md. Preserve saved notes on error
and report a material save/capture gap once. Local capture does not prove remote
receipt. Keep personal/company boundaries, read-only grants and private indexes intact.
