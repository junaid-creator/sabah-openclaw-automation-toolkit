"""Offline Meta/Sheets tests. All Meta responses are mocked; no live HTTP or Sheets calls."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


from toolkit import meta_publisher as meta


class FakeSecrets:
    def __init__(self):
        self.tokens = {"facebook": "unit-test-facebook-token", "instagram": "unit-test-instagram-token"}
        self.app_tokens = {"facebook": "unit-test-fb-app-token", "instagram": "unit-test-ig-app-token"}
        self.validation_user_token = "unit-test-validation-user-token"
    def get_facebook_page_access_token(self): return self.tokens["facebook"]
    def get_instagram_access_token(self): return self.tokens["instagram"]
    def get_validation_user_access_token(self): return self.validation_user_token
    def get_meta_app_access_token(self, platform): return self.app_tokens[platform]


class FakeApproval:
    def __init__(self, allow=True): self.allow, self.calls = allow, []
    def authorize(self, job_id, platform):
        self.calls.append((job_id, platform))
        return self.allow


class FakeMedia:
    def __init__(self): self.calls = []
    def verify_public_jpeg(self, url): self.calls.append(url)


class FakeLogger:
    def __init__(self): self.events = []
    def emit(self, event, fields): self.events.append((event, dict(fields)))


class FakeTransport:
    def __init__(self, *responses): self.responses = list(responses); self.calls = []
    def request(self, method, url, *, params=None, form=None, timeout=20):
        self.calls.append((method, url, dict(params or {}), dict(form or {})))
        value = self.responses.pop(0)
        if isinstance(value, Exception): raise value
        return value


class FakeSheets:
    def __init__(self, *, status="APPROVED", facebook="TRUE", instagram="TRUE", tiktok="TRUE"):
        self.queue = {"job_id": "SM-TEST-NEW", "enabled": "TRUE", "action": "PUBLISH", "approval_mode": "MANUAL",
            "status": status, "facebook": facebook, "instagram": instagram, "tiktok": tiktok,
            "agent_notes": ""}
        self.content = {"job_id": "SM-TEST-NEW", "selected_concept": "1",
            "final_master_asset_url": "https://cdn.example.test/creative.jpg",
            "facebook_asset_url": "", "instagram_asset_url": "",
            "facebook_caption": "Professional construction and equipment rental services in the UAE.",
            "instagram_caption": "Professional construction and equipment rental services in the UAE.",
            "facebook_hashtags": "#Toolkit #UAE",
            "instagram_hashtags": "#Toolkit #UAE",
            "qa_status": "READY_FOR_OWNER_REVIEW"}
        self.logs, self.status_updates, self.reads = [], [], 0
    def read_queue_job(self, job_id): self.reads += 1; return dict(self.queue)
    def read_content_job(self, job_id): return dict(self.content)
    def upsert_post_log(self, row): self.logs.append(dict(row))
    def update_queue_status(self, job_id, status, note):
        self.status_updates.append((status, note)); self.queue["status"] = status; self.queue["agent_notes"] = note


class TargetChangingSheets(FakeSheets):
    def read_queue_job(self, job_id):
        self.reads += 1
        row = dict(self.queue)
        # Initial read and pre-Facebook recheck retain both targets; before Instagram it is disabled.
        if self.reads >= 3:
            row["instagram"] = "FALSE"
        return row


class FakeWorksheet:
    def __init__(self, title, rows): self.title, self.rows, self.writes = title, rows, []
    def get_all_values(self): return [list(r) for r in self.rows]
    def append_row(self, row, value_input_option=None): self.rows.append(list(row)); self.writes.append(("append", row))
    def update_cell(self, row, col, value):
        while len(self.rows) < row: self.rows.append([])
        while len(self.rows[row - 1]) < col: self.rows[row - 1].append("")
        self.rows[row - 1][col - 1] = value; self.writes.append(("update", row, col, value))


class FakeWorkbook:
    def __init__(self, worksheets): self.worksheets = worksheets
    def worksheet(self, name): return self.worksheets[name]


class MetaPublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = meta.PublishLedger(str(Path(self.temp.name) / "ledger.sqlite"))
        self.sheets = FakeSheets()
        self.secrets = FakeSecrets()
        self.approval = FakeApproval()
        self.media = FakeMedia()
        self.logger = FakeLogger()
        self.settings = meta.MetaSettings(api_version="v25.0", instagram_auth_mode=meta.InstagramAuthMode.FACEBOOK_LOGIN,
            page_id="12345678901", instagram_user_id="10987654321",
            expected_page_name="Example Organization", expected_instagram_username="example_account",
            business_portfolio_id="3333333333333333",
            facebook_app_id="4444444444444444", instagram_app_id="5555555555555555",
            verified_media_hosts=frozenset({"cdn.example.test"}),
            api_contracts_verified=True, live_enablement_approved=True)

    def tearDown(self): self.temp.cleanup()

    def make_publisher(self, transport, *, dry_run=False, settings=None, approval=None):
        with patch.object(meta, "LIVE_ENABLEMENT_APPROVED", (not dry_run)):
            return meta.MetaPublisher(settings=settings or self.settings, transport=transport, secrets=self.secrets,
                sheets=self.sheets, ledger=self.ledger, media_verifier=self.media,
                approval_gate=approval or self.approval, logger=self.logger, dry_run=dry_run)

    def live(self, publisher):
        with patch.object(meta, "LIVE_ENABLEMENT_APPROVED", True):
            return publisher.run_job("SM-TEST-NEW")

    def test_settings_require_explicit_version_and_graph_account_ids(self):
        with self.assertRaisesRegex(meta.MetaIntegrationError, "version"):
            meta.MetaSettings(api_version="latest", instagram_auth_mode=meta.InstagramAuthMode.FACEBOOK_LOGIN,
                page_id="12345678901", instagram_user_id="10987654321", expected_page_name="Toolkit")
        with self.assertRaisesRegex(meta.MetaIntegrationError, "Page ID"):
            meta.MetaSettings(api_version="v25.0", instagram_auth_mode=meta.InstagramAuthMode.FACEBOOK_LOGIN,
                page_id="3333333333333333", instagram_user_id="10987654321", expected_page_name="Toolkit", expected_instagram_username="example_account",
                business_portfolio_id="3333333333333333")

    def test_unapproved_sheet_job_never_reaches_meta(self):
        self.sheets.queue["status"] = "WAITING_APPROVAL"
        p = self.make_publisher(FakeTransport())
        with self.assertRaisesRegex(meta.MetaIntegrationError, "APPROVED"):
            self.live(p)
        self.assertEqual(p.transport.calls, [])

    def test_sheet_approval_alone_is_not_live_authorization(self):
        p = self.make_publisher(FakeTransport(), approval=FakeApproval(False))
        with self.assertRaisesRegex(meta.MetaIntegrationError, "owner approval"):
            self.live(p)
        self.assertEqual(p.transport.calls, [])

    def test_sheet_publication_gate_enforces_owner_operational_flags(self):
        gate = meta.SheetPublicationGate(self.sheets)
        self.assertTrue(gate.authorize("SM-TEST-NEW", "facebook"))
        self.sheets.queue["status"] = "WAITING_APPROVAL"
        self.assertFalse(gate.authorize("SM-TEST-NEW", "facebook"))
        self.sheets.queue.update(status="APPROVED", approval_mode="AUTO",
                                 publish_date="2020-01-01", publish_time="11:00", timezone="Asia/Dubai")
        self.assertTrue(gate.authorize("SM-TEST-NEW", "facebook"))
        self.assertFalse(gate.authorize("SM-TEST-NEW", "tiktok"))

    def test_live_enablement_flag_defaults_closed(self):
        settings = meta.MetaSettings(api_version="v25.0", instagram_auth_mode=meta.InstagramAuthMode.FACEBOOK_LOGIN,
            page_id="12345678901", instagram_user_id="10987654321", expected_page_name="Toolkit", expected_instagram_username="example_account",
            api_contracts_verified=True, live_enablement_approved=False)
        with self.assertRaisesRegex(meta.MetaIntegrationError, "disabled"):
            meta.MetaPublisher(settings=settings, transport=FakeTransport(), secrets=self.secrets,
                sheets=self.sheets, ledger=self.ledger, media_verifier=self.media, dry_run=False)

    def test_dry_run_reads_job_but_makes_no_meta_media_secret_or_sheet_writes(self):
        p = self.make_publisher(FakeTransport(), dry_run=True)
        result = p.run_job("SM-TEST-NEW")
        self.assertEqual(result["status"], "DRY_RUN")
        self.assertEqual(result["platforms"], ["facebook", "instagram"])
        self.assertEqual(result["tiktok"], "excluded")
        self.assertEqual(p.transport.calls, [])
        self.assertEqual(self.media.calls, [])
        self.assertEqual(self.sheets.logs, [])
        self.assertEqual(self.sheets.status_updates, [])

    def test_tiktok_selection_never_routes_to_meta(self):
        self.sheets.queue.update(facebook="FALSE", instagram="FALSE", tiktok="TRUE")
        with self.assertRaisesRegex(meta.MetaIntegrationError, "No Facebook or Instagram"):
            self.make_publisher(FakeTransport(), dry_run=True).run_job("SM-TEST-NEW")

    def test_http_nonpublic_media_is_rejected_before_remote_call(self):
        self.sheets.content["final_master_asset_url"] = "http://cdn.example.test/creative.jpg"
        p = self.make_publisher(FakeTransport())
        with self.assertRaisesRegex(meta.MetaIntegrationError, "HTTPS"):
            self.live(p)
        self.assertEqual(p.transport.calls, [])
        self.assertEqual(self.sheets.logs[0]["error_code"], "MEDIA_INVALID")

    def test_signed_media_url_is_rejected(self):
        with self.assertRaisesRegex(meta.MetaIntegrationError, "public HTTPS"):
            meta._validate_media_url("https://cdn.example.test/a.jpg?token=secret", {"cdn.example.test"})
        with self.assertRaisesRegex(meta.MetaIntegrationError, "allowlist"):
            meta._validate_media_url("https://unapproved.example/a.jpg", {"cdn.example.test"})

    def test_facebook_photo_publish_logs_confirmed_id_and_link(self):
        self.sheets.queue.update(instagram="FALSE")
        t = FakeTransport(meta.HttpResponse(200, {"id": "fb-photo-1", "post_id": "fb-post-1",
                                      "permalink_url": "https://www.facebook.com/123/posts/1"}))
        p = self.make_publisher(t)
        result = self.live(p)
        self.assertEqual(result["results"]["facebook"]["post_id"], "fb-post-1")
        self.assertEqual(t.calls[0][1], "https://graph.facebook.com/v25.0/12345678901/photos")
        self.assertEqual(t.calls[0][3]["url"], self.sheets.content["final_master_asset_url"])
        self.assertEqual(t.calls[0][3]["caption"],
                         "Professional construction and equipment rental services in the UAE.\n\n#Toolkit #UAE")
        self.assertEqual(self.sheets.logs[0]["platform_post_id"], "fb-post-1")
        self.assertEqual(self.sheets.logs[0]["status"], "POSTED")
        self.assertEqual(self.sheets.status_updates[-1][0], "POSTED")

    def test_facebook_permalink_lookup_failure_does_not_republish(self):
        self.sheets.queue.update(instagram="FALSE")
        t = FakeTransport(meta.HttpResponse(200, {"id": "fb-photo-2"}),
                          meta.HttpResponse(403, {"error": {"code": 10}}))
        p = self.make_publisher(t)
        result = self.live(p)
        self.assertEqual(result["results"]["facebook"]["status"], "POSTED")
        self.assertEqual(len(t.calls), 2)  # one publish plus a read-only permalink lookup
        self.assertEqual(self.ledger.get("SM-TEST-NEW", "facebook")["state"], "PUBLISHED")

    def test_instagram_facebook_login_uses_two_step_publish_and_correct_host(self):
        self.sheets.queue.update(facebook="FALSE")
        t = FakeTransport(meta.HttpResponse(200, {"id": "container-1"}),
                          meta.HttpResponse(200, {"id": "ig-media-1"}),
                          meta.HttpResponse(200, {"id": "ig-media-1", "permalink": "https://www.instagram.com/p/abc/"}))
        result = self.live(self.make_publisher(t))
        self.assertEqual(result["results"]["instagram"]["post_id"], "ig-media-1")
        self.assertEqual(t.calls[0][1], "https://graph.facebook.com/v25.0/10987654321/media")
        self.assertEqual(t.calls[1][1], "https://graph.facebook.com/v25.0/10987654321/media_publish")
        self.assertEqual(t.calls[1][3]["creation_id"], "container-1")
        self.assertEqual(self.sheets.logs[0]["post_url"], "https://www.instagram.com/p/abc/")

    def test_queue_target_is_reread_before_each_platform(self):
        self.sheets = TargetChangingSheets()
        t = FakeTransport(meta.HttpResponse(200, {"id": "fb-photo", "post_id": "fb-post",
                                      "permalink_url": "https://www.facebook.com/p/fb"}))
        with self.assertRaisesRegex(meta.MetaIntegrationError, "selection changed"):
            self.live(self.make_publisher(t))
        self.assertEqual(len([c for c in t.calls if c[0] == "POST"]), 1)
        self.assertEqual(self.ledger.get("SM-TEST-NEW", "facebook")["state"], "PUBLISHED")
        self.assertEqual(self.sheets.status_updates[-1][0], "FAILED")
        self.assertIn("PARTIAL: confirmed facebook", self.sheets.status_updates[-1][1])

    def test_auto_mode_enforces_dubai_schedule_and_logs_scheduled_time(self):
        self.sheets.queue.update(approval_mode="AUTO", facebook="TRUE", instagram="FALSE")
        self.sheets.queue.update(publish_date=meta.datetime.now(meta.ZoneInfo("Asia/Dubai")).date().isoformat(),
                                 publish_time="00:00", timezone="Asia/Dubai")
        t = FakeTransport(meta.HttpResponse(200, {"id":"fb-photo", "post_id":"fb-post",
            "permalink_url":"https://www.facebook.com/p/fb"}))
        self.live(self.make_publisher(t))
        self.assertTrue(self.sheets.logs[0]["scheduled_at"].endswith("+04:00"))

    def test_future_auto_schedule_blocks_before_any_meta_request(self):
        self.sheets.queue.update(approval_mode="AUTO", publish_date="2099-01-01",
                                 publish_time="09:00", timezone="Asia/Dubai")
        t = FakeTransport()
        with self.assertRaisesRegex(meta.MetaIntegrationError, "not yet due"):
            self.live(self.make_publisher(t))
        self.assertEqual(t.calls, [])

    def test_instagram_login_is_explicit_and_uses_its_host(self):
        self.sheets.queue.update(facebook="FALSE")
        settings = meta.MetaSettings(api_version="v25.0", instagram_auth_mode=meta.InstagramAuthMode.INSTAGRAM_LOGIN,
            page_id="12345678901", instagram_user_id="10987654321", expected_page_name="Toolkit", expected_instagram_username="example_account",
            api_contracts_verified=True, live_enablement_approved=True,
            verified_media_hosts=frozenset({"cdn.example.test"}))
        t = FakeTransport(meta.HttpResponse(200, {"id": "container"}), meta.HttpResponse(200, {"id": "ig"}),
                          meta.HttpResponse(200, {"id": "ig", "permalink": ""}))
        self.live(self.make_publisher(t, settings=settings))
        self.assertEqual(t.calls[0][1], "https://graph.instagram.com/v25.0/10987654321/media")

    def test_duplicate_platform_publish_is_blocked_by_durable_ledger(self):
        self.ledger.reserve("SM-TEST-NEW", "facebook", 2)
        self.ledger.update("SM-TEST-NEW", "facebook", "PUBLISHED", remote_id="fb-known")
        with self.assertRaisesRegex(meta.MetaIntegrationError, "already published"):
            self.ledger.reserve("SM-TEST-NEW", "facebook", 2)

    def test_confirmed_platform_is_skipped_on_reprocessing(self):
        self.sheets.queue.update(instagram="FALSE")
        self.ledger.reserve("SM-TEST-NEW", "facebook", 2)
        self.ledger.update("SM-TEST-NEW", "facebook", "PUBLISHED", remote_id="fb-known",
                           permalink="https://www.facebook.com/p/known")
        t = FakeTransport()
        result = self.live(self.make_publisher(t))
        self.assertEqual(result["results"]["facebook"]["status"], "PUBLISHED")
        self.assertEqual(t.calls, [])

    def test_uncertain_outcome_is_terminal_and_not_replayed(self):
        self.sheets.queue.update(instagram="FALSE")
        t = FakeTransport(TimeoutError("fake timeout"), meta.HttpResponse(200, {"id": "must-not-send"}))
        p = self.make_publisher(t)
        with self.assertRaisesRegex(meta.MetaIntegrationError, "uncertain"):
            self.live(p)
        self.assertEqual(self.ledger.get("SM-TEST-NEW", "facebook")["state"], "UNCERTAIN")
        self.sheets.queue["status"] = "APPROVED"  # simulated separate owner re-approval
        with self.assertRaisesRegex(meta.MetaIntegrationError, "uncertain"):
            self.live(p)
        self.assertEqual(len(t.calls), 1)

    def test_definitive_rate_limit_is_retryable_but_bounded(self):
        self.sheets.queue.update(instagram="FALSE")
        t = FakeTransport(meta.HttpResponse(429, {"error": {"code": 4}}),
                          meta.HttpResponse(200, {"id": "fb-post-2"}))
        p = self.make_publisher(t)
        result = self.live(p)
        self.assertEqual(result["results"]["facebook"]["status"], "POSTED")
        self.assertEqual(len([c for c in t.calls if c[0] == "POST"]), 2)
        self.assertEqual([row["attempt_number"] for row in self.sheets.logs], ["1", "2"])

    def test_partial_success_never_erases_confirmed_platform(self):
        t = FakeTransport(meta.HttpResponse(200, {"id": "fb-photo", "post_id": "fb-post",
                                      "permalink_url": "https://www.facebook.com/p/fb"}),
                          meta.HttpResponse(200, {"id": "container"}),
                          meta.HttpResponse(400, {"error": {"code": 200}}))
        p = self.make_publisher(t)
        with self.assertRaisesRegex(meta.MetaIntegrationError, "rejected"):
            self.live(p)
        self.assertEqual(self.ledger.get("SM-TEST-NEW", "facebook")["state"], "PUBLISHED")
        self.assertEqual(self.ledger.get("SM-TEST-NEW", "instagram")["state"], "FAILED_FINAL")
        self.assertEqual([r["platform"] for r in self.sheets.logs], ["facebook", "instagram"])
        self.assertEqual(self.sheets.status_updates[-1][0], "FAILED")
        self.assertIn("PARTIAL: confirmed facebook", self.sheets.status_updates[-1][1])

    def test_token_validation_rejects_wrong_app_permissions_and_expiry(self):
        good = {"data": {"is_valid": True, "app_id": "4444444444444444",
            "scopes": ["pages_manage_posts", "pages_read_engagement"], "expires_at": 9999999999}}
        meta.validate_meta_token_response(good, expected_app_id="4444444444444444",
            required_scopes={"pages_manage_posts"}, now=100)
        with self.assertRaisesRegex(meta.MetaIntegrationError, "different application"):
            meta.validate_meta_token_response(good, expected_app_id="else", required_scopes=set(), now=100)
        with self.assertRaisesRegex(meta.MetaIntegrationError, "missing required"):
            meta.validate_meta_token_response(good, expected_app_id="4444444444444444",
                required_scopes={"instagram_content_publish"}, now=100)
        expired = {"data": {**good["data"], "expires_at": 99}}
        with self.assertRaisesRegex(meta.MetaIntegrationError, "expired"):
            meta.validate_meta_token_response(expired, expected_app_id="4444444444444444",
                required_scopes=set(), now=100)
        invalid = {"data": {**good["data"], "is_valid": False}}
        with self.assertRaisesRegex(meta.MetaIntegrationError, "invalid"):
            meta.validate_meta_token_response(invalid, expected_app_id="4444444444444444",
                required_scopes=set(), now=100)

    def test_read_only_token_and_page_identity_preflight(self):
        self.sheets.queue.update(facebook="FALSE", instagram="FALSE")
        t = FakeTransport(meta.HttpResponse(200, {"data": {"is_valid": True,
                "app_id": "4444444444444444", "scopes": ["pages_manage_posts", "pages_read_engagement"],
                "expires_at": 9999999999}}), meta.HttpResponse(200, {"id": "12345678901",
                "name": "Example Organization"}),
                meta.HttpResponse(200, {"data": {"is_valid": True, "app_id": "4444444444444444",
                    "scopes": ["pages_show_list", "pages_read_engagement"], "expires_at": 9999999999}}),
                meta.HttpResponse(200, {"data": [{"id": "12345678901", "tasks": ["CREATE_CONTENT"]}]}))
        p = self.make_publisher(t)
        result = p.validate_token_and_identity(meta.Platform.FACEBOOK)
        self.assertEqual(result["identity"], "verified")
        self.assertIn("/debug_token", t.calls[0][1])
        self.assertIn("/12345678901", t.calls[1][1])
        self.assertNotIn("tasks", t.calls[1][2]["fields"])
        self.assertIn("/debug_token", t.calls[2][1])
        self.assertEqual(t.calls[2][2]["input_token"], self.secrets.validation_user_token)
        self.assertIn("/me/accounts", t.calls[3][1])
        self.assertEqual(t.calls[3][2]["access_token"], self.secrets.validation_user_token)
        self.assertNotEqual(t.calls[3][2]["access_token"], self.secrets.app_tokens["facebook"])

    def test_facebook_login_instagram_identity_must_match_linked_professional_account(self):
        scopes = ["instagram_basic", "instagram_content_publish", "pages_show_list", "pages_read_engagement"]
        t = FakeTransport(meta.HttpResponse(200, {"data": {"is_valid": True, "app_id": "5555555555555555",
                "scopes": scopes, "expires_at": 9999999999}}),
            meta.HttpResponse(200, {"instagram_business_account": {"id": "10987654321", "username": "example_account"}}))
        result = self.make_publisher(t).validate_token_and_identity(meta.Platform.INSTAGRAM)
        self.assertEqual(result["identity"], "verified")
        self.assertEqual(t.calls[1][1], "https://graph.facebook.com/v25.0/12345678901")
        self.assertIn("instagram_business_account", t.calls[1][2]["fields"])

    def test_instagram_login_token_and_identity_use_instagram_host_and_scopes(self):
        settings = meta.MetaSettings(api_version="v25.0", instagram_auth_mode=meta.InstagramAuthMode.INSTAGRAM_LOGIN,
            page_id="12345678901", instagram_user_id="10987654321", expected_page_name="Toolkit", expected_instagram_username="example_account",
            instagram_app_id="5555555555555555", api_contracts_verified=True,
            verified_media_hosts=frozenset({"cdn.example.test"}))
        t = FakeTransport(meta.HttpResponse(200, {"data": {"is_valid": True, "app_id": "5555555555555555",
                "scopes": ["instagram_business_basic", "instagram_business_content_publish"],
                "expires_at": 9999999999}}),
            meta.HttpResponse(200, {"id": "10987654321", "username": "example_account"}))
        result = self.make_publisher(t, settings=settings, dry_run=True).validate_token_and_identity(meta.Platform.INSTAGRAM)
        self.assertEqual(result["identity"], "verified")
        self.assertEqual(t.calls[1][1], "https://graph.instagram.com/v25.0/10987654321")

    def test_sheet_adapter_upserts_per_platform_without_overwriting_other_platform(self):
        headers = list(meta.POST_LOG_FIELDS)
        fb_row = ["SM-X", "facebook", "1", "", "", "", "POSTED", "fb-id", "fb-url", "", "", "0", "t1"]
        ws = FakeWorksheet("POST_LOG", [headers, fb_row])
        workbook = FakeWorkbook({"POST_LOG": ws})
        store = meta.GspreadSheetsStore(workbook)
        store.upsert_post_log({"job_id": "SM-X", "platform": "instagram", "attempt_number": "1",
            "status": "POSTED", "platform_post_id": "ig-id", "last_updated": "t2"})
        self.assertEqual(len(ws.rows), 3)
        self.assertEqual(ws.rows[1][1], "facebook")
        self.assertEqual(ws.rows[2][1], "instagram")

    def test_sheet_adapter_refuses_schema_mismatch(self):
        ws = FakeWorksheet("POST_LOG", [["job_id", "platform"]])
        with self.assertRaisesRegex(meta.MetaIntegrationError, "schema mismatch"):
            meta.GspreadSheetsStore(FakeWorkbook({"POST_LOG": ws})).upsert_post_log(
                {"job_id": "SM-X", "platform": "facebook", "attempt_number": "1"})


if __name__ == "__main__":
    unittest.main()


def setUpModule():
    global _guards
    import socket, subprocess, os
    def deny(*a, **k): raise AssertionError("External I/O forbidden in mock tests")
    _guards=[patch.object(socket,"socket",deny),patch.object(socket,"create_connection",deny),patch.object(subprocess,"Popen",deny),patch.object(os,"system",deny)]
    for g in _guards:g.start()

def tearDownModule():
    for g in reversed(_guards):g.stop()
