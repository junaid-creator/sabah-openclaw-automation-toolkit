#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def build_brief(item: dict) -> dict:
    primary = item.get('primary_keyword', '')
    cluster = item.get('cluster', primary)
    intent = item.get('intent', 'commercial')
    secondary = item.get('secondary_keywords', [])

    return {
        'title': f'{primary.title()} Content Brief',
        'primary_keyword': primary,
        'secondary_keywords': secondary,
        'search_intent': intent,
        'recommended_url_slug': item.get('suggested_slug', primary.replace(' ', '-')),
        'outline': [
            f'Introduction: address the main need behind "{primary}"',
            f'Core section: explain the main solution for {cluster}',
            'Trust section: proof, examples, or testimonials',
            'FAQ section: answer objections and related searches',
            'CTA section: direct the user to the next action',
        ],
        'cta': 'Request a quote, book a call, or contact the business',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate content briefs from a keyword plan JSON file.')
    parser.add_argument('--input', required=True, help='Keyword plan JSON from keyword_research.py')
    parser.add_argument('--output', required=True, help='Output JSON file for content briefs')
    args = parser.parse_args()

    items = json.loads(Path(args.input).read_text())
    briefs = [build_brief(item) for item in items]
    Path(args.output).write_text(json.dumps(briefs, indent=2))
    print(f'wrote {len(briefs)} briefs to {args.output}')


if __name__ == '__main__':
    main()
