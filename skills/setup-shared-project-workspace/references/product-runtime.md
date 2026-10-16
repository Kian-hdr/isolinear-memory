# Product runtime and format routing

Isolinear Memory 0.7.0, formerly Shared Memory, defaults to direct shared-folder editing. Use Python 3.11+ and
an exact verified `.pyz`. The version-specific release is
[v0.7.0](https://github.com/Kian-hdr/isolinear-memory/releases/tag/v0.7.0); execute
`isolinear-memory-0.7.0.pyz` only when actually supplied/present and verified against
external `SHA256SUMS`. An explicitly provided reviewed candidate is separate from
a published release. Verify before execution, then check `version` and the command help needed. Install it in private immutable tools storage using `install-package`.
This skill is not the runtime and must not silently substitute the advisory tracker.

## Normal folder workflow

Run `setup PROJECT` on the actual existing folder. It defaults to `--workflow folder`
and Markdown discovery. It discovers a new, joined or resumed format-3 project;
optional inputs include `--state-dir`, `--actor`, `--person`, `--agent`,
`--expected-project-id`, `--provider` and `--read-only`. Providers are local,
Google Drive, iCloud, OneDrive, Nextcloud or an explicitly selected self-hosted route.
These flags record intent and local binding, not account authentication or receipt.

Version 0.7.0 seeds team, personal or project layouts only in an
entirely empty folder. See [vault profiles](vault-profiles.md) for selection and
custom project folders. Older releases retain their Raw/Wiki/Output empty-folder
seed; inspect setup help and pre-create the designed notes before legacy setup.
Existing content, hidden files or empty directories prevent automatic scaffolding.
Setup never reorganizes existing workspaces. Join and resume retain their content.

Metadata/history lives in `.shared-memory.json` and `.shared-memory/` with the
project. Per-device baseline/config/recovery stays private outside shared storage.
Default state is a per-root application-data directory with a `folder` child; use
the returned `state_dir` for exact discovery. Do not copy another person's baseline.
Keep provider/OS permissions and explicit read-only bindings intact.

Edit notes directly and read back local bytes. A verified configured capture job
records history independently; otherwise run one `sync PROJECT --brief`. Use
`folder-status PROJECT --brief` and `history PROJECT [--path RELATIVE_NOTE]` only
when their diagnostics/history are needed, not after every routine save. Do not
check cloud client apps, upload queues or provider status to complete local work.
Capture provenance identifies the observer;
provider-arrived bytes may have been authored elsewhere. Compatible text can merge;
semantic agreement still needs judgment. Resolve with `resolve PROJECT --path NOTE
--text-file REVIEWED_FILE --evidence TEXT`, retaining competing history. The agent
may review after the work; there is no mandatory reviewer or automatic approval.

Use `delete PROJECT --path NOTE --evidence TEXT` for an intended deletion and
`rename PROJECT --source OLD --destination NEW --evidence TEXT` for a move.
Rename does not rewrite backlinks; inspect/correct them separately. Missing files
can be delayed provider delivery and are not silently treated as deletions.
`watch PROJECT --interval 5 --cycles 12` is a bounded local capture loop, not an
always-running AI service. Do not promise future provider receipt from a local call.

## Existing coordinator or advisory project

Formats 1/2 retain the older coordinator. Normal setup requests migration rather
than replacing them. `setup PROJECT --workflow coordinator` explicitly keeps the
historical route; consult its exact bundled/source guide. Do not mix folder commands
with old proposal/session state or reinterpret pending proposals as accepted.

For an authorized workflow conversion, inspect
`migrate-folder PROJECT --state-dir OLD_STATE --backup-dir FRESH_PRIVATE_BACKUP`,
then apply with the same arguments plus `--apply`. The complete old local authority,
metadata and current files must be preserved and verified; remote client state
alone is insufficient. Retry interrupted migration with its original paths. New
folder state lives in `OLD_STATE/folder`; old SQLite/history remains private.
The standard setup command can then discover the child from that old base.

A preserved old reader roster is not a new provider ACL. Maintain actual read-only
bindings and provider permissions. For the advisory tracker only, use the explicitly
selected legacy references; its Python 3.9+ scripts remain separate from the product.
