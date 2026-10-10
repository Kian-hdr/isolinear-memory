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

## Vault profiles and project design

Choose the profile from the user's purpose before creating a vault:

- **Team:** a company vault, shared team knowledge base or general organizational knowledge. Default to `Raw/`, `Wiki/`, `Output/`. Preserve source provenance, useful shared ownership and collaboration rules. Do not invent a mandatory approval process.
- **Personal:** one person's private knowledge. Use a light topic-based structure; the runtime seed is `Notes/`, `Resources/`. No manual person/agent attribution tables, team change register, contributor onboarding or mandatory verification/confidence templates. Write naturally and concisely. Keep useful sources and dates when they matter, correct factual errors, and preserve recovery/conflicts. Runtime causal metadata remains internal; do not repeatedly load or narrate it.
- **Project:** a bounded project knowledge base, usually shared. Infer its domain, lifecycle, participants, working assets and deliverables from the brief and existing evidence. Design folders for that work rather than forcing `Raw/Wiki/Output`. Retain person/agent contributor attribution and team collaboration rules when shared; a sole-owner project can use the lighter personal writing policy. Sharing/access rights remain a separate decision and are never inferred from a profile.

When asked to start a new project or set up its vault, establish the structure and instructions as part of that task. Use sensible labelled assumptions and ask only for consequential missing information. Choose the smallest useful folder set, explain each folder in INDEX.md, and identify the canonical brief/current handoff, decisions, source/asset locations and deliverable location. Examples are starting points, not templates to apply blindly: software `Planning/`, `Architecture/`, `Development/`, `Testing/`, `Releases/`; film `Brief/`, `Storyboard/`, `Assets/`, `Production/`, `Review/`, `Delivery/`; hardware `Requirements/`, `Design/`, `Components/`, `Prototypes/`, `Validation/`, `Deliveries/`. Keep executable code in its established repository and large working assets in their governed storage; link instead of duplicating.

For Isolinear Memory 0.6.0 or later, use `setup PROJECT --vault-type team|personal|project`; supply repeatable `--project-folder RELATIVE_FOLDER` for the chosen project structure. With no custom folders the project seed is a minimal `Knowledge/`, `Planning/`, `Deliverables/` fallback. The runtime creates safe folders and routing; the agent reasons about the domain and fills meaningful project-specific guidance. Published older runtimes may not support these flags: inspect `setup --help` first. On an older runtime, create the intended AGENTS.md, INDEX.md and folder README files natively before setup so its empty-folder legacy seed cannot overwrite the design. Do not pretend flags are supported. Older runtime recall may remain Wiki-scoped; use native bounded search/read for custom layouts until profile-aware retrieval is installed.

Profiles are defaults for new empty vaults. Preserve existing hierarchy, instructions, project identity and history on join/resume. An existing vault's policy can be updated with targeted authorized edits; reorganizing its files needs a separate scoped migration. Do not remove existing logs or immutable history to make personal writing lighter. No profile grants provider access or changes ACLs.

Routine agents read INDEX.md and only the relevant canonical notes, then edit
Markdown directly. Use `recall` for bounded source-linked discovery and `show`
for a hash-checked passage. Treat durable memory upkeep as part of task completion:
record meaningful findings, decisions, corrections, generated deliverables, changed
status and next steps in the correct existing canonical note without a separate user
request. Keep substantial artifacts in the profile's deliverable location and code in its own repository;
link exact paths or versions from the canonical note. Create a new note and short INDEX route only
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
