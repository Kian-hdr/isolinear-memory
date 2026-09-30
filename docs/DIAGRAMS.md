# Isolinear Memory system diagrams

These diagrams describe the **0.5.1 format-3 folder workflow**. They
separate note storage, private indexing, local history capture, provider
transport and recipient verification. The older format-1/2 coordinator has a
[separate operating guide](COORDINATOR-WORKFLOW.md).

The editable `.mmd` files under `assets/diagrams/` are the source of truth.
Each diagram below is generated from one of those files, as are the matching
SVG fallbacks. The [README](../README.md) uses the same sources with native
GitHub colors. Change a source file, regenerate both Markdown documents and
SVGs, then inspect the rendered figures. The product runtime does not depend
on Mermaid, Node or Chrome.

## 1. Portable project and private device state

<!-- BEGIN GENERATED MERMAID: 01-shared-folder.mmd -->
```mermaid
flowchart TB
  accTitle: One selected project, separate private device state
  accDescr: Each device holds a selected Markdown project and a private baseline, recovery state and FTS5 index. Isolinear Memory reads and records only the selected project. Provider sync scope is configured separately; the private state is outside the project route.
  subgraph A["DEVICE A"]
    direction LR
    AE["Person or agent<br/>native Markdown editor"] --> AF["Selected project folder<br/>AGENTS + INDEX + Raw / Wiki / Output<br/>format-3 manifest + portable events"]
    AM["Isolinear Memory<br/>recall + sync + history"] <-->|"read and capture"| AF
    AM <-->|"local only"| AS["Private device state<br/>baseline + recovery + FTS5 index"]
  end
  AF <-->|"project files<br/>if configured"| P["One chosen folder provider"]
  P <-->|"project files<br/>if delivered"| BF
  subgraph B["DEVICE B"]
    direction LR
    BE["Person or agent<br/>native Markdown editor"] --> BF["Authorized project copy<br/>Markdown + portable events"]
    BM["Isolinear Memory<br/>recall + sync + history"] <-->|"read and capture"| BF
    BM <-->|"local only"| BS["Separate private state<br/>baseline + recovery + FTS5 index"]
  end
  classDef project fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e;
  classDef private fill:#f1f5f9,stroke:#64748b,color:#334155;
  classDef route fill:#ecfdf5,stroke:#059669,color:#064e3b;
  class AF,BF project;
  class AS,BS private;
  class P route;
```
<!-- END GENERATED MERMAID: 01-shared-folder.mmd -->

<details>
<summary>SVG fallback</summary>

![Two devices hold copies of one selected Markdown project, but each keeps its baseline, recovery and FTS5 index private.](../assets/diagrams/01-shared-folder.svg)

</details>

[Editable Mermaid source](../assets/diagrams/01-shared-folder.mmd)

The selected folder contains canonical Markdown, the format-3 manifest and
portable immutable events. Isolinear Memory reads and records that folder;
the provider's own sync scope and access permissions are configured separately.
Each device's private baseline, recovery material
and FTS5 database remain outside the shared folder. The private index contains
rebuildable passage text for faster retrieval; it never decides which note is
authoritative. A parent Obsidian vault and nested projects stay outside the
selected project's boundary.

## 2. Bounded recall and hash-checked expansion

<!-- BEGIN GENERATED MERMAID: 05-recall-and-index.mmd -->
```mermaid
flowchart TB
  accTitle: Bounded recall verifies current Markdown before returning evidence
  accDescr: Recall searches the selected project's Wiki and root routing files by default. Path matches, private FTS5 chunks and bounded direct scanning provide candidates. Every returned hit is checked against current Markdown. Show expands lines only when the source hash still matches; incomplete coverage is reported.
  Q["Agent asks for a fact"] --> R["recall query<br/>selected project only"]
  R --> S["Default scope<br/>AGENTS + INDEX + Wiki<br/>Raw / Output only on request"]
  S --> C{"Find candidate passages"}
  C --> P["Path and title matches"]
  C --> I["Private rebuildable FTS5<br/>stores passage chunks"]
  C --> D["Bounded direct scan<br/>when index unavailable"]
  P --> V["Re-read current Markdown<br/>verify source + excerpt"]
  I --> V
  D --> V
  V --> O["At most 5 ranked hits<br/>2 KiB default packet<br/>path + heading + lines + SHA<br/>unsearched / unavailable flags"]
  O --> H["show with path + SHA + lines"]
  H --> G{"Current hash matches?"}
  G -->|"yes"| E["Return exact bounded lines"]
  G -->|"no"| X["Refuse stale evidence<br/>recall again"]
  classDef route fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e;
  classDef private fill:#f1f5f9,stroke:#64748b,color:#334155;
  classDef valid fill:#ecfdf5,stroke:#059669,color:#064e3b;
  classDef stale fill:#fff7ed,stroke:#c2410c,color:#7c2d12;
  class Q,R,S,C,P,D,V,O,H,G route;
  class I private;
  class E valid;
  class X stale;
```
<!-- END GENERATED MERMAID: 05-recall-and-index.mmd -->

<details>
<summary>SVG fallback</summary>

![Recall uses path matches, a private FTS5 index or bounded direct scanning, verifies current Markdown, then returns small cited hits for hash-checked expansion.](../assets/diagrams/05-recall-and-index.svg)

</details>

[Editable Mermaid source](../assets/diagrams/05-recall-and-index.mmd)

`recall` searches root `AGENTS.md` and `INDEX.md` plus `Wiki/` by default.
`Raw/` and `Output/` require explicit inclusion. Path and title matches,
private FTS5 chunks and bounded direct scans supply candidate passages.
The runtime rechecks current Markdown before returning at most five hits
inside a 2 KiB default packet. Each hit carries a source path, heading, line
span, exact excerpt and source hash. The packet reports unavailable,
truncated and unsearched material. A warm cached hit may not discover a new
nonmatching file until refresh; use `--refresh` or native targeted search
when the coverage flag matters. `show` expands up to 80 lines only if the
current source hash still matches. A changed file produces a stale-evidence
refusal instead of an old quote.

## 3. Save, capture, transport and verify

<!-- BEGIN GENERATED MERMAID: 02-edit-and-deliver.mmd -->
```mermaid
flowchart TB
  accTitle: Local save, history capture, provider delivery and recipient receipt
  accDescr: A Markdown save is local. Manual sync or an optional macOS capture job records history and private baseline state. A separately configured provider may deliver project files. A recipient must observe and sync them; missing sources or parents remain partial.
  E["Person or agent edits Markdown"] -->|"1. save local bytes"| S["Selected project file"]
  S --> T{"Capture trigger"}
  T -->|"manual on any supported OS"| M["Run Isolinear sync"]
  T -->|"optional macOS job"| A["Scheduled local capture"]
  A --> X["Compare with private baseline<br/>capture edits + reconcile visible arrivals"]
  M --> X
  X -->|"2. local history"| H["Portable immutable events<br/>in selected project folder"]
  X --> B["Private baseline + recovery<br/>outside synced folder"]
  X -->|"unavailable or incomplete"| Q["Partial result<br/>saved Markdown remains"]
  H -->|"3. configured transport"| P["Chosen provider<br/>delivery checked separately"]
  P --> R["Authorized other copy<br/>observe arriving files"]
  R --> Y["Recipient runs sync<br/>check event parents"]
  Y -->|"4. independent readback"| V["Recipient receipt verified"]
  Y -->|"parents missing"| D["Defer reconciliation<br/>keep received history"]
  classDef local fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e;
  classDef private fill:#f1f5f9,stroke:#64748b,color:#334155;
  classDef route fill:#ecfdf5,stroke:#059669,color:#064e3b;
  classDef caution fill:#fff7ed,stroke:#c2410c,color:#7c2d12;
  class E,S,M,A,X,H,R,Y local;
  class B private;
  class P,V route;
  class Q,D caution;
```
<!-- END GENERATED MERMAID: 02-edit-and-deliver.mmd -->

<details>
<summary>SVG fallback</summary>

![A local Markdown save, history capture, provider transport and independent recipient readback are four separate events.](../assets/diagrams/02-edit-and-deliver.svg)

</details>

[Editable Mermaid source](../assets/diagrams/02-edit-and-deliver.mmd)

An editor or agent saves Markdown directly. Manual `sync` on any supported OS,
or an optional macOS capture job, compares observed bytes with the private
causal baseline. It records local events before reconciling history already
visible from the provider. Event files are portable; the baseline is not.
The provider transports selected project files separately. A recipient
must actually observe the intended files and run `sync` before independent
receipt can be asserted. Missing source bytes, invalid events or missing
parents remain explicit partial/deferred states. A partial capture preserves
the saved note and its private recovery state.

| State | Evidence needed |
| --- | --- |
| Local save | Read back the file on this device. |
| Local capture | Verify the new history event and private baseline. |
| Provider delivery | Inspect the provider's actual transfer state. |
| Recipient receipt | Read the intended content and history on the other device. |

## 4. Offline ancestry and conflicts

<!-- BEGIN GENERATED MERMAID: 03-offline-and-conflicts.mmd -->
```mermaid
flowchart TB
  accTitle: Offline edits keep ancestry and visible conflicts
  accDescr: Two offline copies can edit from the same base. Complete parent events permit compatible text to merge. Missing parents defer reconciliation, while overlapping edits keep both versions for evidence-backed resolution. No timestamp selects a winner.
  B["Known common version"] --> A["Copy A edits offline<br/>capture event with parent"]
  B --> C["Copy B edits offline<br/>capture event with parent"]
  A --> P["Provider exchanges project files<br/>when connected"]
  C --> P
  P --> H{"Are required parent<br/>events available?"}
  H -->|"no"| D["Defer affected event<br/>preserve incoming history"]
  H -->|"yes"| T{"Are text changes<br/>compatible?"}
  T -->|"yes"| M["Merge text + record ancestry<br/>review factual meaning"]
  T -->|"no"| K["Keep both versions<br/>write readable conflict report"]
  K --> R["Authorized editor resolves<br/>with chosen text + evidence"]
  classDef state fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e;
  classDef merge fill:#ecfdf5,stroke:#059669,color:#064e3b;
  classDef caution fill:#fff7ed,stroke:#c2410c,color:#7c2d12;
  class B,A,C,P,H,T state;
  class M,R merge;
  class D,K caution;
```
<!-- END GENERATED MERMAID: 03-offline-and-conflicts.mmd -->

<details>
<summary>SVG fallback</summary>

![Independent offline edits retain causal parents; complete history can merge compatible text or retain competing versions for explicit resolution.](../assets/diagrams/03-offline-and-conflicts.svg)

</details>

[Editable Mermaid source](../assets/diagrams/03-offline-and-conflicts.mmd)

Both copies can descend from one known version. Capture records each change
with its parent rather than selecting a winner by wall-clock time. If a parent
event has not arrived, reconciliation of the affected event waits. With
complete ancestry, compatible text can merge; overlapping or ambiguous
changes retain both versions and a readable conflict report. An authorized
editor supplies chosen text and evidence to resolve a conflict. A clean text
merge is still only text convergence, not factual agreement.

Missing files alone never mean intentional deletion. `delete` and `rename`
record explicit intent; rename does not automatically repair Markdown or
Obsidian backlinks. Read-only bindings and provider permissions remain in
force.

## 5. Local-only use and provider choice

<!-- BEGIN GENERATED MERMAID: 04-provider-options.mmd -->
```mermaid
flowchart TB
  accTitle: Local-only use or one provider per physical project
  accDescr: Isolinear Memory works in a local Markdown folder. To share a project, choose one configured provider for that physical folder. Google Drive, iCloud Drive, OneDrive and operator-managed Nextcloud are alternatives, not bridges. Verify files and history on each recipient device.
  P["Selected physical project"] --> C{"Share this project?"}
  C -->|"yes"| S["Choose one folder provider<br/>Google Drive / iCloud Drive<br/>OneDrive / operator-managed Nextcloud"]
  C -->|"no"| L["Local only<br/>no provider required"]
  S --> D["Authorized other copy<br/>if files arrive"]
  D --> V["Recipient reads content<br/>and runs sync"]
  classDef state fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e;
  classDef provider fill:#f8fafc,stroke:#64748b,color:#0f172a;
  classDef verified fill:#ecfdf5,stroke:#059669,color:#064e3b;
  class P,C,D state;
  class S provider;
  class L,V verified;
```
<!-- END GENERATED MERMAID: 04-provider-options.mmd -->

<details>
<summary>SVG fallback</summary>

![One project may stay local or use exactly one configured provider; another copy verifies files after arrival.](../assets/diagrams/04-provider-options.svg)

</details>

[Editable Mermaid source](../assets/diagrams/04-provider-options.mmd)

A project needs no provider for local-only use. For sharing, choose one
provider for each physical folder: Google Drive, iCloud Drive, OneDrive or an
operator-managed Nextcloud service. These are alternatives, not bridges.
Account permissions, desktop-client behavior, offline availability and
conflict copies vary by setup. The provider must be configured separately;
Isolinear Memory does not provision it or grant another person access.
See [provider guidance](PROVIDERS.md). Recipient readback is the final
acceptance check for delivery.

## Regenerate and inspect

The standard-library checker compares all generated Mermaid blocks in both
the README and this guide against the `.mmd` sources:

```bash
python3 scripts/render_diagrams.py --check-markdown
python3 scripts/render_diagrams.py --update-markdown
```

The checker does not validate SVG freshness. To render SVGs and optional PNG
previews, use pinned Mermaid CLI **11.17.0**, Node.js and an existing
Chrome/Chromium executable. Install development-only tooling outside the
repository:

```bash
PUPPETEER_SKIP_DOWNLOAD=true npm install \
  --prefix /tmp/isolinear-memory-diagram-tools \
  --no-save --ignore-scripts --no-audit --no-fund \
  @mermaid-js/mermaid-cli@11.17.0

python3 scripts/render_diagrams.py \
  --mmdc /tmp/isolinear-memory-diagram-tools/node_modules/.bin/mmdc \
  --chrome "/path/to/Chrome-or-Chromium" \
  --png-dir /tmp/isolinear-memory-diagram-previews
```

The renderer processes every `.mmd` source, writes corresponding SVGs,
optionally creates PNG previews outside the repository and updates both
Markdown documents. Inspect every figure for readable labels, clipping,
arrow direction, contrast and accurate privacy boundaries. The SVGs carry
Mermaid accessibility titles and descriptions; surrounding prose explains
the same relationships without relying on color.
