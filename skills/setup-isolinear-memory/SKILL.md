---
name: setup-isolinear-memory
description: Install, update, repair, or migrate Isolinear Memory for a selected Markdown folder. Use native file tools for ordinary note work.
---

# Set up Isolinear Memory

1. Identify the selected folder. Read its `AGENTS.md` and `INDEX.md` if present. Check the existing project identity, format, profile and local binding before setup.
2. Verify the runtime and any installer or skill archives against the same release's external `SHA256SUMS`. Use helpers from that verified release and retain the prior runtime for rollback. Follow the [installation guide](https://github.com/Kian-hdr/isolinear-memory/blob/v0.7.2/docs/INSTALL.md) for 0.7.2. Use the guide for the actual installed or target version when it differs.
3. For a new empty folder, use `isolinear-memory setup PROJECT --vault-type team|personal|project` with one profile. Team starts with `Raw/`, `Wiki/` and `Output/`. Personal starts with `Notes/` and `Resources/`. Project can use repeatable `--project-folder` options. Preserve populated layouts, editor settings, instructions, project IDs, `.shared-memory.json` and `.shared-memory/`. For formats 1 and 2, use the [documented migration](https://github.com/Kian-hdr/isolinear-memory/blob/v0.7.2/docs/PRODUCT-V1.md) when authorized to switch workflows.
4. Reuse a verified capture job or run `isolinear-memory sync PROJECT --brief` once after material edits. The release supplies a macOS installer. If capture fails, keep the saved notes and report the gap. Keep credentials, indexes and local recovery state outside shared storage. Use one provider per folder and preserve access grants.

## Working in the folder

- Read the relevant canonical note or handoff directly when its path is known. For discovery, start with `isolinear-memory recall PROJECT "specific terms" --max-hits 2 --text`. Try `--strategy hybrid` if exact search falls short. Check coverage. Expand incomplete hits with a targeted source read or hash-checked `show`. Keep searches inside the selected folder.
- Save durable decisions, evidence, artifact links and next steps in the existing note. Keep sources and uncertainty, and read back the saved file. Leave cloud upload queues and sync settings alone for routine local saves. Local capture and provider delivery are separate checks.
- For client integration, use the [MCP guide](https://github.com/Kian-hdr/isolinear-memory/blob/v0.7.2/docs/MCP.md). For optional context features, see [context packets](https://github.com/Kian-hdr/isolinear-memory/blob/v0.7.2/docs/PROGRESSIVE-CONTEXT.md) and [evidence receipts](https://github.com/Kian-hdr/isolinear-memory/blob/v0.7.2/docs/EVIDENCE-RECEIPTS.md). Without a local mirror, use an authorized provider connector or separately configured remote service and verify source scope and freshness.
