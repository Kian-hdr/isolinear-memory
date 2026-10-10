"""Manifest-declared Markdown retrieval directories; no workspace mutation."""
from __future__ import annotations

import json
from pathlib import Path

from .errors import ProductError
from .folder import read_bytes, validate_vault_profile


def scope(root, *, raw=False, output=False):
    """Return selected directories and deliberately excluded source directories.

    Missing/unclassified manifests retain historical scope. Invalid declarations
    fail closed rather than silently widening retrieval to guessed directories.
    """
    manifest = Path(root) / '.shared-memory.json'
    if not manifest.exists():
        profile = None
    else:
        try:
            value = json.loads(read_bytes(manifest, 65536).decode('utf-8'))
        except (UnicodeError, ValueError) as error:
            raise ProductError(3, 'recall_profile', 'Cannot read the selected vault profile.') from error
        if not isinstance(value, dict):
            raise ProductError(3, 'recall_profile', 'Invalid selected vault manifest.')
        profile = value.get('vault_profile')
        validate_vault_profile(profile)
    if profile and profile['type'] == 'personal':
        return (['Notes'] + (['Resources'] if raw else []), [] if raw else ['Resources'])
    if profile and profile['type'] == 'project':
        # Directory roles are domain-specific. Do not infer source/output roles
        # from their names or include undeclared siblings from a populated vault.
        return list(profile['project_folders']), ['undeclared_project_folders']
    return (['Wiki'] + (['Raw'] if raw else []) + (['Output'] if output else []),
            ([] if raw else ['Raw']) + ([] if output else ['Output']))


def contains(name, roots):
    return name in {'AGENTS.md', 'INDEX.md'} or any(name.startswith(folder + '/') for folder in roots)
