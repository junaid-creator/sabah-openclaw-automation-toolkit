#!/usr/bin/env python3
"""Score public OSM business listings using a separate business profile."""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

HEADERS = ["Lead ID", "Business Name", "Industry", "Area", "Address", "Website", "Public Business Phone", "Public Business Email (if available)", "Source URL", "Source Type", "Relevant Services", "Qualification Score", "Qualification Reason", "Priority", "First Seen", "Last Checked", "Review Status", "Contact Status", "Notes"]


def normalized(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def domain(url):
    try:
        host = urlparse(url).hostname or ""
        return host.lower().removeprefix("www.")
    except ValueError:
        return ""


def qualify(item, profile, today):
    name = str(item.get("name") or "").strip()
    tags = item.get("tags") or {}
    low = name.casefold()
    if not name or re.fullmatch(r"buildings+[da-z -]+", low):
        return None
    if any(term in low for term in ("car rental", "bowling", "college", "electronics", "cosmetics", "burger", "construction site", "sports equipment", "kitchen equipment", "office furniture")):
        return None
    if tags.get("access") == "university" or tags.get("office") == "research":
        return None
    direct = next((term for term in profile["industry_keywords"]["direct"] if re.search('(?<![a-z])' + re.escape(term) + '(?![a-z])', low)), None)
    adjacent = next((term for term in profile["industry_keywords"]["adjacent"] if re.search('(?<![a-z])' + re.escape(term) + '(?![a-z])', low)), None)
    if not (direct or adjacent):
        return None
    lat, lon = item.get("latitude"), item.get("longitude")
    geo = profile["geographic_targets"]
    in_area = isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and geo["latitude_min"] <= lat <= geo["latitude_max"] and geo["longitude_min"] <= lon <= geo["longitude_max"]
    if not in_area:
        return None
    website = str(item.get("website") or "").strip()
    phone = str(item.get("phone") or "").strip()
    email = str(item.get("email") or "").strip()
    business_tag = tags.get("office") or tags.get("shop") or tags.get("craft")
    industry = 30 if direct else 20
    need = 15 if direct else 10
    presence = 15 if website else 5 if business_tag else 0
    contact = 10 if phone or email else 0
    score = industry + 25 + need + presence + contact
    priority = "High-priority prospect" if score >= 70 else "Medium-priority prospect" if score >= 40 else "Low priority"
    osm_url = str(item.get("osmUrl") or "")
    if not osm_url:
        return None
    source_id = f"osm:{item.get('osmType')}:{item.get('osmId')}"
    reason = f"{direct or adjacent} name match; configured-area coordinates; OSM {business_tag or 'listing'}; business need inferred, purchasing intent unverified"
    row = [source_id, name, "Maintenance / contracting" if direct else "Construction supply / equipment", geo["area"], str(item.get("addressFull") or ""), website, phone, email, osm_url, "OpenStreetMap via Apify", direct or adjacent, score, reason, priority, today, today, "NOT REVIEWED", "NOT CONTACTED", "© OpenStreetMap contributors, ODbL 1.0; contact fields absent where blank"]
    return row


def qualify_overture(item, profile, today):
    geo = profile["geographic_targets"]
    lat, lon = item.get("latitude"), item.get("longitude")
    if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and geo["latitude_min"] <= lat <= geo["latitude_max"] and geo["longitude_min"] <= lon <= geo["longitude_max"]):
        return None
    if not item.get("id"): return None
    name = str(item.get("name") or "").strip()
    low = name.casefold()
    category = str(item.get("category") or "")
    allowed = {"contractor", "building_or_construction_service", "hvac_service", "property_management"}
    if category not in allowed or not re.search(r"contract|construction|maintenance|facilit|fit.?out|mep|electro.?mechanical|hvac", low):
        return None
    if re.search(r"material|equipment|trading|supply|steel|consult|design|real estate|transport|automotiv|appliance|home fix|shop|store|interior decor", low):
        return None
    if category == "property_management" and not re.search(r"maintenance|facilit", low):
        return None
    phone = str(item.get("phone") or "").strip()
    website = str(item.get("website") or "").strip()
    email = str(item.get("email") or "").strip()
    if website and (not website.startswith("http") or re.search(r"facebook|instagram|linkedin|yellowpages|2gis", website, re.I)):
        website = ""
    if email and not re.match(r"^(info|contact|sales|admin|office|enquiries|inquiries|hello|business|projects|tenders)@", email, re.I):
        email = ""
    if not phone or not (website or email):
        return None
    score = 55 + (10 if category in {"contractor", "building_or_construction_service"} else 0) + (10 if website else 0) + (10 if email else 0)
    priority = "High-priority prospect" if score >= 70 else "Medium-priority prospect"
    industry = "Construction / contracting" if category in {"contractor", "building_or_construction_service"} else "Facilities / maintenance"
    reason = f"Overture category {category}; relevant company name; public business contact; purchasing intent unverified"
    lead_id = "overture:" + str(item.get("id") or "")
    notes = f"Overture Maps Places; CDLA Permissive 2.0; collected {today}; feature ID: {item.get('id')}; potential customer, not confirmed buyer"
    return [lead_id, name, industry, str(item.get("area") or profile["geographic_targets"]["area"]), str(item.get("address") or item.get("locality") or ""), website, phone, email, "https://overturemaps.org/", "Overture Maps Places", category, score, reason, priority, today, today, "NOT REVIEWED", "NOT CONTACTED", notes]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--raw", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    profile = json.loads(Path(args.profile).read_text())
    raw = json.loads(Path(args.raw).read_text())
    today = datetime.now(timezone.utc).date().isoformat()
    by_id, seen_domain, seen_phone, seen_name = {}, set(), set(), set()
    for item in raw:
        row = qualify_overture(item, profile, today) if item.get("category") else qualify(item, profile, today)
        if row is None:
            continue
        key, site, phone, name = row[0], domain(row[5]), normalized(row[6]), normalized(row[1])
        if key in by_id or (site and site in seen_domain) or (phone and phone in seen_phone) or (name and name in seen_name):
            continue
        by_id[key] = row
        if site:
            seen_domain.add(site)
        if phone:
            seen_phone.add(phone)
        if name:
            seen_name.add(name)
    rows = sorted(by_id.values(), key=lambda r: (-r[11], r[1].casefold()))
    Path(args.output).write_text(json.dumps({"headers": HEADERS, "all": rows, "qualified": [r for r in rows if r[11] >= 40], "reviewed": [], "collected": len(raw)}, ensure_ascii=False, indent=2))
    print("collected", len(raw), "retained", len(rows), "high", sum(r[11] >= 70 for r in rows), "medium", sum(40 <= r[11] < 70 for r in rows))



if __name__ == "__main__":
    main()
