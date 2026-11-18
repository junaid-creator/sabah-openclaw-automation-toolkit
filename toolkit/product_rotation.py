"""Durable, narrowly admitted Toolkit daily product series. No external writes here."""
from __future__ import annotations

import os
from urllib.parse import urlsplit
import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SERIES = os.environ.get("TOOLKIT_SERIES_ID", "daily-products-v1")
ZONE = os.environ.get("TOOLKIT_TIMEZONE", "UTC")
SLOT_HOUR = int(os.environ.get("TOOLKIT_HOUR", "16"))
SLOT_MINUTE = int(os.environ.get("TOOLKIT_MINUTE", "0"))
if not (0 <= SLOT_HOUR < 24 and 0 <= SLOT_MINUTE < 60): raise ValueError("Invalid schedule slot")
CRON = f"{SLOT_MINUTE} {SLOT_HOUR} * * *"
PRODUCT_HOST = os.environ.get("TOOLKIT_PRODUCT_HOST", "example.com")
DUBAI = ZoneInfo(ZONE)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def inventory(catalog):
    """Use the complete read-only WooCommerce source snapshot, never guessed facts."""
    result = {}
    for row in catalog["records"]:
        post, data = row.get("post") or {}, row.get("data") or {}
        if post.get("post_type") != "product" or data.get("status") != "publish":
            continue
        url = row.get("url") or ""
        parsed=urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != PRODUCT_HOST or parsed.username or parsed.password or parsed.query or parsed.fragment or not re.fullmatch(r"/product/[a-z0-9-]+/", parsed.path):
            continue
        if not data.get("name"):
            continue
        pid = int(row["id"])
        result[pid] = {
            "id": pid, "name": data["name"], "url": url,
            "description": data.get("description") or "",
            "short_description": data.get("short_description") or "",
            "category_ids": data.get("category_ids") or [],
            "category_names": row.get("category_names") or [],
            "image_id": int(data.get("image_id") or 0),
            "image_url": row.get("image_url") or "",
            "representative_image": "representative" in (row.get("image_url") or "").lower(),
            # Woo variable price can be a minimum, not a verified Rent/Sell offer.
            "price_evidence": str(data.get("price") or ""),
            "stock_status": data.get("stock_status") or "",
            "type": data.get("type") or "",
        }
    if not result:
        raise ValueError("PUBLISHED_PRODUCT_CATALOG_EMPTY")
    return result


def order(items, catalog):
    """Use the verified storefront sequence, never product IDs or QA records."""
    ids = catalog.get("storefront_ids")
    if not isinstance(ids, list) or len(ids) != len(items) or len(ids) != len(set(ids)):
        raise ValueError("STOREFRONT_ORDER_MISSING_OR_DUPLICATED")
    if set(ids) != set(items) or any(type(pid) is not int for pid in ids):
        raise ValueError("STOREFRONT_CATALOG_IDENTITY_MISMATCH")
    return ids


def schema(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS daily_social_series (
      series_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL, cron TEXT NOT NULL,
      timezone TEXT NOT NULL, product_position INTEGER NOT NULL,
      template_position INTEGER NOT NULL, cycle INTEGER NOT NULL,
      cycle_ids TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS daily_social_assignments (
      series_id TEXT NOT NULL, uae_date TEXT NOT NULL, product_id INTEGER NOT NULL,
      template_number INTEGER NOT NULL, cycle INTEGER NOT NULL, cycle_position INTEGER NOT NULL,
      product_snapshot TEXT NOT NULL, job_id TEXT, request_id TEXT NOT NULL,
      state TEXT NOT NULL DEFAULT 'RESERVED', error TEXT, created_at TEXT NOT NULL,
      PRIMARY KEY(series_id,uae_date), UNIQUE(job_id), UNIQUE(request_id));
    CREATE TABLE IF NOT EXISTS daily_social_inventory (
      product_id INTEGER PRIMARY KEY, snapshot TEXT NOT NULL, last_seen TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS daily_social_history (
      id INTEGER PRIMARY KEY, series_id TEXT NOT NULL, uae_date TEXT NOT NULL,
      state TEXT NOT NULL, detail TEXT, recorded_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS daily_social_image_eligibility (
      product_id INTEGER NOT NULL, image_sha256 TEXT NOT NULL, image_url TEXT NOT NULL,
      eligible INTEGER NOT NULL, origin TEXT NOT NULL, reason TEXT NOT NULL,
      reviewed_at TEXT NOT NULL, PRIMARY KEY(product_id,image_sha256));
    CREATE TABLE IF NOT EXISTS daily_social_skips (
      series_id TEXT NOT NULL, uae_date TEXT NOT NULL, product_id INTEGER NOT NULL,
      image_sha256 TEXT, reason TEXT NOT NULL, replacement_product_id INTEGER NOT NULL,
      PRIMARY KEY(series_id,uae_date,product_id));
    CREATE TABLE IF NOT EXISTS daily_social_unresolved (
      series_id TEXT NOT NULL, product_id INTEGER NOT NULL, first_uae_date TEXT NOT NULL,
      last_uae_date TEXT NOT NULL, reason TEXT NOT NULL, resolved_at TEXT,
      PRIMARY KEY(series_id,product_id));
    """)


@contextmanager
def _connect(path):
    db = sqlite3.connect(path, timeout=30)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA synchronous=FULL")
        schema(db)
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def install_series(path, catalog, *, now=None):
    """Explicit one-time activation; a timer call cannot self-authorize a series."""
    when = now or datetime.now(DUBAI)
    items = inventory(catalog)
    ids = order(items, catalog)
    with _connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT * FROM daily_social_series WHERE series_id=?", (SERIES,)).fetchone()
        if old:
            if (old["cron"], old["timezone"]) != (CRON, ZONE):
                raise ValueError("EXISTING_DAILY_SERIES_SCHEDULE_CONFLICT")
            return dict(old)
        db.execute("INSERT INTO daily_social_series VALUES(?,?,?,?,?,?,?,?,?)",
                   (SERIES, 1, CRON, ZONE, 0, 0, 0,
                    canonical(ids), when.isoformat()))
        for item in items.values():
            db.execute("INSERT INTO daily_social_inventory VALUES(?,?,?)",
                       (item["id"], canonical(item), when.isoformat()))
        return dict(db.execute("SELECT * FROM daily_social_series WHERE series_id=?",
                               (SERIES,)).fetchone())


def reserve(path, day, catalog, *, now=None, eligibility=None):
    """One immutable assignment per configured-zone date; loops advance independently."""
    when = now or datetime.now(DUBAI)
    if when.tzinfo is None or when.astimezone(DUBAI).date().isoformat() != day:
        raise ValueError("CURRENT_UAE_DATE_REQUIRED")
    items = inventory(catalog)
    with _connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT * FROM daily_social_assignments WHERE series_id=? AND uae_date=?",
                         (SERIES, day)).fetchone()
        if old:
            return dict(old)
        series = db.execute("SELECT * FROM daily_social_series WHERE series_id=?", (SERIES,)).fetchone()
        if series is None:
            raise ValueError("DAILY_SERIES_NOT_INSTALLED")
        if not series["enabled"] or series["cron"] != CRON or series["timezone"] != ZONE:
            raise ValueError("DAILY_SERIES_DISABLED_OR_CHANGED")
        ids = json.loads(series["cycle_ids"])
        position, template_position, cycle = (series[k] for k in
                                                ("product_position", "template_position", "cycle"))
        # A failed visual is the day's intended product, not permission to
        # silently publish a different catalog entry. Legacy already-assigned
        # products are the only forward-only migration exception.
        for _ in range(2):
            while position < len(ids):
                candidate = ids[position]
                previously_assigned = db.execute(
                    'SELECT 1 FROM daily_social_assignments WHERE series_id=? AND cycle=? '
                    'AND product_id=? LIMIT 1', (SERIES, cycle, candidate)).fetchone()
                if previously_assigned or candidate not in items:
                    position += 1
                    continue
                break
            if position < len(ids):
                break
            ids, position, cycle = order(items, catalog), 0, cycle + 1
        else:
            raise ValueError('NO_CURRENT_PUBLISHED_PRODUCT')
        pid = ids[position]
        if pid not in items:
            raise ValueError("ASSIGNED_PRODUCT_REMOVED_OR_UNPUBLISHED")
        product = items[pid]
        template = template_position % 6 + 1
        request_id = "daily-products-" + day.replace("-", "")
        db.execute("INSERT INTO daily_social_assignments"
                   "(series_id,uae_date,product_id,template_number,cycle,cycle_position,"
                   "product_snapshot,request_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                   (SERIES, day, pid, template, cycle, position, canonical(product),
                    request_id, when.isoformat()))
        db.execute("UPDATE daily_social_series SET product_position=?,template_position=?,cycle=?,"
                   "cycle_ids=?,updated_at=? WHERE series_id=?",
                   (position + 1, template_position + 1, cycle, canonical(ids),
                    when.isoformat(), SERIES))
        if eligibility is not None:
            for item_id, review in eligibility.items():
                if review.get('image_sha256') and review.get('image_url') and review.get('origin'):
                    db.execute('INSERT INTO daily_social_image_eligibility VALUES(?,?,?,?,?,?,?) '
                               'ON CONFLICT(product_id,image_sha256) DO UPDATE SET '
                               'eligible=excluded.eligible,image_url=excluded.image_url,'
                               'origin=excluded.origin,reason=excluded.reason,reviewed_at=excluded.reviewed_at',
                               (item_id, review['image_sha256'], review['image_url'],
                                int(review.get('eligible') is True), review['origin'],
                                review.get('reason', '')[:240], when.isoformat()))
        for item in items.values():
            db.execute("INSERT INTO daily_social_inventory VALUES(?,?,?) ON CONFLICT(product_id)"
                       " DO UPDATE SET snapshot=excluded.snapshot,last_seen=excluded.last_seen",
                       (item["id"], canonical(item), when.isoformat()))
        return dict(db.execute("SELECT * FROM daily_social_assignments WHERE series_id=? AND uae_date=?",
                               (SERIES, day)).fetchone())


def bind_job(path, day, job_id):
    if not re.fullmatch(r"JOB-\d{4,}", job_id):
        raise ValueError("INVALID_SOCIAL_JOB_ID")
    with _connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM daily_social_assignments WHERE series_id=? AND uae_date=?",
                         (SERIES, day)).fetchone()
        if not row or row["job_id"] not in (None, job_id):
            raise ValueError("DAILY_ASSIGNMENT_JOB_CONFLICT")
        db.execute("UPDATE daily_social_assignments SET job_id=?,state='DRAFTED' WHERE series_id=? AND uae_date=?",
                   (job_id, SERIES, day))


def record(path, day, state, detail=""):
    if state not in {"RESERVED", "GENERATING", "DRAFTED", "AUTHORIZED",
                     "ACTIVE", "POSTED", "REVIEW_REQUIRED", "BLOCKED"}:
        raise ValueError("INVALID_DAILY_STATE")
    with _connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT 1 FROM daily_social_assignments WHERE series_id=? AND uae_date=?",
                         (SERIES, day)).fetchone()
        if not row:
            return
        db.execute("UPDATE daily_social_assignments SET state=?,error=? WHERE series_id=? AND uae_date=?",
                   (state, detail[:240] if state in {"REVIEW_REQUIRED", "BLOCKED"} else None,
                    SERIES, day))
        last = db.execute("SELECT state,detail FROM daily_social_history WHERE series_id=? AND uae_date=?"
                          " ORDER BY id DESC LIMIT 1", (SERIES, day)).fetchone()
        if not last or (last["state"], last["detail"]) != (state, detail[:240]):
            db.execute("INSERT INTO daily_social_history(series_id,uae_date,state,detail,recorded_at)"
                       " VALUES(?,?,?,?,?)", (SERIES, day, state, detail[:240],
                                            datetime.now(DUBAI).isoformat()))


def verify_receipt(path, job_id, receipt, *, now=None):
    """Check durable series admission, date, exact job and frozen product/template."""
    source = receipt.get("source") or {}
    if not isinstance(source, dict) or source.get("kind") != "DAILY_SERIES":
        return False
    if source.get("series_id") != SERIES or source.get("job_id") != job_id:
        return False
    day = source.get("uae_date")
    if not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        return False
    local = (now or datetime.now(DUBAI)).astimezone(DUBAI)
    if local.date().isoformat() != day or (local.hour, local.minute) < (SLOT_HOUR, SLOT_MINUTE):
        return False
    with _connect(path) as db:
        series = db.execute("SELECT * FROM daily_social_series WHERE series_id=?", (SERIES,)).fetchone()
        row = db.execute("SELECT * FROM daily_social_assignments WHERE series_id=? AND uae_date=?",
                         (SERIES, day)).fetchone()
    if not series or not series["enabled"] or series["cron"] != CRON or series["timezone"] != ZONE:
        return False
    if not row or row["job_id"] != job_id or row["product_id"] != source.get("product_id") or row["template_number"] != source.get("template_number"):
        return False
    if hashlib.sha256(row["product_snapshot"].encode()).hexdigest() != source.get("product_sha256"):
        return False
    return True


def assignment(path, day):
    with _connect(path) as db:
        row = db.execute("SELECT * FROM daily_social_assignments WHERE series_id=? AND uae_date=?",
                         (SERIES, day)).fetchone()
        return dict(row) if row else None


def refresh_due(path):
    with _connect(path) as db:
        row = db.execute('SELECT product_position,cycle_ids FROM daily_social_series '
                         'WHERE series_id=?', (SERIES,)).fetchone()
        if not row:
            raise ValueError('DAILY_SERIES_NOT_INSTALLED')
        return row['product_position'] >= len(json.loads(row['cycle_ids']))


def skips(path, day):
    with _connect(path) as db:
        return [dict(row) for row in db.execute(
            'SELECT * FROM daily_social_skips WHERE series_id=? AND uae_date=? ORDER BY rowid',
            (SERIES, day)).fetchall()]


def store_eligibility(path, reviews, *, now=None):
    """Persist product/image evidence without reserving a date or moving cursors."""
    when = (now or datetime.now(DUBAI)).isoformat()
    with _connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        for pid, review in reviews.items():
            digest = review.get('image_sha256')
            if not digest or not re.fullmatch(r'[a-f0-9]{64}', digest):
                continue
            db.execute('INSERT INTO daily_social_image_eligibility VALUES(?,?,?,?,?,?,?) '
                       'ON CONFLICT(product_id,image_sha256) DO UPDATE SET '
                       'eligible=excluded.eligible,image_url=excluded.image_url,'
                       'origin=excluded.origin,reason=excluded.reason,reviewed_at=excluded.reviewed_at',
                       (pid, digest, review['image_url'], int(review.get('eligible') is True),
                       review['origin'], review.get('reason', '')[:240], when))


def mark_unresolved(path, day, product_id, reason):
    with _connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT 1 FROM daily_social_assignments WHERE series_id=? '
                         'AND uae_date=? AND product_id=?',
                         (SERIES, day, product_id)).fetchone()
        if not row:
            raise ValueError('UNRESOLVED_PRODUCT_NOT_ASSIGNED')
        db.execute('INSERT INTO daily_social_unresolved VALUES(?,?,?,?,?,NULL) '
                   'ON CONFLICT(series_id,product_id) DO UPDATE SET '
                   'last_uae_date=excluded.last_uae_date,reason=excluded.reason,resolved_at=NULL',
                   (SERIES, product_id, day, day, reason[:240]))


def resolve_unresolved(path, product_id):
    with _connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('UPDATE daily_social_unresolved SET resolved_at=? '
                   'WHERE series_id=? AND product_id=? AND resolved_at IS NULL',
                   (datetime.now(DUBAI).isoformat(), SERIES, product_id))




def next_expected(path):
    with _connect(path) as db:
        series = db.execute("SELECT * FROM daily_social_series WHERE series_id=?", (SERIES,)).fetchone()
        if not series:
            return None
        ids = json.loads(series["cycle_ids"])
        position = series["product_position"]
        while position < len(ids) and db.execute(
                'SELECT 1 FROM daily_social_assignments WHERE series_id=? AND cycle=? '
                'AND product_id=? LIMIT 1', (SERIES, series['cycle'], ids[position])).fetchone():
            position += 1
        pid = ids[position] if position < len(ids) else ids[0]
        image = db.execute("SELECT snapshot FROM daily_social_inventory WHERE product_id=?", (pid,)).fetchone()
        name = json.loads(image["snapshot"])["name"] if image else None
        return {"product_id": pid, "product_name": name,
                "template_number": series["template_position"] % 6 + 1}
