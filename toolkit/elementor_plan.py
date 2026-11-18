#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import shlex
from urllib.parse import urlsplit
from pathlib import Path

SUPPORTED_COMMANDS = {
    '/wp-login',
    '/open-elementor',
    '/elementor-ai-draft',
    '/elementor-review-checklist',
    '/create-landing-page',
}


def build_plan(args: argparse.Namespace, brief: dict) -> list[dict]:
    if args.command not in SUPPORTED_COMMANDS:
        raise ValueError('Unsupported planning command')
    parsed = urlsplit(args.site_url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise ValueError('Explicit trusted HTTPS origin required')
    if not args.admin_path.startswith('/') or not args.admin_path.endswith('/') or '..' in args.admin_path or any(c in args.admin_path for c in ('?', '#', chr(10), chr(13))):
        raise ValueError('Explicit rooted admin directory required')
    site_url = args.site_url.rstrip('/')
    admin_url = f"{site_url}{args.admin_path}"
    page_title = args.page_title or brief.get('page_title', 'New Landing Page')
    steps = [
        {
            'step': 'open_admin',
            'command': f"agent-browser --session {shlex.quote(args.session)} open {shlex.quote(admin_url)}",
            'note': 'Open WordPress admin or login page.',
        },
        {
            'step': 'snapshot_admin',
            'command': f"agent-browser --session {shlex.quote(args.session)} snapshot -i --json",
            'note': 'Inspect login/admin screen before acting.',
        },
    ]

    if args.command in {'/wp-login', '/create-landing-page', '/open-elementor', '/elementor-ai-draft'}:
        steps.append({
            'step': 'login_guidance',
            'command': 'MANUAL_OR_AUTH_STATE',
            'note': 'Use saved auth state if available, otherwise fill login fields only after user-approved credential handling.',
        })

    if args.command in {'/open-elementor', '/create-landing-page', '/elementor-ai-draft'}:
        new_page_url = f"{admin_url}post-new.php?post_type=page"
        steps.extend([
            {
                'step': 'open_new_page',
                'command': f"agent-browser --session {shlex.quote(args.session)} open {shlex.quote(new_page_url)}",
                'note': 'Open new page creation flow.',
            },
            {
                'step': 'snapshot_new_page',
                'command': f"agent-browser --session {shlex.quote(args.session)} snapshot -i --json",
                'note': f'Find title input and Elementor launch controls for {page_title}.',
            },
        ])

    if args.command in {'/elementor-ai-draft', '/create-landing-page'}:
        steps.extend([
            {
                'step': 'brief_summary',
                'command': 'NO_BROWSER_ACTION',
                'note': f"Use brief: primary_keyword={brief.get('primary_keyword', '')}, audience={brief.get('audience', '')}, cta={brief.get('cta', '')}",
            },
            {
                'step': 'open_elementor_ai',
                'command': f"agent-browser --session {shlex.quote(args.session)} snapshot -i --json",
                'note': 'Locate Elementor AI controls, then trigger them using refs from the snapshot.',
            },
            {
                'step': 'review_generated_sections',
                'command': f"agent-browser --session {shlex.quote(args.session)} snapshot -i --json",
                'note': 'Verify hero, benefits, proof, CTA, and FAQ sections exist and are sensible.',
            },
        ])

    if args.command in {'/elementor-review-checklist', '/create-landing-page', '/elementor-ai-draft'}:
        steps.append({
            'step': 'final_review',
            'command': f"agent-browser --session {shlex.quote(args.session)} snapshot -i --json",
            'note': 'Run the Elementor checklist before saving. Do not publish automatically.',
        })

    return steps


def main() -> None:
    parser = argparse.ArgumentParser(description='Safe wrapper for WordPress and Elementor browser workflows using agent-browser.')
    parser.add_argument('command', help='Workflow shorthand such as /create-landing-page')
    parser.add_argument('--site-url', required=True, help='Base site URL, e.g. https://example.com')
    parser.add_argument('--admin-path', default='/wp-admin/', help='WordPress admin path')
    parser.add_argument('--page-title', help='Target landing page title')
    parser.add_argument('--brief-file', help='JSON file with audience, offer, CTA, sections, and keywords')
    parser.add_argument('--session', default='seo-admin', help='agent-browser session name')
    parser.add_argument('--dry-run', action='store_true', help='Print plan only, do not imply execution')
    args = parser.parse_args()

    if args.command not in SUPPORTED_COMMANDS:
        raise SystemExit(f'unsupported command: {args.command}')

    brief = {}
    if args.brief_file:
        brief = json.loads(Path(args.brief_file).read_text())

    plan = {
        'command': args.command,
        'dry_run': True,
        'executed': False,
        'session': args.session,
        'site_url': args.site_url,
        'page_title': args.page_title or brief.get('page_title'),
        'steps': build_plan(args, brief),
        'guardrails': [
            'Do not auto-publish.',
            'Do not store credentials in the skill.',
            'Use auth state when possible.',
            'Re-snapshot after each important UI change.',
            'Pause for user confirmation before destructive actions.',
        ],
    }

    print(json.dumps(plan, indent=2))


if __name__ == '__main__':
    main()
