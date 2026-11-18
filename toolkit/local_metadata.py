#!/usr/bin/env python3
from __future__ import annotations
import argparse
import csv
import json
import re
from html import escape
from pathlib import Path


def load_updates(path: Path) -> dict[str, dict[str, str]]:
    if path.suffix.lower() == '.json':
        data = json.loads(path.read_text())
        return {item['path']: item for item in data}
    updates = {}
    with path.open(newline='') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            updates[row['path']] = row
    return updates


def replace_or_insert(html: str, pattern: str, replacement: str, insert_before: str = '</head>') -> str:
    if re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL):
        return re.sub(pattern, lambda _: replacement, html, count=1, flags=re.IGNORECASE | re.DOTALL)
    if not re.search(r"</head>", html, re.I):
        raise ValueError("HTML head closing tag missing")
    return re.sub(r"</head>", lambda _: "  " + replacement + chr(10) + "</head>", html, count=1, flags=re.I)


def apply_update(html: str, title: str | None, description: str | None) -> str:
    if title:
        html = replace_or_insert(html, r'<title>.*?</title>', f'<title>{escape(title)}</title>')
    if description:
        tag = f'<meta name="description" content="{escape(description, quote=True)}">'
        html = replace_or_insert(
            html,
            r'<meta\s+name=["\']description["\']\s+content=["\'].*?["\']\s*/?>',
            tag,
        )
    return html


def main() -> None:
    parser = argparse.ArgumentParser(description='Update local HTML title/meta description tags.')
    parser.add_argument('--site-root', required=True, help='Directory containing HTML files')
    parser.add_argument('--updates', required=True, help='CSV or JSON file with path,title,description')
    parser.add_argument('--dry-run', action='store_true', help='Preview only (default)')
    parser.add_argument('--apply', action='store_true', help='Explicitly write reviewed local copies')
    args = parser.parse_args()

    site_root = Path(args.site_root)
    updates = load_updates(Path(args.updates))

    changed = 0
    for rel_path, payload in updates.items():
        target = (site_root / rel_path).resolve()
        if not target.is_relative_to(site_root.resolve()):
            raise ValueError('Path escapes site root')
        if not target.exists():
            print(f'missing: {rel_path}')
            continue
        html = target.read_text()
        updated = apply_update(html, payload.get('title'), payload.get('description'))
        if updated == html:
            print(f'nochange: {rel_path}')
            continue
        changed += 1
        print(f'update: {rel_path}')
        if args.apply and not args.dry_run:
            target.write_text(updated)

    mode = 'updated' if args.apply and not args.dry_run else 'previewed'
    print(f'{mode} {changed} files')


if __name__ == '__main__':
    main()
