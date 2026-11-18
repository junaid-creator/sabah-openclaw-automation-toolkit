"""Deterministic supplemental release checks, not a substitute for secret review."""
import ast
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
errors = []
files = []
tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.decode().split(chr(0))
if any((p == ".venv" or p.startswith(".venv/")) for p in tracked):
    errors.append("Installed .venv must not be tracked as release content")
for p in ROOT.rglob('*'):
    if '.git' in p.parts or '__pycache__' in p.parts or p.relative_to(ROOT).parts[0] == '.venv':
        continue
    if p.is_symlink():
        errors.append(str(p.relative_to(ROOT)) + ': symlink')
        continue
    if not p.is_file():
        continue
    rel = str(p.relative_to(ROOT)); files.append(rel)
    if p.suffix in {'.db','.sqlite','.sqlite3','.pem','.key','.log','.jsonl','.zip','.png','.jpg'} or p.name == '.env':
        errors.append(rel + ': disallowed artifact')
    try:
        text = p.read_text()
    except UnicodeError:
        errors.append(rel + ': non-text artifact'); continue
    if chr(0) in text:
        errors.append(rel + ': binary content')
    if p.suffix == '.py':
        try: ast.parse(text)
        except SyntaxError: errors.append(rel + ': invalid Python')
    if p.suffix == '.json':
        try: json.loads(text)
        except ValueError: errors.append(rel + ': invalid JSON')
    forbidden = ['/home/' + 'sabahauto', 'sabahalmustaqbal' + '.com', 'client-' + 'company', 'tail1' + 'f5698', '+971' + '504902091', '+971 2' + ' 626 9786']
    if any(value in text for value in forbidden):
        errors.append(rel + ': deployment identity')
    if p.name == 'SKILL.md':
        parts = text.split('---', 2)
        if len(parts) != 3 or not parts[0].strip() == '':
            errors.append(rel + ': frontmatter missing'); continue
        if 'name: '+p.parent.name not in parts[1] or 'description:' not in parts[1]:
            errors.append(rel + ': invalid skill name/description')
        for line in parts[1].splitlines():
            if line.startswith('metadata: '):
                try: json.loads(line.split(': ',1)[1])
                except ValueError: errors.append(rel + ': invalid metadata')
    if p.suffix == '.md':
        for link in re.findall(r'\]\(([^)]+)\)',text):
            if '://' in link or link.startswith('#'): continue
            target=(p.parent/link.split('#')[0]).resolve()
            if not target.is_relative_to(ROOT) or not target.exists():
                errors.append(rel + ': broken local link ' + link)
print(json.dumps({'checked_files':len(files),'errors':errors},indent=2))
raise SystemExit(bool(errors))
