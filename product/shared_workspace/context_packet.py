"""Complete authored bootstrap context, without summaries or a new memory store.

Independently authored design adaptation; see docs/PROGRESSIVE-CONTEXT.md.
Delivery is all-or-nothing. Source reads are individually checked, not a
transactional multi-file snapshot, and selected sections are not exhaustive policy.
"""
from __future__ import annotations

import json
import re

from . import evidence_receipts, recall
from .errors import ProductError

ATX = re.compile(r'^ {0,3}(#{1,6})(?:[ \t]+(.*))?$')
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')


def _error(code, message, status=3):
    raise ProductError(status, 'context_' + code, message)


def _headings(lines):
    """ATX headings outside frontmatter, fenced code and HTML comments."""
    fence = None
    frontmatter = bool(lines and lines[0].lstrip('\ufeff').strip() == '---')
    comment = False
    raw_tag = None
    for offset, line in enumerate(lines):
        if frontmatter:
            if offset and line.strip() in {'---', '...'}:
                frontmatter = False
            continue
        if fence is not None:
            marker, length = fence
            if re.fullmatch(r' {0,3}' + re.escape(marker) + r'{' + str(length) + r',}[ \t]*', line):
                fence = None
            continue
        if raw_tag is not None:
            if re.search(r'</' + raw_tag + r'\s*>', line, re.IGNORECASE):
                raw_tag = None
            continue
        found = FENCE.match(line) if not comment else None
        if found:
            run, info = found.groups()
            if run[0] != '`' or '`' not in info:
                fence = run[0], len(run)
                continue
        # Removing comments must never synthesize a new heading at column 0.
        # Only a physical ATX prefix already outside a comment may delimit a
        # section (e.g. '-->## Fake' remains ordinary text, not a boundary).
        physical_heading = not comment and ATX.match(line) is not None
        # Comments can start after ordinary text, not only at line start.
        visible = ''
        rest = line
        while rest:
            if comment:
                close = rest.find('-->')
                if close < 0:
                    break
                rest = rest[close + 3:]
                comment = False
            else:
                opening = rest.find('<!--')
                if opening < 0:
                    visible += rest
                    break
                visible += rest[:opening]
                rest = rest[opening + 4:]
                comment = True
        line = visible
        raw = re.match(r'^ {0,3}<(script|pre|style|textarea)(?:[ \t>]|$)', line, re.IGNORECASE)
        if raw:
            tag = raw.group(1).lower()
            if not re.search(r'</' + tag + r'\s*>', line, re.IGNORECASE):
                raw_tag = tag
            continue
        if re.match(r'^ {0,3}</?[A-Za-z][\w-]*(?:[ \t/>]|$)', line):
            _error('heading', 'Raw HTML section boundaries are unsupported; choose the complete source.')
        found = ATX.match(line) if physical_heading else None
        if found:
            text = (found.group(2) or '').strip()
            text = re.sub(r'[ \t]+#+[ \t]*$', '', text).strip()
            yield offset, len(found.group(1)), text


def _span(content, heading):
    lines = content.splitlines()
    if not lines:
        _error('source', 'A required context source is empty; no packet was returned.')
    if heading is None:
        return 1, len(lines), '\n'.join(lines)
    headings = list(_headings(lines))
    matches = [(offset, level) for offset, level, text in headings if text == heading]
    if len(matches) != 1:
        _error('heading', 'Choose one exact, unique ATX heading; no packet was returned.')
    start, level = matches[0]
    end = next((offset for offset, depth, _ in headings if offset > start and depth <= level), len(lines))
    return start + 1, end, '\n'.join(lines[start:end])


def _context(root, name, heading, max_bytes, receipt_mode, known):
    roots, excluded = recall._profile_scope(root, raw=False, output=False)
    hits = []
    for path_name, selected_heading in [('AGENTS.md', None), ('INDEX.md', None), (name, heading)]:
        try:
            path = recall._relative(root, path_name, allowed_roots=roots)
        except ProductError as error:
            if error.code == 'recall_missing':
                _error('source', 'A required context source is unavailable; no packet was returned.', 5)
            raise
        content = recall._read(path)
        if content is None:
            _error('source', 'A required context source cannot be read safely; no packet was returned.', 5)
        start, end, excerpt = _span(content, selected_heading)
        hits.append({'path': path_name, 'heading': selected_heading or '', 'start': start,
                     'end': end, 'sha256': recall._source_hash(content), 'excerpt': excerpt})
    result = {'hits': hits, 'method': 'context_packet', 'unavailable': 0,
              'unavailable_sources': [], 'unsearched': excluded + ['other_sections', 'linked_sources'],
              'truncated': False, 'snapshot': 'per_source', 'derivation': 'authored_exact'}
    if receipt_mode:
        return evidence_receipts.deliver(root, result, known, max_bytes, atomic=True)
    if len(json.dumps(result, ensure_ascii=True).encode('utf-8')) > max_bytes - 300:
        _error('budget', 'Complete context exceeds the output budget; no packet was returned.')
    return result


def context(root, name, heading=None, *, max_bytes=8192, deadline=5.0,
            with_receipts=False, known_evidence=()):
    """Return complete instructions/index/selected section, or no excerpts."""
    if not 512 <= max_bytes <= 65536:
        _error('budget', 'Use a 512–65536 byte context output budget.')
    if not isinstance(name, str) or name in {'AGENTS.md', 'INDEX.md'}:
        _error('source', 'Choose a separate canonical Markdown source.')
    if heading is not None and (not isinstance(heading, str) or not heading.strip() or len(heading) > 160):
        _error('heading', 'Use a nonempty exact heading of at most 160 characters.')
    known = evidence_receipts.validate(known_evidence)
    return recall._bounded(lambda: _context(root, name, heading, max_bytes,
                                           with_receipts or bool(known), known), deadline,
                           lambda: _error('deadline', 'Context read exceeded the deadline; no packet was returned.', 5))
