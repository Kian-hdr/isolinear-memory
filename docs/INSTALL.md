# Install or update Isolinear Memory 0.7.1

This is setup reference, not routine agent context. Preserve the selected workspace,
private state and previous runtime. Python 3.11+ is required. Download the versioned
runtime and SHA256SUMS from the [v0.7.1 release](https://github.com/Kian-hdr/isolinear-memory/releases/tag/v0.7.1).
Verify the runtime SHA-256 against its external SHA256SUMS entry before execution.
If unavailable or mismatched, stop installation; do not substitute an unverified asset.

Choose the matching assets from that same release:

| Asset | When needed |
| --- | --- |
| `isolinear-memory-0.7.1.pyz` | The self-contained runtime |
| `SHA256SUMS` | External checksums for downloaded assets |
| `isolinear-memory-0.7.1.zip` | Versioned source kit, including the launcher and capture installer scripts |
| `isolinear-memory-skills-0.7.1.zip` | Packaged setup skills for the host agent |

Before executing a helper script, download and verify the **source kit ZIP** against
its external checksum, then extract it to a separate tools/source directory outside
the memory folder. Use only scripts from that exact extracted kit. Do not run a
same-named script found in the selected project or on an unrelated search path.
Verify the skills ZIP as well before installing its contents. A runtime-only Python
invocation does not need the source kit; the commands below that use installer
scripts do. Use a compatible Python command on your platform; `python3` is the
example spelling here.

Use the verified package's `version` and `install-package --help`, then:

```text
python3 isolinear-memory-0.7.1.pyz install-package isolinear-memory-0.7.1.pyz --sha256 VERIFIED_SHA --tools-dir PRIVATE_TOOLS
```

Substitute actual discovered paths and checksum. Use the returned immutable package
for `setup PROJECT` and subsequent commands. Existing format-3 projects retain their
private state; supply `--state-dir` only when required by their existing binding.
For old formats, read the [migration guide](PRODUCT-V1.md) before proceeding.
Version 0.7.1 supports `--vault-type team|personal|project`
and repeatable `--project-folder` inputs. Team keeps Raw/Wiki/Output; personal uses
Notes/Resources; project uses chosen domain folders. See [vault profiles](../skills/setup-shared-project-workspace/references/vault-profiles.md).
Published older releases may lack these options; inspect setup help and pre-create
the designed instructions/folder notes before legacy setup. Populated folders are
not reorganized.

The versioned source kit includes a POSIX launcher installer (macOS/Linux) and a
macOS automatic-capture installer. On native Windows, invoke the verified package
with Python directly; this release does not install a Windows command shim.

```text
python3 VERIFIED_SOURCE_KIT/scripts/install_command.py --runtime INSTALLED_PACKAGE --sha256 VERIFIED_SHA
python3 VERIFIED_SOURCE_KIT/scripts/install_capture.py PROJECT --state-dir PRIVATE_STATE --runtime INSTALLED_PACKAGE --sha256 VERIFIED_SHA --install
```

Replace `VERIFIED_SOURCE_KIT` with the absolute extracted-kit path, and use the
actual selected project, private state and installed-package paths. These are
placeholders, not commands to execute literally. Reuse an existing valid capture
binding before considering an installer update. The second command installs a
macOS user LaunchAgent. Read [automatic capture](AUTOMATIC-CAPTURE.md)
for status, recovery and removal. Other systems can continue with native edits and
one manual sync; an automatic Windows/Linux service is not supplied in this release.
Use the host's existing private scheduler if separately configured and verified.

Install `setup-isolinear-memory` from the verified skills ZIP in a supported skill
path, preserving any prior copy. The same ZIP includes
`setup-shared-project-workspace` for existing agents. Codex uses ~/.codex/skills; OpenCode also supports
~/.agents/skills. Do not duplicate the same name across its discovery paths.
The skill is for setup/repair, not a prerequisite for ordinary note edits.

For an existing populated project, preserve its `AGENTS.md` and add the compact
automatic-memory rule through a targeted edit: after substantive work, the agent
saves durable findings, decisions, artifact links, status and next steps in the
authorized canonical note and reads the edit back. New empty projects receive this
rule during setup. Tasks started outside the selected folder also need a small
host-local routing instruction. Codex uses `~/.codex/AGENTS.md`, OpenCode uses
[`~/.config/opencode/AGENTS.md`](https://opencode.ai/docs/rules/), and older
Claude Code versions use [`~/.claude/CLAUDE.md`](https://code.claude.com/docs/en/memory).
Route only to projects the agent is authorized to open; keep device paths and
capture-job status out of synchronized project instructions. Verify the rule
with a nonprivate task that produces a canonical note update without a memory prompt.

The default command locations are ~/.local/bin/isolinear-memory and
~/.local/bin/shared-memory. Both run the same verified package. An intentional
single-command installation may use `--no-legacy-alias`.
Use an absolute path if that directory is absent from PATH. From the selected
workspace, `isolinear-memory sync` defaults to the current folder and brief output.
`--full` restores complete
sync/status diagnostics. Direct `.pyz` calls retain full output unless `--brief` is
requested. Never pass a project UUID where a folder path is expected.

Check the job's latest result and confirm a bounded edit appears in history. Report
local capture separately from remote provider delivery. Roll back with the runtime's
`rollback-package` command, then reinstall the launcher/capture job pointing at the
chosen verified package. Runtime rollback does not erase or downgrade history.
