"""Optional deterministic hybrid recall; current Markdown remains authoritative.

The private FTS index is an accelerator, never evidence. Fusion combines lexical
OR retrieval, title/path routing and explicit outbound wikilinks only. No model,
network service, inferred relationship or shared-file write is involved.

Design provenance: Vectorize Hindsight f7dd3f4fd7420f7beec60c32c965e5e5cf7be066
(search/fusion.py and temporal/filter tests), MIT, Copyright (c) 2025
Vectorize AI, Inc. Independently authored adaptation; no upstream code copied.
See docs/READINESS.md for the source-to-target map and semantic differences.
"""
from __future__ import annotations

import contextlib
import json
from datetime import date
from pathlib import Path
import re
import sqlite3
import threading
import time

from . import recall as source
from .errors import ProductError

MAX_CANDIDATES = 120
MAX_GRAPH_SEEDS = 12
MAX_GRAPH_TARGETS = 32
MAX_WARM_FILES = 30
MAX_PENDING_READS = 3
WARM_READ_SECONDS = 3.0
SOURCE_READ_SECONDS = .15
RRF_K = 60
ISO_DATE = re.compile(r'(?<![\w-])(\d{4}-\d{2}-\d{2})(?![\w-])')
WIKILINK = re.compile(r'\[\[([^\]\n]+)\]\]')
NOTE_STAMP = re.compile(r'^\s*(?:[*_]{0,2})?(?:updated|modified|last[_ -]updated|last[_ -]modified|created)(?:[*_]{0,2})?\s*:', re.IGNORECASE)


def validate_dates(after=None, before=None):
    """Validate inclusive YYYY-MM-DD bounds, without assuming event semantics."""
    parsed = []
    for value in (after, before):
        if value is None:
            parsed.append(None)
            continue
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            source._error('date', 'Use explicit YYYY-MM-DD date bounds.')
        try:
            parsed.append(date.fromisoformat(value))
        except ValueError:
            source._error('date', 'Use valid calendar dates in YYYY-MM-DD form.')
    if all(parsed) and parsed[0] > parsed[1]:
        source._error('date', 'The after date must not be later than before.')
    return tuple(parsed)


def _dated(excerpt, after, before):
    if after is None and before is None:
        return True
    # A note-maintenance stamp is not a dated source assertion. Other
    # literal dates are eligibility only, without inferred event semantics.
    text = '\n'.join(line for line in excerpt.splitlines() if not NOTE_STAMP.match(line))
    for match in ISO_DATE.finditer(text):
        try:
            value = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if (after is None or value >= after) and (before is None or value <= before):
            return True
    return False


def _key(hit):
    return hit['path'], hit['start'], hit['end']


def _blocks(name, content):
    digest = source._source_hash(content)
    return [{'path': name, 'heading': heading, 'start': start, 'end': end,
             'excerpt': text, 'sha256': digest}
            for start, end, heading, text in source._blocks(content)]


def _resolve_link(target, origin, names, *, allow_basename=True, roots=('Wiki', 'Raw', 'Output')):
    """Resolve a safe explicit path or unique basename, never guess ambiguity."""
    target = target.split('|', 1)[0].split('#', 1)[0].strip()
    if not target or '\\' in target or ':' in target or target.startswith('/'):
        return None
    parts = target.split('/')
    if any(not part or part in {'.', '..'} or part.startswith('.') for part in parts):
        return None
    variants = [target] if Path(target).suffix.casefold() in {'.md', '.markdown'} else [target + '.md', target + '.markdown']
    if len(parts) == 1:
        if not allow_basename:
            return None
        folded = {variant.casefold() for variant in variants}
        matches = [name for name in names if Path(name).name.casefold() in folded]
        return matches[0] if len(matches) == 1 else None
    # Declared profile directories are canonical project-root paths, never
    # originating-note-relative alternatives. Warm inventories cannot prove
    # uniqueness for arbitrary relative qualified links with uncaptured peers.
    if any(target == folder or target.startswith(folder + '/') for folder in roots):
        rooted = [variant for variant in variants if variant in names]
        return rooted[0] if len(rooted) == 1 else None
    if not allow_basename:
        return None
    explicit = set()
    for variant in variants:
        if variant in names:
            explicit.add(variant)
        relative = (Path(origin).parent / variant).as_posix()
        if relative in names:
            explicit.add(relative)
    if len(explicit) == 1:
        return next(iter(explicit))
    if explicit or len(parts) > 1:
        return None
    return None



def _scope_name(name, raw, output, roots=None):
    """Filter private index paths without touching a provider-backed folder."""
    if not isinstance(name, str) or not name or Path(name).is_absolute() or '\\' in name:
        return False
    parts = name.split('/')
    if any(not part or part in {'.', '..'} or part.startswith('.') or
           part.casefold() in source.PRIVATE or part.casefold() in source.PRIVATE_FILES or
           part.casefold() == 'coordination' for part in parts):
        return False
    if roots is None:
        roots = ('Wiki',) + (('Raw',) if raw else ()) + (('Output',) if output else ())
    return (Path(name).suffix.casefold() in {'.md', '.markdown'} and
            source._scope_contains(name, roots))


def _warm_inventory(root, state, terms, raw, output):
    """Use private capture/index for candidate routing, never a cloud walk."""
    roots, excluded = source._profile_scope(root, raw=raw, output=output)
    index = source._index_path(state, root)
    if not index.exists():
        baseline_path = index.parent / 'baseline.json'
        if not baseline_path.exists() or baseline_path.stat().st_size > source.MAX_DIRECT_BYTES:
            return None
        from .folder import Folder
        baseline = Folder(root, state)._baseline()
        with contextlib.closing(source._connect(index)) as db:
            scanned = 0
            for offset, (name, record) in enumerate(baseline.items()):
                if offset >= source.MAX_SCAN_FILES:
                    break
                content = record.get('text')
                if not _scope_name(name, raw, output, roots) or not isinstance(content, str):
                    continue
                size = len(content.encode('utf-8'))
                if size > source.MAX_FILE:
                    continue
                if scanned + size > source.MAX_DIRECT_BYTES:
                    break
                scanned += size
                db.executemany('INSERT INTO chunks(path,start,end,heading,text) VALUES(?,?,?,?,?)',
                               ((name, start, end, heading, block)
                                for start, end, heading, block in source._blocks(content)))
                db.execute('INSERT OR REPLACE INTO files VALUES(?,?,?,?,?,?)',
                           (name, -1, -1, -1, -1, source._source_hash(content)))
            db.commit()
    with contextlib.closing(source._connect(index)) as db:
        inventory = [name for (name,) in db.execute('SELECT path FROM files ORDER BY path LIMIT ?',
                                                   (source.MAX_SCAN_FILES + 1,))
                     if _scope_name(name, raw, output, roots)]
        incomplete = len(inventory) > source.MAX_SCAN_FILES
        inventory = inventory[:source.MAX_SCAN_FILES]
        names = set(inventory)
        # A newly opted-in scope must be inventoried before cached routing
        # can represent it. Cold hydration is explicit and remains bounded.
        if any(not any(name.startswith(folder + '/') for name in names) for folder in roots):
            return None
        expression = ' OR '.join('"' + term.replace('"', '""') + '"' for term in terms)
        rows = db.execute('SELECT path FROM chunks WHERE chunks MATCH ? '
                          'ORDER BY bm25(chunks),path,start LIMIT ?',
                          (expression, MAX_CANDIDATES + 1)).fetchall()
        selected = [name for (name,) in rows[:MAX_CANDIDATES] if name in names]
        titles = sorted((name for name in inventory if any(term in name.casefold() for term in terms)),
                        key=lambda name: (Path(name).stem.casefold() != ' '.join(terms),
                                          'archive' in (part.casefold() for part in Path(name).parts),
                                          -sum(term in name.casefold() for term in terms), name))
        selected = list(dict.fromkeys(titles[:12] + selected))
        limited = len(selected) > MAX_WARM_FILES
        selected = selected[:MAX_WARM_FILES]
        meta = {'unavailable': 0, 'unavailable_sources': [],
                'unsearched': excluded + ['changes_since_index', 'uncaptured_paths'],
                'truncated_scan': incomplete or limited or len(rows) > MAX_CANDIDATES or len(titles) > 12}
        return [(name, root / name) for name in selected], names, meta


def hybrid_recall(root, state, terms, *, raw, output, max_hits, max_bytes,
                  refresh, after=None, before=None):
    """Return bounded source-checked relevance candidates, inside recall._bounded.

    Date bounds require at least one literal valid ISO date in a returned
    passage. They do not filter modification timestamps or infer event dates.
    """
    after_date, before_date = validate_dates(after, before)
    if not 1 <= max_hits <= 5 or not 512 <= max_bytes <= 65536:
        source._error('bounds', 'Use 1–5 hits and a 512–65536 byte output budget.')
    terms = list(dict.fromkeys(term.casefold() for term in terms))[:12]
    if not terms:
        source._error('query', 'Provide at least one search word.')
    warm = None
    if not refresh:
        try:
            warm = _warm_inventory(root, state, terms, raw, output)
        except (OSError, sqlite3.Error, ProductError, ValueError, KeyError):
            warm = None
    if warm is not None:
        paths, inventory_names, meta = warm
    else:
        paths, meta = source._eligible(root, raw=raw, output=output)
        inventory_names = {name for name, _ in paths}
    allowed, _ = source._profile_scope(root, raw=raw, output=output)
    phrase = ' '.join(terms)
    # Read title candidates first when a provider-backed folder exceeds budgets.
    paths.sort(key=lambda item: (Path(item[0]).stem.casefold() != phrase,
                                 -sum(term in item[0].casefold() for term in terms), item[0]))
    documents = {}
    blocks = {}
    read_bytes = 0
    truncated = bool(meta.get('truncated_scan'))
    initial_names = {name for name, _ in paths}
    expanded_names = set()
    read_deadline = time.monotonic() + WARM_READ_SECONDS
    pending_reads = []
    timeout_marker = object()

    def read_live(name, remaining_bytes):
        path = source._relative(root, name, allowed_roots=allowed)
        size = path.stat().st_size
        if size > source.MAX_FILE:
            raise OSError('Source exceeds file bound')
        if size > remaining_bytes:
            raise OSError('Source read byte budget exceeded')
        return size, source._read(path)

    def partial_reads():
        if 'source_read_budget' not in meta['unsearched']:
            meta['unsearched'].append('source_read_budget')

    for name, _ in paths:
        try:
            if warm is not None:
                pending_reads = [event for event in pending_reads if not event.is_set()]
                remaining = read_deadline - time.monotonic()
                if remaining < .1 or len(pending_reads) >= MAX_PENDING_READS:
                    partial_reads()
                    truncated = True
                    break
                finished = threading.Event()

                def operation(name=name, finished=finished, remaining_bytes=source.MAX_DIRECT_BYTES - read_bytes):
                    try:
                        return read_live(name, remaining_bytes)
                    finally:
                        finished.set()

                value = source._bounded(operation, min(SOURCE_READ_SECONDS, remaining),
                                        lambda: timeout_marker)
                if value is timeout_marker:
                    pending_reads.append(finished)
                    partial_reads()
                    truncated = True
                    raise OSError('Source read deadline exceeded')
                size, content = value
            else:
                # Cold scans retain the original bounded per-file operation.
                path = source._relative(root, name, allowed_roots=allowed)
                size = path.stat().st_size
                if size > source.MAX_FILE:
                    raise OSError('Source exceeds file bound')
                if read_bytes + size > source.MAX_DIRECT_BYTES:
                    truncated = True
                    break
                content = source._read(path)
            if read_bytes + size > source.MAX_DIRECT_BYTES:
                truncated = True
                break
            read_bytes += size
            if content is None:
                raise OSError('Source is unavailable')
            actual_size = len(content.encode('utf-8'))
            read_bytes += max(0, actual_size - size)
            if read_bytes > source.MAX_DIRECT_BYTES:
                truncated = True
                break
            documents[name] = content
            blocks[name] = _blocks(name, content)
            if warm is not None and name in initial_names:
                for link in WIKILINK.findall(content):
                    target = _resolve_link(link, name, inventory_names, allow_basename=False, roots=allowed)
                    if target and target not in initial_names and target not in expanded_names:
                        if len(expanded_names) >= MAX_GRAPH_TARGETS:
                            truncated = True
                            break
                        expanded_names.add(target)
                        paths.append((target, root / target))
        except (OSError, ProductError):
            meta['unavailable'] += 1
            meta['unavailable_sources'] = source._source_names(meta['unavailable_sources'], [name])
    lists = {}
    fts_status = 'unavailable'
    try:
        index = source._index_path(state, root)
        existed = index.exists()
        with contextlib.closing(source._connect(index)) as db:
            if refresh or not existed or (warm is None and (raw or output)):
                # Index exactly the bounded bytes already inspected. Sentinel
                # stamps prevent normal recall from trusting metadata reuse.
                for name, content in documents.items():
                    db.execute('DELETE FROM chunks WHERE path=?', (name,))
                    db.executemany('INSERT INTO chunks(path,start,end,heading,text) VALUES(?,?,?,?,?)',
                                   ((name, hit['start'], hit['end'], hit['heading'], hit['excerpt'])
                                    for hit in blocks[name]))
                    db.execute('INSERT OR REPLACE INTO files VALUES(?,?,?,?,?,?)',
                               (name, -1, -1, -1, -1, source._source_hash(content)))
                if not truncated:
                    for (old,) in db.execute('SELECT path FROM files').fetchall():
                        if old not in documents:
                            db.execute('DELETE FROM chunks WHERE path=?', (old,))
                            db.execute('DELETE FROM files WHERE path=?', (old,))
                db.commit()
            expression = ' OR '.join('"' + term.replace('"', '""') + '"' for term in terms)
            rows = db.execute('SELECT path,start,end,text FROM chunks WHERE chunks MATCH ? '
                              'ORDER BY bm25(chunks),path,start LIMIT ?',
                              (expression, MAX_CANDIDATES + 1)).fetchall()
            truncated |= len(rows) > MAX_CANDIDATES
            lexical = []
            for name, start, end, text in rows[:MAX_CANDIDATES]:
                if name not in documents:
                    continue
                recorded = db.execute('SELECT sha256 FROM files WHERE path=?', (name,)).fetchone()
                if not recorded or recorded[0] != source._source_hash(documents[name]):
                    fts_status = 'stale'
                    continue
                match = next((hit for hit in blocks[name] if hit['start'] == start and hit['end'] == end and hit['excerpt'] == text), None)
                if match and _dated(text, after_date, before_date):
                    lexical.append(match)
            lists['bm25_or'] = lexical
            if fts_status != 'stale':
                fts_status = 'current'
    except (OSError, sqlite3.Error, ProductError):
        pass
    # Direct lexical OR remains useful without FTS5, and repairs candidate
    # coverage for notes whose index is stale. It shares the same read budget.
    lexical = []
    titles = []
    for name, passages in blocks.items():
        path_score = sum(term in name.casefold() for term in terms)
        for hit in passages:
            if not _dated(hit['excerpt'], after_date, before_date):
                continue
            hay = (hit['heading'] + ' ' + hit['excerpt']).casefold()
            matched = sum(term in hay for term in terms)
            if matched:
                lexical.append((matched, sum(hay.count(term) for term in terms), hit))
            title_score = path_score + sum(term in hit['heading'].casefold() for term in terms)
            if title_score:
                exact = Path(name).stem.casefold() == phrase
                titles.append((int(exact), title_score, matched, hit))
    lexical.sort(key=lambda item: (-item[0], -item[1], _key(item[2])))
    titles.sort(key=lambda item: (-item[0], -item[1], -item[2], _key(item[3])))
    truncated |= len(lexical) > MAX_CANDIDATES or len(titles) > MAX_CANDIDATES
    lists['lexical_or'] = [hit for _, _, hit in lexical[:MAX_CANDIDATES]]
    lists['title_path'] = [hit for _, _, _, hit in titles[:MAX_CANDIDATES]]
    # Seed one-hop outgoing links from relevant passages, not every note whose
    # filename happens to match. Read only already eligible/current sources.
    seeds = lists.get('bm25_or', []) + lists['lexical_or'] + lists['title_path']
    graph = []
    seed_keys = set()
    targets = set()
    for seed in seeds:
        if _key(seed) in seed_keys:
            continue
        if len(seed_keys) >= MAX_GRAPH_SEEDS:
            truncated = True
            break
        seed_keys.add(_key(seed))
        for link in WIKILINK.findall(seed['excerpt']):
            target = _resolve_link(link, seed['path'], inventory_names,
                                   allow_basename=warm is None and not meta.get('truncated_scan', False), roots=allowed)
            if target not in documents or target == seed['path'] or target in targets:
                continue
            if len(targets) >= MAX_GRAPH_TARGETS:
                truncated = True
                break
            targets.add(target)
            candidates = [hit for hit in blocks[target] if _dated(hit['excerpt'], after_date, before_date)]
            candidates.sort(key=lambda hit: (-sum(term in (hit['heading'] + ' ' + hit['excerpt']).casefold() for term in terms), hit['start']))
            if candidates:
                graph.append(candidates[0])
    lists['wikilink_one_hop'] = graph
    scores = {}
    hits = {}
    for strategy, ranked in lists.items():
        seen = set()
        for rank, hit in enumerate(ranked, 1):
            key = _key(hit)
            if key in seen:
                continue
            seen.add(key)
            scores[key] = scores.get(key, 0) + 1 / (RRF_K + rank)
            hits[key] = hit
    ordered = [hits[key] for key in sorted(scores, key=lambda key: (
        'archive' in (part.casefold() for part in Path(key[0]).parts), -scores[key], key))]
    # An exact current note title is an explicit navigation request. Keep a
    # compact live source anchor ahead of frequency-heavy archival passages,
    # including when a freshly edited note no longer matches its cached hash.
    routes = []
    for name, content in documents.items():
        if (Path(name).stem.casefold() != phrase or
                'archive' in (part.casefold() for part in Path(name).parts)):
            continue
        candidates = []
        heading = ''
        in_frontmatter = content.startswith('---\n')
        for line_number, line in enumerate(content.splitlines(), 1):
            if in_frontmatter:
                if line_number > 1 and line.strip() == '---':
                    in_frontmatter = False
                continue
            found_heading = source.HEADING.match(line)
            if found_heading:
                heading = found_heading.group(1).strip()[:160]
                continue
            if (not line.strip() or line.strip() in {'---', '```'} or NOTE_STAMP.match(line)
                    or len(line.encode('utf-8')) > min(1024, max_bytes // 2)
                    or not _dated(line, after_date, before_date)):
                continue
            candidates.append({'path': name, 'heading': heading, 'start': line_number,
                               'end': line_number, 'excerpt': line,
                               'sha256': source._source_hash(content)})
        candidates.sort(key=lambda hit: (
            -sum(term in hit['excerpt'].casefold() for term in terms), hit['start']))
        if candidates:
            routes.append(candidates[0])
    def contains_route(hit):
        return any(hit['path'] == route['path'] and hit['start'] <= route['start']
                   and hit['end'] >= route['end'] for route in routes)
    ordered = sorted(routes, key=_key) + [hit for hit in ordered if not contains_route(hit)]
    result = {'hits': ordered[:max_hits], 'method': 'hybrid',
              'unavailable': meta['unavailable'], 'unavailable_sources': meta['unavailable_sources'],
              'unsearched': meta['unsearched'] + (['candidate_or_scan_limits'] if truncated else []),
              'truncated': truncated or len(ordered) > max_hits,
              'retrieval': {'strategies': list(lists), 'fts': fts_status,
                            'semantic_model': False, 'fusion': 'rrf60',
                            'graph': ('qualified_outbound_seed_subset_one_hop' if warm is not None else
                                      'explicit_outbound_seed_subset_one_hop'),
                            'date_scope': 'excerpt_iso_dates' if after or before else 'none'}}
    # At the smallest envelope budget return compact diagnostics and fewer
    # excerpts, preserving the same source/scope status fields.
    if max_bytes < 1024:
        result['retrieval'] = {'semantic_model': False, 'graph': 'links1_subset'}
        if warm is not None:
            result['unsearched'] = [name for name in meta['unsearched']
                                   if name not in {'changes_since_index', 'uncaptured_paths', 'source_read_budget'}] + ['index_snapshot_only']
        if result['unavailable_sources']:
            # Counts stay exact; detailed source names may not fit this cap.
            result['unavailable_sources'] = source._source_names(
                [name.split('/', 1)[0] for name in result['unavailable_sources']])
        metadata = dict(result, hits=[])
        while result['unavailable_sources'] and len(json.dumps(metadata, ensure_ascii=True, separators=(',', ':')).encode('utf-8')) > max_bytes - 300:
            result['unavailable_sources'].pop()
            result['truncated'] = True
            metadata = dict(result, hits=[])
    result = source._fit(result, max_bytes - 300)
    # Output fitting can shorten distinct windows into the same source span.
    seen = set()
    distinct = []
    for hit in result['hits']:
        key = _key(hit)
        if key not in seen:
            distinct.append(hit)
            seen.add(key)
    result['hits'] = distinct
    # _fit can shorten passages; a date that was trimmed away must not make
    # the shortened excerpt appear to satisfy an explicit date bound.
    if after_date is not None or before_date is not None:
        retained = [hit for hit in result['hits'] if _dated(hit['excerpt'], after_date, before_date)]
        if len(retained) != len(result['hits']):
            result['truncated'] = True
            result['hits'] = retained
    return result
