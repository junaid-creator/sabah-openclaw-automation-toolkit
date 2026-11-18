"""Fail-closed Facebook Pages + Instagram publishing primitives for portable workflows.

No queue consumer, scheduler, OAuth flow, or live credential is enabled here.
The API version and Instagram authorization mode are explicit runtime inputs;
live requests additionally require reviewed contracts and an owner approval
gate that is independent of editable Google Sheet cells.
"""
from __future__ import annotations

import os
import hashlib
import ipaddress
import json
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timezone
from enum import Enum
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def urlopen(req, timeout=20):
    return build_opener(_NoRedirect()).open(req, timeout=timeout)
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DRY_RUN = True
LIVE_ENABLEMENT_APPROVED = os.environ.get("TOOLKIT_ALLOW_LIVE_META") == "I_UNDERSTAND"
MAX_ATTEMPTS = 2
POST_LOG_FIELDS = (
    "job_id", "platform", "attempt_number", "scheduled_at", "attempted_at",
    "posted_at", "status", "platform_post_id", "post_url", "error_code",
    "error_message", "retry_count", "last_updated",
)
QUEUE_FIELDS = {
    "job_id", "enabled", "action", "approval_mode", "status", "facebook", "instagram",
    "tiktok", "agent_notes",
}
OUTPUT_FIELDS = {
    "job_id", "selected_concept", "final_master_asset_url", "facebook_asset_url",
    "instagram_asset_url", "facebook_caption", "instagram_caption", "facebook_hashtags",
    "instagram_hashtags", "qa_status",
}
APPROVAL_STATES = {"APPROVED"}
IMAGE_MIMES = {"image/jpeg"}


class MetaIntegrationError(RuntimeError):
    """Safe diagnostic; must never include tokens, app secrets, or raw API bodies."""


class InstagramAuthMode(str, Enum):
    FACEBOOK_LOGIN = "facebook_login"
    INSTAGRAM_LOGIN = "instagram_login"


class Platform(str, Enum):
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"


@dataclass(frozen=True)
class MetaSettings:
    api_version: str
    instagram_auth_mode: InstagramAuthMode
    page_id: str
    instagram_user_id: str
    expected_page_name: str
    expected_instagram_username: str = ""
    business_portfolio_id: str = ""
    facebook_app_id: str = ""
    instagram_app_id: str = ""
    verified_media_hosts: frozenset[str] = frozenset()
    api_contracts_verified: bool = False
    live_enablement_approved: bool = False

    def __post_init__(self) -> None:
        if not re.fullmatch(r"v[0-9]{1,2}\.0", self.api_version):
            raise MetaIntegrationError("Explicit supported Graph API version is required")
        for name, value in (("Page ID", self.page_id), ("Instagram account ID", self.instagram_user_id)):
            if not value or not re.fullmatch(r"[0-9]{5,32}", value):
                raise MetaIntegrationError(f"Verified numeric {name} is required")
        if not self.expected_page_name.strip():
            raise MetaIntegrationError("Expected Page name is required")
        if self.business_portfolio_id and self.page_id == self.business_portfolio_id:
            raise MetaIntegrationError("Business Portfolio ID cannot be used as a Graph API Page ID")


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: dict[str, Any]


class MetaTransport(Protocol):
    def request(self, method: str, url: str, *, params: dict[str, str] | None = None,
                form: dict[str, str] | None = None, timeout: int = 20) -> HttpResponse: ...


class SecretStore(Protocol):
    def get_facebook_page_access_token(self) -> str: ...
    def get_instagram_access_token(self) -> str: ...
    def get_validation_user_access_token(self) -> str: ...
    def get_meta_app_access_token(self, platform: str) -> str: ...


class SheetsStore(Protocol):
    def read_queue_job(self, job_id: str) -> dict[str, str]: ...
    def read_content_job(self, job_id: str) -> dict[str, str]: ...
    def upsert_post_log(self, row: dict[str, str]) -> None: ...
    def update_queue_status(self, job_id: str, status: str, note: str) -> None: ...


class ApprovalGate(Protocol):
    """Trusted owner-approval service, separate from the editable Sheet."""
    def authorize(self, job_id: str, platform: str) -> bool: ...


class MediaVerifier(Protocol):
    def verify_public_jpeg(self, url: str) -> None: ...


class EventLogger(Protocol):
    def emit(self, event: str, fields: dict[str, str]) -> None: ...


class DenyAllApprovalGate:
    def authorize(self, job_id: str, platform: str) -> bool:
        return False


def scheduled_at(queue: dict[str, str]) -> datetime | None:
    """Parse the existing queue schedule. Empty means unscheduled/manual-now."""
    day = str(queue.get("publish_date", "")).strip()
    clock = str(queue.get("publish_time", "")).strip()
    zone = str(queue.get("timezone", "")).strip()
    if not day and not clock and not zone:
        return None
    if not day or not clock or not zone:
        raise MetaIntegrationError("Schedule requires publish_date, publish_time, and timezone")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or not re.fullmatch(r"\d{2}:\d{2}", clock):
        raise MetaIntegrationError("Schedule date/time must use YYYY-MM-DD and HH:MM")
    try:
        local_day = date.fromisoformat(day)
        local_time = datetime_time.fromisoformat(clock)
        tz = ZoneInfo(zone)
    except (ValueError, ZoneInfoNotFoundError):
        raise MetaIntegrationError("Schedule date, time, or timezone is invalid") from None
    if local_time.tzinfo is not None or local_time.second or local_time.microsecond:
        raise MetaIntegrationError("Schedule time must use local HH:MM")
    return datetime.combine(local_day, local_time, tzinfo=tz)


def _schedule_is_due(queue: dict[str, str], *, now: datetime | None = None,
                     require_schedule: bool = False) -> bool:
    scheduled = scheduled_at(queue)
    if scheduled is None:
        return not require_schedule
    current = now or datetime.now(scheduled.tzinfo)
    if current.tzinfo is None:
        raise MetaIntegrationError("Schedule comparison requires an aware current time")
    return current.astimezone(scheduled.tzinfo) >= scheduled


def validate_publishable_row(queue: dict[str, str], content: dict[str, str]) -> None:
    if not QUEUE_FIELDS.issubset(queue) or not OUTPUT_FIELDS.issubset(content):
        raise MetaIntegrationError("Toolkit sheet schema mismatch")
    if queue.get("enabled", "").strip().upper() not in {"TRUE", "YES", "1"}:
        raise MetaIntegrationError("Toolkit job is disabled")
    mode = queue.get("approval_mode", "").strip().upper()
    if mode not in {"MANUAL", "AUTO"}:
        raise MetaIntegrationError("POST_QUEUE approval_mode must be MANUAL or AUTO")
    if queue.get("action", "").strip().upper() != "PUBLISH":
        raise MetaIntegrationError("An explicit PUBLISH action is required")
    if queue.get("status", "").strip().upper() not in APPROVAL_STATES:
        raise MetaIntegrationError("Only explicitly APPROVED jobs may publish")
    if not _schedule_is_due(queue, require_schedule=mode == "AUTO"):
        raise MetaIntegrationError("Job is not yet due under its configured schedule")
    if not content.get("selected_concept", "").strip():
        raise MetaIntegrationError("An owner-selected concept is required")


class SheetPublicationGate:
    """Operational Sheet gate; not a cryptographically authenticated approval."""
    def __init__(self, sheets: SheetsStore):
        self.sheets = sheets

    def authorize(self, job_id: str, platform: str) -> bool:
        if platform not in {"facebook", "instagram"}:
            return False
        try:
            queue = self.sheets.read_queue_job(job_id)
            mode = queue.get("approval_mode", "").strip().upper()
            if (queue.get("enabled", "").strip().upper() not in {"TRUE", "YES", "1"}
                    or queue.get("action", "").strip().upper() != "PUBLISH"
                    or queue.get("status", "").strip().upper() != "APPROVED"
                    or mode not in {"MANUAL", "AUTO"}
                    or queue.get(platform, "").strip().upper() not in {"TRUE", "YES", "1"}):
                return False
            return _schedule_is_due(queue, require_schedule=mode == "AUTO")
        except (MetaIntegrationError, KeyError, TypeError, ValueError):
            return False


class NoopLogger:
    def emit(self, event: str, fields: dict[str, str]) -> None:
        # The caller supplies only identifiers/statuses; credentials are never accepted.
        pass


class UrllibMetaTransport:
    """Minimal transport. Does not log URLs, bodies, headers, or Meta response bodies."""
    def request(self, method: str, url: str, *, params: dict[str, str] | None = None,
                form: dict[str, str] | None = None, timeout: int = 20) -> HttpResponse:
        target = url + ("?" + urlencode(params) if params else "")
        data = urlencode(form).encode() if form else None
        req = Request(target, data=data, method=method.upper(),
                      headers={"Accept": "application/json",
                               "Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urlopen(req, timeout=timeout) as response:
                body = response.read(2_000_000)
                parsed = json.loads(body.decode("utf-8")) if body else {}
                return HttpResponse(int(response.status), parsed if isinstance(parsed, dict) else {})
        except HTTPError as exc:
            # Parse only in memory; do not propagate raw provider content into logs/errors.
            try:
                body = json.loads(exc.read(2_000_000).decode("utf-8"))
            except Exception:
                body = {}
            return HttpResponse(int(exc.code), body if isinstance(body, dict) else {})
        except (URLError, TimeoutError, OSError):
            raise MetaIntegrationError("Meta request outcome is uncertain") from None


class PublicJpegVerifier:
    """HEAD-check public HTTPS image URLs; no authentication or redirect to HTTP."""
    def __init__(self, allowed_hosts: set[str] | frozenset[str]):
        self.allowed_hosts = {host.lower().rstrip(".") for host in allowed_hosts}

    def verify_public_jpeg(self, url: str) -> None:
        _validate_media_url(url, self.allowed_hosts)
        request = Request(url, method="HEAD", headers={"User-Agent": "Toolkit-MetaPublisher/1.0"})
        try:
            with urlopen(request, timeout=12) as response:
                if response.status != 200:
                    raise MetaIntegrationError("Media URL did not return HTTP 200")
                final = urlsplit(response.geturl())
                if final.scheme != "https" or final.username or final.password or final.query or final.fragment:
                    raise MetaIntegrationError("Media URL redirected outside HTTPS")
                if response.headers.get_content_type().lower() not in IMAGE_MIMES:
                    raise MetaIntegrationError("Media URL must serve a JPEG image")
        except MetaIntegrationError:
            raise
        except Exception:
            raise MetaIntegrationError("Public media URL could not be verified") from None


def _validate_media_url(url: str, allowed_hosts: set[str] | frozenset[str] = frozenset()) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise MetaIntegrationError("Media URL is malformed") from None
    host = (parsed.hostname or "").lower().rstrip(".")
    if (parsed.scheme != "https" or not host or parsed.username or parsed.password
            or port not in (None, 443) or parsed.fragment or parsed.query):
        raise MetaIntegrationError("Media URL must be public HTTPS without credentials or fragments")
    if host not in {item.lower().rstrip(".") for item in allowed_hosts}:
        raise MetaIntegrationError("Media URL host is not on the verified public-host allowlist")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise MetaIntegrationError("Media URL host is not publicly routable")
    else:
        if not address.is_global:
            raise MetaIntegrationError("Media URL host is not publicly routable")


class GspreadSheetsStore:
    """Adapter over the current helper's existing gspread connection/workbook.

    Construct with a workbook from the existing authorized helper; this adapter
    performs no connection by itself, so callers control when read/write is allowed.
    """
    def __init__(self, workbook: Any):
        self.workbook = workbook
        self._lock = threading.RLock()


    @staticmethod
    def _read_row(ws: Any, job_id: str) -> dict[str, str]:
        values = ws.get_all_values()
        if not values:
            raise MetaIntegrationError(f"{ws.title} is empty")
        headers = values[0]
        if "job_id" not in headers:
            raise MetaIntegrationError(f"{ws.title} has no job_id column")
        matches = []
        for cells in values[1:]:
            row = cells + [""] * max(0, len(headers) - len(cells))
            item = dict(zip(headers, row[:len(headers)]))
            if item.get("job_id", "").strip() == job_id:
                matches.append(item)
        if len(matches) > 1:
            raise MetaIntegrationError("Duplicate Toolkit job IDs; refusing ambiguous publication")
        if matches:
            return matches[0]
        raise MetaIntegrationError("Toolkit job was not found")

    def read_queue_job(self, job_id: str) -> dict[str, str]:
        with self._lock:
            item = self._read_row(self.workbook.worksheet("POST_QUEUE"), job_id)
            if not QUEUE_FIELDS.issubset(item):
                raise MetaIntegrationError("POST_QUEUE schema mismatch")
            return item

    def read_content_job(self, job_id: str) -> dict[str, str]:
        with self._lock:
            item = self._read_row(self.workbook.worksheet("CONTENT_OUTPUT"), job_id)
            if not OUTPUT_FIELDS.issubset(item):
                raise MetaIntegrationError("CONTENT_OUTPUT schema mismatch")
            return item

    def upsert_post_log(self, row: dict[str, str]) -> None:
        if row.get("platform") not in {"facebook", "instagram"} or not row.get("job_id"):
            raise MetaIntegrationError("POST_LOG requires job_id and a supported platform")
        ws = self.workbook.worksheet("POST_LOG")
        with self._lock:
            values = ws.get_all_values()
            if not values:
                raise MetaIntegrationError("POST_LOG schema is empty; refusing to write")
            headers = values[0]
            if set(POST_LOG_FIELDS) - set(headers):
                raise MetaIntegrationError("POST_LOG schema mismatch; refusing to write")
            if "updated_at" in row and "last_updated" not in row:
                row = {**row, "last_updated": row["updated_at"]}
            attempt = str(row.get("attempt_number", ""))
            if not attempt.isdigit():
                raise MetaIntegrationError("POST_LOG attempt_number must be numeric")
            key = (row["job_id"], row["platform"], attempt)
            found = None
            for line, cells in enumerate(values[1:], 2):
                padded = cells + [""] * max(0, len(headers) - len(cells))
                existing = dict(zip(headers, padded[:len(headers)]))
                if (existing.get("job_id"), existing.get("platform"), existing.get("attempt_number")) == key:
                    found = line
                    if existing.get("status") == "POSTED":
                        if row.get("status") != "POSTED" or row.get("platform_post_id") != existing.get("platform_post_id"):
                            raise MetaIntegrationError("Confirmed POST_LOG history cannot be overwritten")
                        if not existing.get("post_url") and row.get("post_url"):
                            ws.update_cell(found, headers.index("post_url") + 1, str(row["post_url"]))
                        return
                    break
            if found is None:
                new_row = [""] * len(headers)
                for field, value in row.items():
                    if field in headers:
                        new_row[headers.index(field)] = str(value)
                ws.append_row(new_row, value_input_option="RAW")
            else:
                for field, value in row.items():
                    if field in headers:
                        ws.update_cell(found, headers.index(field) + 1, str(value))

    def update_queue_status(self, job_id: str, status: str, note: str) -> None:
        if status not in {"APPROVED", "POSTING", "POSTED", "FAILED"}:
            raise MetaIntegrationError("Invalid publisher-controlled queue status")
        ws = self.workbook.worksheet("POST_QUEUE")
        with self._lock:
            values = ws.get_all_values()
            headers = values[0] if values else []
            if not {"job_id", "status", "agent_notes"}.issubset(headers):
                raise MetaIntegrationError("POST_QUEUE schema mismatch; refusing to write")
            found = None
            for line, cells in enumerate(values[1:], 2):
                padded = cells + [""] * max(0, len(headers) - len(cells))
                if dict(zip(headers, padded)).get("job_id", "").strip() == job_id:
                    found = line
                    break
            if found is None:
                raise MetaIntegrationError("Toolkit job was not found")
            ws.update_cell(found, headers.index("status") + 1, status)
            ws.update_cell(found, headers.index("agent_notes") + 1, note)


class PublishLedger:
    """Durable per-job/per-platform idempotency; uncertain states never auto-retry."""
    TERMINAL_SUCCESS = "PUBLISHED"
    def __init__(self, database_path: str):
        self.database_path = database_path
        self._lock = threading.RLock()
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS meta_posts (
                job_id TEXT NOT NULL, platform TEXT NOT NULL, state TEXT NOT NULL,
                attempts INTEGER NOT NULL, remote_id TEXT, permalink TEXT,
                error_code TEXT, updated_at TEXT NOT NULL,
                PRIMARY KEY(job_id, platform))""")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=10, isolation_level="IMMEDIATE")
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, job_id: str, platform: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM meta_posts WHERE job_id=? AND platform=?", (job_id, platform)).fetchone()
        return dict(row) if row else None

    def reserve(self, job_id: str, platform: str, max_attempts: int) -> int:
        if platform not in {"facebook", "instagram"}:
            raise MetaIntegrationError("Unsupported platform")
        now = _now()
        with self._lock, self._connect() as db:
            row = db.execute("SELECT state,attempts FROM meta_posts WHERE job_id=? AND platform=?",
                             (job_id, platform)).fetchone()
            if row is None:
                db.execute("INSERT INTO meta_posts VALUES (?,?, 'POSTING',1,NULL,NULL,NULL,?)",
                           (job_id, platform, now))
                return 1
            if row["state"] == "PUBLISHED":
                raise MetaIntegrationError(f"{platform} already published for this job")
            if row["state"] == "UNCERTAIN":
                raise MetaIntegrationError(f"{platform} outcome uncertain; reconcile before retry")
            if row["state"] != "FAILED_RETRYABLE" or row["attempts"] >= max_attempts:
                raise MetaIntegrationError(f"{platform} job is already claimed or retry limit reached")
            attempt = int(row["attempts"]) + 1
            db.execute("UPDATE meta_posts SET state='POSTING',attempts=?,updated_at=?,error_code=NULL WHERE job_id=? AND platform=?",
                       (attempt, now, job_id, platform))
            return attempt

    def update(self, job_id: str, platform: str, state: str, *, remote_id: str | None = None,
               permalink: str | None = None, error_code: str | None = None) -> None:
        if state not in {"POSTING", "CONTAINER_CREATED", "PUBLISHED", "FAILED_RETRYABLE", "FAILED_FINAL", "UNCERTAIN"}:
            raise MetaIntegrationError("Invalid ledger state")
        with self._lock, self._connect() as db:
            db.execute("""UPDATE meta_posts SET state=?,remote_id=COALESCE(?,remote_id),
                permalink=COALESCE(?,permalink),error_code=?,updated_at=? WHERE job_id=? AND platform=?""",
                       (state, remote_id, permalink, error_code, _now(), job_id, platform))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_url(version: str, mode: InstagramAuthMode | None = None) -> str:
    host = "graph.instagram.com" if mode == InstagramAuthMode.INSTAGRAM_LOGIN else "graph.facebook.com"
    return f"https://{host}/{version}"


def _safe_error_code(response: HttpResponse) -> str:
    body = response.body if isinstance(response.body, dict) else {}
    error = body.get("error", {})
    if isinstance(error, dict):
        code = error.get("code") or error.get("type") or f"http_{response.status}"
        subcode = error.get("error_subcode")
    else:
        code = f"http_{response.status}"
        subcode = None
    text = str(code)
    if isinstance(subcode, int) or (isinstance(subcode, str) and subcode.isdigit()):
        text += f"_subcode_{subcode}"
    return re.sub(r"[^A-Za-z0-9_.-]", "_", text)[:80]


def _error_code_from_message(message: str) -> str:
    match = re.search(r"Meta API rejected request \(([^)]+)\)", message)
    return match.group(1)[:80] if match else "API_ERROR"


class MetaPublisher:
    """Approval-gated Meta publisher. No remote publishing or Sheet writes in dry-run mode; job reads still occur."""
    def __init__(self, *, settings: MetaSettings, transport: MetaTransport,
                 secrets: SecretStore, sheets: SheetsStore, ledger: PublishLedger,
                 media_verifier: MediaVerifier, approval_gate: ApprovalGate | None = None,
                 logger: EventLogger | None = None, dry_run: bool = DRY_RUN,
                 max_attempts: int = MAX_ATTEMPTS):
        if not dry_run and (not LIVE_ENABLEMENT_APPROVED or not settings.live_enablement_approved):
            raise MetaIntegrationError("Live publishing is disabled pending separate owner approval")
        if not dry_run and not settings.api_contracts_verified:
            raise MetaIntegrationError("Official Meta contracts/version are unverified; refusing live requests")
        self.settings, self.transport, self.secrets, self.sheets = settings, transport, secrets, sheets
        self.ledger, self.media_verifier = ledger, media_verifier
        self.approval_gate = approval_gate or DenyAllApprovalGate()
        self.logger = logger or NoopLogger()
        self.dry_run = dry_run
        self.max_attempts = max_attempts

    def _base(self, platform: Platform) -> str:
        mode = self.settings.instagram_auth_mode if platform == Platform.INSTAGRAM else None
        return _base_url(self.settings.api_version, mode)

    def validate_token_and_identity(self, platform: Platform) -> dict[str, str]:
        """Read-only Meta token, Page task, and account identity preflight."""
        # This read-only credential/account preflight is separate from the
        # unverified publishing contracts gated by api_contracts_verified.
        token = self._token(platform)
        app_token = self.secrets.get_meta_app_access_token(platform.value)
        expected_app_id = (self.settings.facebook_app_id if platform == Platform.FACEBOOK
                           else self.settings.instagram_app_id)
        if not token or not app_token or not expected_app_id:
            raise MetaIntegrationError("Meta validation credentials/app reference are unavailable")
        body = self._api_request("GET", f"{_base_url(self.settings.api_version)}/debug_token", app_token,
            params={"input_token": token})
        scopes = ("pages_manage_posts", "pages_read_engagement") if platform == Platform.FACEBOOK else (
            ("instagram_basic", "instagram_content_publish", "pages_show_list", "pages_read_engagement")
            if self.settings.instagram_auth_mode == InstagramAuthMode.FACEBOOK_LOGIN else
            ("instagram_business_basic", "instagram_business_content_publish"))
        validate_meta_token_response(body, expected_app_id=expected_app_id, required_scopes=set(scopes))
        if platform == Platform.FACEBOOK:
            page = self._api_request("GET", f"{_base_url(self.settings.api_version)}/{self.settings.page_id}", token,
                params={"fields": "id,name"})
            if str(page.get("id", "")) != self.settings.page_id:
                raise MetaIntegrationError("Page token does not identify the configured Graph API Page")
            if str(page.get("name", "")).strip().casefold() != self.settings.expected_page_name.strip().casefold():
                raise MetaIntegrationError("Graph API Page name does not match the requested company Page")
            # Page.tasks is not a Page-node field in v26. Read assigned tasks
            # from the authorized user's accounts edge instead.
            validation_user_token = self.secrets.get_validation_user_access_token()
            if not validation_user_token:
                raise MetaIntegrationError("Read-only validation User Access Token is unavailable")
            user_debug = self._api_request("GET", f"{_base_url(self.settings.api_version)}/debug_token", app_token,
                params={"input_token": validation_user_token})
            validate_meta_token_response(user_debug, expected_app_id=expected_app_id,
                required_scopes={"pages_show_list", "pages_read_engagement"})
            # /me/accounts requires a User Access Token. The Page token remains
            # reserved for Page publishing/identity checks; the App token is
            # reserved for debug_token and is never substituted here.
            accounts = self._api_request("GET", f"{_base_url(self.settings.api_version)}/me/accounts", validation_user_token,
                params={"fields": "id,tasks", "limit": "100"})
            matches = [item for item in accounts.get("data", []) if str(item.get("id", "")) == self.settings.page_id]
            tasks = matches[0].get("tasks") if len(matches) == 1 else None
            if not isinstance(tasks, list) or not {str(x).upper() for x in tasks}.intersection({"CREATE_CONTENT", "MANAGE"}):
                raise MetaIntegrationError("Page token lacks a verified content-management task")
        elif self.settings.instagram_auth_mode == InstagramAuthMode.FACEBOOK_LOGIN:
            linked = self._api_request("GET", f"{_base_url(self.settings.api_version)}/{self.settings.page_id}", token,
                params={"fields": "instagram_business_account{id,username}"})
            account = linked.get("instagram_business_account")
            if not isinstance(account, dict) or str(account.get("id", "")) != self.settings.instagram_user_id:
                raise MetaIntegrationError("Instagram account is not the configured Page-linked professional account")
            if str(account.get("username", "")).lstrip("@").casefold() != self.settings.expected_instagram_username.lstrip("@").casefold():
                raise MetaIntegrationError("Linked Instagram username does not match the requested account")
        else:
            account = self._api_request("GET", f"{_base_url(self.settings.api_version, self.settings.instagram_auth_mode)}/{self.settings.instagram_user_id}", token,
                params={"fields": "id,username"})
            if str(account.get("id", "")) != self.settings.instagram_user_id:
                raise MetaIntegrationError("Instagram token does not identify the configured professional account")
            if str(account.get("username", "")).lstrip("@").casefold() != self.settings.expected_instagram_username.lstrip("@").casefold():
                raise MetaIntegrationError("Instagram username does not match the requested account")
        return {"platform": platform.value, "identity": "verified", "app_id": expected_app_id}

    def _token(self, platform: Platform) -> str:
        token = (self.secrets.get_facebook_page_access_token() if platform == Platform.FACEBOOK
                 else self.secrets.get_instagram_access_token())
        if not isinstance(token, str) or not token.strip():
            raise MetaIntegrationError(f"{platform.value} credential is unavailable")
        return token

    def _read_approved_job(self, job_id: str) -> tuple[dict[str, str], dict[str, str]]:
        queue = self.sheets.read_queue_job(job_id)
        content = self.sheets.read_content_job(job_id)
        validate_publishable_row(queue, content)
        return queue, content

    def run_job(self, job_id: str) -> dict[str, Any]:
        """Publish selected FB/IG channels; TikTok is never routed here."""
        queue, content = self._read_approved_job(job_id)
        targets = [p for p, field in ((Platform.FACEBOOK, "facebook"), (Platform.INSTAGRAM, "instagram"))
                   if queue.get(field, "").strip().upper() in {"TRUE", "YES", "1"}]
        if not targets:
            raise MetaIntegrationError("No Facebook or Instagram target is selected")
        for platform in targets:
            if not self.approval_gate.authorize(job_id, platform.value):
                raise MetaIntegrationError(f"Separate verified owner approval is required for {platform.value}")
        if self.dry_run:
            return {"status": "DRY_RUN", "job_id": job_id,
                    "platforms": [p.value for p in targets], "tiktok": "excluded",
                    "detail": "No Sheet writes, credentials, media fetches, or Meta calls were made"}
        if not self.settings.live_enablement_approved or not LIVE_ENABLEMENT_APPROVED:
            raise MetaIntegrationError("Live publishing is disabled pending separate owner approval")
        if not self.settings.api_contracts_verified:
            raise MetaIntegrationError("Official Meta contracts/version are unverified; refusing live requests")

        results: dict[str, dict[str, str]] = {}
        failures: list[MetaIntegrationError] = []
        for platform in targets:
            # Re-read the actual queue row immediately before each platform action.
            current_queue, current_content = self._read_approved_job(job_id)
            if current_queue.get(platform.value, "").strip().upper() not in {"TRUE", "YES", "1"}:
                results[platform.value] = {"status": "FAILED", "error_code": "TARGET_CHANGED"}
                self._update_queue_from_results(job_id, results, targets)
                raise MetaIntegrationError(f"{platform.value} selection changed before publishing")
            if not self.approval_gate.authorize(job_id, platform.value):
                results[platform.value] = {"status": "FAILED", "error_code": "OWNER_APPROVAL_REQUIRED"}
                self._update_queue_from_results(job_id, results, targets)
                raise MetaIntegrationError(f"Owner approval expired or missing for {platform.value}")
            saved = self.ledger.get(job_id, platform.value)
            if saved and saved.get("state") == "PUBLISHED":
                # Repair a missing Sheets log after a confirmed remote success without replaying the post.
                self._write_log(job_id, platform, saved["attempts"], "POSTED",
                                remote_id=saved.get("remote_id") or "",
                                permalink=saved.get("permalink") or "",
                                posted_at=saved["updated_at"])
                results[platform.value] = {"status": "PUBLISHED", "post_id": saved.get("remote_id") or "",
                                          "permalink": saved.get("permalink") or "",
                                          "detail": "Already confirmed; log reconciled without republishing"}
                continue
            try:
                results[platform.value] = self._publish_one(job_id, platform, current_queue, current_content)
            except MetaIntegrationError as exc:
                results[platform.value] = {"status": "UNCERTAIN" if "uncertain" in str(exc).lower() else "FAILED",
                                           "error_code": "REQUEST_UNCERTAIN" if "uncertain" in str(exc).lower() else "PUBLISH_FAILED"}
                failures.append(exc)
        self._update_queue_from_results(job_id, results, targets)
        if failures:
            raise failures[0]
        return {"job_id": job_id, "results": results}

    def _publish_one(self, job_id: str, platform: Platform, queue: dict[str, str], content: dict[str, str]) -> dict[str, str]:
        due = scheduled_at(queue)
        scheduled_text = due.isoformat() if due else ""
        asset_field = "facebook_asset_url" if platform == Platform.FACEBOOK else "instagram_asset_url"
        caption_field = "facebook_caption" if platform == Platform.FACEBOOK else "instagram_caption"
        hashtags_field = "facebook_hashtags" if platform == Platform.FACEBOOK else "instagram_hashtags"
        media_url = content.get(asset_field, "").strip() or content.get("final_master_asset_url", "").strip()
        caption = content.get(caption_field, "").strip()
        hashtags = content.get(hashtags_field, "").strip()
        if not caption:
            raise MetaIntegrationError(f"{platform.value} caption is missing")
        if hashtags:
            caption = f"{caption}\n\n{hashtags}"
        try:
            _validate_media_url(media_url, self.settings.verified_media_hosts)
            self.media_verifier.verify_public_jpeg(media_url)
        except MetaIntegrationError:
            self._write_log(job_id, platform, 0, "FAILED", scheduled_at=scheduled_text, error_code="MEDIA_INVALID",
                            error_message="Media URL is not a verified public JPEG")
            raise
        attempt = self.ledger.reserve(job_id, platform.value, self.max_attempts)
        while True:
            self.logger.emit("meta_publish_started", {"job_id": job_id, "platform": platform.value,
                                                        "attempt": str(attempt)})
            try:
                response = (self._publish_facebook(media_url, caption) if platform == Platform.FACEBOOK
                            else self._publish_instagram(job_id, media_url, caption))
                break
            except MetaIntegrationError as exc:
                uncertain = "uncertain" in str(exc).lower()
                retryable = "safe bounded retry" in str(exc).lower()
                state = "UNCERTAIN" if uncertain else "FAILED_RETRYABLE" if retryable else "FAILED_FINAL"
                code = "REQUEST_UNCERTAIN" if uncertain else "RATE_LIMITED" if retryable else _error_code_from_message(str(exc))
                self.ledger.update(job_id, platform.value, state, error_code=code)
                self._write_log(job_id, platform, attempt, state, scheduled_at=scheduled_text, error_code=code,
                                error_message="Outcome uncertain; reconcile before retry" if uncertain else
                                              "Definitive rate limit; bounded retry pending" if retryable and attempt < self.max_attempts else
                                              "Definitive rate limit; retry limit exhausted" if retryable else
                                              "Meta rejected the publishing operation")
                if retryable and attempt < self.max_attempts:
                    time.sleep(min(2 ** (attempt - 1), 2))
                    attempt = self.ledger.reserve(job_id, platform.value, self.max_attempts)
                    continue
                raise
        remote_id, permalink = response
        if not remote_id:
            self.ledger.update(job_id, platform.value, "UNCERTAIN", error_code="MISSING_REMOTE_ID")
            self._write_log(job_id, platform, attempt, "UNCERTAIN", scheduled_at=scheduled_text,
                            error_code="MISSING_REMOTE_ID",
                            error_message="Meta response lacked a confirmed post ID; reconcile before retry")
            raise MetaIntegrationError("Meta publish outcome uncertain: response lacked a post ID")
        self.ledger.update(job_id, platform.value, "PUBLISHED", remote_id=remote_id, permalink=permalink)
        self._write_log(job_id, platform, attempt, "POSTED", scheduled_at=scheduled_text,
                        remote_id=remote_id, permalink=permalink,
                        posted_at=_now())
        self.logger.emit("meta_publish_confirmed", {"job_id": job_id, "platform": platform.value,
                                                       "attempt": str(attempt), "remote_id": remote_id})
        return {"status": "POSTED", "post_id": remote_id, "permalink": permalink}

    def _api_request(self, method: str, url: str, token: str, *, form: dict[str, str] | None = None,
                     params: dict[str, str] | None = None) -> dict[str, Any]:
        # Keep credential transmission out of operational logs; Graph API calls use form/query fields.
        payload = dict(form or {})
        query = dict(params or {})
        if method.upper() == "GET":
            query["access_token"] = token
        else:
            payload["access_token"] = token
        try:
            response = self.transport.request(method, url, params=query, form=payload or None)
        except MetaIntegrationError:
            raise
        except Exception:
            raise MetaIntegrationError("Meta request outcome uncertain") from None
        if not isinstance(response, HttpResponse):
            raise MetaIntegrationError("Invalid Meta transport response")
        if response.status >= 500 or response.status in {408, 425}:
            raise MetaIntegrationError("Meta request outcome uncertain")
        if response.status == 429:
            raise MetaIntegrationError("Meta rate limit; safe bounded retry permitted")
        body = response.body if isinstance(response.body, dict) else {}
        if response.status >= 400 or "error" in body:
            code = _safe_error_code(response)
            endpoint = urlsplit(url).path.rstrip("/").split("/")[-1]
            endpoint = endpoint if endpoint in {"debug_token", "me", "accounts", "photos", "media", "media_publish"} else "graph_request"
            raise MetaIntegrationError(f"Meta API rejected request ({code}; endpoint={endpoint})")
        return body

    def _publish_facebook(self, image_url: str, caption: str) -> tuple[str, str]:
        token = self._token(Platform.FACEBOOK)
        url = f"{_base_url(self.settings.api_version)}/{self.settings.page_id}/photos"
        body = self._api_request("POST", url, token, form={"url": image_url, "caption": caption, "published": "true"})
        photo_id = body.get("id")
        post_id = body.get("post_id") or photo_id
        permalink = str(body.get("permalink_url") or "")
        if not post_id:
            return "", ""
        if not permalink:
            try:
                details = self._api_request("GET", f"{_base_url(self.settings.api_version)}/{post_id}", token,
                                            params={"fields": "permalink_url"})
                permalink = str(details.get("permalink_url") or "")
            except MetaIntegrationError:
                # The photo publish response already confirmed the post; never replay for a missing permalink.
                permalink = ""
        return str(post_id), permalink

    def _publish_instagram(self, job_id: str, image_url: str, caption: str) -> tuple[str, str]:
        token = self._token(Platform.INSTAGRAM)
        base = _base_url(self.settings.api_version, self.settings.instagram_auth_mode)
        created = self._api_request("POST", f"{base}/{self.settings.instagram_user_id}/media", token,
                                    form={"image_url": image_url, "caption": caption})
        container_id = created.get("id")
        if not isinstance(container_id, str) or not container_id:
            raise MetaIntegrationError("Meta Instagram container response lacked an ID")
        self.ledger.update(job_id, "instagram", "CONTAINER_CREATED", remote_id=container_id)
        try:
            published = self._api_request("POST", f"{base}/{self.settings.instagram_user_id}/media_publish", token,
                                          form={"creation_id": container_id})
        except MetaIntegrationError as exc:
            if "uncertain" in str(exc).lower():
                raise
            # Container creation itself did not publish; no automatic replay of this job.
            raise
        media_id = published.get("id")
        if not isinstance(media_id, str) or not media_id:
            raise MetaIntegrationError("Meta Instagram publish outcome uncertain: response lacked a media ID")
        permalink = ""
        try:
            details = self._api_request("GET", f"{base}/{media_id}", token,
                                        params={"fields": "id,permalink,media_type,timestamp"})
            permalink = str(details.get("permalink") or "")
        except MetaIntegrationError:
            # Publish ID already confirms publication; never republish because permalink lookup failed.
            pass
        return str(media_id), permalink

    def _write_log(self, job_id: str, platform: Platform, attempt: int, status: str, *,
                   scheduled_at: str = "", remote_id: str = "", permalink: str = "", error_code: str = "",
                   error_message: str = "", posted_at: str = "") -> None:
        row = {"job_id": job_id, "platform": platform.value, "attempt_number": str(attempt),
               "scheduled_at": scheduled_at, "attempted_at": _now(), "status": status, "platform_post_id": remote_id,
               "post_url": permalink, "error_code": error_code, "error_message": error_message,
               "retry_count": str(max(0, attempt - 1)), "last_updated": _now()}
        if posted_at:
            row["posted_at"] = posted_at
        self.sheets.upsert_post_log(row)

    def _update_queue_from_results(self, job_id: str, results: dict[str, dict[str, str]], targets: list[Platform]) -> None:
        successful = [p.value for p in targets if results.get(p.value, {}).get("status") == "POSTED"
                      or (self.ledger.get(job_id, p.value) or {}).get("state") == "PUBLISHED"]
        if len(successful) == len(targets):
            self.sheets.update_queue_status(job_id, "POSTED", "Facebook and Instagram publication confirmed; see per-platform POST_LOG rows.")
        elif successful:
            self.sheets.update_queue_status(job_id, "FAILED", "PARTIAL: confirmed " + ", ".join(successful) + "; reconcile failed/uncertain platform before any retry.")
        else:
            self.sheets.update_queue_status(job_id, "FAILED", "Meta publishing failed or is uncertain; reconcile before retry.")


def validate_meta_token_response(body: dict[str, Any], *, expected_app_id: str,
                                 required_scopes: set[str], now: int | None = None) -> None:
    """Strict validator for reviewed debug-token response shape; never logs values."""
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict) or data.get("is_valid") is not True:
        raise MetaIntegrationError("Meta token is invalid")
    if str(data.get("app_id", "")) != expected_app_id:
        raise MetaIntegrationError("Meta token belongs to a different application")
    scopes = data.get("scopes")
    if not isinstance(scopes, list) or not required_scopes.issubset({str(x) for x in scopes}):
        raise MetaIntegrationError("Meta token is missing required permissions")
    expiry = data.get("expires_at")
    if not isinstance(expiry, int) or (expiry != 0 and expiry <= (now if now is not None else int(time.time()))):
        raise MetaIntegrationError("Meta token is expired or has no verifiable expiry")
    data_expiry = data.get("data_access_expires_at")
    current = now if now is not None else int(time.time())
    if isinstance(data_expiry, int) and data_expiry != 0 and data_expiry <= current:
        raise MetaIntegrationError("Meta token data access has expired")


def _store_row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("job_id", ""), row.get("platform", ""), row.get("attempt_number", "")

class EnvironmentSecrets:
    """Environment-only Secret Store adapter; intentionally no file fallback."""
    def get_facebook_page_access_token(self):
        return os.environ.get('TOOLKIT_META_FACEBOOK_PAGE_ACCESS_TOKEN', '')
    def get_instagram_access_token(self):
        return os.environ.get('TOOLKIT_META_INSTAGRAM_ACCESS_TOKEN', '')
    def get_validation_user_access_token(self):
        return os.environ.get('TOOLKIT_META_VALIDATION_ACCESS_TOKEN', '')
    def get_meta_app_access_token(self, platform):
        # debug_token requires an App Access Token, not a User/Page token.
        return os.environ.get('TOOLKIT_META_APP_ACCESS_TOKEN', '')

def fingerprint_rows(settings, job, queue, content):
    fields = {'job_id':job,'page_id':settings.page_id,'instagram_id':settings.instagram_user_id,
              'mode':settings.instagram_auth_mode.value,'version':settings.api_version,
              'queue':{k:queue.get(k,'') for k in ('enabled','action','approval_mode','status',
                  'facebook','instagram','tiktok','publish_date','publish_time','timezone')},
              'content':{k:content.get(k,'') for k in sorted(OUTPUT_FIELDS)}}
    return hashlib.sha256(json.dumps(fields,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
