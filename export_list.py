"""Build a private, standalone restaurant list from locally vetted CSV rows.

No downloads, geocoding or coordinate requirements. External evidence and
selection stay in the existing private pipeline; this module only presents it.
"""
import argparse
import csv
import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parent
REGION_GROUPS = (
    ('광주권', ('동구', '서구', '남구', '북구', '광산구')),
    ('전남권', ('목포시', '여수시', '순천시', '나주시', '광양시', '담양군',
               '곡성군', '구례군', '고흥군', '보성군', '화순군', '장흥군',
               '강진군', '해남군', '영암군', '무안군', '함평군', '영광군',
               '장성군', '완도군', '진도군', '신안군')),
)


def naver_url(address):
    """Search only the clicked address; never append the business name."""
    return 'https://map.naver.com/p/search/' + quote(address, safe='')


def default_input(root=ROOT):
    """Keep the reviewed list separate from the historical four-point map."""
    reviewed = root/'output'/'list_ready.csv'
    return reviewed if reviewed.is_file() else root/'output'/'map_ready.csv'


def public_text(value):
    """Defense in depth after manual review; not a general PII detector."""
    text = str(value or '').strip()
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[연락처 비공개]', text)
    text = re.sub(r'(?<!\d)0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)', '[연락처 비공개]', text)
    text = re.sub(r'(?<!\d)\d{6}[-\s]?[1-8]\d{6}(?!\d)', '[개인정보 비공개]', text)
    text = re.sub(r'((?:담당자|성명)\s*[:：]\s*)[가-힣]{2,4}', r'\1[이름 비공개]', text)
    return text


def render_page(rows, record_details=None):
    """Whitelist public-facing fields and escape all source text at boundaries."""
    clean = []
    for row in rows:
        record = {key: str(row.get(key, '')).strip()
                  for key in ('id', 'name', 'address', 'region')}
        if not all(record.values()):
            raise ValueError('Each restaurant needs an id, name, address and region')
        raw_count = row.get('record_count')
        if raw_count is None or (isinstance(raw_count, str) and not raw_count.strip()):
            record['record_count'] = None
        elif (not isinstance(raw_count, bool) and isinstance(raw_count, (str, int))
              and str(raw_count).strip().isdecimal()):
            record['record_count'] = int(raw_count)
        else:
            raise ValueError('record_count must be a nonnegative integer or unknown')
        clean.append(record)
    if len({r['id'] for r in clean}) != len(clean):
        raise ValueError('Duplicate restaurant ids must be reviewed before display')
    clean.sort(key=lambda r: (r['record_count'] is None,
                             -(r['record_count'] or 0), r['name'].casefold(), r['id']))
    detail_input = record_details if record_details is not None else {}
    if not isinstance(detail_input, dict) or set(detail_input) - {r['id'] for r in clean}:
        raise ValueError('Record details must be keyed only by listed restaurant ids')
    details = {}
    for restaurant in clean:
        incoming = detail_input.get(restaurant['id'], [])
        if not isinstance(incoming, list):
            raise ValueError('Each detail group must be a list')
        if (restaurant['id'] in detail_input and restaurant['record_count'] is not None
                and len(incoming) != restaurant['record_count']):
            raise ValueError('Record detail count does not match the displayed count')
        safe_records = []
        for raw in incoming:
            source_url = str(raw.get('source_url', '')).strip()
            parsed = urlsplit(source_url)
            if (parsed.scheme not in ('https', 'http') or not parsed.hostname
                    or parsed.username or parsed.password):
                raise ValueError('Only public HTTP(S) source links without credentials are allowed')
            safe_records.append({
                'date': date.fromisoformat(str(raw.get('date', '')).strip()).isoformat(),
                'organization': public_text(raw.get('organization')) or None,
                'department': public_text(raw.get('department')) or '부서 미확인',
                'purpose': public_text(raw.get('purpose')) or '집행목적 미확인',
                'source_url': source_url,
            })
        details[restaurant['id']] = sorted(safe_records, key=lambda r: r['date'], reverse=True)
    available = {r['region'] for r in clean}
    options = ['<option value="">전체 지역</option>']
    known = set()
    for label, regions in REGION_GROUPS:
        options.append(f'<optgroup label="{html.escape(label)}">')
        for region in regions:
            known.add(region)
            display = ('광주 ' if label == '광주권' else '') + region
            if region not in available:
                display += ' · 준비 중'
            options.append(f'<option value="{html.escape(region, quote=True)}">{html.escape(display)}</option>')
        options.append('</optgroup>')
    for region in sorted(available - known):
        options.append(f'<option value="{html.escape(region, quote=True)}">{html.escape(region)}</option>')
    cards = []
    for row in clean:
        name = html.escape(row['name'])
        address = html.escape(row['address'])
        url = html.escape(naver_url(row['address']), quote=True)
        label = html.escape(f"{row['address']} 네이버지도 검색 (새 탭)", quote=True)
        count = row['record_count']
        rid = html.escape(row['id'], quote=True)
        button_label = html.escape(f"{row['name']} 공개 이용기록 {count}건 보기", quote=True)
        badge = ('<div class="record-count"><span>기록 수 확인 중</span></div>' if count is None
                 else f'<button class="record-count" type="button" data-restaurant-id="{rid}" '
                      f'aria-haspopup="dialog" aria-controls="record-dialog" aria-label="{button_label}">'
                      f'<span>이용기록</span><strong>{count}<small>건</small></strong></button>')
        cards.append(f'<li class="restaurant"><div class="restaurant-main"><h3>{name}</h3>'
                     f'<a class="address" href="{url}" target="_blank" rel="noopener noreferrer" '
                     f'referrerpolicy="no-referrer" aria-label="{label}"><span>{address}</span>'
                     '<span class="arrow" aria-hidden="true">↗</span></a></div>'
                     + badge + '</li>')
    # JSON inside a script element must not contain a literal closing script tag.
    data = (json.dumps(clean, ensure_ascii=False)
            .replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e'))
    detail_data = (json.dumps(details, ensure_ascii=False)
                   .replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e'))
    if clean:
        region_label = ' · '.join(('광주 ' + r if r in REGION_GROUPS[0][1] else r)
                                for r in sorted(available))
        scope = f'현재 {region_label}의 식당 {len(clean)}곳을 확인한 시험판입니다.'
    else:
        scope = '현재 확인이 끝난 식당 목록은 준비 중입니다.'
    return (TEMPLATE.replace('__SCOPE_NOTE__', html.escape(scope))
            .replace('__OPTIONS__', ''.join(options))
            .replace('__CARDS__', ''.join(cards))
            .replace('__COUNT__', str(len(clean)))
            .replace('__EMPTY_HIDDEN__', ' hidden' if clean else '')
            .replace('__DETAIL_DATA__', detail_data)
            .replace('__DATA__', data))


TEMPLATE = '''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>기록으로 찾는 식당 · 목록형 MVP</title>
<style>
:root{color-scheme:light;--ink:#152d35;--muted:#5a6968;--paper:#f6f4ec;--line:#dadfd4;--green:#1d5c46;--accent:#e8edb1}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:system-ui,-apple-system,"Malgun Gothic",sans-serif;line-height:1.65}a{color:inherit}button,select{font:inherit}[hidden]{display:none!important}a:focus-visible,select:focus-visible{outline:3px solid #8b6b12;outline-offset:5px}
.shell{width:min(100% - 64px,1040px);margin:auto}.topbar{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:25px 0;border-bottom:1px solid var(--line)}.brand{font-weight:800;letter-spacing:-.6px;display:flex;align-items:center;gap:10px}.brand-mark{width:28px;height:28px;display:inline-grid;place-items:center;border:1px solid var(--green);border-radius:50%;color:var(--green);font-size:16px}.badge{font-size:12px;padding:4px 10px;border:1px solid var(--line);border-radius:30px;color:var(--muted);white-space:nowrap}
.hero{padding:54px 0 34px}.eyebrow{font-size:12px;font-weight:750;letter-spacing:2px;color:var(--green);margin:0 0 16px}.hero h1{font-size:clamp(30px,4.1vw,46px);line-height:1.3;letter-spacing:-1.8px;margin:0 0 19px;font-weight:780}.hero h1 span{color:var(--green)}.intro{font-size:15px;color:var(--muted);margin:0;max-width:670px;word-break:keep-all}.intro strong{color:var(--ink);font-weight:650}
.toolbar{display:flex;align-items:center;justify-content:space-between;gap:24px;background:#e9eddf;border:1px solid #d6ddcb;padding:20px 24px;border-radius:14px}.filter{display:flex;align-items:center;gap:16px;flex-shrink:0}.filter label{font-size:14px;font-weight:700}.select-wrap{position:relative}select{min-width:208px;max-width:100%;color:var(--ink);background:#fffdf7;border:1px solid #b7c4b2;border-radius:7px;padding:10px 12px;cursor:pointer;font-size:14px}.toolbar-note{margin:0;color:var(--muted);font-size:13px;word-break:keep-all}
.results{padding:30px 0 0}.results-heading{display:flex;align-items:center;gap:12px;margin-bottom:13px}.results-heading h2{font-size:19px;letter-spacing:-.5px;margin:0}.count{font-size:12px;font-weight:650;color:var(--green);background:#e4eadb;padding:3px 9px;border-radius:30px}.column-head{display:flex;justify-content:space-between;padding:11px 24px;color:var(--muted);font-size:12px;border-bottom:1px solid var(--line)}.restaurant-list{margin:0;padding:0;list-style:none}.restaurant{display:flex;justify-content:space-between;align-items:center;gap:24px;padding:24px;background:#fffef9;border-bottom:1px solid var(--line)}.restaurant:first-child{border-radius:10px 10px 0 0}.restaurant:last-child{border-radius:0 0 10px 10px}.restaurant-main{min-width:0}.restaurant h3{font-size:19px;margin:0 0 7px;font-weight:730;letter-spacing:-.5px;overflow-wrap:anywhere}.address{display:inline-flex;align-items:baseline;gap:8px;color:var(--green);font-size:14px;text-decoration-thickness:1px;text-underline-offset:4px;overflow-wrap:anywhere}.address:hover{color:#0a3d27;text-decoration-thickness:2px}.arrow{font-size:16px;flex-shrink:0}.naver-hint{color:var(--muted);font-size:12px;white-space:nowrap}.empty{text-align:center;background:#fffef9;padding:52px 22px;border:1px dashed #c6cebf;border-radius:10px}.empty h3{font-size:20px;margin:0 0 8px}.empty p{font-size:14px;color:var(--muted);margin:0;word-break:keep-all}
.notice{display:flex;gap:13px;padding:19px 0 27px;color:var(--muted);font-size:12px;word-break:keep-all}.notice strong{color:var(--ink);font-weight:650}.notice p{margin:0}.dot{color:var(--green);font-size:16px;line-height:1.4}.footer{border-top:1px solid var(--line);padding:19px 0 30px;display:flex;justify-content:space-between;gap:15px;color:var(--muted);font-size:11px}.noscript{padding:12px;font-size:13px;color:var(--muted)}
@media(max-width:620px){.shell{width:calc(100% - 36px)}.topbar{padding:18px 0}.brand{font-size:14px}.badge{font-size:10px;padding:4px 8px}.hero{padding:34px 0 25px}.hero h1{letter-spacing:-1px}.intro{font-size:14px}.toolbar{padding:18px;display:block}.filter{display:block}.filter label{display:block;margin-bottom:8px}.select-wrap,select{width:100%}.toolbar-note{margin-top:12px;font-size:12px}.results{padding-top:24px}.column-head{padding:10px 16px}.column-head span:last-child{display:none}.restaurant{padding:20px 16px;gap:0}.restaurant h3{font-size:18px}.address{font-size:13px}.naver-hint{display:none}.notice{padding-top:17px}.footer{display:block}.footer span{display:block;margin-bottom:5px}}
@media(prefers-reduced-motion:no-preference){.address{transition:color .15s ease}}
.record-count{flex-shrink:0;min-width:88px;display:flex;flex-direction:column;align-items:flex-end;padding:9px 13px;background:#edf1e5;border-radius:9px;color:var(--green);font-variant-numeric:tabular-nums}.record-count span{font-size:11px}.record-count strong{font-size:25px;line-height:1.3;font-weight:750}.record-count small{font-size:12px;font-weight:500;margin-left:4px}.sort-note{margin-left:auto;font-size:12px;color:var(--muted)}
@media(max-width:620px){.restaurant{gap:12px}.record-count{min-width:72px;padding:8px}.record-count strong{font-size:21px}.sort-note{font-size:11px}}
button.record-count{font-family:inherit;border:1px solid transparent;cursor:pointer;text-align:right}button.record-count:hover{background:#e0e9d2;border-color:#b4c9a4}button:focus-visible{outline:3px solid #8b6b12;outline-offset:4px}
.record-dialog{width:min(960px,calc(100% - 40px));max-height:84vh;max-height:84dvh;padding:0;border:1px solid #c4cdbb;border-radius:16px;background:#fffef9;color:var(--ink);box-shadow:0 20px 80px #10291f33}.record-dialog[open]{display:flex;flex-direction:column}.record-dialog::backdrop{background:#142c2bc2}.dialog-header{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;padding:24px 26px 14px}.dialog-header h2{margin:0;font-size:23px;line-height:1.35;letter-spacing:-.6px;overflow-wrap:anywhere}.dialog-header p{margin:7px 0 0;color:var(--green);font-size:13px}.dialog-header form{margin:0}.dialog-close{border:1px solid #cbd3c1;border-radius:7px;padding:8px 12px;background:#f3f5eb;color:var(--ink);cursor:pointer;white-space:nowrap;font-size:13px}.record-description{margin:0;padding:0 26px 18px;font-size:12px;line-height:1.65;color:var(--muted);border-bottom:1px solid var(--line);word-break:keep-all}.record-body{overflow-y:auto;overscroll-behavior:contain;min-height:0;padding:0 26px 20px}.record-head,.record-entry{display:grid;grid-template-columns:94px 180px minmax(0,1fr) 76px;gap:16px;align-items:start}.record-head{position:sticky;top:0;background:#fffef9;padding:13px 0;border-bottom:1px solid var(--line);font-size:11px;color:var(--muted)}.record-list{margin:0;padding:0;list-style:none}.record-entry{padding:17px 0;border-bottom:1px solid var(--line);font-size:13px;line-height:1.6;overflow-wrap:anywhere}.record-entry time{font-variant-numeric:tabular-nums;color:var(--muted)}.source-unit strong,.source-unit span{display:block}.source-unit strong{font-size:12px;font-weight:650}.source-unit span{color:var(--muted);font-size:12px;margin-top:3px}.record-purpose{margin:0;white-space:pre-wrap}.record-source{font-size:12px;color:var(--green);text-underline-offset:4px}.record-empty{text-align:center;padding:36px 12px;color:var(--muted);font-size:14px}
@media(max-width:620px){.record-dialog{width:calc(100% - 24px);max-height:90vh;max-height:90dvh;border-radius:12px}.dialog-header{padding:19px 18px 12px}.dialog-header h2{font-size:20px}.record-description{padding:0 18px 14px}.record-body{padding:0 18px 18px}.record-head{display:none}.record-entry{display:block;padding:18px 0}.source-unit{margin:7px 0}.record-purpose{margin:8px 0 10px}.record-source{display:inline-block}}
</style>
</head>
<body>
<div class="shell">
<header class="topbar"><div class="brand"><span class="brand-mark" aria-hidden="true">밥</span>기록으로 찾는 식당</div><span class="badge">비공개 연구용 MVP</span></header>
<main>
<section class="hero" aria-labelledby="page-title"><p class="eyebrow">LOCAL FOOD · PUBLIC RECORDS</p><h1>동네의 한 끼,<br><span>선택의 기록</span>에서 찾아보세요.</h1><p class="intro">공개된 업무추진비 이용기록을 바탕으로 식당 후보를 모았습니다.<br><strong>지역을 고르고, 주소를 누르면 네이버지도로 연결됩니다.</strong></p></section>
<section class="toolbar" aria-label="지역 선택"><div class="filter"><label for="region">어디에서 드시나요?</label><div class="select-wrap"><select id="region">__OPTIONS__</select></div></div><p class="toolbar-note">__SCOPE_NOTE__<br>다른 지역은 자료를 확인한 뒤 추가합니다.</p></section>
<section class="results" aria-labelledby="region-title"><div class="results-heading"><h2 id="region-title">전체 지역</h2><span class="count" id="result-count" role="status" aria-live="polite">__COUNT__곳</span><span class="sort-note">이용기록 많은 순</span></div><div class="column-head" id="column-head"><span>식당 · 주소</span><span>주소를 클릭하면 새 탭으로 열립니다</span></div><ul class="restaurant-list" id="restaurant-list">__CARDS__</ul><div class="empty" id="empty"__EMPTY_HIDDEN__><h3>이 지역의 식당 목록은 준비 중입니다.</h3><p>자료가 아직 없거나 확인 중인 지역입니다. 식당이 없다는 뜻은 아닙니다.</p></div></section>
<noscript><p class="noscript">지역 선택과 이용기록 팝업에는 자바스크립트가 필요합니다. 전체 식당 목록과 주소 링크는 그대로 이용할 수 있습니다.</p></noscript>
<aside class="notice" aria-label="자료 안내"><span class="dot" aria-hidden="true">ⓘ</span><p><strong>횟수는 수집한 공개 이용기록 기준이며, 실제 방문횟수와 다를 수 있습니다.</strong><br>방문 전 네이버지도에서 상호·지점과 영업 여부를 확인해 주세요. 주소를 누르면 해당 주소만 검색합니다.</p></aside>
</main>
<footer class="footer"><span>일부 공개자료 기반 · 분기 갱신 목표</span><span>재이용 조건 확인 전 · 로컬 연구용 · 외부 배포 금지</span></footer>
</div>
<dialog class="record-dialog" id="record-dialog" aria-labelledby="record-title" aria-describedby="record-description">
<header class="dialog-header"><div><h2 id="record-title">공개 이용기록</h2><p id="record-meta"></p></div><form method="dialog"><button class="dialog-close" type="submit" autofocus aria-label="이용기록 팝업 닫기">닫기 ×</button></form></header>
<p class="record-description" id="record-description">공개 지출내역이며 실제 방문을 보증하지 않습니다. 기관명은 확인된 범위만 표시하며, 출처 부서는 실제 참석 부서와 다를 수 있습니다.</p>
<div class="record-body"><div class="record-head" id="record-head" aria-hidden="true"><span>사용일</span><span>출처 기관·부서</span><span>집행목적</span><span>출처</span></div><ol class="record-list" id="record-list"></ol><p class="record-empty" id="record-empty" hidden>상세 이용기록은 아직 준비 중입니다.</p></div>
</dialog>
<script type="application/json" id="restaurants">__DATA__</script>
<script type="application/json" id="record-details">__DETAIL_DATA__</script>
<script>
'use strict';
const restaurants = JSON.parse(document.getElementById('restaurants').textContent);
const region = document.getElementById('region');
const list = document.getElementById('restaurant-list');
const recordDetails = JSON.parse(document.getElementById('record-details').textContent);
const recordDialog = document.getElementById('record-dialog');
let lastRecordTrigger = null;
let previousBodyOverflow = '';
function openRecords(item, trigger) {
  const records = recordDetails[item.id] || [];
  lastRecordTrigger = trigger;
  document.getElementById('record-title').textContent = item.name + ' 이용기록';
  document.getElementById('record-meta').textContent = records.length ? '공개 이용기록 ' + records.length + '건 · 최신순' : '상세자료 준비 중';
  const recordList = document.getElementById('record-list');
  recordList.replaceChildren();
  for (const record of records) {
    const entry = document.createElement('li'); entry.className = 'record-entry';
    const when = document.createElement('time'); when.dateTime = record.date; when.textContent = record.date.replaceAll('-', '.');
    const source = document.createElement('div'); source.className = 'source-unit';
    const agency = document.createElement('strong'); agency.textContent = record.organization || '기관명 미확인'; source.append(agency);
    if (record.department !== record.organization) {
      const department = document.createElement('span'); department.textContent = record.department; source.append(department);
    }
    const purpose = document.createElement('p'); purpose.className = 'record-purpose'; purpose.textContent = record.purpose;
    const link = document.createElement('a'); link.className = 'record-source'; link.href = record.source_url; link.textContent = '원문 보기 ↗';
    link.target = '_blank'; link.rel = 'noopener noreferrer'; link.referrerPolicy = 'no-referrer';
    link.setAttribute('aria-label', record.date + ' ' + record.department + ' 원문 게시물 보기 (새 탭)');
    entry.append(when, source, purpose, link); recordList.append(entry);
  }
  document.getElementById('record-empty').hidden = records.length > 0;
  document.getElementById('record-head').hidden = records.length === 0;
  document.querySelector('.record-body').scrollTop = 0;
  previousBodyOverflow = document.body.style.overflow;
  document.body.style.overflow = 'hidden';
  recordDialog.showModal();
}
recordDialog.addEventListener('close', () => {
  document.body.style.overflow = previousBodyOverflow;
  if (lastRecordTrigger && lastRecordTrigger.isConnected) lastRecordTrigger.focus({preventScroll:true});
});
recordDialog.addEventListener('click', event => {
  if (event.target !== recordDialog) return;
  const rect = recordDialog.getBoundingClientRect();
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) recordDialog.close();
});
list.addEventListener('click', event => {
  const trigger = event.target.closest('button.record-count');
  if (!trigger) return;
  const item = restaurants.find(restaurant => restaurant.id === trigger.dataset.restaurantId);
  if (item) openRecords(item, trigger);
});
function showRegion() {
  const selected = region.value;
  const visible = restaurants.filter(item => !selected || item.region === selected);
  document.getElementById('region-title').textContent = selected ? region.selectedOptions[0].textContent.replace(' · 준비 중', '') : '전체 지역';
  document.getElementById('result-count').textContent = visible.length ? `${visible.length}곳` : '준비 중';
  list.replaceChildren();
  for (const item of visible) {
    const li = document.createElement('li'); li.className = 'restaurant';
    const main = document.createElement('div'); main.className = 'restaurant-main';
    const title = document.createElement('h3'); title.textContent = item.name;
    const address = document.createElement('a'); address.className = 'address';
    address.href = 'https://map.naver.com/p/search/' + encodeURIComponent(item.address);
    address.target = '_blank'; address.rel = 'noopener noreferrer'; address.referrerPolicy = 'no-referrer';
    address.setAttribute('aria-label', item.address + ' 네이버지도 검색 (새 탭)');
    const text = document.createElement('span'); text.textContent = item.address;
    const arrow = document.createElement('span'); arrow.className = 'arrow'; arrow.textContent = '↗'; arrow.setAttribute('aria-hidden', 'true');
    address.append(text, arrow); main.append(title, address);
    const badge = document.createElement(item.record_count === null ? 'div' : 'button'); badge.className = 'record-count';
    const label = document.createElement('span');
    if (item.record_count === null) {
      label.textContent = '기록 수 확인 중'; badge.append(label);
    } else {
      label.textContent = '이용기록';
      const value = document.createElement('strong'); value.textContent = String(item.record_count);
      const unit = document.createElement('small'); unit.textContent = '건';
      value.append(unit); badge.append(label, value);
      badge.type = 'button'; badge.dataset.restaurantId = item.id;
      badge.setAttribute('aria-label', item.name + ' 공개 이용기록 ' + item.record_count + '건 보기');
      badge.setAttribute('aria-haspopup', 'dialog'); badge.setAttribute('aria-controls', 'record-dialog');
    }
    li.append(main, badge); list.append(li);
  }
  document.getElementById('empty').hidden = visible.length > 0;
  document.getElementById('column-head').hidden = visible.length === 0;
}
region.addEventListener('change', showRegion);
showRegion();
</script>
</body>
</html>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=default_input())
    parser.add_argument('--output', type=Path, default=ROOT/'output'/'restaurant_list.html')
    parser.add_argument('--records', type=Path, help='Manually reviewed popup records; no raw audit input')
    args = parser.parse_args()
    with args.input.open(encoding='utf-8-sig', newline='') as source:
        rows = list(csv.DictReader(source))
    records_path = args.records
    if records_path is None and args.input.resolve() == default_input().resolve():
        candidate = ROOT/'output'/'list_records.private.json'
        if candidate.is_file():
            records_path = candidate
    record_details = json.loads(records_path.read_text(encoding='utf-8')) if records_path else None
    page = render_page(rows, record_details=record_details)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding='utf-8')
    print(json.dumps({'output': str(args.output.resolve()), 'restaurants': len(rows),
                      'regions': sorted({r['region'] for r in rows}),
                      'use': 'local_private_research_only'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
