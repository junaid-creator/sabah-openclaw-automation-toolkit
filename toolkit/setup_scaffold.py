"""Create an inert workspace scaffold only; never touch an OpenClaw profile."""
import argparse
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def scaffold(destination, *, apply=False):
    target = Path(destination).expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise ValueError('Destination must not exist; no merge or overwrite is performed')
    # Explicitly exclude OpenClaw profile locations even when nonexistent.
    if '.openclaw' in target.parts:
        raise ValueError('Use a separate staging directory, not an OpenClaw profile')
    manifest = {'destination': str(target), 'activated': False,
                'agents': ['main-assistant', 'customer-support'],
                'network': False, 'paid_apis': False, 'schedules': False,
                'publishing': False, 'customer_sending': False}
    if not apply:
        return dict(manifest, applied=False)
    target.mkdir(mode=0o700, parents=False, exist_ok=False)
    for agent in manifest['agents']:
        workspace = target/agent
        workspace.mkdir(mode=0o700)
        (workspace/'knowledge').mkdir(mode=0o700)
        source = ROOT/'agents'/agent
        for path in source.glob('*.md'):
            shutil.copyfile(path, workspace/path.name)
        if agent == 'customer-support':
            shutil.copyfile(source/'company-profile.example.json', workspace/'company-profile.example.json')
        else:
            (workspace/'AGENTS.md').write_text('''# Main assistant staging profile

No live tools or schedules are authorized by this scaffold.
Review each operation and configure trusted owner routing before activation.
''')
    (target/'private-state').mkdir(mode=0o700)
    (target/'activation-plan.json').write_text(json.dumps(manifest, indent=2)+chr(10))
    shutil.copyfile(ROOT/'examples/customer-routing.example.json', target/'routing.REVIEW-ONLY.json')
    # Scaffolding deliberately does not copy skills into a configured agent or
    # write any live config. Operators inspect and install selected skills later.
    for p in target.rglob('*'):
        if p.is_file():
            os.chmod(p, 0o600)
    return dict(manifest, applied=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(scaffold(args.destination, apply=args.apply), indent=2))


if __name__ == '__main__':
    main()
