# Isolinear Memory name transition

Version 0.5.0 adopts **Isolinear Memory** as the public product name. The
repository is `Kian-hdr/isolinear-memory`. Verify the versioned release assets
before installation.

The release assets are `isolinear-memory-0.5.0.pyz`,
`isolinear-memory-0.5.0.zip`, `isolinear-memory-skills-0.5.0.zip`, and
`isolinear-memory-icons-0.5.0.zip`. The skill ZIP contains the new
`setup-isolinear-memory` entry point and the historical
`setup-shared-project-workspace` entry point. Existing releases retain their
original URLs and asset names.

The POSIX launcher installer installs `isolinear-memory` and the existing
`shared-memory` command together by default, pointing both to the same
verified package. Use `--no-legacy-alias` only for an intentional single-command
installation. Windows continues to run the
verified `.pyz` with Python directly. Existing launchers remain usable; this
source change does not modify a machine's installed commands.

**No project migration is needed.** Keep `.shared-memory.json`,
`.shared-memory/`, project IDs, format-3 history, the `shared_workspace` Python
module, private state paths, and existing provider bindings unchanged. Those
names are protocol and compatibility identifiers, not public branding. Do not
rename files or folders merely to adopt the product name. Rollback selects a
prior verified runtime and does not downgrade history.

The v0.5.0 release introduced a connected-pages icon and outlined
`assets/isolinear-memory-wordmark-{dark,light}.{svg,png}` spelling the new name.
Version 0.5.1 replaces that icon with a colored memory lattice on Apple system
light and dark backgrounds. Version 0.5.2 centers four equally spaced nodes for
a balanced mark in both appearances. Historical `shared-memory*` icon files remain in the
complete source kit but are excluded from the public icons ZIP. The name is inspired by
[Star Trek's isolinear chips](https://www.startrek.com/en-un/news/below-deck-with-lower-decks-403-move-along).
