# Teammate onboarding prompt

After normal folder setup, provide a short prompt in chat when the task involves
sharing. Fill it with observed compatible package source, project identity and the
actual chosen provider/folder access route. Do not include credentials or sender-only
private paths. Mark missing access as missing; a prompt does not grant permissions.

The recipient's agent should verify the package, locate that recipient's own local
copy, inspect existing metadata, retain private local state and run ordinary setup.
It should not initialize a second project, request a coordinator token for folder
mode or create another cloud service. Direct edits persist offline. Use configured
capture, or one local sync after material edits/reconnect, preserving conflict
copies and recording resolution evidence. This onboarding access check does not
make provider-app or upload-queue checks part of ordinary note saving.

If the recipient has no local mirror, provide the already authorized remote
connector/service route instead of asking them to install a desktop runtime,
initialize another project or copy another device's private state. Verify that the
actual client supports that route; local stdio MCP alone is not remote access.
Neither an onboarding prompt nor a saved skill grants credentials or vault rights.

For a recipient with a local mirror, use language like the following, replacing
only details that have been verified. A remote-only recipient needs the scoped
connector/service instructions instead of this desktop setup prompt:

```text
Set up the existing Isolinear Memory project available through the folder access
instructions supplied with this message. Verify the specified compatible runtime
and its external checksum, then locate my own local copy and inspect its metadata.
Use the normal direct-edit folder workflow, preserving existing notes, permissions
and private parent folders. Keep my baseline/recovery state private and preserve
shared history. Read back saved local files. Use configured capture, or one local
sync after changes/reconnect, and report any unresolved conflicts. Leave background
cloud clients and upload queues alone during routine saves.
Do not copy another user's private state or create an unrequested coordinator.
```

Add the verified package and access details above this block. If either is missing,
state that explicitly. Existing coordinator formats follow their historical guide
until migrated with backup. Send no invitation or message automatically merely because
the prompt is ready.
