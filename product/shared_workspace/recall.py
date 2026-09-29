"""Bounded, source-checked Markdown recall over one selected folder.

The SQLite database is a disposable private acceleration structure. Markdown is
always the authority; every returned hit is checked against current file bytes.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile
import threading
import time

from .errors import ProductError
from .folder import fsync_dir, private_path, read_bytes, safe
from .knowledge import PRIVATE, PRIVATE_FILES
from .path_safety import is_link_or_reparse

MAX_FILE = 2 * 1024 * 1024
MAX_SCAN_FILES = 10000
MAX_DIRECT_BYTES = 16 * 1024 * 1024
MAX_UNAVAILABLE_SOURCES = 3
TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
HASH = re.compile(r"(?:[0-9a-f]{24}|[0-9a-f]{64})\Z")


def _metadata_reuse_allowed():
    # On Windows through Python 3.13, st_ctime is creation time. An in-place
    # same-size edit whose mtime is restored can retain every indexed stamp.
    return os.name != 'nt'


def _error(code, message, status=3):
    raise ProductError(status, 'recall_' + code, message)


def _source_names(*groups):
    result = []
    for group in groups:
        for name in group:
            # Paths are only emitted after they have passed the selected-root
            # inventory or _relative. Long names consume output without adding
            # useful location context, so report their safe scope instead.
            if len(name) > 120:
                name = name.split('/', 1)[0]
            if name not in result:
                result.append(name)
    return result[:MAX_UNAVAILABLE_SOURCES]


def _eligible(root, *, raw=False, output=False):
    """Yield only in-scope regular Markdown; report excluded/unavailable counts."""
    roots = ['Wiki'] + (['Raw'] if raw else []) + (['Output'] if output else [])
    paths = []
    meta = {'unavailable': 0, 'unavailable_sources': [],
            'unsearched': ['Raw'] if not raw else []}
    def unavailable(name=None):
        meta['unavailable'] += 1
        if name:
            meta['unavailable_sources'] = _source_names(meta['unavailable_sources'], [name])
    if not output:
        meta['unsearched'].append('Output')
    for name in ('AGENTS.md', 'INDEX.md'):
        path = root / name
        if path.exists() and not is_link_or_reparse(path) and path.is_file():
            paths.append((name, path))
        else:
            unavailable(name)
    for name in roots:
        base = root / name
        if not base.exists():
            unavailable(name)
            continue
        if is_link_or_reparse(base) or not base.is_dir():
            unavailable(name)
            continue
        def walk_error(error):
            relative = None
            try:
                candidate = Path(error.filename).relative_to(root)
                parts = candidate.parts
                if (parts and parts[0] == name and
                        not any(part.startswith('.') or part.casefold() in PRIVATE or
                                part.casefold() in PRIVATE_FILES or part.casefold() == 'coordination'
                                for part in parts)):
                    relative = candidate.as_posix()
            except (TypeError, ValueError, AttributeError):
                pass
            unavailable(relative or name)
            meta['truncated_scan'] = True
        for directory, dirs, names in os.walk(base, followlinks=False, onerror=walk_error):
            directory = Path(directory)
            retained = []
            for child in dirs:
                path = directory / child
                if (child.startswith('.') or child.casefold() in PRIVATE or
                        child.casefold() == 'coordination' or is_link_or_reparse(path) or
                        (path / '.shared-memory.json').exists()):
                    unavailable()
                    continue
                retained.append(child)
            dirs[:] = retained
            for child in names:
                path = directory / child
                if child.startswith('.') or child.casefold() in PRIVATE_FILES or path.suffix.casefold() not in {'.md', '.markdown'}:
                    continue
                if is_link_or_reparse(path) or not path.is_file():
                    unavailable(path.relative_to(root).as_posix())
                    continue
                paths.append((path.relative_to(root).as_posix(), path))
                if len(paths) >= MAX_SCAN_FILES:
                    unavailable()
                    meta['truncated_scan'] = True
                    return paths, meta
    return paths, meta


def _read(path):
    try:
        return read_bytes(path, MAX_FILE).decode('utf-8')
    except (OSError, UnicodeError, ProductError):
        return None


def _blocks(content):
    lines = content.splitlines()
    heading = ''
    for start in range(0, len(lines), 8):
        block = lines[start:start + 8]
        for line in block:
            found = HEADING.match(line)
            if found:
                heading = found.group(1).strip()[:160]
        yield start + 1, min(start + 8, len(lines)), heading, '\n'.join(block)


def _source_hash(content):
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def _smallest_excerpt(start, end, heading, block, terms, name):
    lines = block.split('\n')
    # A filename can route to a note, but it must not make an arbitrary line
    # appear to satisfy the rest of the query. Prefer the smallest source span
    # containing every term not already supplied by the filename.
    name_folded = name.casefold()
    lowered = [term.casefold() for term in terms if term.casefold() not in name_folded]
    if not lowered:
        lowered = [term.casefold() for term in terms]
    for width in range(1, len(lines) + 1):
        for offset in range(len(lines) - width + 1):
            excerpt = '\n'.join(lines[offset:offset + width])
            hay = excerpt.casefold()
            if all(term in hay for term in lowered):
                return start + offset, start + offset + width - 1, excerpt
    return start, end, block


def _index_path(state, root):
    state = private_path(state, root)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    return state / 'recall.sqlite3'


def _connect(path):
    if path.exists() and is_link_or_reparse(path):
        _error('index_unsafe', 'Private index cannot be a link or reparse point.')
    db = sqlite3.connect(path, timeout=2)
    db.execute('PRAGMA busy_timeout=2000')
    if db.execute('PRAGMA user_version').fetchone()[0] != 2:
        # The index is disposable; never migrate or alter canonical Markdown.
        db.execute('DROP TABLE IF EXISTS chunks')
        db.execute('DROP TABLE IF EXISTS files')
        db.execute('PRAGMA user_version=2')
    db.execute('CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, mtime_ns INTEGER, ctime_ns INTEGER, size INTEGER, inode INTEGER, sha256 TEXT)')
    db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(path, start UNINDEXED, end UNINDEXED, heading, text)')
    return db


def _refresh(db, paths, *, remove_absent=True):
    current = set()
    unavailable = 0
    sources = []
    for offset, (name, path) in enumerate(paths):
        current.add(name)
        try:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE:
                unavailable += 1
                sources = _source_names(sources, [name])
                continue
            prior = db.execute('SELECT mtime_ns,ctime_ns,size,inode FROM files WHERE path=?', (name,)).fetchone()
            if (_metadata_reuse_allowed() and
                    prior == (info.st_mtime_ns, info.st_ctime_ns, info.st_size, info.st_ino)):
                continue
            content = _read(path)
            if content is None:
                unavailable += 1
                sources = _source_names(sources, [name])
                continue
            db.execute('DELETE FROM chunks WHERE path=?', (name,))
            db.executemany('INSERT INTO chunks(path,start,end,heading,text) VALUES(?,?,?,?,?)',
                           ((name, start, end, heading, block) for start, end, heading, block in _blocks(content)))
            db.execute('INSERT OR REPLACE INTO files VALUES(?,?,?,?,?,?)',
                       (name, info.st_mtime_ns, info.st_ctime_ns, info.st_size, info.st_ino, _source_hash(content)))
        except (OSError, sqlite3.Error):
            unavailable += 1
            sources = _source_names(sources, [name])
        # Persist bounded progress before a cloud-backed read stalls. A later
        # invocation can skip files whose metadata has not changed.
        if offset % 16 == 15:
            db.commit()
    if remove_absent:
        for (old,) in db.execute('SELECT path FROM files').fetchall():
            if old not in current:
                db.execute('DELETE FROM chunks WHERE path=?', (old,))
                db.execute('DELETE FROM files WHERE path=?', (old,))
    db.commit()
    return unavailable, sources


def _matches(content, query_terms, *, name):
    terms = [term.casefold() for term in query_terms]
    found = []
    source_sha = _source_hash(content)
    for start, end, heading, block in _blocks(content):
        hay = (name + ' ' + heading + ' ' + block).casefold()
        if not all(term in hay for term in terms):
            continue
        count = sum(hay.count(term) for term in terms)
        if count:
            start, end, block = _smallest_excerpt(start, end, heading, block, terms, name)
            found.append((count, {'path': name, 'heading': heading, 'start': start,
                                  'end': end, 'excerpt': block, 'sha256': source_sha}))
    return found


def _direct(root, paths, terms):
    found = []
    scanned = 0
    unavailable = 0
    sources = []
    truncated = False
    for name, path in paths:
        try:
            size = path.lstat().st_size
        except OSError:
            unavailable += 1
            sources = _source_names(sources, [name])
            continue
        if size > MAX_FILE:
            unavailable += 1
            sources = _source_names(sources, [name])
            continue
        if scanned + size > MAX_DIRECT_BYTES:
            truncated = True
            break
        content = _read(path)
        if content is None:
            unavailable += 1
            sources = _source_names(sources, [name])
            continue
        scanned += size
        found.extend(_matches(content, terms, name=name))
    found.sort(key=lambda item: (-item[0], item[1]['path'], item[1]['start']))
    return [item for _, item in found], unavailable, truncated, sources


def _fts(db, root, terms, paths):
    available = {name: path for name, path in paths}
    expression = ' AND '.join('"' + term.replace('"', '""') + '"' for term in terms)
    rows = db.execute("SELECT path,start,end,heading,text FROM chunks WHERE chunks MATCH ? "
                      "ORDER BY (instr(lower(path), '/archive/') > 0), bm25(chunks) LIMIT 30",
                      (expression,)).fetchall()
    found = []
    unavailable = 0
    sources = []
    cache = {}
    for name, start, end, heading, block in rows:
        path = available.get(name)
        if path is None:
            continue
        if name not in cache:
            cache[name] = _read(path)
        content = cache[name]
        if content is None:
            unavailable += 1
            sources = _source_names(sources, [name])
            continue
        lines = content.splitlines()
        if '\n'.join(lines[start-1:end]) != block:
            unavailable += 1
            sources = _source_names(sources, [name])
            continue
        current_heading = ''
        for line in lines[:end]:
            found_heading = HEADING.match(line)
            if found_heading:
                current_heading = found_heading.group(1).strip()[:160]
        if not all(term.casefold() in (name + ' ' + current_heading + ' ' + block).casefold() for term in terms):
            unavailable += 1
            sources = _source_names(sources, [name])
            continue
        heading = current_heading
        start, end, block = _smallest_excerpt(start, end, heading, block, terms, name)
        found.append({'path': name, 'heading': heading, 'start': start, 'end': end,
                      'excerpt': block, 'sha256': _source_hash(content)})
    # Filename routing is useful for broad topic queries. Keep exact-title,
    # current notes ahead of archival references without hiding the latter.
    phrase = ' '.join(terms).casefold()
    found.sort(key=lambda hit: (
        'archive' in (part.casefold() for part in Path(hit['path']).parts),
        0 if Path(hit['path']).stem.casefold() == phrase else
        1 if phrase in Path(hit['path']).stem.casefold() else 2,
        len(Path(hit['path']).parts)))
    compact = []
    exact_titles = set()
    for hit in found:
        if Path(hit['path']).stem.casefold() == phrase:
            if hit['path'] in exact_titles:
                continue
            exact_titles.add(hit['path'])
        compact.append(hit)
    return compact, unavailable, sources


def _cached(db, root, terms, *, raw, output):
    """Read only indexed candidate paths; do not walk a provider on routine hits."""
    expression = ' AND '.join('"' + term.replace('"', '""') + '"' for term in terms)
    rows = db.execute("SELECT path FROM chunks WHERE chunks MATCH ? "
                      "ORDER BY (instr(lower(path), '/archive/') > 0), bm25(chunks) LIMIT 30",
                      (expression,)).fetchall()
    paths = []
    unavailable = 0
    sources = []
    for (name,) in rows:
        if not (name in {'AGENTS.md', 'INDEX.md'} or name.startswith('Wiki/') or
                (raw and name.startswith('Raw/')) or (output and name.startswith('Output/'))):
            continue
        try:
            paths.append((name, _relative(root, name)))
        except ProductError as error:
            unavailable += 1
            if error.code not in {'recall_nested_project', 'recall_path'}:
                sources = _source_names(sources, [name])
    hits, missing, missing_sources = _fts(db, root, terms, paths)
    return hits, unavailable + missing, _source_names(sources, missing_sources)


def _path_first(root, paths, terms, *, max_hits):
    """Search a few relevant titles before touching broad provider content."""
    phrase = ' '.join(terms).casefold()
    ranked = []
    for name, path in paths:
        name_folded = name.casefold()
        if not all(term.casefold() in name_folded for term in terms):
            continue
        stem = path.stem.casefold()
        score = (50 if stem == phrase else 0) + (20 if phrase in stem else 0)
        score += 60 if path.parent.name.casefold() == phrase and stem in {'project brief', 'readme', 'overview'} else 0
        score += 4 * sum(term.casefold() in stem for term in terms)
        score -= 40 if 'archive' in (part.casefold() for part in Path(name).parts) else 0
        ranked.append((score, name, path))
    ranked.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    candidates = [(name, path) for _, name, path in ranked[:12]]
    found = []
    unavailable = 0
    sources = []
    for name, path in candidates:
        content = _read(path)
        if content is None:
            unavailable += 1
            sources = _source_names(sources, [name])
            continue
        blocks = _matches(content, terms, name=name)
        if not blocks:
            continue
        # Prefer actual content terms to a filename-only match. Return one
        # compact, source-verified result per note for navigational queries.
        blocks.sort(key=lambda item: (-sum(term.casefold() in item[1]['excerpt'].casefold() for term in terms),
                                      -item[0], item[1]['start']))
        found.append(blocks[0][1])
        if len(found) >= max_hits:
            break
    return found, candidates, unavailable, len(ranked) > len(candidates), sources


def _seed_private_baseline(root, state, index, paths):
    """Seed a disposable index from captured local text without provider reads.

    Baseline text can lag current Markdown. _fts checks every returned span
    against live bytes; sentinel metadata forces a later live refresh.
    """
    from .folder import Folder
    try:
        baseline = Folder(root, state)._baseline()
    except (ProductError, OSError, ValueError, KeyError):
        return 0
    count = 0
    with contextlib.closing(_connect(index)) as db:
        for name, _ in paths:
            record = baseline.get(name)
            content = record.get('text') if isinstance(record, dict) else None
            if not isinstance(content, str) or len(content.encode('utf-8')) > MAX_FILE:
                continue
            db.execute('DELETE FROM chunks WHERE path=?', (name,))
            db.executemany('INSERT INTO chunks(path,start,end,heading,text) VALUES(?,?,?,?,?)',
                           ((name, start, end, heading, block) for start, end, heading, block in _blocks(content)))
            db.execute('INSERT OR REPLACE INTO files VALUES(?,?,?,?,?,?)',
                       (name, -1, -1, -1, -1, _source_hash(content)))
            count += 1
            if count % 16 == 0:
                db.commit()
        db.commit()
    return count


def _fit(result, max_bytes):
    """Limit complete JSON data so the versioned envelope also fits the cap."""
    def size():
        return len(json.dumps(result, ensure_ascii=True, separators=(',', ':')).encode('utf-8'))
    while result['hits'] and size() > max_bytes:
        last = result['hits'][-1]
        lines = last['excerpt'].split('\n')
        if len(lines) > 1:
            last['excerpt'] = '\n'.join(lines[:-1])
            last['end'] -= 1
            result['truncated'] = True
        else:
            result['hits'].pop()
            result['truncated'] = True
    if size() > max_bytes:
        _error('budget', 'Output metadata exceeds the requested byte budget.')
    return result


def _recall_impl(root, state, terms, *, raw, output, max_hits, max_bytes, refresh):
    # A previously indexed current hit can be returned without walking a slow
    # provider. Source bytes are checked by _fts before any hit is emitted.
    index = _index_path(state, root)
    if index.exists() and not refresh:
        try:
            with contextlib.closing(_connect(index)) as db:
                hits, unavailable, sources = _cached(db, root, terms, raw=raw, output=output)
            if hits:
                return _fit({'hits': hits[:max_hits], 'method': 'fts5_cached',
                             'unavailable': unavailable, 'unavailable_sources': sources,
                             'unsearched': (["Raw"] if not raw else []) + (["Output"] if not output else []) + ['changes_since_index'],
                             'truncated': len(hits) > max_hits}, max_bytes - 300)
        except (sqlite3.Error, OSError, ProductError):
            pass
    if not 1 <= max_hits <= 5 or not 512 <= max_bytes <= 65536:
        _error('bounds', 'Use 1–5 hits and a 512–65536 byte output budget.')
    paths, meta = _eligible(root, raw=raw, output=output)
    seeded = 0
    if not index.exists():
        try:
            seeded = _seed_private_baseline(root, state, index, paths)
        except (sqlite3.Error, OSError, ProductError):
            seeded = 0
    if not refresh:
        quick, candidates, unavailable, more_candidates, sources = _path_first(root, paths, terms, max_hits=max_hits)
        if quick:
            return _fit({'hits': quick, 'method': 'path_first',
                         'unavailable': meta['unavailable'] + unavailable,
                         'unavailable_sources': _source_names(meta['unavailable_sources'], sources),
                         'unsearched': meta['unsearched'] + ['other Wiki content'],
                         'truncated': True}, max_bytes - 300)
        if seeded:
            try:
                with contextlib.closing(_connect(index)) as db:
                    hits, unavailable, sources = _cached(db, root, terms, raw=raw, output=output)
                if hits:
                    return _fit({'hits': hits[:max_hits], 'method': 'fts5_baseline',
                                 'unavailable': meta['unavailable'] + unavailable,
                                 'unavailable_sources': _source_names(meta['unavailable_sources'], sources),
                                 'unsearched': meta['unsearched'] + ['changes_since_capture'],
                                 'truncated': len(hits) > max_hits}, max_bytes - 300)
            except (sqlite3.Error, OSError, ProductError):
                pass
    method = 'fts5'
    try:
        with contextlib.closing(_connect(_index_path(state, root))) as db:
            refreshed, refresh_sources = _refresh(db, paths)
            meta['unavailable'] += refreshed
            meta['unavailable_sources'] = _source_names(meta['unavailable_sources'], refresh_sources)
            hits, unavailable, sources = _fts(db, root, terms, paths)
            meta['unavailable'] += unavailable
            meta['unavailable_sources'] = _source_names(meta['unavailable_sources'], sources)
    except (sqlite3.Error, OSError, ProductError):
        method = 'direct'
        hits, unavailable, truncated, sources = _direct(root, paths, terms)
        meta['unavailable'] += unavailable
        meta['unavailable_sources'] = _source_names(meta['unavailable_sources'], sources)
        meta['truncated_scan'] = meta.get('truncated_scan', False) or truncated
    result = {'hits': hits[:max_hits], 'method': method, 'unavailable': meta['unavailable'],
              'unavailable_sources': meta['unavailable_sources'],
              'unsearched': meta['unsearched'], 'truncated': len(hits) > max_hits or meta.get('truncated_scan', False)}
    return _fit(result, max_bytes - 300)


def _bounded(operation, deadline, on_timeout):
    if not .1 <= deadline <= 30:
        _error('bounds', 'Use a 0.1–30 second deadline.')
    finished = threading.Event()
    outcome = {}

    def run():
        try:
            outcome['value'] = operation()
        except BaseException as exc:
            outcome['error'] = exc
        finally:
            finished.set()

    threading.Thread(target=run, daemon=True, name='bounded-markdown-memory').start()
    if not finished.wait(deadline):
        return on_timeout()
    if 'error' in outcome:
        raise outcome['error']
    return outcome['value']


def deadline_result(*, raw=False, output=False, max_bytes=2048):
    return _fit({'hits': [], 'method': 'deadline', 'unavailable': 'unknown',
                 'unavailable_sources': [],
                 'unsearched': ['Wiki', 'AGENTS.md', 'INDEX.md'] +
                               (['Raw'] if not raw else []) + (['Output'] if not output else []),
                 'truncated': True}, max_bytes - 300)


def bounded_cli(operation, *, command, raw=False, output=False, max_bytes=2048):
    """Include selected-root validation and cloud stat calls in the CLI deadline."""
    if command == 'recall':
        timeout = lambda: deadline_result(raw=raw, output=output, max_bytes=max_bytes)
    else:
        timeout = lambda: _error('deadline', 'Source read exceeded five seconds; no excerpt was returned.', 5)
    return _bounded(operation, 5.0, timeout)


def recall(root, state, query, *, raw=False, output=False, max_hits=5, max_bytes=2048,
           refresh=False, deadline=5.0):
    if not 1 <= max_hits <= 5 or not 512 <= max_bytes <= 65536:
        _error('bounds', 'Use 1–5 hits and a 512–65536 byte output budget.')
    if len(query) > 1024:
        _error('query', 'Search query exceeds 1024 characters.')
    terms = list(dict.fromkeys(TOKEN.findall(query)))[:12]
    if not terms:
        _error('query', 'Provide at least one search word.')
    return _bounded(lambda: _recall_impl(root, state, terms, raw=raw, output=output,
                                         max_hits=max_hits, max_bytes=max_bytes, refresh=refresh),
                    deadline, lambda: deadline_result(raw=raw, output=output, max_bytes=max_bytes))


def _relative(root, name, *, allowed_roots=('Wiki', 'Raw', 'Output')):
    if not name or Path(name).is_absolute() or '\\' in name or any(p in {'', '.', '..'} or p.startswith('.') or p.casefold() in PRIVATE or p.casefold() in PRIVATE_FILES or p.casefold() == 'coordination' for p in name.split('/')):
        _error('path', 'Use a vault-relative Markdown path without links or traversal.')
    if name not in {'AGENTS.md', 'INDEX.md'} and (name.split('/')[0] not in allowed_roots or len(name.split('/')) < 2):
        _error('scope', 'Path is outside the selected Markdown memory scope.')
    path = root.joinpath(*name.split('/'))
    if path.suffix.casefold() not in {'.md', '.markdown'}:
        _error('scope', 'Choose a Markdown file.')
    for ancestor in (path, *path.parents):
        if ancestor == root.parent:
            break
        if is_link_or_reparse(ancestor):
            _error('path', 'Path traverses a link or reparse point.')
        if ancestor != root and ancestor != path and (ancestor / '.shared-memory.json').exists():
            _error('nested_project', 'Nested project content is outside this selected folder.')
    if not path.is_file():
        _error('missing', 'Selected Markdown file is unavailable.', 5)
    return path


def _show_impl(root, name, sha256, start, end, *, max_bytes):
    if not HASH.fullmatch(sha256) or not 1 <= start <= end <= start + 79 or not 512 <= max_bytes <= 65536:
        _error('bounds', 'Use a source SHA-256, 1–80 lines, and a 512–65536 byte bound.')
    path = _relative(root, name)
    content = _read(path)
    if content is None:
        _error('unavailable', 'Selected Markdown file cannot be read safely.', 5)
    actual = _source_hash(content)
    if not actual.startswith(sha256):
        _error('stale', 'Source changed since recall; search again before quoting it.', 4)
    lines = content.splitlines()
    if end > len(lines):
        _error('bounds', 'Requested range exceeds this source.')
    excerpt = '\n'.join(lines[start - 1:end])
    if len(excerpt.encode('utf-8')) > max_bytes:
        _error('budget', 'Requested lines exceed the output budget; select fewer lines.')
    result = {'path': name, 'start': start, 'end': end, 'sha256': actual, 'excerpt': excerpt}
    if len(json.dumps(result, ensure_ascii=True).encode('utf-8')) > max_bytes - 300:
        _error('budget', 'Requested lines exceed the complete output budget; select fewer lines.')
    return result


def show(root, name, sha256, start, end, *, max_bytes=8192, deadline=5.0):
    return _bounded(lambda: _show_impl(root, name, sha256, start, end, max_bytes=max_bytes),
                    deadline, lambda: _error('deadline', 'Source read exceeded the deadline; no excerpt was returned.', 5))


@contextlib.contextmanager
def _local_lock(root):
    # Shared across every local actor binding for this physical project.
    from .onboarding import default_state
    state = private_path(default_state(root), root)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = state / '.append-row.lock'
    with open(path, 'a+b') as stream:
        deadline = time.monotonic() + 3
        while True:
            try:
                if os.name == 'nt':
                    import msvcrt
                    stream.seek(0)
                    if not stream.read(1):
                        stream.write(b'0'); stream.flush()
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    _error('busy', 'Another local table edit holds the append lock; retry later.', 4)
                time.sleep(.05)
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def append_row(root, name, heading, row):
    """Append to one existing Markdown table; preserve concurrent local appends."""
    if not heading.strip() or '\n' in heading or '\r' in heading or not row.startswith('|') or not row.endswith('|') or '\n' in row or '\r' in row:
        _error('row', 'Provide a heading and one complete single-line Markdown table row.')
    if not name.startswith('Wiki/'):
        _error('scope', 'Atomic rows are limited to existing Wiki tables.')
    path = _relative(root, name, allowed_roots=('Wiki',))
    with _local_lock(root):
        before = read_bytes(path, 10 * 1024 * 1024)
        try:
            content = before.decode('utf-8')
        except UnicodeError:
            _error('unavailable', 'Table file is not UTF-8.')
        newline = '\r\n' if '\r\n' in content else '\n'
        lines = content.splitlines(keepends=True)
        headings = [i for i, line in enumerate(lines) if (m := HEADING.match(line.rstrip('\r\n'))) and m.group(1).strip() == heading.strip()]
        if len(headings) != 1:
            _error('table', 'Find exactly one matching heading before its table.')
        i = headings[0] + 1
        separator = re.compile(r'\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*')
        while i + 1 < len(lines) and not HEADING.match(lines[i].rstrip('\r\n')):
            if lines[i].lstrip().startswith('|') and separator.fullmatch(lines[i + 1].rstrip('\r\n')):
                break
            i += 1
        if i + 1 >= len(lines) or HEADING.match(lines[i].rstrip('\r\n')):
            _error('table', 'Heading does not lead to a valid Markdown table.')
        columns = len(lines[i].strip().strip('|').split('|'))
        if len(row.strip().strip('|').split('|')) != columns:
            _error('row', 'Table row column count differs from the header.')
        # A long register may contain blank lines between batches of the same
        # table. Continue across those rows, but stop before a new heading,
        # prose, or a differently shaped table.
        cursor = i + 2
        j = cursor
        while cursor < len(lines):
            line = lines[cursor].strip()
            if not line:
                cursor += 1
                continue
            if HEADING.match(line) or not line.startswith('|'):
                break
            if len(line.strip('|').split('|')) != columns:
                break
            cursor += 1
            j = cursor
        inserted = row + newline
        if j and not lines[j - 1].endswith(('\n', '\r')):
            inserted = newline + inserted
        data = ''.join(lines[:j]).encode('utf-8') + inserted.encode('utf-8') + ''.join(lines[j:]).encode('utf-8')
        if read_bytes(path, 10 * 1024 * 1024) != before:
            _error('changed', 'Table changed while preparing the append; retry.', 4)
        info = path.lstat()
        fd, temp_name = tempfile.mkstemp(prefix='.shared-memory-row-', dir=path.parent)
        temporary = Path(temp_name)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            os.chmod(temporary, stat.S_IMODE(info.st_mode))
            os.replace(temporary, path)
            fsync_dir(path.parent)
        finally:
            temporary.unlink(missing_ok=True)
    return {'path': name, 'heading': heading, 'row_sha256': hashlib.sha256(row.encode('utf-8')).hexdigest(),
            'source_sha256': hashlib.sha256(data).hexdigest(), 'line': j + 1}
