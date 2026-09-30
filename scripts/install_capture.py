#!/usr/bin/env python3
"""Prepare/install one user LaunchAgent, or run its bounded capture operation."""
import argparse
try:
    import fcntl
except ImportError:  # Windows may inspect/prepare configuration, but cannot run a LaunchAgent.
    fcntl = None
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time


def physical(value):
    path = Path(value).expanduser().absolute()
    for candidate in (path, *path.parents):
        if candidate.is_symlink() or (candidate.exists() and getattr(candidate.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Symlink/reparse paths are not supported; supply a physical absolute path.')
    if path.resolve() != path:
        raise ValueError('Symlink paths are not supported; supply the physical absolute path.')
    return path


def private(path, project):
    path = physical(path)
    if path == project or project in path.parents or path in project.parents:
        raise ValueError('Private capture/state paths must be separate from the selected workspace.')
    lower = str(path).replace('\\', '/').casefold()
    if lower.startswith('//') or any(marker in lower for marker in ('/cloudstorage/', '/mobile documents/', '/nextcloud/', 'onedrive', 'googledrive', 'google drive', 'dropbox')):
        raise ValueError('Private capture/state paths must be outside synchronized or network storage.')
    for parent in (path, *path.parents):
        if (parent / '.shared-memory.json').exists() or parent.name.casefold() in ('cloudstorage', 'mobile documents', 'nextcloud', 'box'):
            raise ValueError('Private capture/state paths must be outside synchronized workspaces.')
    return path


def validate(config):
    project = physical(config['project'])
    state = private(config['state'], project)
    binding_path = state / ('folder/folder.json' if (state / 'connection.json').exists() else 'folder.json')
    manifest = json.loads(physical(project / '.shared-memory.json').read_text())
    binding = json.loads(physical(binding_path).read_text())
    if manifest.get('format_version') != 3 or manifest.get('workflow') != 'folder':
        raise ValueError('Automatic capture requires an existing format-3 folder workspace.')
    if binding.get('readonly') is not False:
        raise ValueError('Automatic capture refuses read-only or unknown access bindings.')
    if binding.get('root') != str(project) or binding.get('project_id') != manifest.get('project_id'):
        raise ValueError('Private binding does not match the selected workspace.')
    if config.get('project_id', manifest['project_id']) != manifest['project_id']:
        raise ValueError('Workspace identity changed; prepare a new installation.')
    for key in ('python', 'runtime'):
        path = physical(config[key]) if key == 'python' else private(config[key], project)
        if not path.is_file():
            raise ValueError(f'{key} must be an existing absolute file.')
    if not os.access(config['python'], os.X_OK):
        raise ValueError('Python interpreter is not executable.')
    if hashlib.sha256(Path(config['runtime']).read_bytes()).hexdigest() != config.get('sha256'):
        raise ValueError('Runtime SHA-256 does not match the explicitly verified expected digest.')
    private(config['capture'], project)
    return manifest['project_id']


def atomic(path, data):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Refusing a symlink output.')
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def command(config):
    return [config['python'], config['runtime'], 'sync', config['project'], '--state-dir', config['state'], '--brief']


def folder_state(config):
    state = Path(config['state'])
    return state / 'folder' if (state / 'connection.json').exists() else state



def fingerprint(project, stop=None):
    """Cheap metadata hint; any incomplete scan disables the idle optimization.

    Open each directory relative to its held parent descriptor with O_NOFOLLOW.
    Include portable history and ignored paths conservatively; never follow links.
    This is an idle check, not a replacement for runtime content validation.
    """
    if not hasattr(os, 'O_NOFOLLOW') or os.scandir not in os.supports_fd:
        return None
    digest = hashlib.sha256(b'shared-memory-capture-stat-v1\0')
    entries = 0

    def record(relative, metadata):
        nonlocal entries
        if stop is not None and stop.is_set():
            raise TimeoutError()
        entries += 1
        digest.update(json.dumps((relative, metadata.st_dev, metadata.st_ino,
                      metadata.st_mode, metadata.st_size, metadata.st_mtime_ns,
                      metadata.st_ctime_ns), ensure_ascii=True).encode())
        digest.update(b'\0')

    def scan(descriptor, relative):
        if stop is not None and stop.is_set():
            raise TimeoutError()
        record(relative, os.fstat(descriptor))
        with os.scandir(descriptor) as iterator:
            children = sorted(iterator, key=lambda item: item.name)
        for child in children:
            if stop is not None and stop.is_set():
                raise TimeoutError()
            path = relative + '/' + child.name
            metadata = child.stat(follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode) and not getattr(metadata, 'st_file_attributes', 0) & 0x400:
                nested = os.open(child.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                try:
                    scan(nested, path)
                finally:
                    os.close(nested)
            else:
                record(path, metadata)

    try:
        root = os.open(project, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            scan(root, '')
        finally:
            os.close(root)
    except (OSError, RecursionError, TimeoutError):
        return None
    return {'version': 1, 'sha256': digest.hexdigest(), 'entries': entries}


def bounded_fingerprint(project, timeout=10):
    """Disable idle reuse if provider metadata does not finish promptly."""
    stop = threading.Event()
    done = threading.Event()
    result = {}
    def scan():
        try:
            result['value'] = fingerprint(project, stop=stop)
        except Exception:
            result['value'] = None
        finally:
            done.set()
    threading.Thread(target=scan, daemon=True).start()
    if not done.wait(timeout):
        stop.set()
        return None
    return result.get('value')


def cached_result(capture):
    try:
        path = physical(capture / 'last-result.json')
        if path.stat().st_size > 32768:
            return None
        result = json.loads(path.read_text())
        return result if isinstance(result, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def brief_status(loaded, healthy, stale, last):
    """Small agent-facing health signal; detailed diagnostics stay private."""
    if not loaded:
        state = 'unloaded'
    elif last is None:
        state = 'no_result'
    elif stale:
        state = 'stale'
    elif last.get('ok') is not True:
        state = 'failed'
    elif last.get('readiness') != 'ready':
        state = 'partial'
    elif not healthy:
        state = 'configuration_changed'
    else:
        state = 'ready'
    return {'local_capture': state, 'attention_required': not healthy}


def brief_status_failure(error, phase):
    """Normalize pre-status failures without exposing their exception text."""
    if phase == 'config' and isinstance(error, FileNotFoundError):
        state = 'unconfigured'
    elif phase == 'config' and isinstance(error, (ValueError, UnicodeError, KeyError, TypeError, AttributeError, IndexError)):
        state = 'configuration_invalid'
    else:
        state = 'unavailable'
    return {'local_capture': state, 'attention_required': True}


def capture_signature(config):
    binding = folder_state(config) / 'folder.json'
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode())
    digest.update(physical(binding).read_bytes())
    # Updating the installed runner also forces a fresh full capture.
    digest.update(Path(__file__).read_bytes())
    return digest.hexdigest()


def recent_full_capture(result):
    # Both clocks bound idle reuse. Either clock moving backwards invalidates
    # the cache rather than extending its lifetime.
    for key, now in (('synced_at', time.time()), ('full_sync_monotonic', time.monotonic())):
        stamp = result.get(key)
        if not isinstance(stamp, (int, float)) or not 0 <= now - stamp < 600:
            return False
    return True


def error_kind(error):
    """Keep exception paths and possibly private subprocess text out of status."""
    if isinstance(error, subprocess.TimeoutExpired):
        return 'timeout_300s'
    if isinstance(error, OSError):
        import errno
        return 'os_' + errno.errorcode.get(error.errno, 'UNKNOWN')
    return type(error).__name__


def runtime_failure(payload):
    code = payload.get('code') if isinstance(payload, dict) else None
    if not isinstance(code, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', code):
        code = 'runtime_failure'
    # These messages are generated by this package from fixed labels and OS
    # error codes. Other runtime messages can contain note text or private paths.
    message = payload.get('message') if isinstance(payload, dict) else None
    safe_io = (isinstance(message, str) and re.fullmatch(
        r'Folder operation failed during [a-z_]+ \([A-Za-z]+, [A-Z0-9_]+\); preserve history and private recovery state\.', message))
    safe_lock = message == 'Private folder state remained busy; retry after the other operation finishes.'
    if (code == 'folder_io' and safe_io) or (code == 'folder_lock_timeout' and safe_lock):
        return code, message
    return code, 'Runtime reported failure; inspect the direct CLI response privately.'


def read_progress(config, started_at):
    """Read only an enumerated, fresh phase marker from private state."""
    try:
        path = physical(folder_state(config) / 'capture-progress.json')
        if path.stat().st_size > 2048:
            return None
        record = json.loads(path.read_text())
        phase = record.get('phase')
        stamp = record.get('updated_at')
        if (record.get('format') != 1 or not isinstance(phase, str)
                or not re.fullmatch(r'[a-z_]{1,48}', phase)
                or not isinstance(stamp, (int, float)) or stamp < started_at - 1):
            return None
        result = {'phase': phase}
        if type(record.get('count')) is int and 0 <= record['count'] <= 1_000_000:
            result['count'] = record['count']
        return result
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def run_once(config):
    if fcntl is None:
        raise ValueError('Automatic capture requires POSIX file locking; use the ordinary sync command on this platform.')
    capture = private(config['capture'], physical(config['project']))
    # launchd serializes this job; this additional lock also covers manual runs.
    if (capture / 'run.lock').is_symlink():
        raise ValueError('Refusing a symlink capture lock.')
    with (capture / 'run.lock').open('a') as lock:
        os.chmod(capture / 'run.lock', 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 75
        started = time.perf_counter()
        result = {'checked_at': time.time(), 'ok': False, 'mode': 'sync', 'phase': 'validate'}
        code = 1
        try:
            validate(config)
            result['phase'] = 'fingerprint'
            signature = capture_signature(config)
            before = bounded_fingerprint(config['project'])
            previous = cached_result(capture)
            if (before is not None and previous and previous.get('ok') is True
                    and previous.get('readiness') == 'ready'
                    and previous.get('capture_signature') == signature
                    and previous.get('pre_sync_fingerprint') == before
                    and recent_full_capture(previous)):
                result = {**previous, 'checked_at': time.time(), 'unchanged': True,
                          'mode': 'unchanged', 'phase': 'complete',
                          'duration_seconds': round(time.perf_counter() - started, 6)}
                atomic(capture / 'last-result.json', json.dumps(result, indent=2).encode())
                return 0
            result['unchanged'] = False
            # Output can contain private paths. Keep only the final bounded result,
            # never append forever or emit it into launchd's system log.
            result['phase'] = 'runtime_sync'
            completed = subprocess.run(command(config), capture_output=True, timeout=300,
                                       env={**os.environ, 'SHARED_MEMORY_CAPTURE_PHASES': '1'})
            code = completed.returncode
            result['exit_code'] = code
            try:
                payload = json.loads(completed.stdout)
                result['ok'] = code == 0 and payload.get('ok') is True
                data = payload.get('data', {})
                result['readiness'] = data.get('readiness')
                result['provider_delivery'] = data.get('provider_delivery', 'unverified')
                result['attention_required'] = result['readiness'] != 'ready'
                result['summary'] = {key: value for key, value in data.items() if key in ('counts', 'attention', 'changes', 'conflicts', 'pending', 'excluded_count', 'partial_count', 'events', 'provider_duplicate_bytes_unverified')}
                if len(json.dumps(result['summary'])) > 8192:
                    result['summary'] = {'truncated': True, 'message': 'Inspect folder-status --brief for details.'}
                if not result['ok']:
                    result['error_code'], result['error'] = runtime_failure(payload)
            except (ValueError, AttributeError):
                result['ok'] = False
                result['error'] = 'Runtime did not return a valid JSON success response.'
            if not result['ok']:
                result['stderr_bytes'] = len(completed.stderr)
                code = code or 1
        except Exception as error:
            result['ok'] = False
            code = code or 1
            result['error_code'] = error_kind(error)
            result['error'] = ('Runtime exceeded the 300 second capture limit; its outcome is unknown.'
                               if isinstance(error, subprocess.TimeoutExpired)
                               else 'Capture could not finish; inspect the selected phase and error code.')
            if result['phase'] == 'validate' and str(error) == 'Runtime SHA-256 does not match the explicitly verified expected digest.':
                result['error'] = str(error)
        if result.get('phase') == 'runtime_sync':
            progress = read_progress(config, result['checked_at'])
            if progress:
                result['runtime_progress'] = progress
        if result['ok'] and result.get('readiness') == 'ready':
            result['synced_at'] = time.time()
            result['full_sync_monotonic'] = time.monotonic()
            result['capture_signature'] = signature
            # Only the PRE-sync snapshot is cached. A concurrent edit, or a new
            # history event written by sync itself, forces a subsequent full run.
            if before is not None:
                result['pre_sync_fingerprint'] = before
        if result['ok'] and result.get('attention_required'):
            code = 2
        if result['ok']:
            result['phase'] = 'complete'
        result['duration_seconds'] = round(time.perf_counter() - started, 6)
        atomic(capture / 'last-result.json', json.dumps(result, indent=2).encode())
        return code


def plan(args):
    project = physical(args.project)
    identifier = hashlib.sha256(str(project).encode()).hexdigest()[:16]
    capture = Path.home() / 'Library/Application Support/Shared Memory/Capture' / identifier
    if getattr(args, 'status', False) or getattr(args, 'uninstall', False):
        config = json.loads(physical(capture / 'config.json').read_text())
        if config.get('project') != str(project) or config.get('capture') != str(capture):
            raise ValueError('Saved capture configuration does not match this workspace path.')
    else:
        if not all((args.state_dir, args.runtime, args.sha256)):
            raise ValueError('--state-dir, --runtime and independently verified --sha256 are required.')
        config = dict(project=str(project), state=str(physical(args.state_dir)),
                  python=str(physical(args.python)), runtime=str(physical(args.runtime)), capture=str(capture), sha256=args.sha256.lower(), interval=args.interval)
        config['project_id'] = validate(config)
    label = 'space.sharedmemory.capture.' + identifier
    plist = {'Label': label, 'ProgramArguments': [config['python'], str(capture / 'capture.py'),
             '--run-config', str(capture / 'config.json')], 'StartInterval': config.get('interval', args.interval),
             'RunAtLoad': True, 'ProcessType': 'Background', 'Umask': 0o077}
    return config, plist, Path.home() / 'Library/LaunchAgents' / (label + '.plist')


def launchctl(*args, check=True):
    if sys.platform != 'darwin':
        raise ValueError('LaunchAgent control requires macOS.')
    return subprocess.run(['/bin/launchctl', *args], check=check, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', nargs='?')
    parser.add_argument('--state-dir')
    parser.add_argument('--runtime')
    parser.add_argument('--sha256', help='Independently verified SHA-256 of the installed runtime')
    parser.add_argument('--python', default=str(Path(sys.executable).resolve()))
    parser.add_argument('--interval', type=int, default=60, choices=range(30, 3601))
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--uninstall', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--brief', action='store_true',
                        help='With --status, print only local capture health for an agent')
    parser.add_argument('--run-config')
    args = parser.parse_args()
    status_phase = 'config'
    try:
        if args.run_config:
            config_path = physical(args.run_config)
            config = json.loads(config_path.read_text())
            if config_path.parent != physical(config['capture']):
                raise ValueError('Configuration must live in its private capture directory.')
            return run_once(config)
        if not args.project:
            if args.status and args.brief:
                print(json.dumps({'local_capture': 'unconfigured', 'attention_required': True}))
                return 2
            parser.error('project is required')
        if sum((args.install, args.uninstall, args.status)) > 1:
            parser.error('Choose only one of --install, --uninstall, --status')
        if args.brief and not args.status:
            parser.error('--brief requires --status')
        config, plist, destination = plan(args)
        status_phase = 'control'
        capture = Path(config['capture'])
        if not args.install and not args.uninstall and not args.status:
            print(json.dumps({'config': config, 'plist': plist, 'destination': str(destination)}, indent=2))
            return 0
        if sys.platform != 'darwin':
            raise ValueError('LaunchAgent control requires macOS.')
        target = 'gui/' + str(os.getuid())
        service = target + '/' + plist['Label']
        if args.status:
            status = launchctl('print', service, check=False)
            last = cached_result(capture)
            checked_at = last.get('checked_at') if last else None
            stale = (type(checked_at) not in (int, float) or
                     not 0 <= time.time() - checked_at <= max(600, config.get('interval', 60) * 2 + 300))
            try:
                validate(config)
                current_signature = capture_signature(config)
            except (OSError, ValueError):
                current_signature = None
            healthy = bool(status.returncode == 0 and last and last.get('ok') and last.get('readiness') == 'ready'
                           and current_signature and last.get('capture_signature') == current_signature and not stale)
            if args.brief:
                print(json.dumps(brief_status(status.returncode == 0, healthy, stale, last)))
            else:
                print(json.dumps({'loaded': status.returncode == 0, 'healthy': healthy,
                                  'health_scope': 'local_capture_only',
                                  'provider_integrity': 'unverified' if last and last.get('provider_delivery') != 'not_applicable' else 'not_applicable',
                                  'stale': stale, 'plist': str(destination), 'last_result': last}))
            return 0 if healthy else 2
        private(capture, Path(config['project']))
        if args.install:
            # A full folder-status reads every provider event and can take many
            # minutes on cloud-backed roots. Validate binding and package digest
            # now; only a later completed sync can establish capture health.
            validate(config)
        capture.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(capture, 0o700)
        loaded = launchctl('print', service, check=False).returncode == 0
        if destination.is_symlink():
            raise ValueError('Refusing a symlink LaunchAgent plist.')
        if destination.exists():
            existing = plistlib.loads(destination.read_bytes())
            if existing.get('Label') != plist['Label'] or existing.get('ProgramArguments', [None, None])[1:2] != [str(capture / 'capture.py')]:
                raise ValueError('Existing plist is not owned by this capture installation.')
            if not args.uninstall and destination.read_bytes() != plistlib.dumps(plist):
                shutil.copy2(destination, capture / ('previous-' + str(time.time_ns()) + '.plist'))
        if loaded and not destination.exists():
            raise ValueError('Loaded label has no owned plist; refusing to modify it.')
        if loaded:
            launchctl('bootout', service)
        if args.uninstall:
            if destination.exists():
                destination.rename(capture / ('uninstalled-' + str(time.time_ns()) + '.plist'))
            print(json.dumps({'uninstalled': True, 'history_preserved': True, 'private_recovery': str(capture)}))
            return 0
        destination.parent.mkdir(parents=True, exist_ok=True)
        for name, data in (('capture.py', Path(__file__).read_bytes()), ('config.json', json.dumps(config).encode())):
            path = capture / name
            if path.is_symlink():
                raise ValueError('Refusing a symlink capture file.')
            if path.exists() and path.read_bytes() != data:
                shutil.copy2(path, capture / ('previous-' + str(time.time_ns()) + '-' + name))
            atomic(path, data)
        atomic(destination, plistlib.dumps(plist))
        launchctl('bootstrap', target, str(destination))
        launchctl('print', service)
        print(json.dumps({'installed': True, 'capture_verified': False,
                          'label': plist['Label'], 'result': str(capture / 'last-result.json')}))
        return 0
    except Exception as error:
        if args.status and args.brief:
            print(json.dumps(brief_status_failure(error, status_phase)))
            return 2
        if args.run_config:
            # launchd logs must not receive private paths or untrusted note text.
            print(json.dumps({'ok': False, 'error_code': error_kind(error)}), file=sys.stderr)
        else:
            print(json.dumps({'ok': False, 'error': str(error)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
