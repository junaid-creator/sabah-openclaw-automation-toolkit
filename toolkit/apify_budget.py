"""Source-derived fail-closed billing evidence checks; does not start Actors."""
import json, math, re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

class RunBudgetUnsafe(RuntimeError):
    """A mandatory financial guard cannot be established."""

def billing_guard(evidence_path, *, now=None, cap=0.20, reserve=0.30):
    BILLING_EVIDENCE = Path(evidence_path)
    CAP, ACCOUNT_RESERVE = float(cap), float(reserve)
    if not math.isfinite(CAP) or not math.isfinite(ACCOUNT_RESERVE) or CAP <= 0 or ACCOUNT_RESERVE < 0: raise RunBudgetUnsafe("Invalid budget limits")
    """Keep account-policy proof distinct from current-cycle credit proof."""
    if not BILLING_EVIDENCE.exists():
        raise RunBudgetUnsafe("RUN_BUDGET_UNSAFE: verified Free-plan/no-overage evidence unavailable")
    evidence = json.loads(BILLING_EVIDENCE.read_text())
    now = now or datetime.now(timezone.utc)
    try:
        policy_checked = datetime.fromisoformat(evidence["policy_verified_at"].replace("Z", "+00:00"))
        credit_checked = datetime.fromisoformat(evidence["credit_verified_at"].replace("Z", "+00:00"))
        cycle_start = datetime.fromisoformat(evidence["cycle_start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(evidence["cycle_end"].replace("Z", "+00:00"))
        balance = float(evidence["remaining_usd"])
        limit = float(evidence["monthly_limit_usd"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RunBudgetUnsafe("RUN_BUDGET_UNSAFE: malformed billing evidence") from exc
    if any(t.tzinfo is None for t in (policy_checked, credit_checked, cycle_start, end, now)):
        raise RunBudgetUnsafe("Billing evidence timestamps must be timezone-aware")
    if (evidence.get("free_plan_verified") is not True or evidence.get("no_overage_verified") is not True
            or not math.isfinite(limit) or not 0 < limit <= 5.00 or policy_checked > now
            or now - policy_checked > timedelta(days=30)):
        raise RunBudgetUnsafe("RUN_BUDGET_UNSAFE: Free-plan/no-overage policy evidence expired or invalid")
    if (credit_checked > now or now - credit_checked > timedelta(days=7)
            or cycle_start > credit_checked or end <= now or not math.isfinite(balance)
            or balance < CAP + ACCOUNT_RESERVE):
        raise RunBudgetUnsafe("RUN_BUDGET_UNSAFE: current-cycle credit evidence expired or reserve insufficient")
    evidence["cycle_start"] = cycle_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return evidence, balance

def norm(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())

def identity(row):
    return ((urlparse(str(row[5])).hostname or "").lower().removeprefix("www."),
            re.sub(r"\D", "", str(row[6])), norm(row[1]))

def email_matches_site(email, website):
    host = (urlparse(website).hostname or "").lower().removeprefix("www.")
    domain = email.lower().split("@")[-1]
    return bool(host and domain and (host == domain or host.endswith("." + domain)))
