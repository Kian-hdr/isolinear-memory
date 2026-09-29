#!/usr/bin/env python3
"""Install a stable, checksum-bound command for an already verified runtime."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import re


def launcher(python, runtime, digest):
    return (f'#!{python}\n' + '''import hashlib, json, os, sys
from pathlib import Path
''' + f'RUNTIME = {str(runtime)!r}\nEXPECTED = {digest!r}\nPYTHON = {str(python)!r}\n' + '''try:
    if hashlib.sha256(Path(RUNTIME).read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('Installed runtime checksum changed; restore or reinstall the verified package.')
    args = sys.argv[1:]
    if args and args[0] in ('sync', 'folder-status') and '--full' not in args and '--brief' not in args:
        args.append('--brief')
    args = [arg for arg in args if arg != '--full']
    os.execv(PYTHON, [PYTHON, RUNTIME, *args])
except (OSError, ValueError) as error:
    print(json.dumps({'ok': False, 'code': 'launcher_error', 'message': str(error)}))
    sys.exit(5)
''')


def managed_launcher(raw):
    """Recognize this exact generated launcher without executing prior code."""
    try:
        source = raw.decode('utf-8')
        values = {}
        for node in ast.parse(source).body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name in {'RUNTIME', 'EXPECTED', 'PYTHON'}:
                    values[name] = ast.literal_eval(node.value)
        if (set(values) != {'RUNTIME', 'EXPECTED', 'PYTHON'}
                or any(not isinstance(value, str) for value in values.values())
                or not re.fullmatch(r'[0-9a-f]{64}', values['EXPECTED'])
                or not Path(values['RUNTIME']).is_absolute()
                or not Path(values['PYTHON']).is_absolute()):
            return False
        return raw == launcher(values['PYTHON'], values['RUNTIME'], values['EXPECTED']).encode()
    except (UnicodeError, SyntaxError, ValueError, TypeError, KeyError, RecursionError):
        return False


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--sha256', required=True)
    p.add_argument('--destination', type=Path, default=Path.home()/'.local/bin/isolinear-memory')
    p.add_argument('--no-legacy-alias', action='store_true',
                   help='Do not update the compatible shared-memory launcher beside the canonical command')
    a = p.parse_args()
    if os.name == "nt":
        p.error("The command launcher supports macOS/Linux; on Windows use Python with the verified .pyz directly.")
    runtime = a.runtime.expanduser().absolute()
    target = a.destination.expanduser().absolute()
    if runtime.resolve() != runtime or not runtime.is_file():
        p.error('Runtime must be a physical installed file.')
    if hashlib.sha256(runtime.read_bytes()).hexdigest() != a.sha256:
        p.error('Runtime checksum mismatch.')
    python = Path(sys.executable).resolve()
    if any(c in str(python) for c in (' ', '\n')):
        p.error('Interpreter shebang requires a path without spaces; choose a compatible interpreter.')
    data = launcher(python, runtime, a.sha256).encode()
    targets = [target]
    if not a.no_legacy_alias and target.name != 'shared-memory':
        targets.append(target.with_name('shared-memory'))
    observed = {}
    for destination in targets:
        if destination.is_symlink() or destination.parent.resolve() != destination.parent:
            p.error('Command destination must not traverse symlinks.')
        if destination.exists():
            if not destination.is_file() or destination.stat().st_size > 64 * 1024:
                p.error('Existing command is not a bounded regular launcher; no launcher was changed.')
            prior = destination.read_bytes()
            if prior != data and not managed_launcher(prior):
                p.error('Existing command is not a recognized Isolinear/Shared Memory launcher; no launcher was changed. Use --no-legacy-alias only after reviewing the destination.')
            observed[destination] = prior
        else:
            observed[destination] = None
    installed = []
    for destination in targets:
        destination.parent.mkdir(parents=True, exist_ok=True)
        current = destination.read_bytes() if destination.exists() else None
        if current != observed[destination]:
            p.error('Command changed during installation; retry after inspecting it.')
        recovery = None
        if current is not None and current != data:
            recovery = destination.with_name(destination.name + '.previous-' + str(time.time_ns()))
            shutil.copy2(destination, recovery)
        temporary = destination.with_name(destination.name + '.new-' + str(time.time_ns()))
        with temporary.open('xb') as f:
            f.write(data)
        temporary.chmod(0o755)
        os.replace(temporary, destination)
        installed.append({'command': str(destination), 'recovery': str(recovery) if recovery else None})
    print(json.dumps({'command': str(target), 'runtime': str(runtime),
                      'recovery': installed[0]['recovery'], 'launchers': installed}))


if __name__ == '__main__':
    main()
