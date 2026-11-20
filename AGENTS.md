# Isolinear Memory contributor instructions

- Keep private workspace content, account details, credentials and transcripts
  out of this public repository. Use synthetic fixtures for tests and examples.
- Use the selected Markdown folder's instructions and scope. Read known sources
  directly and use scoped recall for discovery. Save durable decisions and evidence
  in the existing canonical note and verify the local readback.
- Preserve project IDs, on-disk formats, history, conflicts, provider bindings and
  read-only boundaries. Formats 1 and 2 use their existing workflow until an
  explicit backed-up migration. See [compatibility](docs/BRAND-MIGRATION.md).
- Keep ordinary setup and capture independent of Obsidian and hosted services.
  Leave cloud upload queues and sync settings alone for routine local saves.
- Put setup instructions in the [canonical skill](skills/setup-isolinear-memory/SKILL.md)
  or the [installation guide](docs/INSTALL.md). Use Isolinear Memory in user-facing
  text and preserve identifiers used by existing callers.
- The runtime supports Python 3.11+ on macOS, Linux and Windows. Run the relevant
  tests in `product/tests` and any affected toolkit checks. Build with
  `scripts/build_product.py` and build releases from a clean commit with
  `scripts/build_release.py`. Check generated Mermaid blocks with
  `python scripts/render_diagrams.py --check-markdown`.
