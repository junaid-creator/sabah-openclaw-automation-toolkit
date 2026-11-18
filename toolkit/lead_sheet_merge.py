"""Source-derived lead merge preserving review/contact/history fields."""
from urllib.parse import urlparse
import re

def merged(headers, existing, incoming):
    if len(headers)!=19: raise ValueError("Expected 19-column lead schema")
    ids=[str(r[0]) for r in existing[1:] if r and r[0]]
    if len(ids)!=len(existing[1:]) or len(set(ids))!=len(ids): raise ValueError("Blank or duplicated existing lead IDs")
    if any(len(r)>19 or not r or not r[0] for r in incoming): raise ValueError("Invalid incoming lead row")
    if existing and existing[0] != headers:
        raise RuntimeError("Existing Sheet columns differ from the lead schema")
    result = {str(row[0]): list(row) + [""] * max(0, len(headers) - len(row)) for row in existing[1:] if row and row[0]}
    def identity(row):
        website = str(row[5] or "").strip()
        host = (urlparse(website).hostname or "").lower().removeprefix("www.")
        phone = re.sub(r"\D", "", str(row[6] or ""))
        name = re.sub(r"[^a-z0-9]", "", str(row[1] or "").casefold())
        return host, phone, name
    by_host, by_phone, by_name = {}, {}, {}
    for key, row in result.items():
        host, phone, name = identity(row)
        if host: by_host.setdefault(host, key)
        if phone: by_phone.setdefault(phone, key)
        if name: by_name.setdefault(name, key)
    for row in incoming:
        row = list(row) + [""] * max(0, len(headers) - len(row))
        incoming_id = str(row[0])
        host, phone, name = identity(row)
        key = str(row[0])
        key = (key if key in result else
               by_host.get(host) if host and host in by_host else
               by_phone.get(phone) if phone and phone in by_phone else
               by_name.get(name) if name and name in by_name else key)
        if key in result:
            old = result[key]
            row[0] = old[0]
            for col in (5, 6, 7, 8, 9, 10, 12):
                row[col] = row[col] or old[col]
            row[14] = old[14] or row[14]
            row[16] = old[16] or row[16]
            row[17] = old[17] or row[17]
            if old[18]:
                row[18] = old[18]
            if incoming_id != str(key):
                source_note = f"Additional source ID: {incoming_id}"
                if source_note not in row[18]:
                    row[18] = f"{row[18]}; {source_note}" if row[18] else source_note
        if key.startswith("overture:"):
            feature = key.removeprefix("overture:")
            source_note = f"Overture feature ID: {feature}"
            if source_note not in row[18]:
                row[18] = f"{row[18]}; {source_note}" if row[18] else source_note
        result[key] = row
        host, phone, name = identity(row)
        if host: by_host.setdefault(host, key)
        if phone: by_phone.setdefault(phone, key)
        if name: by_name.setdefault(name, key)
    return [headers, *result.values()]
