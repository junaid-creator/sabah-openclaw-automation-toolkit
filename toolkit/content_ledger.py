#!/usr/bin/env python3
"""RECONSTRUCTED from preserved skill requirements, not recovered legacy source."""
import argparse
import html
import json
import os
from pathlib import Path
import re
import unicodedata
from .reliability import ROOT, lock

DEFAULT = ROOT / 'content-ledger.jsonl'
REQUIRED = {'run_id','date','topic','primary_keyword','search_intent','title','slug',
            'post_id','category','secondary_keywords','featured_media_id','status',
            'url','created_at','result'}

def load(path):
    path = Path(path)
    if not path.exists():
        return []
    raw = path.read_text()
    if raw and not raw.endswith('\n'):
        raise ValueError('Ledger incomplete trailing line; preserve and reconcile')
    records, seen = [], set()
    for line in raw.splitlines():
        row = json.loads(line)
        if not isinstance(row, dict) or not row.get('run_id'):
            raise ValueError('Malformed ledger row')
        if row['run_id'] in seen:
            raise ValueError('Duplicate historical run ID; preserve and reconcile')
        seen.add(row['run_id'])
        records.append(row)
    return records

def normalize(value):
    value = unicodedata.normalize('NFKC', html.unescape(str(value))).casefold()
    return re.sub(r'\s+', ' ', re.sub(r'[^\w]+', ' ', value)).strip()

def check(records, title='', slug='', keyword='', exclude_post_id='', date=''):
    matches, publications = {}, set()
    proposed = {'title':title, 'slug':slug, 'primary_keyword':keyword}
    for row in records:
        if row.get('run_type') == 'validation':
            continue
        post = str(row.get('post_id') or '')
        if not post and row.get('status') == 'not-created':
            continue
        if date and row.get('date') == date and row.get('status') == 'publish' and post:
            publications.add(post)
        if exclude_post_id and post == str(exclude_post_id):
            continue
        fields = [key for key, value in proposed.items()
                  if normalize(value) and normalize(value) == normalize(row.get(key,''))]
        if fields:
            key = 'post:' + post if post else 'run:' + row['run_id']
            item = matches.setdefault(key, {'post_id':post,'run_ids':[], 'fields':[]})
            item['run_ids'].append(row['run_id'])
            item['fields'] = sorted(set(item['fields'] + fields))
    return {'clear':not matches and not publications, 'matches':list(matches.values()),
            'published_on_date':sorted(publications),
            'requires_authenticated_wp_inventory_and_semantic_review':True}

def append(path, record):
    if not isinstance(record,dict) or not REQUIRED <= record.keys() or not record['run_id']:
        raise ValueError('Missing required completed-run fields')
    from datetime import date, datetime
    date.fromisoformat(record['date'])
    datetime.fromisoformat(record['created_at'].replace('Z', '+00:00'))
    if record['status'] not in {'draft','publish','pending','private','future','not-created'}:
        raise ValueError('Noncanonical WordPress status')
    if record['status'] != 'not-created':
        if not str(record['post_id']).isdigit() or int(record['post_id']) <= 0:
            raise ValueError('Positive Post ID required')
        if not all(str(record[k]).strip() for k in ('title','slug','primary_keyword')):
            raise ValueError('Title, slug and primary keyword required')
    if not isinstance(record['secondary_keywords'], list):
        raise ValueError('secondary_keywords must be a list')
    path = Path(path)
    with lock(str(path) + '.lock'):
        rows = load(path)
        if any(r['run_id'] == record['run_id'] for r in rows):
            raise ValueError('Run ID already recorded; append rejected')
        with path.open('a') as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
    return {'appended':True, 'run_id':record['run_id']}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check','append'])
    parser.add_argument('--ledger', default=str(DEFAULT))
    parser.add_argument('--record-json')
    for name in ['title','slug','keyword','exclude-post-id','date']:
        parser.add_argument('--'+name, default='')
    args = parser.parse_args()
    try:
        if args.action == 'append':
            result = append(args.ledger, json.loads(args.record_json or '{}'))
        else:
            with lock(args.ledger + '.lock'):
                result = check(load(args.ledger), args.title,args.slug,args.keyword,
                               args.exclude_post_id,args.date)
        print(json.dumps(result))
        return 0 if result.get('clear',True) else 2
    except (ValueError,RuntimeError,OSError) as exc:
        print(json.dumps({'error':str(exc)}))
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
