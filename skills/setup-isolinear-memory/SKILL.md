---
name: setup-isolinear-memory
description: Set up, update, or repair Isolinear Memory in a selected Markdown folder. Ordinary note work uses native file tools; load this skill for installation, capture, migration, or troubleshooting.
---

# Isolinear Memory setup

Isolinear Memory is the public name for the existing Shared Memory format-3
runtime. Keep `.shared-memory.json`, `.shared-memory/`, project IDs, event history,
private state, and provider bindings intact. The `shared-memory` command and
`setup-shared-project-workspace` skill remain compatibility aliases.

For installation, inspect the selected folder's AGENTS.md and INDEX.md, then
read the versioned [installation guide](https://github.com/Kian-hdr/isolinear-memory/blob/main/docs/INSTALL.md).
Use only a reviewed runtime whose checksum matches its external SHA256SUMS entry.
Verify the actual release asset before running it. Install `isolinear-memory` and `shared-memory` launchers for the
same verified runtime outside synchronized folders. Preserve prior runtime
versions for rollback.

For a new or resumed folder, run `setup` on the actual selected path. Only an
entirely empty folder receives Raw/, Wiki/, Output/, AGENTS.md, and INDEX.md.
Never reset an existing project or reorganize a populated folder. Formats 1/2
retain their older workflow until an explicit backed-up migration. One provider
owns each physical folder; local capture does not establish remote receipt.

Routine agents read INDEX.md and only the relevant canonical notes, then edit
Markdown directly. Use `recall` for bounded source-linked discovery and `show`
for a hash-checked passage. Treat durable memory upkeep as part of task completion:
record meaningful findings, decisions, corrections, generated deliverables, changed
status and next steps in the correct existing Wiki note without a separate user
request. Keep substantial artifacts in Output/ and code in its own repository;
link exact paths or versions from Wiki. Create a new note and short INDEX route only
when there is no suitable canonical note. Preserve source, date, uncertainty and
completed-versus-planned status. Do not dump conversations or save fleeting chatter.
Read back touched notes and artifacts before confirming they were saved.
This is an agent instruction, not an automatic conversation-extraction service;
each host agent must perform the native edit within its selected folder permissions.

An installed capture job records history outside the model; otherwise run one `sync`
after material edits. Once `--status --brief` confirms a job is ready, record its
active status only in device-local host guidance for that selected project; recheck
and clear that signal if health changes. Never put device-specific status in shared
`AGENTS.md`. Ordinary successful capture and provider activity should not
appear in the user-facing reply. Optionally give the saved note's short location when
it helps the user; report a failed canonical save or material capture gap once. Discuss
remote receipt only when requested or consequential to the requested outcome, and do
not imply local capture proves it. Keep personal and company folder boundaries,
read-only grants, credentials, and private indexes intact.
