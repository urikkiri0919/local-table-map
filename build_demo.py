"""Build the public, explicitly redacted UI demo using only reviewed examples.

No network, private workspace, originals or actual transaction text is loaded.
"""
import argparse
import csv
import json
import re
from pathlib import Path
from export_list import render_page

ROOT = Path(__file__).resolve().parent


def render_demo():
    with (ROOT / 'examples/demo-restaurants.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    details = json.loads((ROOT / 'examples/demo-records.json').read_text())
    for r in rows:
        if not r['name'].startswith('[비식별]') or '비공개' not in r['address']:
            raise ValueError('Only redacted demonstration identities are allowed')
    for arr in details.values():
        for r in arr:
            if r['date'] != '2000-01-01' or r['source_url'] != 'https://example.com/' or '시연용' not in r['purpose']:
                raise ValueError('Do not publish actual transaction details')
    page = render_page(rows, details)
    count = len(rows)
    records = sum(int(r['record_count']) for r in rows)
    scope = f'현재 구현 범위: 광주 5개 구 · 영암군 · 담양군 · 장흥군 / {count}곳 · {records}건.'
    page = re.sub(r'현재[^<]+시험판입니다\.', scope, page, count=1)
    page = page.replace('비공개 연구용 MVP', '공개 비식별 데모')
    page = page.replace('지역을 고르고, 주소를 누르면 네이버지도로 연결됩니다.', '지역을 고르고, 이용기록 수를 누르면 시연 기록을 확인합니다.')
    page = page.replace('재이용 조건 확인 전 · 로컬 연구용 · 외부 배포 금지', '세부 내용은 시연용 대체 · 실제 원문 미포함')
    page = page.replace('주소를 클릭하면 새 탭으로 열립니다', '공개 데모의 상세주소·외부 연결은 비공개')
    notice = '<div class="redaction-notice">공개 비식별 데모 · 지역/건수 구조만 실제 결과 반영. 상호·상세주소·날짜·기관/부서·목적은 시연용 대체. 지도·원문 링크는 공개본에서 비활성화.</div>'
    style = '<style>.redaction-notice{margin:18px auto 0;max-width:1040px;padding:14px 18px;border:1px solid #c4cdbb;font:14px/1.6 system-ui;background:#fffef9;color:#183b36}.record-entry time{font-size:0}.record-entry time:after{content:"날짜 비공개";font-size:14px}.address[aria-disabled=true],.record-source[aria-disabled=true]{cursor:default;text-decoration:none}</style>'
    script = """<script>(()=>{function mask(){document.querySelectorAll('a.address,a.record-source').forEach(a=>{a.href='#';a.removeAttribute('target');a.setAttribute('aria-disabled','true');a.title='공개 데모에서는 실제 주소·원문을 공개하지 않습니다.';if(a.classList.contains('record-source'))a.textContent='원문 링크 비공개'})}document.addEventListener('click',e=>{if(e.target.closest('a.address,a.record-source'))e.preventDefault()},true);new MutationObserver(mask).observe(document.querySelector('#restaurant-list'),{childList:true});new MutationObserver(mask).observe(document.querySelector('#record-list'),{childList:true});mask()})();</script>"""
    return page.replace('<body>', '<body>' + notice, 1).replace('</head>', style + '</head>').replace('</body>', script + '</body>')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/index.html')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_demo(), encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'use': 'public_redacted_demonstration'}))
