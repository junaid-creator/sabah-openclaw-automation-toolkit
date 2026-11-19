"""Read-only executable prestart fence using native plugin discovery metadata.

Does not install, enable, stop or restart anything. A failed check exits nonzero
so an explicitly configured ExecStartPre can prevent startup on a separate host.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
from toolkit.gateway_monitor import startup_integrity


def trusted_file(value):
    path = Path(value)
    if not path.is_absolute() or path.resolve() != path or not path.is_file():
        raise ValueError('Absolute regular non-symlink path required')
    stat = path.stat()
    if stat.st_uid != os.geteuid() or stat.st_mode & 0o022:
        raise PermissionError('Owned non-writable-by-others file required')
    return path


def check(config, *, runner=subprocess.run):
    if not isinstance(config, dict) or set(config) != {'runtime', 'integrity'}:
        raise ValueError('Exact runtime and integrity contract required')
    runtime = config['runtime']
    if set(runtime) != {'node', 'entry', 'home', 'state', 'config'}:
        raise ValueError('Explicit isolated runtime paths required')
    node = Path(runtime['node'])
    # System-owned node is permitted, but mutable shared executables are not.
    if not node.is_absolute() or not node.is_file() or node.stat().st_mode & 0o022:
        raise PermissionError('Trusted absolute Node executable required')
    entry = trusted_file(runtime['entry'])
    native_config = trusted_file(runtime['config'])
    for key in ('home', 'state'):
        p = Path(runtime[key])
        if not p.is_absolute() or p.resolve() != p or not p.is_dir():
            raise ValueError('Existing absolute runtime directory required')
        if p.stat().st_uid != os.geteuid() or p.stat().st_mode & 0o077:
            raise PermissionError('Private owned runtime directory required')
    env = {'PATH': str(node.parent) + ':/usr/bin:/bin', 'HOME': runtime['home'],
           'LANG': 'C.UTF-8', 'OPENCLAW_STATE_DIR': runtime['state'],
           'OPENCLAW_CONFIG_PATH': str(native_config), 'OPENCLAW_SKIP_CHANNELS': '1',
           'OPENCLAW_SKIP_BROWSER_CONTROL_SERVER': '1', 'OPENCLAW_SKIP_CANVAS_HOST': '1'}
    result = runner([str(node), str(entry), 'plugins', 'list', '--json'],
                    env=env, cwd=runtime['home'], capture_output=True, timeout=30, check=False)
    if result.returncode != 0:
        raise PermissionError('Native plugin discovery failed; details withheld')
    if len(result.stdout) > 2_000_000:
        raise ValueError('Native plugin discovery exceeded bound')
    discovered = json.loads(result.stdout)
    if not isinstance(discovered, dict) or not isinstance(discovered.get('plugins'), list):
        raise ValueError('Unsupported native discovery schema')
    sources = {}
    for row in discovered['plugins']:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str):
            raise ValueError('Invalid native plugin record')
        if row['id'] in sources:
            raise PermissionError('Ambiguous native plugin identity')
        # Disabled, errored or merely discovered plugins are not an active guard.
        sources[row['id']] = row.get('source') if row.get('enabled') is True and row.get('status') == 'loaded' else None
    return startup_integrity(config['integrity'], plugin_source_reader=sources.get)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    try:
        path = trusted_file(args.config)
        if path.stat().st_mode & 0o077 or path.stat().st_size > 1_000_000:
            raise PermissionError('Bounded private fence configuration required')
        result = check(json.loads(path.read_text()))
    except (ValueError, OSError, PermissionError, subprocess.SubprocessError) as exc:
        print(json.dumps({'verified': False, 'error_type': type(exc).__name__, 'service_action': None}))
        return 78
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
