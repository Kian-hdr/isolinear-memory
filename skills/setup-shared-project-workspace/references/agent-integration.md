# Low-context everyday use

Read INDEX.md and only relevant notes. Search before writing. Use the host's native
read/edit tools. The agent maintains memory as part of finishing each task, without
waiting for the human to request documentation. Save meaningful findings, decisions,
corrections, generated artifacts, status changes and useful next steps in the relevant
existing canonical note. Save substantial deliverables in the selected layout's deliverable folder and link them
from canonical notes; keep code in its project repository and link the exact path/version. Keep
source inputs in the selected layout's source/resource folder. If there is no suitable note, create one within the selected
folder and add one short route in INDEX.md. Make the smallest targeted edit that
preserves evidence, dates, uncertainty, confidentiality and unrelated changes.
Read back touched notes and artifacts before claiming a save.
With a local mirror, that readback is the routine save check. Leave background
syncing alone: do not open Drive/OneDrive clients or menus, inspect upload queues
or provider status, poll for receipt, force sync, restart clients or change sync
settings for ordinary note work or local history capture. Do not treat unchecked
upload state as a blocker. Local capture and remote delivery remain distinct facts;
that distinction does not require checking both after every save.
Distinguish completed work from ideas or unverified outcomes. Leave a concise Current
handoff for substantive work. Do not copy the chat transcript, repeat an existing log,
or save transient conversation with no durable value. Respect explicit do-not-save
instructions and the selected folder's scope, ownership and permissions.

For a known path or exact symbol, use native bounded search and read. For an
unknown location, `isolinear-memory recall . "QUERY" --text` from the selected folder returns a small
source-linked result; use `isolinear-memory show` with its path/hash/lines to expand
only a relevant passage. If unavailable or incomplete, fall back to native file
tools and say which sources were not checked. The private index is disposable;
the selected project's Markdown is still the record of truth. Use targeted edits,
not whole-note rewrites, for routine memory updates.

For a startup/reset that needs several complete authored sources, use
`context-packet` only if the installed runtime's help advertises it. It combines
complete AGENTS.md, INDEX.md and an explicitly selected canonical file or exact
unique handoff section, with current hashes/locators. Missing or oversized required
content fails as a whole; never drop a stop condition to make it fit. Native
bounded reads and recall/show remain appropriate for focused evidence.

Optional `--with-receipts`/`--known-evidence` reuse exact passages the caller still
holds after source revalidation. Forget receipts after a new chat, compaction,
reset or uncertain retention; reload authored text. Receipts cannot reconstruct
lost context and do not prove model understanding, delivery or factual truth.

An installed local capture job can run Isolinear Memory without a model tool call.
The installer must verify its actual runtime, project and private state once. A
running configured job is not another AI agent, a provider upload or a recipient
receipt. Do not claim automatic capture unless its status is verified.

Without that integration, use the stable installed command:

    isolinear-memory sync /actual/selected/project --brief

The compatible `shared-memory` launcher accepts the same commands and should
point to the same verified runtime after an upgrade.

For troubleshooting, use `folder-status PROJECT --brief`; omit `--brief` only when
complete diagnostic details are needed. A sync error does not invalidate a saved
Markdown edit. Quietly handle routine successful local capture;
an optional `Saved in Wiki/...` is enough when a location helps. Do not narrate Google
Drive upload state or inspect it in ordinary tasks.
Report a failed canonical save or a material history-capture gap once, with the
smallest useful recovery action. Investigate remote receipt only for an explicit
request or actual recipient/delivery outcome; never claim it from local capture.
Do not invent Python scripts or repeatedly load setup, capabilities, full guide or
historical manuals.

Codex, Claude, OpenCode and other agents can use native file operations. This guidance
is portable Markdown, but no CLI or skill can extract durable facts from a model's
conversation without the agent choosing and writing them. OpenCode also discovers
skills under ~/.agents/skills; install this skill only once per
search path. Provider model names and tool permissions belong to the host, not the
memory format. GLM/OpenRouter/Z.ai tool-call adapter errors need separate evidence
from an Isolinear Memory process error. Automatic capture removes the model's need to
launch the capture process; it cannot repair a provider's malformed native edits.

See the source repository's docs/AUTOMATIC-CAPTURE.md for deterministic installation,
status and removal. Local-mirror workflows need no MCP server, API key or extra
tool schemas.

## Hosts without a local mirror

Use the host's authorized Google Drive, OneDrive or Isolinear MCP/connector for the
selected sources. A phone need not install a desktop Python runtime or run a cloud
sync client. Availability depends on that host and connector; do not assume a saved
skill transfers credentials, access rights or support across clients/devices.
Retrieve only bounded relevant evidence, retain source IDs/revisions and scope,
and distinguish an indexed projection from a freshly checked source. Verify a
remote write through its returned receipt or source readback when that is the
actual save operation. These necessary remote reads are not upload-status checks
for a local mirror. Preserve personal/company isolation and report unavailable
source access without inventing a cloud copy or changing another project's binding.

Use [vault profiles](vault-profiles.md): personal vaults omit manual contributor logs
and mandatory verification templates; project vaults use a domain-specific layout.
