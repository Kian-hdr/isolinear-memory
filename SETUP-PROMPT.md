# Set up Isolinear Memory with an agent

Copy the block below into an agent with authorized local file access. Give it the
exact folder you want to use, or select that folder as its workspace. Use this
for installation, updates or repair; ordinary note work does not need setup again.

A phone without a local mirror needs an existing authorized remote connection.
This local setup request does not provision a hosted memory service. See the
[client and MCP guide](docs/MCP.md).

```text
Set up or update Isolinear Memory in my selected folder.

1. Establish the boundary. Use the exact folder I supplied or deliberately
   selected. If it is unclear, ask for the folder before changing anything.
   Read its existing AGENTS.md and INDEX.md when present. Discover the existing
   project identity, profile, provider, private binding and capture configuration.
   Preserve populated layouts, source files, attachments, instructions, history,
   conflicts, credentials and read-only restrictions. Do not include a parent
   vault or initialize another identity for an existing project.

2. Install a verified release. Follow the published Isolinear Memory installation
   guide, using the same release tag as the downloaded assets:
   https://github.com/Kian-hdr/isolinear-memory/blob/v0.7.1/docs/INSTALL.md
   Verify the runtime against its external SHA256SUMS before execution. Verify
   any source-kit or skill ZIP against that same external checksum file too.
   Run helper installers only from the matching verified extracted source kit,
   never from a same-named script in my selected project. If the
   asset is unavailable or mismatched, report that exact gap; do not substitute
   an unreviewed build. Keep the runtime, private index, baseline, recovery and
   credentials outside shared storage, and retain the prior package for rollback.
   On macOS/Linux, install checksum-bound isolinear-memory and shared-memory
   command aliases. On Windows, use compatible Python with the verified package.

3. Configure the selected project. For a new empty folder, infer team, personal
   or project scope from my purpose. Team knowledge starts with Raw/Wiki/Output.
   Personal memory uses concise topic notes without manual team contribution
   registers or mandatory verification templates. Project memory uses folders
   designed for its domain, lifecycle, assets and deliverables. Use the supported
   --vault-type and repeatable --project-folder options. Create meaningful
   AGENTS.md, INDEX.md and a brief/current handoff for a new project. Preserve an
   existing folder's layout and profile. Formats 1/2 require their documented
   backed-up migration path, never a reset or replacement identity.

4. Keep everyday use simple. Instructions should route agents through AGENTS.md,
   INDEX.md and the relevant canonical note. Use native reads for known paths,
   bounded recall for discovery, and hash-checked show when an excerpt lacks
   needed facts or qualifiers. Use the graph for explicit-link inspection, not
   as routine context to load in full. After substantive work, update the existing
   canonical note with durable results, sources, uncertainty, artifact links and
   next steps, then read the file back. Avoid transcripts and temporary chatter.

5. Verify local capture. Reuse a valid existing capture job. Configure automatic
   capture only where supported; this release supplies a macOS installer. On
   other hosts, use the existing scheduler or one bounded manual sync. Verify a
   small authorized note change, or a suitable existing captured change on an
   update, against its local history. Do not invent project facts for the test.
   If capture fails, preserve saved Markdown, report the error once and continue
   feasible note work. Keep .shared-memory.json, .shared-memory/ and all existing
   project IDs and history intact.

6. Respect access and delivery limits. Use one provider per physical project;
   local capture is not proof of remote receipt. Routine saves finish with local
   file readback. Do not open Drive/OneDrive apps, inspect upload queues, poll,
   force sync, restart clients or change sync settings to verify those saves.
   Remote source access without a mirror and an explicitly requested delivery
   investigation are separate tasks. Configure optional MCP only when needed:
   the released local adapter is read-only stdio, not a phone backend. Preserve
   provider grants and host authentication/OS protections.

Finish by reporting the actual installed version, selected folder and profile,
what was preserved or created, the local capture check and any remaining limits.
Separate completed checks from unsupported or untested device/provider behavior.
```
