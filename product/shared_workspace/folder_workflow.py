"""Ordinary shared-folder CLI. No coordinator, session or approval operations."""
from __future__ import annotations

import getpass
import json
from pathlib import Path, PurePosixPath
import secrets
import time

from .errors import ProductError
from . import workflow

COMMANDS = ('sync', 'folder-status', 'history', 'resolve', 'delete', 'rename', 'migrate-folder', 'watch',
            'recall', 'show', 'context-packet', 'memory-mcp', 'append-row')
FOLDER_PROVIDERS = ('local', 'google-drive', 'icloud', 'onedrive', 'nextcloud', 'self-hosted')


VAULT_TYPES = ('team', 'personal', 'project')


def validate_project_folders(folders):
    """Portable relative domain directories, never filesystem or markup syntax."""
    import re
    result = []
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
    for value in folders or ():
        if not isinstance(value, str) or len(value) > 160 or not value:
            raise ProductError(2, 'project_folder_unsafe', 'Project folders must be bounded relative directory names.')
        parts = value.split('/')
        if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,63}', part)
               or part.endswith(' ') or part.upper() in reserved for part in parts):
            raise ProductError(2, 'project_folder_unsafe', 'Use portable relative folders without traversal, hidden names, reserved names or markup.')
        folded = value.casefold()
        if folded in {'agents', 'index'} or any(folded == old.casefold() or
                folded.startswith(old.casefold() + '/') or old.casefold().startswith(folded + '/') for old in result):
            raise ProductError(2, 'project_folder_unsafe', 'Project folders must be distinct non-overlapping directories.')
        result.append(value)
    if len(result) > 32:
        raise ProductError(2, 'project_folder_unsafe', 'Choose at most 32 project folders.')
    return result


def profile_workspace_files(vault_type, folders):
    if vault_type == 'personal':
        title = 'Personal vault'
        routes = [('Notes', 'Personal knowledge, decisions and useful notes'),
                  ('Resources', 'Reference material and original sources')]
        guidance = ('This is a single-person vault. Use simple natural notes. Do not require manual\n'
                    'person-agent attribution, change registers, evidence labels, verification templates\n'
                    'or team audit reports. Keep factual accuracy, useful source links, uncertainty when\n'
                    'material, conflict recovery and confidentiality. Runtime causal history remains\n'
                    'available for synchronization and recovery; it is not a manual writing task.\n')
    else:
        title = 'Project vault'
        routes = [(name, 'Project material for ' + name) for name in folders]
        guidance = ('This vault is scoped to this project and usually shared by its team. Choose domain\n'
                    'folders from the actual project purpose, deliverables and working process before\n'
                    'initialization; the generic Knowledge/Planning/Deliverables fallback is only a\n'
                    'starting point. Preserve established folders and do not reorganize existing work\n'
                    'during setup. Retain person/agent contribution attribution in recoverable history.\n'
                    'Use actual --person and --agent labels and a distinct --actor when binding a teammate;\n'
                    'labels record asserted capture provenance, not authenticated authorship.\n'
                    'Coordinate overlapping writes and preserve source links and factual\n'
                    'uncertainty where they matter. A vault profile does not change access permissions.\n')
    agents = f'''# {title}

Read INDEX.md, then only relevant notes using bounded topic/path searches.

{guidance}
Memory upkeep is part of completing a task. Without waiting to be asked, update the
appropriate existing note with useful durable decisions, findings, corrections,
artifact links and next steps. Create and index a note only when no existing home
fits. Read back touched notes before claiming a save. Keep handoffs concise and
useful; avoid transcripts, duplicate logs and routine tool narration. Respect
explicit do-not-save instructions and keep private material in its authorized vault.

Use native file tools. Preserve existing instructions, hierarchy, attachments and
unrelated edits. Retain conflicts; resolve factual disagreements against evidence.
Record explicit renames/deletions through Isolinear Memory and check links; missing
files alone are not deletions. Configured automatic capture records history;
otherwise run the installed isolinear-memory sync once after material edits.
Complete routine saves by local readback. Leave Drive/OneDrive background syncing
alone: do not inspect apps, queues or upload status, poll, force sync or restart
clients. Remote source access is appropriate when no local mirror exists; check
remote delivery only for an explicit delivery/investigation task. Local capture
is not remote receipt. Report actual read/capture errors once and preserve notes.
Keep credentials, private runtime state and recovery outside the vault. Respect
read-only grants and OS/provider controls. Preserve .shared-memory/ and
.shared-memory.json. One provider per folder.
'''
    index = f'# {title} index\n\nRead [[AGENTS]] first.\n\n| Need | Location |\n| --- | --- |\n'
    files = {'AGENTS.md': agents}
    for name, purpose in routes:
        index += f'| {purpose} | [[{name}/README|{name}/]] |\n'
        files[name + '/README.md'] = f'# {PurePosixPath(name).name}\n\n{purpose}. Add useful subfolders and canonical notes as needed.\nPreserve originals and link relevant decisions and deliverables from the vault index.\n'
    files['INDEX.md'] = index + '\nAdd links to canonical notes here as the vault grows.\n'
    return files


def new_workspace_files(root, vault_type='team', project_folders=None):
    """Seed only an empty selected folder; never classify or move existing work.

    The normal initialization intent, immutable event and materialization journal
    make these files recoverable across interrupted setup and provider delivery.
    Even hidden files or empty user folders mean this is an existing workspace.
    """
    if any(root.iterdir()):
        return None
    if vault_type != 'team':
        return profile_workspace_files(vault_type, project_folders or ['Knowledge', 'Planning', 'Deliverables'])
    return {
        'AGENTS.md': '''# Shared workspace

Read INDEX.md, then only relevant Wiki sections; search by topic/path with bounded
reads. Raw/ holds sources, Wiki/ canonical knowledge, Output/ substantial deliverables.

Memory upkeep is part of completing a task. Without waiting to be asked, update the
relevant existing Wiki note for durable findings, decisions, corrections, generated
artifacts, status changes and next steps. Keep substantial deliverables in Output/
and code in its project repository; link their exact paths/versions from Wiki. If no
note fits, create one in the selected scope and add a short INDEX.md route. Use
targeted edits, then read back touched notes and artifacts before claiming a save.
Record source/date, uncertainty and completed versus planned status; leave a concise
Current handoff after substantive work. No transcript, duplicate log or fleeting
chat. Respect explicit do-not-save instructions.

Use native file tools within selected-folder permissions; do not ask the human to
manage routine memory. Never put private material in a company folder or expand
project access. Preserve hierarchy, attachments, instructions and unrelated edits;
coordinate overlapping writes. Retain conflicts and review factual disagreements.
Record explicit renames/deletions through Isolinear Memory and check links; missing
files alone are not deletions.

Configured automatic capture records history independently. Otherwise run the
installed isolinear-memory sync once after material edits. If capture fails, keep
saved Markdown and report a material history gap once, without repeated retries.
Complete routine saves by local readback; an optional short saved-note location
is enough. Do not inspect cloud apps, menus, upload queues or provider status,
poll uploads, force syncing, restart clients or change sync settings for routine
work. Use connected source tools when no local mirror exists. Check remote
receipt only for an explicit delivery/investigation task; local capture does not
prove it. An actual local read/save failure still needs to be reported.

Keep private state, credentials and recovery outside shared storage. Respect
confidentiality, read-only grants and OS/provider controls. One provider per folder.
Preserve .shared-memory/ and .shared-memory.json.
''',
        'INDEX.md': '''# Workspace index

Read [[AGENTS]] first, then use this routing map.

| Need | Location |
| --- | --- |
| Unprocessed information and original sources | [[Raw/README|Raw/]] |
| Durable knowledge, decisions and project state | [[Wiki/README|Wiki/]] |
| Substantial generated deliverables | [[Output/README|Output/]] |

## Canonical pages and projects

No project or domain pages have been created yet. Add links to important canonical
pages here as the workspace grows, following the established Wiki hierarchy.
Retrieve relevant Wiki pages first; inspect Raw sources only when necessary.
''',
        'Raw/README.md': '''# Raw

Inbox for unprocessed information and original source material. Extract useful
durable knowledge into the appropriate existing Wiki page, preserving provenance.
Keep sources unless there is a clear, authorized reason to archive or remove them.
See [[INDEX]] for routing and [[AGENTS]] for the shared workflow.
''',
        'Wiki/README.md': '''# Wiki

Canonical long-term memory: projects, people, companies, research, technical
documentation, decisions, processes and current project state. Build on existing
pages and preserve the hierarchy as it develops. Substantial generated deliverables
belong in Output/; record their durable conclusions here with a source link.
See [[INDEX]] for routing and [[AGENTS]] for the shared workflow.
''',
        'Output/README.md': '''# Output

Default location for substantial generated deliverables: reports, briefings,
applications, drafts, presentations and other finished artifacts. Create useful
subfolders as needed. Update the relevant Wiki page when work establishes durable
knowledge, decisions, status changes or next steps. Wiki/ remains authoritative.
See [[INDEX]] for routing and [[AGENTS]] for the shared workflow.
''',
    }


def add_commands(commands):
    for name in COMMANDS:
        command = commands.add_parser(name, help={
            'sync': 'Capture direct edits and reconcile delivered immutable history',
            'folder-status': 'Inspect folder history and conflicts without changing notes',
            'history': 'Read preserved direct-edit history',
            'resolve': 'Record an evidence-backed conflict resolution by this editing member',
            'delete': 'Record an explicit recoverable deletion; missing files alone are not deletes',
            'rename': 'Record an explicit recoverable rename',
            'migrate-folder': 'Plan or apply a backed-up migration from historical coordinator mode',
            'watch': 'Optional local history capture loop; no background AI or approval service',
            'recall': 'Search current Markdown with private indexing and bounded source-linked results',
            'show': 'Expand exact lines only when the source hash still matches',
            'context-packet': 'Read complete instructions, index and an authored section as one bounded packet',
            'memory-mcp': 'Serve read-only source-checked memory tools over local stdio (optional SDK)',
            'append-row': 'Atomically append one row to an existing Markdown table',
        }[name])
        command.add_argument('project', nargs='?', default='.', help='Selected folder; defaults to current directory')
        if name not in {'migrate-folder', 'recall', 'show', 'context-packet', 'memory-mcp', 'append-row'}:
            command.add_argument('--brief', action='store_true', help='Bounded summary without full per-note heads or excluded paths')
        command.add_argument('--state-dir', help='Existing private per-device state; otherwise discovered locally')
        if name in {'recall', 'show', 'context-packet', 'append-row'}:
            command.add_argument('--text', action='store_true', help='Concise plain-text output instead of versioned JSON')
        if name == 'recall':
            command.add_argument('query', help='Search words; quote phrases with spaces')
            command.add_argument('--include-raw', action='store_true')
            command.add_argument('--include-output', action='store_true')
            command.add_argument('--max-hits', type=int, default=5)
            command.add_argument('--max-bytes', type=int, default=2048)
            command.add_argument('--refresh', action='store_true', help='Recheck changed Markdown before searching; may wait up to five seconds')
            command.add_argument('--strategy', choices=('exact', 'hybrid'), default='exact',
                                 help='Exact terms (default) or fused lexical/title/explicit-link retrieval')
            command.add_argument('--after', help='Hybrid only: inclusive YYYY-MM-DD lower bound on dates in excerpts')
            command.add_argument('--before', help='Hybrid only: inclusive YYYY-MM-DD upper bound on dates in excerpts')
            command.add_argument('--with-receipts', action='store_true',
                                 help='Identify delivered passages for optional context-local reuse')
            command.add_argument('--known-evidence', action='append', default=[], metavar='RECEIPT',
                                 help='Omit an exact revalidated passage still retained in context; repeat up to 32 times')
        if name == 'context-packet':
            command.add_argument('--path', required=True, help='Explicit canonical source in the selected scope')
            command.add_argument('--heading', help='Exact unique ATX heading; includes all nested sections')
            command.add_argument('--max-bytes', type=int, default=8192)
            command.add_argument('--with-receipts', action='store_true')
            command.add_argument('--known-evidence', action='append', default=[], metavar='RECEIPT')
        if name == 'show':
            command.add_argument('--path', required=True)
            command.add_argument('--sha256', required=True)
            command.add_argument('--start', type=int, required=True)
            command.add_argument('--end', type=int, required=True)
            command.add_argument('--max-bytes', type=int, default=8192)
        if name == 'append-row':
            command.add_argument('--path', required=True)
            command.add_argument('--heading', required=True)
            row = command.add_mutually_exclusive_group(required=True)
            row.add_argument('--row', help='Single Markdown table row')
            row.add_argument('--row-file', help='Existing UTF-8 file containing one reviewed table row')
        if name in {'history', 'resolve', 'delete'}:
            command.add_argument('--path', required=name != 'history')
        if name == 'resolve':
            command.add_argument('--text-file', required=True, help='Reviewed UTF-8 resolution file; may be the locally edited note')
        if name in {'resolve', 'delete', 'rename'}:
            command.add_argument('--evidence', required=True)
        if name == 'rename':
            command.add_argument('--source', required=True)
            command.add_argument('--destination', required=True)
        if name == 'migrate-folder':
            command.add_argument('--backup-dir', required=True, help='Fresh private recovery directory outside shared storage')
            command.add_argument('--apply', action='store_true')
            command.add_argument('--replan', action='store_true', help='Preserve a superseded pre-cutover intent and use a fresh backup after newer work')
        if name == 'watch':
            command.add_argument('--interval', type=float, default=5)
            command.add_argument('--cycles', type=int, default=12, help='Bounded sync cycles; restart explicitly if more are needed')


def metadata(root):
    path = root / '.shared-memory.json'
    return workflow.json_file(path) if path.exists() else None


def is_folder(root):
    item = metadata(root)
    return isinstance(item, dict) and item.get('workflow') == 'folder'


def state_path(args, root):
    from .onboarding import default_state
    selected = workflow.private_path(args.state_dir, root) if getattr(args, 'state_dir', None) else default_state(root)
    if args.command == 'migrate-folder':
        return selected
    if not getattr(args, 'state_dir', None) or (selected / 'connection.json').exists():
        return workflow.private_path(selected / 'folder', root)
    return selected


def setup(args):
    from .folder import Folder, validate_vault_profile
    if not args.project.strip():
        raise ProductError(2, 'usage_error', 'Select a nonempty project path.')
    if getattr(args, 'content_mode', None) not in (None, 'markdown'):
        raise ProductError(3, 'content_mode', 'Direct folder workflow uses Markdown discovery; legacy content mode belongs to historical coordinator setup.')
    requested_type = getattr(args, 'vault_type', None)
    requested_folders = validate_project_folders(getattr(args, 'project_folder', None))
    if requested_folders and requested_type != 'project':
        raise ProductError(2, 'vault_profile', '--project-folder requires --vault-type project.')
    root = workflow.selected_root(args.project)
    state = state_path(args, root)
    item = metadata(root)
    pending_profile = workflow.json_file(state / 'initialization.json') if (state / 'initialization.json').exists() else None
    for profile_source in (item, pending_profile):
        if profile_source:
            validate_vault_profile(profile_source.get('vault_profile'))
    retained = (item or pending_profile or {}).get('vault_profile')
    if retained:
        if requested_type and requested_type != retained['type']:
            raise ProductError(3, 'vault_profile_mismatch', 'Existing vault profile is preserved; setup does not reclassify it.')
        if requested_folders and requested_folders != retained.get('project_folders', []):
            raise ProductError(3, 'vault_profile_mismatch', 'Existing project folders are preserved; setup does not reorganize them.')
    elif (item or pending_profile) and (requested_type not in (None, 'team') or requested_folders):
        raise ProductError(3, 'vault_profile_mismatch', 'Existing unclassified history is preserved; profile changes require an explicit separate migration.')
    vault_type = retained['type'] if retained else requested_type or 'team'
    project_folders = retained.get('project_folders', []) if retained else (
        (requested_folders or ['Knowledge', 'Planning', 'Deliverables']) if vault_type == 'project' else [])
    vault_profile = retained or {'type': vault_type, 'project_folders': project_folders}
    if item and args.expected_project_id and args.expected_project_id != item.get('project_id'):
        raise ProductError(3, 'identity_mismatch', 'The selected folder differs from the explicitly expected project identity.')
    if item and item.get('workflow') != 'folder':
        raise ProductError(4, 'migration_required',
            'Existing coordinator history is preserved. Use migrate-folder with a private backup directory to convert it; do not initialize a replacement.',
            data={'workflow': 'historical_coordinator', 'project_id': item.get('project_id'), 'next': 'migrate-folder'})
    if any(getattr(args, k, None) for k in ('endpoint', 'database', 'token_file', 'ca_file')):
        raise ProductError(3, 'folder_access', 'Folder workflow uses existing provider/OS access, not coordinator credentials. Use --workflow coordinator only for historical projects.')
    if ((state / 'folder-migration.json').exists() or (state.parent / 'folder-migration.json').exists()) and not item:
        raise ProductError(4, 'migration_incomplete', 'Resume the recorded migrate-folder operation; existing history must not be reset.')
    if (state / 'folder.json').exists():
        saved = workflow.json_file(state / 'folder.json')
        if item is None and (state / 'initialization.json').exists():
            intent = workflow.json_file(state / 'initialization.json')
            Folder.initialize(root, state, **saved['author'], provider=intent['provider'], project_id=intent['project_id'])
            item = metadata(root)
        folder = Folder(root, state)
        if args.provider and item.get('provider') != args.provider:
            raise ProductError(3, 'provider_mismatch', 'Keep one provider per physical project; existing binding is unchanged.')
        # Identity and read-only grants are saved, never silently widened by setup.
        saved = workflow.json_file(state / 'folder.json')
        if getattr(args, 'read_only', False) and not saved.get('readonly'):
            raise ProductError(3, 'readonly_mismatch', 'This binding is writable. Use a separate explicitly read-only binding; setup does not silently ignore or change access intent.')
        for field in ('actor', 'person', 'agent'):
            if getattr(args, field, None) and saved.get('author', {}).get(field) != getattr(args, field):
                raise ProductError(3, 'identity_mismatch', 'Keep this device identity or use a separate private state directory.')
        if (state / 'initialization.json').exists():
            folder = Folder.initialize(root, state, **saved['author'], provider=item['provider'], project_id=item['project_id'])
        elif not (state / 'baseline.json').exists():
            folder = Folder.attach(root, state, **saved['author'], expected_project_id=item['project_id'], readonly=saved['readonly'])
        elif not saved['readonly']:
            folder.sync()
        route = 'resume_folder'
    else:
        try:
            person = getpass.getuser()
        except (KeyError, OSError):
            person = 'Local user'
        pending = workflow.json_file(state / 'initialization.json') if (state / 'initialization.json').exists() else None
        if pending:
            for field in ('actor', 'person', 'agent'):
                if getattr(args, field, None) and pending['author'][field] != getattr(args, field):
                    raise ProductError(3, 'identity_mismatch', 'Resume the original initialization identity.')
            if args.provider and args.provider != pending['provider']:
                raise ProductError(3, 'provider_mismatch', 'Resume the original initialization provider.')
        identity = {'actor': args.actor or 'device-' + secrets.token_hex(8),
                    'person': args.person or person, 'agent': args.agent or 'Local agent'}
        if pending:
            identity = pending['author']
        readonly = getattr(args, 'read_only', False)
        if item and (state.parent / 'connection.json').exists():
            from .folder_migration import legacy_identity
            _, legacy, member, _, _, _, _ = legacy_identity(state.parent)
            if legacy['project_id'] != item['project_id']:
                raise ProductError(3, 'identity_mismatch', 'Prior private membership belongs to another project.')
            readonly = readonly or member['role'] == 'reader'
            if not args.actor:
                identity = {'actor': member['actor'], 'person': member['human'], 'agent': member['agent']}
        if item:
            if args.provider and item.get('provider') != args.provider:
                raise ProductError(3, 'provider_mismatch', 'Joining retains the selected project provider.')
            folder = Folder.attach(root, state, expected_project_id=args.expected_project_id or item['project_id'],
                                   readonly=readonly, **identity)
            route = 'join_folder'
        else:
            if args.expected_project_id:
                raise ProductError(4, 'folder_not_delivered', 'Expected project metadata/history has not arrived. Do not create a new project identity.')
            if any((base / name).exists() for base in (state, state.parent) for name in ('connection.json', 'setup-intent.json')):
                raise ProductError(4, 'existing_history', 'Existing private coordinator history needs reviewed migration, not fresh setup.')
            seeds = new_workspace_files(root, vault_type, project_folders) if not pending else None
            folder = Folder.initialize(root, state, provider=args.provider or (pending['provider'] if pending else 'local'), readonly=readonly,
                                       project_id=pending['project_id'] if pending else None,
                                       initial_files=seeds, materialize_initial=seeds is not None,
                                       vault_profile=vault_profile if not pending else pending.get('vault_profile'), **identity)
            route = 'new_folder'
    result = folder.status()
    return {'workflow': 'folder', 'route': route, 'project_id': result['project_id'],
            'vault_type': vault_type, 'project_folders': project_folders,
            'state_dir': str(state), 'status': result, 'readiness': result.get('readiness', 'inspect_status'),
            'next': 'Edit notes and verify local readback. Use configured capture, or sync once when absent. Leave background cloud uploads alone.',
            'provider_delivery': 'unverified', 'coordinator_required': False, 'approval_queue': False}


def dispatch(bundle, args):
    from .folder import Folder
    if args.command in {'recall', 'show', 'context-packet'}:
        from . import recall as retrieval
        def selected_read():
            # Bound even selected-root path checks, which may call a cloud
            # provider before the note read begins.
            selected = workflow.selected_root(args.project)
            if args.command == 'context-packet':
                from .context_packet import context
                return context(selected, args.path, args.heading, max_bytes=args.max_bytes,
                               with_receipts=args.with_receipts, known_evidence=args.known_evidence)
            if args.command == 'recall':
                private_state = state_path(args, selected)
                return retrieval.recall(selected, private_state, args.query,
                                        raw=args.include_raw, output=args.include_output,
                                        max_hits=args.max_hits, max_bytes=args.max_bytes,
                                        refresh=args.refresh, strategy=args.strategy,
                                        after=args.after, before=args.before,
                                        with_receipts=getattr(args, 'with_receipts', False),
                                        known_evidence=getattr(args, 'known_evidence', ()))
            return retrieval.show(selected, args.path, args.sha256, args.start,
                                  args.end, max_bytes=args.max_bytes)
        return retrieval.bounded_cli(selected_read, command=args.command,
                                     raw=getattr(args, 'include_raw', False),
                                     output=getattr(args, 'include_output', False),
                                     max_bytes=args.max_bytes)
    root = workflow.selected_root(args.project)
    state = state_path(args, root)
    if args.command == 'append-row':
        from . import recall as retrieval
        folder = Folder(root, state)
        folder._writable()
        if args.row_file:
            row_path = workflow.private_path(args.row_file, root)
            if not row_path.is_file() or row_path.stat().st_size > 16384:
                raise ProductError(3, 'recall_row', 'Choose an existing bounded private row file.')
            row = row_path.read_text(encoding='utf-8').rstrip('\r\n')
        else:
            row = args.row
        return retrieval.append_row(root, args.path, args.heading, row)
    if args.command == 'migrate-folder':
        from .folder_migration import migrate
        return migrate(root, state, args.backup_dir, apply=args.apply, replan=args.replan)
    folder = Folder(root, state)
    command = args.command
    if command in {'folder-status', 'status', 'receipt', 'team-status', 'provider-check'}:
        return folder.status()
    if command == 'sync':
        return folder.sync()
    if command == 'history':
        return folder.history(args.path)
    if command == 'resolve':
        path = Path(args.text_file).expanduser().absolute()
        from .path_safety import unsafe_ancestor
        if unsafe_ancestor(path) is not None or not path.is_file() or path.stat().st_size > 10 * 1024 * 1024:
            raise ProductError(3, 'resolution_file', 'Choose a regular bounded UTF-8 resolution file.')
        return folder.resolve(args.path, path.read_bytes().decode('utf-8'), args.evidence)
    if command == 'delete':
        return folder.delete(args.path, args.evidence)
    if command == 'rename':
        return folder.rename(args.source, args.destination, args.evidence)
    if command == 'watch':
        if not 0.1 <= args.interval <= 3600 or not 1 <= args.cycles <= 100000:
            raise ProductError(3, 'watch_bounds', 'Use interval 0.1–3600 seconds and 1–100000 cycles.')
        result = None
        for index in range(args.cycles):
            result = folder.sync()
            if index + 1 < args.cycles:
                time.sleep(args.interval)
        return {'cycles': args.cycles, 'last': result, 'background_agent': False}
    raise ProductError(2, 'usage_error', 'Unknown folder command.')


def brief(data):
    """Bound routine output while preserving every actionable condition count."""
    result = {key: data[key] for key in (
        'project_id', 'workflow', 'readiness', 'readonly', 'provider_delivery',
        'event_count', 'recovery_pending') if key in data}
    if data.get('skipped_paths', {}).get('count'):
        result['skipped_paths'] = data['skipped_paths']
    if 'heads' in data:
        result['tracked_files'] = len(data['heads'])
    fields = ('conflicts', 'deferred_events', 'invalid_events', 'missing_files',
              'local_changes', 'partial_files', 'excluded', 'path_collisions',
              'history_copies', 'rename_divergences', 'provider_conflict_copies',
              'deferred_materialization', 'warnings')
    result['counts'] = {key: len(data[key]) for key in fields if data.get(key)}
    issues = {key: data[key][:3] for key in fields
              if key != 'excluded' and data.get(key)}
    if issues:
        # Report counts even when unusually large/pathological details are omitted.
        result['attention'] = {key: [str(item)[:240] for item in values]
                               for key, values in issues.items()}
        result['details'] = 'Run the same command without --brief for complete details.'
    if 'last' in data:
        result.update(cycles=data['cycles'], last=brief(data['last']))
    if data.get('provider_duplicate_bytes_unverified'):
        result['provider_duplicate_bytes_unverified'] = data['provider_duplicate_bytes_unverified']
    if data.get('scan_timeout_count'):
        result['scan_timeout_count'] = data['scan_timeout_count']
    if isinstance(data.get('scan_coverage'), dict):
        result['scan_coverage'] = {key: data['scan_coverage'][key] for key in (
            'eligible', 'covered', 'deferred', 'read_this_run', 'read_limit',
            'audit', 'full_audit_at', 'index_rebuilt') if key in data['scan_coverage']}
    if 'events' in data:
        result['event_count'] = len(data['events'])
        result['details'] = 'Run history without --brief to read event contents.'
    return result
