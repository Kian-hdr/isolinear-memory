"""Direct editing with decentralized, immutable history and private recovery.

Only provider/OS permissions establish access. Author labels are self-asserted.
A sync captures present local changes against its saved causal baseline BEFORE
considering incoming events. Absence is never an implicit delete. No background
worker can preserve a provider overwrite that occurred before local capture.
"""
from __future__ import annotations

import contextlib
import errno
import functools
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import threading
import time
import uuid

from . import PRODUCT_VERSION
from .errors import ProductError
from .path_safety import absolute_path, unsafe_ancestor, is_link_or_reparse
from .engine import validate_path, validate_files, MAX_FILE_BYTES, MAX_SNAPSHOT_BYTES
from .knowledge import PRIVATE, PRIVATE_FILES
from .folder_merge import views

MANIFEST = '.shared-memory.json'
HISTORY = '.shared-memory'
VERSION = 1
MAX_EVENTS = 20000
MAX_HISTORY_BYTES = 512 * 1024 * 1024
MAX_EVENT_BYTES = 128 * 1024 * 1024
MAX_SCAN_INDEX_BYTES = 8 * 1024 * 1024
SCAN_READ_LIMIT = 500
SCAN_AUDIT_INTERVAL_SECONDS = 24 * 60 * 60
SCAN_WALL_SECONDS = 45
SCAN_FILE_SECONDS = 3
SCAN_PENDING_READ_LIMIT = 8
SCAN_SECOND_PASS_RESERVE = 8
SCAN_METADATA_SECONDS = 10
SCAN_STAT_SECONDS = 2
SCAN_EVENT_SECONDS = 3
HASH = re.compile(r'[0-9a-f]{64}')
PROVIDERS = {'local', 'google-drive', 'onedrive', 'icloud', 'self-hosted', 'nextcloud'}
LIMITATION = 'Provider overwrites before local capture cannot be recovered by this engine; sync is not a provider receipt or an atomic filesystem transaction.'
LOCK_TIMEOUT_SECONDS = 10
LOCK_POLL_SECONDS = 0.05


def fail(code, message, exit_code=3):
    raise ProductError(exit_code, 'folder_' + code, message) from None


def io_message(phase, error):
    """Describe an I/O failure without paths, note text or exception strings."""
    os_code = errno.errorcode.get(error.errno, 'UNKNOWN') if isinstance(error, OSError) else 'UNKNOWN'
    return (f'Folder operation failed during {phase} ({type(error).__name__}, {os_code}); '
            'preserve history and private recovery state.')


@contextlib.contextmanager
def io_phase(name):
    try:
        yield
    except OSError as error:
        fail('io', io_message(name, error), 5)


def checked(method):
    @functools.wraps(method)
    def run(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except ProductError:
            raise
        except (OSError, ValueError, UnicodeError, KeyError, TypeError) as exc:
            fail('io', io_message(method.__name__, exc), 5)
    return run


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def byte_hash(value):
    return None if value is None else hashlib.sha256(value.encode('utf-8')).hexdigest()


def file_stamp(path):
    info = os.stat(path, follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode):
        fail('partial_file', 'Expected a stable regular local file.', 4)
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def scan_metadata_reuse_allowed():
    # Windows st_ctime is creation time, not a reliable in-place change clock.
    return os.name != 'nt'


def safe(value):
    if unsafe_ancestor(value) is not None:
        fail('unsafe_path', 'Symbolic links and reparse points cannot establish project or state boundaries.')
    return absolute_path(value).resolve()


def private_path(value, root):
    path = safe(Path(value).expanduser())
    lower = str(path).replace('\\', '/').casefold() + '/'
    if (path == root or path.is_relative_to(root) or root.is_relative_to(path) or str(path).startswith('\\\\')
            or any(s in lower for s in ('/cloudstorage/', '/mobile documents/', '/nextcloud/', 'onedrive', 'googledrive', 'google drive', 'dropbox'))):
        fail('private_path', 'Device state must be in a separate private local, non-synchronized directory tree.')
    return path


def fsync_dir(path):
    try:
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        if os.name != 'nt':
            raise


def atomic(path, data, immutable=False):
    safe(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix='.folder-write-', dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        if immutable:
            try:
                os.link(temp, path)
            except FileExistsError:
                if read_bytes(path, max(len(data), MAX_EVENT_BYTES)) != data:
                    fail('immutable_collision', 'Existing immutable history differs; retain both copies and investigate.')
        else:
            os.replace(temp, path)
        fsync_dir(path.parent)
    finally:
        temp.unlink(missing_ok=True)


def read_bytes(path, maximum=MAX_EVENT_BYTES):
    safe(path)
    named_before = os.stat(path, follow_symlinks=False)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            fail('limit', 'Expected a bounded regular local file.')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            result = stream.read(maximum + 1)
        if len(result) > maximum:
            fail('limit', 'Local data exceeds its byte bound.')
        after = os.fstat(fd)
        named = os.stat(path, follow_symlinks=False)
        stamp = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        # Windows path stat preserves creation-time ctime for compatibility,
        # while fstat may expose ChangeTime. Compare timestamps within the same
        # API only; device/file ID and size still bind the open descriptor to the
        # checked pathname. The initial pathname check also catches replacement
        # between inspection and open, even when replacement bytes have equal size.
        file_identity = lambda value: (value.st_dev, value.st_ino)
        stable = (stamp(info) == stamp(after) and stamp(named_before) == stamp(named)
                  and file_identity(after) == file_identity(named)
                  and stat.S_ISREG(named_before.st_mode) and stat.S_ISREG(named.st_mode))
        if not stable:
            fail('partial_file', 'File changed while being read; defer until stable local bytes are available.', 4)
        if len(result) == after.st_size == named.st_size:
            return result
        # Some macOS FileProvider files expose a stable zero byte size through
        # both pathname and descriptor stat while an opened descriptor returns
        # real content. Accept only two identical complete reads from that same
        # inode with unchanged descriptor and no-follow pathname metadata.
        if named.st_size == 0 and result and after.st_size in (0, len(result)):
            os.lseek(fd, 0, os.SEEK_SET)
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                second = stream.read(maximum + 1)
            verified_fd = os.fstat(fd)
            verified_name = os.stat(path, follow_symlinks=False)
            if (second == result and stamp(after) == stamp(verified_fd)
                    and stamp(named) == stamp(verified_name)
                    and file_identity(verified_fd) == file_identity(verified_name)
                    and stat.S_ISREG(verified_name.st_mode)):
                return result
        fail('partial_file', 'File changed while being read; defer until stable local bytes are available.', 4)
    finally:
        os.close(fd)


def read_control_bytes(path, maximum, label):
    """Retry a transient provider metadata change on a required control file."""
    pending = []
    for attempt in range(3):
        try:
            completed, value = bounded_read_only(lambda: read_bytes(path, maximum), SCAN_EVENT_SECONDS, pending)
            if completed:
                return value
        except ProductError as error:
            if error.code != 'folder_partial_file':
                raise
        if attempt < 2:
            time.sleep(0.05)
    fail('control_unstable', f'{label} changed during bounded reads; preserve local state and retry when the provider settles.', 4)


def bounded_read_only(action, timeout, pending):
    """Bound a read-only OS call; a late daemon result is never consumed."""
    pending[:] = [thread for thread in pending if thread.is_alive()]
    if len(pending) >= SCAN_PENDING_READ_LIMIT:
        return False, None
    done = threading.Event()
    result = {}

    def worker():
        try:
            result['value'] = action()
        except Exception as error:
            result['error'] = error
        finally:
            done.set()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    if not done.wait(timeout):
        pending.append(thread)
        return False, None
    if 'error' in result:
        raise result['error']
    return True, result['value']


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                fail('invalid', 'Duplicate JSON keys are not valid history.')
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: fail('invalid', 'Invalid JSON number.'))


def identity(actor, person, agent):
    if not isinstance(actor, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', actor):
        fail('identity', 'Use a stable portable actor label of 1 to 128 characters.')
    if any(not isinstance(s, str) or not s.strip() or len(s.encode('utf-8')) > 1024 for s in (person, agent)):
        fail('identity', 'Person and agent labels must be nonempty bounded text.')
    return {'actor': actor, 'person': person, 'agent': agent}


def path_name(path):
    validate_path(path)
    return path


def evidence_text(value):
    if not isinstance(value, str) or not value.strip() or len(value.encode('utf-8')) > 16384:
        fail('evidence', 'A bounded nonempty explanation is required.')
    return value


def validate_manifest(value):
    if (not isinstance(value, dict) or value.get('format_version') != 3 or value.get('workflow') != 'folder'
            or value.get('provider') not in PROVIDERS):
        fail('format', 'This folder requires the matching format-3 direct-folder runtime.')
    if str(uuid.UUID(value.get('project_id'))) != value.get('project_id'):
        fail('identity', 'Project identity must be a canonical UUID.')
    return value


def validate_event(event, project_id):
    fields = {'format', 'project_id', 'kind', 'author', 'parents', 'base', 'changes', 'evidence', 'rename'}
    if not isinstance(event, dict) or set(event) != fields or event['format'] != VERSION or event['project_id'] != project_id:
        fail('invalid_event', 'Event envelope or project identity is invalid.')
    if event['kind'] not in {'initial', 'edit', 'resolve', 'delete', 'rename'}:
        fail('invalid_event', 'Unknown folder event kind.')
    author = event['author']
    if not isinstance(author, dict) or set(author) != {'actor', 'person', 'agent'}:
        fail('invalid_event', 'Invalid self-asserted author descriptor.')
    identity(**author)
    evidence_text(event['evidence'])
    changes = event['changes']
    if not isinstance(changes, dict) or not changes or len(changes) > 10000:
        fail('invalid_event', 'Events require bounded explicit changes.')
    validate_files({p: text for p, text in changes.items() if text is not None})
    if set(event['parents']) != set(changes) or set(event['base']) != set(changes):
        fail('invalid_event', 'Every changed path requires an explicit causal base.')
    for path, text in changes.items():
        path_name(path)
        parents = event['parents'][path]
        if not isinstance(parents, list) or len(parents) > 256 or parents != sorted(set(parents)) or any(not isinstance(p, str) or not HASH.fullmatch(p) for p in parents):
            fail('invalid_event', 'Invalid parent-head set.')
        if text is not None and not isinstance(text, str):
            fail('invalid_event', 'Changes contain only exact UTF-8 text or explicit deletion.')
    validate_files({p: text for p, text in event['base'].items() if text is not None})
    if event['kind'] == 'delete' and (len(changes) != 1 or next(iter(changes.values())) is not None):
        fail('invalid_event', 'Delete events remove one explicit path.')
    if event['kind'] == 'rename':
        rename = event['rename']
        if not isinstance(rename, dict) or set(rename) != {'source', 'destination'} or rename['source'] == rename['destination']:
            fail('invalid_event', 'Rename requires distinct source and destination.')
        if set(changes) != {rename['source'], rename['destination']} or changes[rename['source']] is not None or not isinstance(changes[rename['destination']], str):
            fail('invalid_event', 'Rename must preserve a source version at its destination.')
    elif event['rename'] is not None:
        fail('invalid_event', 'Only rename events carry a rename descriptor.')
    return event


class Folder:
    @checked
    def __init__(self, root, state):
        self.root = safe(Path(root).expanduser())
        if not self.root.is_dir():
            fail('missing', 'Choose an existing physical project folder.', 5)
        self.state = private_path(state, self.root)
        self.manifest = validate_manifest(parse(read_control_bytes(self.root / MANIFEST, 65536, 'Workspace manifest')))
        self.project_id = self.manifest['project_id']
        self.config = parse(read_control_bytes(self.state / 'folder.json', 65536, 'Private folder binding'))
        if (self.config.get('format') != VERSION or self.config.get('root') != str(self.root)
                or self.config.get('project_id') != self.project_id or type(self.config.get('readonly')) is not bool):
            fail('binding', 'Private device state belongs to another project or folder.')
        identity(**self.config['author'])
        self.shared = safe(self.root / HISTORY)
        self._excluded, self._partial = [], []

    @classmethod
    @checked
    def initialize(cls, root, state, actor, person, agent, provider='local', project_id=None,
                   readonly=False, initial_files=None, migration_origin=None, materialize_initial=False):
        root = safe(Path(root).expanduser()); state = private_path(state, root)
        author = identity(actor, person, agent)
        if readonly:
            fail('readonly', 'Read-only devices may attach to an existing project, not initialize history.', 4)
        if provider not in PROVIDERS:
            fail('provider', 'Select one explicit supported storage route.')
        if not root.is_dir():
            fail('missing', 'Choose an existing physical project folder.', 5)
        if (root / MANIFEST).exists():
            existing = cls(root, state)
            if existing.config['author'] != author or existing.manifest['provider'] != provider or (project_id and project_id != existing.project_id):
                fail('binding', 'Existing project and author binding cannot be replaced.')
            if (state / 'baseline.json').exists():
                existing.sync()
                return existing
            if not (state / 'initialization.json').is_file():
                fail('state_missing', 'Initialization baseline is missing without a recoverable original intent.', 4)
        if state.exists() and any(state.iterdir()):
            # A durable initialization record can resume only its exact saved binding.
            pending = state / 'initialization.json'
            if not pending.is_file():
                fail('state_exists', 'Existing private state cannot be adopted as a new project.')
            intent = parse(read_bytes(pending))
            if intent['root'] != str(root) or intent['author'] != author or intent['provider'] != provider or (project_id and intent['project_id'] != project_id):
                fail('binding', 'Retry the original initialization inputs.')
        else:
            identifier = project_id or str(uuid.uuid4())
            if str(uuid.UUID(identifier)) != identifier:
                fail('identity', 'Project identity must be a canonical UUID.')
            if (root / HISTORY).exists():
                fail('history_exists', 'An existing history directory requires its original project identity.')
            # Inspect before creating state. A minimal unbound object uses the same scan.
            probe = object.__new__(cls); probe.root = root; probe._excluded = []; probe._partial = []
            discovered = probe._scan(set(initial_files or {}))
            if probe._partial:
                fail('partial', 'Initial Markdown is not fully available as stable local UTF-8 text.', 4)
            files = validate_files(initial_files if initial_files is not None else discovered)
            origin = migration_origin
            if origin is not None:
                allowed = {'project_id', 'revision', 'files_hash', 'backup_hash'}
                if not isinstance(origin, dict) or set(origin) - allowed or len(canonical(origin)) > 4096:
                    fail('migration', 'Migration provenance may contain only public project/revision/hash fields.')
                if ('project_id' in origin and str(uuid.UUID(origin['project_id'])) != origin['project_id']) or (
                        'revision' in origin and (type(origin['revision']) is not int or origin['revision'] < 0)):
                    fail('migration', 'Migration origin requires an exact project UUID and nonnegative revision.')
                if any(k.endswith('hash') and (not isinstance(v, str) or not HASH.fullmatch(v)) for k, v in origin.items()):
                    fail('migration', 'Migration digests must be SHA-256 values.')
            intent = {'root': str(root), 'project_id': identifier, 'author': author, 'provider': provider,
                      'files': files, 'migration_origin': origin, 'materialize_initial': materialize_initial}
            atomic(state / 'initialization.json', canonical(intent), immutable=True)
        manifest = {'format_version': 3, 'product_version': PRODUCT_VERSION, 'workflow': 'folder',
                    'project_id': intent['project_id'], 'provider': provider}
        if intent['migration_origin'] is not None:
            manifest['migration_origin'] = intent['migration_origin']
        config = {'format': VERSION, 'root': str(root), 'project_id': intent['project_id'], 'author': author, 'readonly': False}
        atomic(state / 'folder.json', canonical(config), immutable=True)
        atomic(root / MANIFEST, canonical(manifest), immutable=True)
        folder = cls(root, state)
        with folder._lock():
            if not (state / 'baseline.json').exists():
                baseline = {}
                if intent['files']:
                    event = folder._event('initial', intent['files'], {}, 'Initial selected-folder snapshot')
                    event_id = folder._emit(event)
                    # Newly seeded instructions have never existed locally. Leave
                    # them unobserved until the normal journal materializes them;
                    # otherwise the provider-missing guard correctly skips them.
                    # Existing initialization/migration retains its old baseline.
                    if not intent.get('materialize_initial', False):
                        baseline = {p: {'heads': [event_id], 'text': text} for p, text in intent['files'].items()}
                folder._save_baseline(baseline)
        folder.sync()
        return folder

    @classmethod
    @checked
    def attach(cls, root, state, actor, person, agent, expected_project_id, readonly=False):
        root = safe(Path(root).expanduser()); state = private_path(state, root)
        manifest = validate_manifest(parse(read_bytes(root / MANIFEST, 65536)))
        if manifest['project_id'] != expected_project_id:
            fail('binding', 'Selected folder differs from the expected project identity.')
        if type(readonly) is not bool:
            fail('readonly', 'Read-only mode must be explicit true or false.')
        author = identity(actor, person, agent)
        if (state / 'folder.json').exists():
            folder = cls(root, state)
            if folder.config['author'] != author or folder.config['readonly'] != readonly:
                fail('binding', 'Existing device identity or access mode differs.')
            if (state / 'baseline.json').exists():
                return folder
        elif state.exists() and any(state.iterdir()):
            fail('state_exists', 'Choose this device’s own unused private state.')
        probe = object.__new__(cls); probe.root = root; probe._excluded = []; probe._partial = []
        probe._scan(set())
        atomic(state / 'folder.json', canonical({'format': VERSION, 'root': str(root), 'project_id': expected_project_id,
                                                'author': author, 'readonly': readonly}), immutable=True)
        folder = cls(root, state)
        with folder._lock():
            # No claimed ancestry for preexisting unmatched notes on first attach.
            events, _, _ = folder._load_events(cache=False)
            current_views = views(events)
            local = folder._scan(set(current_views))
            baseline = {p: {'heads': v['heads'], 'text': v['text']} for p, v in current_views.items()
                        if not v['conflict'] and local.get(p) == v['text']}
            folder._save_baseline(baseline)
        if not readonly:
            folder.sync()
        return folder

    @contextlib.contextmanager
    def _lock(self):
        with io_phase('lock_prepare'):
            safe(self.state)
            self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
            path = self.state / '.folder.lock'; safe(path)
            stream = open(path, 'a+b')
        with stream:
            if os.name == 'nt':
                import msvcrt
                with io_phase('lock_prepare'):
                    stream.seek(0)
                    if not stream.read(1):
                        stream.write(b'0'); stream.flush()
            else:
                import fcntl
            deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
            while True:
                try:
                    if os.name == 'nt':
                        stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as error:
                    if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        fail('io', io_message('lock_acquire', error), 5)
                    if time.monotonic() >= deadline:
                        fail('lock_timeout', 'Private folder state remained busy; retry after the other operation finishes.', 5)
                    time.sleep(LOCK_POLL_SECONDS)
            try:
                yield
            finally:
                with io_phase('lock_release'):
                    if os.name == 'nt':
                        stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _progress(self, phase, count=None):
        """Opt-in, private sync phase marker with no note names or contents."""
        self._sync_phase = phase
        if os.environ.get('SHARED_MEMORY_CAPTURE_PHASES') != '1':
            return
        if not re.fullmatch(r'[a-z_]{1,48}', phase):
            return
        record = {'format': 1, 'phase': phase, 'updated_at': time.time(), 'pid': os.getpid()}
        if type(count) is int and count >= 0:
            record['count'] = count
        try:
            atomic(self.state / 'capture-progress.json', canonical(record))
        except (OSError, ProductError):
            # Observability must not change the sync outcome.
            pass

    def _writable(self):
        if self.config['readonly']:
            fail('readonly', 'This device is configured read-only; no project or shared-history writes are permitted.', 4)

    def _target(self, name):
        path_name(name)
        path = self.root / name
        safe(path)
        return path

    def _read(self, name):
        path = self._target(name)
        if not path.exists():
            return None
        return read_bytes(path, MAX_FILE_BYTES).decode('utf-8')

    def _load_scan_index(self):
        """Load a rebuildable private hint; never treat it as history authority."""
        path = self.state / 'scan-index.json'
        self._scan_index_rebuilt = False
        try:
            record = parse(read_bytes(path, MAX_SCAN_INDEX_BYTES))
            if (not isinstance(record, dict) or record.get('format') != 1
                    or record.get('project_id') != self.project_id
                    or record.get('checksum') != digest({k: v for k, v in record.items() if k != 'checksum'})):
                raise ValueError()
            entries = record.get('entries')
            if not isinstance(entries, dict) or len(entries) > 100000:
                raise ValueError()
            for name, item in entries.items():
                path_name(name)
                if (not isinstance(item, dict) or set(item) != {'stamp', 'hash', 'verified_at'}
                        or not isinstance(item['stamp'], list) or len(item['stamp']) != 5
                        or any(type(value) is not int or value < 0 for value in item['stamp'])
                        or not isinstance(item['hash'], str) or not HASH.fullmatch(item['hash'])
                        or not isinstance(item['verified_at'], (int, float)) or item['verified_at'] < 0):
                    raise ValueError()
            for key in ('audit_started_at', 'full_audit_at'):
                value = record.get(key)
                if value is not None and (not isinstance(value, (int, float)) or value < 0):
                    raise ValueError()
            record.pop('checksum')
        except FileNotFoundError:
            record = {'format': 1, 'project_id': self.project_id, 'entries': {},
                      'audit_started_at': time.time(), 'full_audit_at': None}
        except (OSError, ProductError, ValueError, KeyError, TypeError):
            self._scan_index_rebuilt = True
            record = {'format': 1, 'project_id': self.project_id, 'entries': {},
                      'audit_started_at': time.time(), 'full_audit_at': None}
        now = time.time()
        full = record['full_audit_at']
        if record['audit_started_at'] is None and (full is None or not 0 <= now - full < SCAN_AUDIT_INTERVAL_SECONDS):
            record['audit_started_at'] = now
        return record

    def _save_scan_index(self, record):
        value = dict(record)
        value['checksum'] = digest(value)
        raw = canonical(value)
        if len(raw) > MAX_SCAN_INDEX_BYTES:
            fail('limit', 'Private scan index exceeds its byte bound.')
        atomic(self.state / 'scan-index.json', raw)

    def _timed_stable_read(self, relative, target):
        """Bound one cloud-backed read without letting a late result enter history."""
        self._pending_scan_reads = [thread for thread in self._pending_scan_reads if thread.is_alive()]
        if len(self._pending_scan_reads) >= self._active_pending_limit:
            return 'saturated', None
        remaining = self._scan_deadline - time.monotonic()
        if remaining <= 0:
            return 'budget', None
        done = threading.Event()
        outcome = {}

        def read():
            try:
                outcome['value'] = (self._read(relative), file_stamp(target))
            except Exception as error:
                outcome['error'] = error
            finally:
                done.set()

        thread = threading.Thread(target=read, daemon=True)
        thread.start()
        if not done.wait(min(SCAN_FILE_SECONDS, remaining)):
            self._pending_scan_reads.append(thread)
            return 'timeout', None
        if 'error' in outcome:
            raise outcome['error']
        return 'ok', outcome['value']

    def _enumerate_scan(self, required):
        """Read-only traversal; safe to abandon if a provider metadata call stalls."""
        excluded, candidates = [], []
        skipped = {'count': 0, 'samples': []}
        scanned = 0
        safe(self.root)
        for directory, dirs, names in os.walk(self.root, followlinks=False):
            safe(directory)
            if Path(directory) != self.root and any(name.casefold() == MANIFEST for name in names):
                excluded.append(Path(directory).relative_to(self.root).as_posix())
                dirs.clear()
                continue
            for name in list(dirs):
                relative = (Path(directory) / name).relative_to(self.root).as_posix()
                reserved = any(part.casefold() == 'coordination' or part.casefold() in PRIVATE or part.startswith('.')
                               for part in Path(relative).parts)
                linked = is_link_or_reparse(Path(directory) / name)
                if (reserved or linked) and not any(p.startswith(relative + '/') for p in required):
                    dirs.remove(name); excluded.append(relative)
                else:
                    safe(Path(directory) / name)
            for name in names:
                scanned += 1
                relative = (Path(directory) / name).relative_to(self.root).as_posix()
                private_ancestor = any(part.startswith('.') or part.casefold() in PRIVATE or part.casefold() == 'coordination'
                                       for part in Path(relative).parts[:-1])
                if relative not in required and (private_ancestor or name.startswith('.')
                                                or name.casefold() in PRIVATE | PRIVATE_FILES
                                                or Path(name).suffix.casefold() not in {'.md', '.markdown'}
                                                or is_link_or_reparse(Path(directory) / name)):
                    excluded.append(relative); continue
                try:
                    path_name(relative)
                except ProductError as exc:
                    portable_errors = {
                        'Project paths must use Unicode NFC normalization.',
                        'Path contains a name unsupported on Windows.',
                        'Path contains a reserved Windows device name.',
                    }
                    if relative in required or exc.code != 'engine_invalid' or str(exc) not in portable_errors:
                        raise
                    excluded.append(relative)
                    skipped['count'] += 1
                    if len(skipped['samples']) < 3:
                        skipped['samples'].append({'path': relative[:240], 'reason': str(exc)})
                    continue
                candidates.append((relative, Path(directory) / name))
        return candidates, excluded, skipped, scanned

    def _known_scan_candidates(self, required):
        """Recover bounded capture from known paths when broad provider listing stalls.

        This is deliberately incomplete: an unlisted new file cannot be inferred
        absent. Check each parent for a nested project before inspecting a known
        path, and defer that path if the provider cannot answer the check.
        """
        candidates, unavailable = [], []
        parent_state = {}
        known = sorted(set(required) | set(self._scan_index_work['entries']))
        for relative in known:
            path_name(relative)
            parts = Path(relative).parts
            blocked = False
            for depth in range(1, len(parts)):
                parent = self.root.joinpath(*parts[:depth])
                if parent not in parent_state:
                    def inspect(directory=parent):
                        safe(directory)
                        with os.scandir(directory) as children:
                            return any(child.name.casefold() == MANIFEST for child in children)
                    remaining = self._scan_deadline - time.monotonic()
                    if remaining <= 0:
                        parent_state[parent] = None
                    else:
                        try:
                            complete, nested = bounded_read_only(
                                inspect, min(SCAN_STAT_SECONDS, remaining), self._pending_metadata_reads)
                            parent_state[parent] = nested if complete else None
                        except OSError:
                            parent_state[parent] = None
                if parent_state[parent] is not False:
                    blocked = True
                    break
            if blocked:
                unavailable.append(relative)
            else:
                candidates.append((relative, self.root / relative))
        return candidates, unavailable

    def _scan(self, required, *, incremental=False, baseline=None):
        self._partial = []
        files = {}
        progress_stage = getattr(self, '_sync_phase', 'scan')
        if incremental:
            self._scan_pass += 1
            self._active_pending_limit = (SCAN_PENDING_READ_LIMIT +
                                          (SCAN_SECOND_PASS_RESERVE if self._scan_pass > 1 else 0))
            completed, enumeration = bounded_read_only(
                lambda: self._enumerate_scan(required), SCAN_METADATA_SECONDS, self._pending_metadata_reads)
            if not completed:
                self._scan_enumeration_incomplete = True
                self._scan_timeout_count += 1
                if self._scan_index_work['audit_started_at'] is None:
                    self._scan_index_work['audit_started_at'] = time.time()
                known, unavailable = self._known_scan_candidates(required)
                enumeration = known, [], {'count': 0, 'samples': []}, len(known)
                self._partial.extend(unavailable)
        else:
            enumeration = self._enumerate_scan(required)
        candidates, self._excluded, self._skipped_paths, scanned = enumeration
        seen = {relative for relative, _ in candidates}
        if hasattr(self, '_sync_phase'):
            self._progress(progress_stage, scanned)
        if not incremental:
            for relative, _ in candidates:
                try:
                    text = self._read(relative)
                    if text is not None:
                        files[relative] = text
                except (UnicodeError, FileNotFoundError):
                    self._partial.append(relative)
                except OSError:
                    raise
                except ProductError as exc:
                    if exc.code in {'folder_limit', 'folder_partial_file'}:
                        self._partial.append(relative)
                    else:
                        raise
        if incremental:
            ordered = []
            audit = self._scan_index_work['audit_started_at']
            for relative, _ in candidates:
                if self._scan_enumeration_incomplete and time.monotonic() >= self._scan_deadline:
                    self._partial.append(relative)
                    continue
                try:
                    def inspect(name=relative):
                        target = self._target(name)
                        return target, file_stamp(target)
                    completed, value = bounded_read_only(inspect, SCAN_STAT_SECONDS, self._pending_metadata_reads)
                    if not completed:
                        self._partial.append(relative)
                        continue
                    target, stamp = value
                except (OSError, FileNotFoundError):
                    self._partial.append(relative)
                    continue
                except ProductError as exc:
                    if exc.code == 'folder_partial_file':
                        self._partial.append(relative); continue
                    raise
                prior = self._scan_index_work['entries'].get(relative)
                prior_text = baseline.get(relative, {}).get('text')
                reusable = bool(scan_metadata_reuse_allowed() and prior and prior_text is not None
                                and not (prior['stamp'][2] == 0 and prior_text)
                                and prior['stamp'] == stamp
                                and prior['hash'] == byte_hash(prior_text)
                                and (audit is None or prior['verified_at'] >= audit))
                if reusable:
                    files[relative] = prior_text
                    continue
                prior_matches_baseline = bool(prior and prior_text is not None
                                              and prior['stamp'] == stamp
                                              and prior['hash'] == byte_hash(prior_text))
                priority = (0 if (relative in {'AGENTS.md', 'INDEX.md'} or
                                  (stamp[2] == 0 and prior is not None) or
                                  (self._scan_pass > 1 and relative in self._scan_verified_this_cycle and stamp[2] == 0)) else
                            1 if prior is not None and not prior_matches_baseline else
                            2 if relative not in baseline else
                            3 if prior is None else 4)
                ordered.append((priority, -stamp[4], relative, target, stamp, prior_text))
            ordered.sort()
            for _, _, relative, target, stamp, prior_text in ordered:
                if self._scan_read_remaining <= 0 or time.monotonic() >= self._scan_deadline:
                    self._partial.append(relative)
                    if prior_text is not None:
                        files[relative] = prior_text
                    continue
                self._pending_scan_reads = [thread for thread in self._pending_scan_reads if thread.is_alive()]
                if len(self._pending_scan_reads) >= self._active_pending_limit:
                    self._partial.append(relative)
                    if prior_text is not None:
                        files[relative] = prior_text
                    continue
                self._scan_read_remaining -= 1
                self._scan_read_this_run += 1
                if self._scan_read_this_run % 50 == 0:
                    self._progress(progress_stage + '_read', self._scan_read_this_run)
                try:
                    read_state, value = self._timed_stable_read(relative, target)
                    if read_state != 'ok':
                        if read_state in {'saturated', 'budget'}:
                            self._scan_read_remaining += 1
                            self._scan_read_this_run -= 1
                        if read_state == 'timeout':
                            self._scan_timeout_count += 1
                        self._partial.append(relative)
                        continue
                    text, after = value
                    if text is None:
                        self._partial.append(relative); continue
                    if text == '' and prior_text not in (None, ''):
                        self._partial.append(relative); continue
                    if after != stamp:
                        self._partial.append(relative); continue
                    self._scan_index_work['entries'][relative] = {
                        'stamp': after, 'hash': byte_hash(text), 'verified_at': time.time()}
                    self._scan_verified_this_cycle.add(relative)
                    files[relative] = text
                except (OSError, UnicodeError, FileNotFoundError):
                    self._partial.append(relative)
                except ProductError as exc:
                    if exc.code in {'folder_limit', 'folder_partial_file'}:
                        self._partial.append(relative)
                    else:
                        raise
        validate_files(files)
        if incremental:
            self._scan_seen = seen
        if hasattr(self, '_sync_phase'):
            self._progress(progress_stage, scanned)
        return files

    def _baseline(self):
        path = self.state / 'baseline.json'
        if not path.exists():
            fail('state_missing', 'Private baseline is missing; preserve state and recover its original history.', 4)
        record = parse(read_bytes(path))
        if (not isinstance(record, dict) or record.get('format') != VERSION or record.get('project_id') != self.project_id
                or record.get('checksum') != digest({k: v for k, v in record.items() if k != 'checksum'})):
            fail('state_invalid', 'Invalid private causal baseline checksum or binding.')
        value = record['paths']
        if not isinstance(value, dict):
            fail('state_invalid', 'Invalid private causal baseline.')
        for name, item in value.items():
            path_name(name)
            if not isinstance(item, dict) or set(item) != {'heads', 'text'} or not isinstance(item['heads'], list):
                fail('state_invalid', 'Invalid private causal baseline entry.')
            if any(not isinstance(h, str) or not HASH.fullmatch(h) for h in item['heads']):
                fail('state_invalid', 'Invalid baseline event identity.')
        validate_files({p: v['text'] for p, v in value.items() if v['text'] is not None})
        return value

    def _save_baseline(self, value):
        record = {'format': VERSION, 'project_id': self.project_id, 'paths': value}
        record['checksum'] = digest(record)
        atomic(self.state / 'baseline.json', canonical(record))

    def _event(self, kind, changes, baseline, explanation, rename=None):
        return validate_event({'format': VERSION, 'project_id': self.project_id, 'kind': kind,
            'author': self.config['author'], 'changes': changes,
            'parents': {p: sorted(baseline.get(p, {}).get('heads', [])) for p in changes},
            'base': {p: baseline.get(p, {}).get('text') for p in changes},
            'evidence': evidence_text(explanation), 'rename': rename}, self.project_id)

    def _emit(self, event):
        raw = canonical(event)
        if len(raw) > MAX_EVENT_BYTES:
            fail('limit', 'Event exceeds its serialized byte bound.')
        event_id = hashlib.sha256(raw).hexdigest()
        # Durable local outbox precedes provider-visible publication.
        atomic(self.state / 'events' / (event_id + '.json'), raw, immutable=True)
        atomic(self.shared / 'events' / (event_id + '.json'), raw, immutable=True)
        return event_id

    def _load_events(self, cache):
        records, deferred, invalid, total = {}, [], [], 0
        self._history_copies = []
        self._provider_duplicate_bytes_unverified = 0
        validated_private = {}
        locations = [self.state / 'events', self.shared / 'events']
        for directory in locations:
            source = 'private' if directory == self.state / 'events' else 'provider'
            if cache:
                self._progress('sync_load_history_' + source, 0)
            scanned = 0
            if cache and source == 'provider':
                def enumerate_events():
                    safe(directory)
                    return sorted(directory.iterdir()) if directory.exists() else []
                completed, paths = bounded_read_only(
                    enumerate_events, SCAN_METADATA_SECONDS, self._pending_metadata_reads)
                if not completed:
                    deferred.append({'reason': 'provider-history-enumeration-timeout'})
                    continue
            else:
                safe(directory)
                paths = sorted(directory.iterdir()) if directory.exists() else []
            for path in paths:
                scanned += 1
                if cache and scanned % 100 == 0:
                    self._progress('sync_load_history_' + source, scanned)
                if path.name.startswith('.folder-write-'):
                    continue
                if len(records) >= MAX_EVENTS and path.stem not in records:
                    fail('limit', 'History event count exceeds the supported bound.')
                try:
                    if cache and source == 'provider':
                        expected_size = validated_private.get(path.name)
                        def inspect_event(selected=path, expected=expected_size):
                            safe(selected)
                            if not selected.is_file() or selected.suffix != '.json':
                                return 'incomplete', None
                            if expected is not None and selected.stat().st_size == expected:
                                return 'duplicate', None
                            return 'raw', read_bytes(selected)
                        completed, inspected = bounded_read_only(
                            inspect_event, SCAN_EVENT_SECONDS, self._pending_metadata_reads)
                        if not completed:
                            deferred.append({'file': path.name, 'reason': 'provider-history-read-timeout'})
                            continue
                        kind, raw = inspected
                        if kind == 'incomplete':
                            deferred.append({'file': path.name, 'reason': 'incomplete-history-entry'}); continue
                        if kind == 'duplicate':
                            self._provider_duplicate_bytes_unverified += 1
                            continue
                    else:
                        safe(path)
                        if not path.is_file() or path.suffix != '.json':
                            deferred.append({'file': path.name, 'reason': 'incomplete-history-entry'}); continue
                        raw = read_bytes(path)
                    # History is content-addressed and immutable. For routine
                    # sync, a provider entry with the same canonical name and
                    # byte size cannot add a new valid event when the private
                    # canonical copy was already validated. A full status call
                    # still rereads the provider bytes to audit duplicate copies.
                    total += len(raw)
                    if total > MAX_HISTORY_BYTES:
                        fail('limit', 'History exceeds the supported scan byte bound.')
                    actual_id = hashlib.sha256(raw).hexdigest()
                    if HASH.fullmatch(path.stem) and actual_id != path.stem:
                        raise ValueError()
                    value = validate_event(parse(raw), self.project_id)
                    if canonical(value) != raw:
                        raise ValueError()
                    if path.stem != actual_id:
                        self._history_copies.append({'file': path.name, 'event': actual_id, 'reason': 'validated-provider-copy'})
                    records[actual_id] = value
                    if directory == self.state / 'events' and path.name == actual_id + '.json':
                        validated_private[path.name] = len(raw)
                    if cache and directory == self.shared / 'events':
                        if actual_id + '.json' not in validated_private:
                            atomic(self.state / 'events' / (actual_id + '.json'), raw, immutable=True)
                            validated_private[actual_id + '.json'] = len(raw)
                except (ValueError, UnicodeError, TypeError, KeyError, ProductError) as exc:
                    if isinstance(exc, ProductError) and exc.code == 'folder_limit':
                        raise
                    if isinstance(exc, ProductError) and exc.code == 'folder_partial_file':
                        deferred.append({'file': path.name, 'reason': 'unstable-history-entry'}); continue
                    invalid.append({'file': path.name, 'reason': 'incomplete-or-invalid-event'})
                except OSError:
                    if cache and source == 'provider':
                        deferred.append({'file': path.name, 'reason': 'provider-history-io-unavailable'}); continue
                    raise
            if cache:
                self._progress('sync_load_history_' + source, scanned)
        if cache:
            self._progress('sync_order_history', 0)
        ready = {}
        remaining = dict(records)
        while remaining:
            advanced = False
            for event_id in sorted(remaining):
                event = remaining[event_id]
                all_parents = {p for values in event['parents'].values() for p in values}
                if not all_parents.issubset(ready):
                    continue
                if any(path not in ready[parent]['changes'] for path, parents in event['parents'].items() for parent in parents):
                    invalid.append({'file': event_id + '.json', 'reason': 'parent-path-mismatch'})
                    del remaining[event_id]; advanced = True; continue
                ready[event_id] = event
                del remaining[event_id]; advanced = True
                if cache and len(ready) % 100 == 0:
                    self._progress('sync_order_history', len(ready))
            if not advanced:
                break
        for event_id in sorted(remaining):
            deferred.append({'event': event_id, 'reason': 'missing-or-cyclic-parents'})
        if cache:
            self._progress('sync_order_history', len(ready))
        return ready, deferred, invalid

    def _capture(self, baseline):
        local = self._scan(set(baseline), incremental=True, baseline=baseline)
        changed = {p: text for p, text in local.items() if p not in baseline or baseline[p]['text'] != text}
        if changed:
            self._progress('sync_capture_emit', len(changed))
            event = self._event('edit', changed, baseline, 'Captured observed local bytes against the saved device baseline; origin may be an editor or provider')
            try:
                event_id = self._emit(event)
            except ProductError as error:
                if error.code != 'folder_partial_file':
                    raise
                # The private outbox may already contain this exact event;
                # leave the old baseline and visible files intact until the
                # provider copy can be checked on a later cycle.
                self._partial.extend(changed)
                self._capture_deferred.update(changed)
                return local
            baseline.update({p: {'heads': [event_id], 'text': text} for p, text in changed.items()})
            self._progress('sync_capture_baseline', len(changed))
            self._save_baseline(baseline)
        return local

    def _backup(self, text):
        if text is not None:
            atomic(self.state / 'backups' / (byte_hash(text) + '.txt'), text.encode('utf-8'), immutable=True)

    def _recover(self):
        journal_path = self.state / 'journal.json'
        if not journal_path.exists():
            return []
        journal = parse(read_bytes(journal_path))
        if (journal.get('format') != VERSION or journal.get('project_id') != self.project_id
                or journal.get('checksum') != digest({k: v for k, v in journal.items() if k != 'checksum'})):
            fail('journal_invalid', 'Recovery journal checksum or project binding is invalid.')
        for name, operation in journal['operations'].items():
            path_name(name)
            if (not re.fullmatch(r'\.folder-old-[0-9a-f]{32}', operation['evacuated'])
                    or not re.fullmatch(r'\.folder-new-[0-9a-f]{32}', operation['new'])):
                fail('journal_invalid', 'Recovery filenames do not belong to this journal.')
        baseline = self._baseline()
        deferred, pending = [], {}
        for path, operation in journal['operations'].items():
            destination = self._target(path)
            evacuated = destination.parent / operation['evacuated']
            safe(evacuated)
            desired, before = operation['text'], operation['before']
            readonly = destination.exists() and not self._can_write(path)
            # The temporary old inode belongs to this journal and is kept until
            # its actual post-crash/editor bytes are safely preserved privately.
            if evacuated.exists():
                try:
                    actual_old = read_bytes(evacuated, MAX_FILE_BYTES).decode('utf-8')
                except ProductError as error:
                    if error.code not in {'folder_partial_file', 'folder_limit'}:
                        raise
                    pending[path] = operation; deferred.append(path); continue
                self._backup(actual_old)
                if actual_old != before:
                    # Preserve a writer that retained the evacuated inode.
                    event_id = self._emit(self._event('edit', {path: actual_old},
                        {path: operation['baseline']}, 'Preserved edit made during interrupted materialization'))
                    if readonly:
                        pending[path] = operation
                        deferred.append(path); continue
                    if not destination.exists():
                        os.link(evacuated, destination); fsync_dir(destination.parent)
                        baseline[path] = {'heads': [event_id], 'text': actual_old}
                        self._save_baseline(baseline)
                    # A different visible file retains its own original ancestry;
                    # it is not causally descended from the old-inode edit.
                    evacuated.unlink(); fsync_dir(destination.parent)
                    deferred.append(path); continue
            if readonly:
                pending[path] = operation
                deferred.append(path); continue
            try:
                current = self._read(path)
            except ProductError as error:
                if error.code not in {'folder_partial_file', 'folder_limit'}:
                    raise
                pending[path] = operation; deferred.append(path); continue
            if current == desired:
                baseline[path] = {'heads': operation['heads'], 'text': desired}
                self._save_baseline(baseline)
                if evacuated.exists():
                    evacuated.unlink(); fsync_dir(destination.parent)
                continue
            if current != before and not (current is None and evacuated.exists()):
                self._backup(current)
                deferred.append(path)
                continue
            self._backup(current)
            if current is not None and not evacuated.exists():
                os.rename(destination, evacuated)
                fsync_dir(destination.parent)
                # A newer file moved by the race is never discarded or replaced.
                try:
                    moved = read_bytes(evacuated, MAX_FILE_BYTES).decode('utf-8')
                except ProductError as error:
                    if error.code not in {'folder_partial_file', 'folder_limit'}:
                        raise
                    pending[path] = operation; deferred.append(path); continue
                if moved != before:
                    self._backup(moved)
                    if not destination.exists():
                        os.link(evacuated, destination); fsync_dir(destination.parent)
                    evacuated.unlink(); fsync_dir(destination.parent)
                    deferred.append(path); continue
            if desired is not None:
                destination.parent.mkdir(parents=True, exist_ok=True)
                temp = destination.parent / operation['new']
                atomic(temp, desired.encode('utf-8'), immutable=True)
                os.chmod(temp, operation.get('mode', 0o600))
                try:
                    os.link(temp, destination)
                except FileExistsError:
                    deferred.append(path)
                else:
                    fsync_dir(destination.parent)
                temp.unlink(missing_ok=True)
            elif destination.exists():
                deferred.append(path)
            if path not in deferred:
                baseline[path] = {'heads': operation['heads'], 'text': desired}
                self._save_baseline(baseline)
            if evacuated.exists():
                evacuated.unlink(); fsync_dir(destination.parent)
        # Every old/new byte is retained in history/backups. A deferred path is
        # recaptured against its saved ancestry before future materialization.
        if pending:
            remaining = {'format': VERSION, 'project_id': self.project_id, 'operations': pending}
            remaining['checksum'] = digest(remaining)
            atomic(journal_path, canonical(remaining))
        else:
            journal_path.unlink(); fsync_dir(self.state)
        return deferred

    def _can_write(self, name):
        path = self._target(name)
        if not path.exists():
            return True
        return bool(path.stat().st_mode & 0o222) and os.access(path, os.W_OK)

    @staticmethod
    def _path_collisions(resolved):
        try:
            validate_files({p: v['versions'][0]['text'] or '' for p, v in resolved.items()
                            if v['conflict'] or v['text'] is not None})
        except ProductError:
            return sorted(resolved)
        return []

    def _materialize(self, baseline, current, resolved):
        operations, protected = {}, []
        partial = set(self._partial)
        for path, value in resolved.items():
            if value['conflict'] or path in partial:
                continue
            desired = value['text']
            before = current.get(path)
            if before is None and path in baseline and baseline[path]['text'] is not None and desired is not None:
                continue  # Missing provider-delayed file is not a delete or a rewrite request.
            if before == desired:
                baseline[path] = {'heads': value['heads'], 'text': desired}
                continue
            if not self._can_write(path):
                protected.append(path); continue
            token = uuid.uuid4().hex
            operations[path] = {'text': desired, 'before': before, 'heads': value['heads'],
                                'baseline': baseline.get(path, {'heads': [], 'text': None}),
                                'evacuated': '.folder-old-' + token, 'new': '.folder-new-' + token,
                                'mode': stat.S_IMODE(self._target(path).stat().st_mode) if before is not None else 0o600}
            self._backup(before)
        self._save_baseline(baseline)
        if not operations:
            return protected
        journal = {'format': VERSION, 'project_id': self.project_id, 'operations': operations}
        journal['checksum'] = digest(journal)
        atomic(self.state / 'journal.json', canonical(journal))
        return protected + self._recover()

    def _reports(self, resolved):
        for path, value in resolved.items():
            if not value['conflict']:
                continue
            conflict_id = digest({'path': path, 'heads': value['heads']})
            lines = ['# Shared Memory conflict', '', 'Historical conflict observation. Run folder status to check whether it remains unresolved.',
                     '', 'Path: `' + path + '`', '', 'No version was silently selected. Resolve with an explanation after reviewing the causal versions.',
                     '', 'Common base event: ' + (value['base_id'] or 'none or ambiguous'), '']
            for version in value['versions']:
                lines += ['- Event `' + version['event'] + '`', '  Exact text/deletion is retained in `../events/' + version['event'] + '.json`.']
            atomic(self.shared / 'conflicts' / (conflict_id + '.md'), ('\n'.join(lines) + '\n').encode(), immutable=True)

    @staticmethod
    def _rename_divergences(events, resolved):
        result = []
        for source, value in sorted(resolved.items()):
            renames = [(head, events[head]['rename']['destination']) for head in value['heads']
                       if events[head]['kind'] == 'rename' and events[head]['rename']['source'] == source]
            destinations = sorted({destination for _, destination in renames})
            if len(destinations) > 1:
                result.append({'source': source, 'event_ids': sorted(head for head, _ in renames),
                               'destinations': destinations})
        return result

    def _summary(self, events, deferred, invalid, resolved, local):
        conflicts = []
        for path, value in resolved.items():
            if value['conflict']:
                cid = digest({'path': path, 'heads': value['heads']})
                conflicts.append({'path': path, 'heads': value['heads'], 'base_event': value['base_id'],
                                  'report': HISTORY + '/conflicts/' + cid + '.md'})
        missing = sorted(p for p, v in resolved.items() if not v['conflict'] and v['text'] is not None and p not in local)
        changed = sorted(p for p, text in local.items() if p not in resolved or resolved[p]['conflict'] or resolved[p]['text'] != text)
        collisions = self._path_collisions(resolved)
        rename_divergences = self._rename_divergences(events, resolved)
        skipped = getattr(self, '_skipped_paths', {'count': 0, 'samples': []})
        copies = sorted(p for p in local if re.search(r'(?i)(conflicted? copy|conflict[- _]|\(.*conflict.*\))', p))
        return {'project_id': self.project_id, 'workflow': 'folder', 'provider': self.manifest['provider'],
                'readonly': self.config['readonly'], 'readiness': 'ready' if not (conflicts or deferred or invalid or missing or changed or self._partial or collisions) else 'partial',
                'history_hash': digest(sorted(events)), 'event_count': len(events),
                'path_collisions': collisions, 'history_copies': getattr(self, '_history_copies', []),
                'rename_divergences': rename_divergences,
                'skipped_paths': skipped,
                'provider_duplicate_bytes_unverified': getattr(self, '_provider_duplicate_bytes_unverified', 0),
                'warnings': ([{'code': 'untracked_nonportable_paths', 'message':
                    str(skipped['count']) + ' untracked paths were excluded from history because their names are not portable; local files remain unchanged.'}]
                    if skipped['count'] else []) + ([{'code': 'rename_intent_divergence', 'message':
                    'Concurrent renames preserved different destinations. File convergence does not resolve intent; review both copies, then resolve or explicitly delete the source with evidence to acknowledge the chosen outcome.'}]
                    if rename_divergences else []),
                'heads': {p: v['heads'] for p, v in resolved.items()}, 'conflicts': conflicts,
                'deferred_events': deferred, 'invalid_events': invalid, 'missing_files': missing,
                'local_changes': changed, 'partial_files': list(self._partial), 'excluded': sorted(self._excluded),
                'provider_conflict_copies': copies, 'copy_detection': 'filename_heuristic_only',
                'provider_delivery': 'not_applicable' if self.manifest['provider'] == 'local' else 'unverified',
                'identity_trust': 'self_asserted_provenance; access is governed by provider and OS permissions',
                'limitation': LIMITATION}

    def _sync_locked(self):
        self._progress('sync_read_baseline')
        with io_phase('sync_read_baseline'):
            baseline = self._baseline()
        self._scan_index_work = self._load_scan_index()
        self._scan_read_remaining = SCAN_READ_LIMIT
        self._scan_read_this_run = 0
        self._scan_deadline = time.monotonic() + SCAN_WALL_SECONDS
        self._scan_timeout_count = 0
        self._scan_pass = 0
        self._scan_verified_this_cycle = set()
        self._scan_enumeration_incomplete = False
        self._capture_deferred = set()
        if not hasattr(self, '_pending_scan_reads'):
            self._pending_scan_reads = []
        if not hasattr(self, '_pending_metadata_reads'):
            self._pending_metadata_reads = []
        # Recovery preserves raced bytes before it can replace any path. Then
        # capture changes using the old private causal ancestry, not incoming heads.
        self._progress('sync_recover')
        with io_phase('sync_recover'):
            raced = self._recover()
        self._progress('sync_read_baseline')
        with io_phase('sync_read_baseline'):
            baseline = self._baseline()
        self._progress('sync_capture_local')
        with io_phase('sync_capture_local'):
            current = self._capture(baseline)
        self._progress('sync_load_history_private')
        with io_phase('sync_load_history'):
            events, deferred, invalid = self._load_events(cache=True)
        self._progress('sync_merge_history')
        with io_phase('sync_merge_history'):
            resolved = views(events)
        for name, value in baseline.items():
            for head in value['heads']:
                if head not in events:
                    deferred.append({'event': head, 'path': name, 'reason': 'saved-baseline-history-unavailable'})
        if (not invalid and not deferred and not self._scan_enumeration_incomplete
                and not (self.state / 'journal.json').exists() and not self._path_collisions(resolved)):
            self._progress('sync_materialize')
            with io_phase('sync_materialize'):
                raced += self._materialize(baseline, current, resolved)
            self._progress('sync_reports')
            with io_phase('sync_reports'):
                self._reports(resolved)
        self._progress('sync_scan_local')
        with io_phase('sync_scan_local'):
            local = self._scan(set(baseline) | set(resolved), incremental=True, baseline=baseline)
        self._partial.extend(sorted(self._capture_deferred - set(self._partial)))
        self._progress('sync_summary')
        result = self._summary(events, deferred, invalid, resolved, local)
        result['deferred_materialization'] = sorted(set(raced))
        if raced:
            result['readiness'] = 'partial'
        if (self.state / 'journal.json').exists():
            result['readiness'] = 'partial'; result['recovery_pending'] = True
        expected = {name for name, item in baseline.items() if item['text'] is not None}
        expected.update(name for name, item in resolved.items() if not item['conflict'] and item['text'] is not None)
        missing_coverage = expected - self._scan_seen
        eligible = len(self._scan_seen | expected | set(self._partial))
        deferred_count = len(set(self._partial) | missing_coverage)
        if (result['readiness'] == 'ready' and not self._scan_enumeration_incomplete and deferred_count == 0
                and self._scan_index_work['audit_started_at'] is not None):
            self._scan_index_work['full_audit_at'] = time.time()
            self._scan_index_work['audit_started_at'] = None
        result['scan_coverage'] = {
            'eligible': eligible, 'covered': eligible - deferred_count,
            'deferred': deferred_count, 'read_this_run': self._scan_read_this_run,
            'enumeration_complete': not self._scan_enumeration_incomplete,
            'read_limit': SCAN_READ_LIMIT,
            'audit': ('metadata_unavailable' if not scan_metadata_reuse_allowed() and deferred_count else
                      'in_progress' if self._scan_index_work['audit_started_at'] is not None
                      else 'coverage_incomplete' if deferred_count else 'current'),
            'full_audit_at': self._scan_index_work['full_audit_at'],
            'index_rebuilt': self._scan_index_rebuilt,
            'reuse_basis': ('baseline_sha256_and_device_inode_size_mtime_ctime' if scan_metadata_reuse_allowed()
                            else 'none_windows_full_byte_read_required')}
        result['scan_timeout_count'] = self._scan_timeout_count
        if self._scan_enumeration_incomplete:
            result['readiness'] = 'partial'
        self._save_scan_index(self._scan_index_work)
        self._progress('complete')
        return result

    @checked
    def sync(self):
        self._writable()
        self._progress('sync_lock_wait')
        with self._lock():
            return self._sync_locked()

    @checked
    def status(self):
        events, deferred, invalid = self._load_events(cache=False)
        resolved = views(events)
        local = self._scan(set(self._baseline()) | set(resolved))
        result = self._summary(events, deferred, invalid, resolved, local)
        if (self.state / 'journal.json').exists():
            result['readiness'] = 'partial'; result['recovery_pending'] = True
        return result

    @checked
    def history(self, path=None):
        if path is not None:
            path_name(path)
        events, deferred, invalid = self._load_events(cache=False)
        return {'project_id': self.project_id, 'events': [{'event_id': key, **value} for key, value in events.items()
                if path is None or path in value['changes']], 'deferred_events': deferred, 'invalid_events': invalid,
                'identity_trust': 'self_asserted_provenance'}

    def _explicit(self, kind, changes, explanation, rename=None):
        self._writable()
        for name in (list(changes) if rename is None else [rename['source'], rename['destination']]):
            if not self._can_write(name):
                fail('readonly_file', 'The selected file is not writable; permissions were not bypassed.', 4)
        with self._lock():
            self._sync_locked()
            events, deferred, invalid = self._load_events(cache=True)
            if deferred or invalid or self._partial or (self.state / 'journal.json').exists():
                fail('history_incomplete', 'Wait for complete history and local files before explicit delete, rename or resolution.', 4)
            resolved = views(events)
            divergent_sources = {item['source'] for item in self._rename_divergences(events, resolved)}
            if kind == 'resolve' and not divergent_sources.intersection(changes) and all(p in resolved and not resolved[p]['conflict'] and resolved[p]['text'] == text
                                          for p, text in changes.items()):
                return self._sync_locked()
            if kind == 'delete':
                name = next(iter(changes))
                if name not in resolved:
                    fail('missing', 'Cannot delete an unknown path.', 4)
                if name not in divergent_sources and not resolved[name]['conflict'] and resolved[name]['text'] is None:
                    return self._sync_locked()
            if kind == 'rename':
                source, destination = rename['source'], rename['destination']
                if source not in resolved or resolved[source]['conflict'] or resolved[source]['text'] is None:
                    prior = [e for e in events.values() if e['kind'] == 'rename' and e['rename'] == rename and e['evidence'] == explanation]
                    if prior and destination in resolved and not resolved[destination]['conflict']:
                        return self._sync_locked()
                    fail('conflict', 'Resolve the source before renaming it.', 4)
                if (destination in resolved and (resolved[destination]['conflict'] or resolved[destination]['text'] is not None)) or self._target(destination).exists():
                    fail('collision', 'Rename destination already exists.', 4)
                # Check portable path/file-directory collisions across the new view.
                validate_files({p: v['text'] for p, v in resolved.items() if p != source and not v['conflict'] and v['text'] is not None} | {destination: resolved[source]['text']})
                changes = {source: None, destination: resolved[source]['text']}
            causal = {p: {'heads': resolved[p]['heads'], 'text': resolved[p]['text']} for p in changes if p in resolved}
            event = self._event(kind, changes, causal, explanation, rename)
            self._emit(event)
            return self._sync_locked()

    @checked
    def resolve(self, path, text, evidence):
        path_name(path)
        if text is not None:
            validate_files({path: text})
        return self._explicit('resolve', {path: text}, evidence_text(evidence))

    @checked
    def delete(self, path, evidence):
        return self._explicit('delete', {path_name(path): None}, evidence_text(evidence))

    @checked
    def rename(self, source, destination, evidence):
        return self._explicit('rename', {}, evidence_text(evidence),
                              {'source': path_name(source), 'destination': path_name(destination)})
