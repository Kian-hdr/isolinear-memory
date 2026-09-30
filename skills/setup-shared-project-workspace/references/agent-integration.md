# Low-context everyday use

Read INDEX.md and only relevant notes. Search before writing. Use the host's native
read/edit tools. The agent maintains memory as part of finishing each task, without
waiting for the human to request documentation. Save meaningful findings, decisions,
corrections, generated artifacts, status changes and useful next steps in the relevant
existing canonical Wiki note. Save substantial deliverables in Output and link them
from Wiki; keep code in its project repository and link the exact path/version. Keep
source inputs in Raw. If there is no suitable note, create one within the selected
folder and add one short route in INDEX.md. Make the smallest targeted edit that
preserves evidence, dates, uncertainty, confidentiality and unrelated changes.
Read back touched notes and artifacts before claiming a save.
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
Markdown edit. Quietly handle routine successful local capture and provider activity;
an optional `Saved in Wiki/...` is enough when a location helps. Do not narrate Google
Drive upload state or repeatedly expose provider diagnostics in ordinary task replies.
Report a failed canonical save or a material history-capture gap once, with the
smallest useful recovery action. Mention remote receipt only when the user asks or
its uncertainty affects the requested result; never claim it from local capture.
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
status and removal. No MCP server, API key or extra tool schemas are required.
