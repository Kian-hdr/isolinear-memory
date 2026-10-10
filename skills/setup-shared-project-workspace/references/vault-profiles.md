# Isolinear Memory vault profiles

## Vault profiles and project design

Choose the profile from the user's purpose before creating a vault:

- **Team:** a company vault, shared team knowledge base or general organizational knowledge. Default to `Raw/`, `Wiki/`, `Output/`. Preserve source provenance, useful shared ownership and collaboration rules. Do not invent a mandatory approval process.
- **Personal:** one person's private knowledge. Use a light topic-based structure; the runtime seed is `Notes/`, `Resources/`. No manual person/agent attribution tables, team change register, contributor onboarding or mandatory verification/confidence templates. Write naturally and concisely. Keep useful sources and dates when they matter, correct factual errors, and preserve recovery/conflicts. Runtime causal metadata remains internal; do not repeatedly load or narrate it.
- **Project:** a bounded project knowledge base, usually shared. Infer its domain, lifecycle, participants, working assets and deliverables from the brief and existing evidence. Design folders for that work rather than forcing `Raw/Wiki/Output`. Retain person/agent contributor attribution and team collaboration rules when shared; a sole-owner project can use the lighter personal writing policy. Sharing/access rights remain a separate decision and are never inferred from a profile.

When asked to start a new project or set up its vault, establish the structure and instructions as part of that task. Use sensible labelled assumptions and ask only for consequential missing information. Choose the smallest useful folder set, explain each folder in INDEX.md, and identify the canonical brief/current handoff, decisions, source/asset locations and deliverable location. Examples are starting points, not templates to apply blindly: software `Planning/`, `Architecture/`, `Development/`, `Testing/`, `Releases/`; film `Brief/`, `Storyboard/`, `Assets/`, `Production/`, `Review/`, `Delivery/`; hardware `Requirements/`, `Design/`, `Components/`, `Prototypes/`, `Validation/`, `Deliveries/`. Keep executable code in its established repository and large working assets in their governed storage; link instead of duplicating.

For Isolinear Memory 0.6.0 or later, use `setup PROJECT --vault-type team|personal|project`; supply repeatable `--project-folder RELATIVE_FOLDER` for the chosen project structure. With no custom folders the project seed is a minimal `Knowledge/`, `Planning/`, `Deliverables/` fallback. The runtime creates safe folders and routing; the agent reasons about the domain and fills meaningful project-specific guidance. Published older runtimes may not support these flags: inspect `setup --help` first. On an older runtime, create the intended AGENTS.md, INDEX.md and folder README files natively before setup so its empty-folder legacy seed cannot overwrite the design. Do not pretend flags are supported. Older runtime recall may remain Wiki-scoped; use native bounded search/read for custom layouts until profile-aware retrieval is installed.

Profiles are defaults for new empty vaults. Preserve existing hierarchy, instructions, project identity and history on join/resume. An existing vault's policy can be updated with targeted authorized edits; reorganizing its files needs a separate scoped migration. Do not remove existing logs or immutable history to make personal writing lighter. No profile grants provider access or changes ACLs.

Profile-aware recall searches personal Notes by default; `--include-raw` adds
Resources. Project recall searches the declared project folders. Both exact and
hybrid discovery and hash-checked show retain selected-folder and nested-project
boundaries. Existing populated layouts may need an explicitly planned profile
migration before the runtime's declared scope matches all their custom folders.
