"""Approval-gated existing-draft publication with no automatic retries."""
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .reliability import Run,STATE,atomic_json,identity
from . import content_ledger as ledger
GATES = ('content', 'taxonomy', 'internal_links', 'three_webp_get200',
         'media_metadata', 'seo_saved_readback', 'robots', 'article_schema',
         'faq', 'template', 'browser_visual', 'tracker_replay_three_tabs',
         'owner_notification_receipt', 'semantic_duplicates', 'legacy_disabled',
         'exclusive_sheet_writer')

def fingerprint(post):
    return identity({k: post[k] for k in ('id','title','slug','content','excerpt',
                                       'categories','tags','featured_media')})

def publish_existing(wp, plan, approval, evidence, public_check, *,
                     expected_owner, expected_account, expected_wp_user, allow_publish=False, timezone_name="UTC", root=STATE, ledger_path=ledger.DEFAULT, now=None):
    if not allow_publish or not expected_owner or not expected_account or type(expected_wp_user) is not int or expected_wp_user<=0: raise RuntimeError("Explicit configured publication admission required")
    if approval.get("owner_verified") is not True: raise RuntimeError("Authenticated owner required")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Aware current time required')
    day = now.astimezone(ZoneInfo(timezone_name)).date().isoformat()
    pid = plan['post_id']
    if type(pid) is not int or pid <= 0 or plan.get('run_type') != 'production':
        raise ValueError('Only a separately approved existing production draft is eligible')
    daily = False  # No inherited standing production authorization
    if not daily and (approval.get('explicit_activation') is not True
        or approval.get('explicit_publish') is not True
        or approval.get('owner') != expected_owner
        or approval.get('account') != expected_account
        or not approval.get('source_message_id')
        or approval.get('post_id') != pid
        or approval.get('run_id') != plan['run_id']
        or approval.get('local_date') != day
        or approval.get('post_hash') != plan['post_hash']):
        raise RuntimeError('Separate explicit owner activation and publication approval required')
    if evidence.get('post_hash') != plan['post_hash'] or evidence.get('post_id') != pid:
        raise RuntimeError('Gate evidence does not bind approved content')
    for gate in GATES:
        item = evidence.get(gate, {})
        if item.get('passed') is not True or not item.get('artifact'):
            raise RuntimeError('Mandatory gate failed: ' + gate)
        stamp = datetime.fromisoformat(item['verified_at'].replace('Z','+00:00'))
        if stamp.tzinfo is None or not 0 <= (now-stamp).total_seconds() <= 1800:
            raise RuntimeError('Gate evidence stale: ' + gate)
    if not callable(public_check):
        raise RuntimeError('Independent public verification required')
    root = Path(root)
    # Same workflow.lock as draft execution: no concurrent local blog write.
    with Run(plan['run_id'] + ('-publication' if daily else ''), {'plan':plan, 'approval':approval}, root=root) as run:
        current = wp.request('/wp-json/wp/v2/posts/' + str(pid) + '?context=edit')
        if fingerprint(current) != plan['post_hash']:
            raise RuntimeError('Approved content changed; new review required')
        previous = run.data['operations'].get('publish', {})
        if previous:
            if current['status'] != 'publish':
                raise RuntimeError('REVIEW_REQUIRED: uncertain publication; never replay POST')
            if previous.get('state') == 'verified':
                return previous['evidence']
        else:
            if current['status'] != 'draft':
                raise RuntimeError('Not an unpublished approved draft')
            if wp.request('/wp-json/wp/v2/users/me?context=edit')['id'] != expected_wp_user:
                raise RuntimeError('Unexpected WordPress identity')
            posts = wp.posts()
            if not ledger.check(ledger.load(ledger_path),date=day)['clear']:
                raise RuntimeError('Ledger local-date cap reached')
            for p in posts:
                if p['status'] != 'publish':
                    continue
                published = datetime.fromisoformat(p['date_gmt'].removesuffix('Z')+'+00:00')
                if published.astimezone(ZoneInfo(timezone_name)).date().isoformat() == day:
                    raise RuntimeError('WordPress local-date cap reached')
            claim = root / ('publication-day-' + day + '.json')
            if claim.exists():
                raise RuntimeError('Local date already reserved; reconcile rather than retry')
            atomic_json(claim, {'run_id':plan['run_id'],'post_id':pid,'state':'reserved'})
            run.checkpoint('publish','sending',attempts=1,post_id=pid)
            try:
                wp.request('/wp-json/wp/v2/posts/' + str(pid), {'status':'publish'})
            except Exception:
                run.checkpoint('publish','unknown',attempts=1,post_id=pid)
            # Independent saved state even after a successful acknowledgement.
            current = wp.request('/wp-json/wp/v2/posts/' + str(pid) + '?context=edit')
            if current['status'] != 'publish':
                run.checkpoint('publish','review_required',attempts=1,post_id=pid)
                raise RuntimeError('REVIEW_REQUIRED: no second publication POST')
        if fingerprint(current) != plan['post_hash']:
            raise RuntimeError('Published content drift; review required')
        publication_run_id = plan['run_id'] + ('-publication' if daily else '')
        entry = dict(plan['ledger_entry'],run_id=publication_run_id,post_id=pid,
                     status='publish',run_type='publication',date=approval['local_date'])
        rows = [r for r in ledger.load(ledger_path) if r['run_id']==publication_run_id]
        if rows and rows != [entry]:
            raise RuntimeError('Publication ledger differs; reconcile manually')
        if not rows:
            ledger.append(ledger_path,entry)
        checked = public_check(current)
        if checked.get('http') != 200 or checked.get('content_verified') is not True:
            raise RuntimeError('Publication recorded; public verification incomplete')
        result = {'post_id':pid,'status':'publish','url':current['link'],'public':checked}
        run.checkpoint('publish','verified',attempts=1,evidence=result)
        return result
