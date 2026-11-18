#!/usr/bin/env python3
from __future__ import annotations
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

STOPWORDS = {
    'a', 'an', 'and', 'for', 'in', 'of', 'on', 'or', 'the', 'to', 'with'
}

INTENT_HINTS = {
    'transactional': ['buy', 'price', 'pricing', 'quote', 'service', 'company', 'agency', 'near me'],
    'commercial': ['best', 'top', 'vs', 'review', 'compare', 'comparison'],
    'informational': ['how', 'what', 'why', 'guide', 'tips', 'checklist'],
    'navigational': ['login', 'homepage', 'contact', 'address'],
}


def normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r'[^a-z0-9\s-]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def detect_intent(keyword: str) -> str:
    for intent, hints in INTENT_HINTS.items():
        if any(hint in keyword for hint in hints):
            return intent
    return 'commercial'


def build_variants(seed: str, location: str | None) -> list[str]:
    variants = {seed}
    variants.add(f'{seed} services')
    variants.add(f'best {seed}')
    variants.add(f'{seed} company')
    if location:
        variants.add(f'{seed} {location}')
        variants.add(f'best {seed} in {location}')
        variants.add(f'{seed} near {location}')
    return sorted(v for v in variants if v)


def cluster_key(keyword: str) -> str:
    words = [w for w in normalize(keyword).split() if w not in STOPWORDS]
    return ' '.join(words[:3]) if words else keyword


def main() -> None:
    parser = argparse.ArgumentParser(description='Create a lightweight keyword plan from seed keywords.')
    parser.add_argument('--input', required=True, help='Text, CSV, or JSON file containing seed keywords')
    parser.add_argument('--location', help='Optional location modifier like dubai or chicago')
    parser.add_argument('--output', required=True, help='Output JSON file')
    args = parser.parse_args()

    input_path = Path(args.input)
    seeds: list[str] = []

    if input_path.suffix.lower() == '.json':
        data = json.loads(input_path.read_text())
        if isinstance(data, list):
            seeds = [str(x) for x in data]
        else:
            seeds = [str(x) for x in data.get('keywords', [])]
    elif input_path.suffix.lower() == '.csv':
        with input_path.open(newline='') as fh:
            reader = csv.reader(fh)
            for row in reader:
                seeds.extend(cell for cell in row if cell.strip())
    else:
        seeds = [line.strip() for line in input_path.read_text().splitlines() if line.strip()]

    grouped = defaultdict(list)
    for seed in seeds:
        for variant in build_variants(normalize(seed), args.location):
            grouped[cluster_key(variant)].append({
                'keyword': variant,
                'intent': detect_intent(variant),
            })

    output = []
    for cluster, items in grouped.items():
        primary = items[0]['keyword']
        output.append({
            'cluster': cluster,
            'primary_keyword': primary,
            'secondary_keywords': [item['keyword'] for item in items[1:]],
            'intent': items[0]['intent'],
            'suggested_slug': re.sub(r'\s+', '-', primary.strip()),
        })

    Path(args.output).write_text(json.dumps(output, indent=2))
    print(f'wrote {len(output)} clusters to {args.output}')


if __name__ == '__main__':
    main()
