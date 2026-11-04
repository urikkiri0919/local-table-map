"""Private normalization and approval boundary; no network or publication."""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'expense-pilot'))
from pipeline import classify

START = '2026-01-01'
END = '2026-09-30'
RECENT = '2026-04-01'
OFFICIAL_HOSTS = {'www.jeonnam-gwangju.go.kr', 'www.seogu.gwangju.kr', 'www.gwangsan.go.kr'}


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def merge_transactions(batches: dict[str, list[dict]]) -> dict:
    """Merge verified inputs, retaining semantic duplicate provenance/uncertainty.

    Equal financial fields are a duplicate candidate, not proof of one visit.
    Known participant-count conflicts are held rather than counted. A source
    bucket namespaces departments; it is not an inferred historical agency name.
    """
    grouped = defaultdict(list)
    excluded = []
    for bucket, records in batches.items():
        for original in records:
            row = dict(original, source_bucket=bucket)
            try:
                date = dt.date.fromisoformat(str(row['date'])).isoformat()
            except (KeyError, TypeError, ValueError):
                excluded.append(dict(record=row, reason='invalid_date'))
                continue
            if not START <= date <= END:
                excluded.append(dict(record=row, reason='out_of_window'))
                continue
            amount = row.get('amount')
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0 or int(amount) != amount:
                excluded.append(dict(record=row, reason='invalid_or_nonpositive_amount'))
                continue
            department = str(row.get('department') or '').strip()
            unit = ''.join(department.split())
            if bucket == 'regional':
                unit = {'광주전략추진단': '전략추진단', '경자청': '경제자유구역청'}.get(unit, unit)
            if not unit or re.search(r'(?:구청장|부구청장|국장|과장|동장|소장)$', unit):
                unit = None
            row.update(date=date, amount=int(amount), department=department,
                       department_key=f'{bucket}|{unit}' if unit else None)
            row['classification'] = classify(row.get('merchant', ''), row.get('purpose', ''))
            fields = [bucket, row['department_key'] or ['unknown', row.get('source_id'), department],
                      date, str(row.get('time') or '').strip(), str(row.get('merchant') or '').strip(),
                      int(amount), str(row.get('purpose') or '').strip()]
            row['record_key'] = _digest(fields)
            grouped[row['record_key']].append(row)
    kept = []
    conflicts = []
    duplicate_rows = 0
    for key, records in sorted(grouped.items()):
        participant_counts = {str(r['attendees']).strip() for r in records if r.get('attendees') is not None}
        if len(participant_counts) > 1:
            conflicts.append(dict(record_key=key, reason='conflicting_participant_counts', records=records))
            continue
        representative = dict(records[0])
        representative['provenance'] = [{k: r.get(k) for k in
                                        ['source_bucket', 'source_id', 'source_url', 'file',
                                         'file_sha256', 'sheet', 'row', 'transaction_key']}
                                       for r in records]
        representative['semantic_duplicate_candidate'] = len(records) > 1
        kept.append(representative)
        duplicate_rows += len(records) - 1
    result = dict(rows=kept, excluded=excluded, conflicts=conflicts,
                  duplicate_rows=duplicate_rows, input_rows=sum(map(len, batches.values())))
    assert result['input_rows'] == len(kept) + len(excluded) + duplicate_rows + sum(len(g['records']) for g in conflicts)
    return result


def group_candidates(rows: list[dict]) -> list[dict]:
    """Unverified name groups; callers must still verify places and popup text."""
    groups = defaultdict(list)
    for row in rows:
        if row['classification'] in ('meal_candidate', 'review_purpose') and row.get('purpose'):
            groups[''.join(str(row['merchant']).split())].append(row)
    result = []
    for name, records in groups.items():
        units = sorted({r['department_key'] for r in records if r['department_key']})
        latest = max(r['date'] for r in records)
        if len(units) < 3 or latest < RECENT:
            continue
        result.append(dict(merchant_key=name, names=sorted({r['merchant'] for r in records}),
                           department_units=units, department_count=len(units),
                           record_count=len({r['record_key'] for r in records}), latest=latest,
                           records=records))
    return sorted(result, key=lambda g: (-g['department_count'], -g['record_count'], g['merchant_key']))


def validate_bundle(csv_bytes: bytes, details: dict, review: dict,
                    allowed_urls: set[str], record_keys_by_id: dict[str, list[str]]) -> None:
    """Require the exact reviewed staged bundle, never just matching row totals.

    This enforces provenance/content bindings, not comprehensive PII detection.
    The builder must independently verify original hashes and review free text.
    """
    reader = csv.DictReader(io.StringIO(csv_bytes.decode('utf-8-sig')))
    if reader.fieldnames != ['id', 'name', 'address', 'region', 'record_count']:
        raise ValueError('Unexpected list fields')
    rows = list(reader)
    ids = [r['id'] for r in rows]
    if len(set(ids)) != len(ids) or set(ids) != set(details) or set(ids) != set(record_keys_by_id):
        raise ValueError('Every list group must have exactly one complete detail/record group')
    for row in rows:
        rid = row['id']
        if not row['record_count'].isdigit():
            raise ValueError('Invalid record count')
        count = int(row['record_count'])
        if count != len(details[rid]) or count != len(set(record_keys_by_id[rid])) or count != len(record_keys_by_id[rid]):
            raise ValueError('Record count does not match unique records and details')
        for detail in details[rid]:
            if set(detail) != {'date', 'organization', 'department', 'purpose', 'source_url'}:
                raise ValueError('Unexpected detail fields')
            url = detail['source_url']
            parsed = urlsplit(url)
            if (parsed.scheme != 'https' or parsed.hostname not in OFFICIAL_HOSTS or
                    parsed.username or parsed.password or parsed.port not in (None, 443) or url not in allowed_urls):
                raise ValueError('Source URL is not an approved official manifest URL')
    if record_keys_by_id != review.get('record_keys_by_id'):
        raise ValueError('Record selection changed after manual review')
    if hashlib.sha256(csv_bytes).hexdigest() != review.get('csv_sha256') or _digest(details) != review.get('details_sha256'):
        raise ValueError('Content hash changed after manual review')


def prepare_bundle(places: list[dict], rows: list[dict], organization_by_file: dict,
                   organization_by_bucket: dict) -> tuple[bytes, dict, list]:
    """Prepare only vetted exact-name places; approval is a separate gate."""
    from export_list import public_text
    list_rows, details, audit = [], {}, []
    claimed = set()
    for place in places:
        if not place.get('is_restaurant') or place.get('ambiguous') or not place.get('address'):
            raise ValueError('Unverified or ambiguous restaurant/address')
        names = set(place['merchant_keys'])
        records = [r for r in rows if ''.join(r['merchant'].split()) in names
                   and r['classification'] in ('meal_candidate', 'review_purpose')
                   and r.get('purpose') and START <= r['date'] <= END]
        records = sorted(records, key=lambda r: (r['date'], r['record_key']), reverse=True)
        keys = [r['record_key'] for r in records]
        if len(keys) != len(set(keys)) or claimed.intersection(keys):
            raise ValueError('Ambiguous overlap between restaurant selections')
        units = sorted({r['department_key'] for r in records if r['department_key']})
        if len(units) < 3 or not any(r['date'] >= RECENT for r in records):
            raise ValueError('Restaurant lacks department diversity or recent evidence')
        claimed.update(keys)
        rid = hashlib.sha256((place['name'] + '|' + place['address']).encode()).hexdigest()[:12]
        if place.get('id') and place['id'] != rid:
            raise ValueError('Restaurant id does not match reviewed name/address')
        list_rows.append(dict(id=rid, name=place['name'], address=place['address'],
                              region=place['region'], record_count=len(keys)))
        details[rid] = []
        for record in records:
            organization = organization_by_file.get(record['file']) or organization_by_bucket.get(record['source_bucket'])
            details[rid].append(dict(date=record['date'],
                                     organization=public_text(organization) if organization else None,
                                     department=public_text(record['department']),
                                     purpose=public_text(record['purpose']),
                                     source_url=record['source_url']))
        audit.append(dict(id=rid, name=place['name'], address=place['address'], region=place['region'],
                          record_count=len(keys), record_keys=sorted(keys), department_count=len(units),
                          department_units=units, latest_record=max(r['date'] for r in records),
                          source_rows=[{k: r.get(k) for k in ['record_key', 'source_bucket', 'source_id',
                                       'source_url', 'file', 'file_sha256', 'sheet', 'row', 'department', 'date']}
                                       for r in records]))
    list_rows.sort(key=lambda r: (-r['record_count'], r['name'].casefold(), r['id']))
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=['id', 'name', 'address', 'region', 'record_count'])
    writer.writeheader()
    writer.writerows(list_rows)
    return buffer.getvalue().encode('utf-8-sig'), details, audit
