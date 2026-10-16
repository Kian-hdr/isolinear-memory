"""Optional content-addressed delivery of already-retained evidence.

This layer runs after recall's current-source checks. A receipt is a cache key,
not evidence of delivery, authorization, factual correctness or agent memory.
No upstream implementation is used; see docs/READINESS.md for design provenance.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re

from .errors import ProductError

MAX_KNOWN = 32
RECEIPT = re.compile(r'[0-9a-f]{32}\Z')


def validate(known):
    """Bound caller input before retrieval; never trust receipts as source data."""
    if (not isinstance(known, (list, tuple)) or len(known) > MAX_KNOWN or
            any(not isinstance(value, str) or not RECEIPT.fullmatch(value) for value in known)):
        raise ProductError(3, 'recall_receipt', 'Use at most 32 lowercase 32-hex evidence receipts.')
    return frozenset(known)


def _identity(root, hit):
    # Scope receipts to this local root, not a global content hash. Exact span
    # and excerpt are necessary: seeing one paragraph is not seeing a file.
    value = ['isolinear-evidence-v1', os.path.normcase(os.path.abspath(root)),
             hit['path'], hit['sha256'], hit['start'], hit['end'], hit['excerpt']]
    encoded = json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode('utf-8')
    # A 128-bit locator limits context overhead. The complete source SHA-256
    # stays in every hit; this locator grants no access and is not a signature.
    return hashlib.sha256(encoded).hexdigest()[:32]


def deliver(root, result, known, max_bytes, *, atomic=False):
    """Decorate final spans; omit text only for exact validated known passages.

    Never shorten a passage here: upstream has already applied query/date
    checks to its final span. Drop complete trailing hits if receipt metadata
    cannot fit, preserving coverage diagnostics and explicit truncation.
    """
    result = copy.deepcopy(result)
    for hit in result['hits']:
        receipt = _identity(root, hit)
        hit['evidence_id'] = receipt
        hit['delivery'] = 'unchanged' if receipt in known else 'full'
        if receipt in known:
            del hit['excerpt']

    # Recall reserves 300 bytes for the versioned CLI envelope. Use ordinary
    # JSON spacing here because that is how cli.emit actually serializes it.
    def size():
        return len(json.dumps(result, ensure_ascii=True).encode('utf-8'))

    if atomic and size() > max_bytes - 300:
        raise ProductError(3, 'context_budget', 'Complete context exceeds the output budget; no packet was returned.')
    while result['hits'] and size() > max_bytes - 300:
        result['hits'].pop()
        result['truncated'] = True
    if size() > max_bytes - 300:
        raise ProductError(3, 'recall_budget', 'Receipt metadata exceeds the requested byte budget.')
    return result
