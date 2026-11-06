"""Local-only reviewed export contract; gates remain active under python -O."""
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlsplit

OFFICIAL_HOSTS = frozenset({
    'www.jeonnam-gwangju.go.kr', 'www.seogu.gwangju.kr', 'www.gwangsan.go.kr',
    'www.yeongam.go.kr', 'www.damyang.go.kr', 'www.jangheung.go.kr',
})

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()

def validate_staged(csv_bytes, details, keys, review, allowed_urls):
    reader = csv.DictReader(io.StringIO(csv_bytes.decode('utf-8-sig')))
    if reader.fieldnames != ['id', 'name', 'address', 'region', 'record_count']:
        raise ValueError('Unexpected list fields')
    rows = list(reader)
    ids = [r['id'] for r in rows]
    if not rows or len(ids) != len(set(ids)) or set(ids) != set(details) or set(ids) != set(keys):
        raise ValueError('Every list group needs matching detail and key groups')
    all_keys = []
    for row in rows:
        rid = row['id']
        if not row['record_count'].isdigit() or int(row['record_count']) <= 0:
            raise ValueError('Invalid record count')
        count = int(row['record_count'])
        if count != len(details[rid]) or count != len(keys[rid]) or count != len(set(keys[rid])):
            raise ValueError('Count does not match unique selection')
        if any(not row[k].strip() for k in ['id', 'name', 'address', 'region']):
            raise ValueError('Missing list identity')
        all_keys.extend(keys[rid])
        dates = []
        for record in details[rid]:
            if set(record) != {'date', 'organization', 'department', 'purpose', 'source_url'}:
                raise ValueError('Unexpected detail fields')
            try:
                day = dt.date.fromisoformat(record['date']).isoformat()
            except (TypeError, ValueError):
                raise ValueError('Invalid date') from None
            if day != record['date'] or not '2026-01-01' <= day <= '2026-09-30':
                raise ValueError('Date outside reviewed period')
            dates.append(day)
            if not isinstance(record['purpose'], str) or not record['purpose'].strip():
                raise ValueError('Missing reviewed purpose')
            url = record['source_url']
            u = urlsplit(url)
            if (u.scheme != 'https' or u.hostname not in OFFICIAL_HOSTS or u.username or u.password
                    or u.port not in (None, 443) or url not in allowed_urls):
                raise ValueError('Not an exact approved official manifest URL')
        if dates != sorted(dates, reverse=True):
            raise ValueError('Details must be latest first')
    if len(all_keys) != len(set(all_keys)):
        raise ValueError('Selection overlaps across places')
    if keys != review.get('record_keys_by_id'):
        raise ValueError('Selected record keys changed')
    if hashlib.sha256(csv_bytes).hexdigest() != review.get('csv_sha256') or digest(details) != review.get('details_sha256'):
        raise ValueError('Reviewed content changed')

def validate_inputs(inputs):
    if not inputs or len({x['path'] for x in inputs}) != len(inputs):
        raise ValueError('Missing or duplicate input snapshot')
    for item in inputs:
        path = Path(item['path'])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Input changed since review: ' + str(path))
