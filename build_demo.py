"""Build the selected 16-place aggregate-only public list.

Only the explicit five-field snapshot is loaded. No private workspace,
original files, transaction rows, fake detail rows or network requests.
"""
import argparse
import csv
import html
import json
import re
from pathlib import Path
from export_list import render_page

ROOT = Path(__file__).resolve().parent
FIELDS = {'id', 'name', 'address', 'region', 'record_count'}
SOURCES = (
 ('전남광주통합특별시 공개자료', 'https://www.jeonnam-gwangju.go.kr/boardView.do?pageId=jngj50&boardId=JG_0000000018&seq=14&movePage=1&recordCnt=300'),
 ('광산구 공개자료', 'https://www.gwangsan.go.kr/getInfoOpenData.do?sn=292&detailSn=1541&infoOpen=D'),
 ('서구 공개자료', 'https://www.seogu.gwangju.kr/openInfoCostList.es?mid=a10518030200&oi_seq=109'),
 ('영암군 공개자료', 'https://www.yeongam.go.kr/home/www/openinfo/workcost/workcost_01/workcost_01_03/show/9jqvo718wq812q6sz7rx?page=1&search=&keyword='),
 ('장흥군 공개자료', 'https://www.jangheung.go.kr/www/open_data/bid_budget/business_expense?idx=372565&page=3&mode=view'),
)


def replace_once(page, before, after):
    if page.count(before) != 1:
        raise ValueError('Renderer contract changed; review public transformation')
    return page.replace(before, after, 1)


def render_demo(rows=None):
    if rows is None:
        with (ROOT / 'examples/public-restaurants.csv').open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
    for row in rows:
        if set(row) != FIELDS or row['region'] == '담양군':
            raise ValueError('Only the selected five-field, non-held snapshot is allowed')
        if row['name'].startswith('[비식별]') or '비공개' in row['address']:
            raise ValueError('This public list requires the selected actual metadata')
    if len(rows) != 16 or sum(int(r['record_count']) for r in rows) != 217:
        raise ValueError('Review required for a different public snapshot')
    page = render_page(rows)  # No actual or synthetic detail rows.
    scope = '현재 공개 목록: 광주 5개 구 · 영암군 · 장흥군 / 16곳 · 217건.'
    page, changed = re.subn(r'현재[^<]+시험판입니다\.', scope, page, count=1)
    if changed != 1:
        raise ValueError('Scope notice contract changed')
    replacements = (
      ('비공개 연구용 MVP', '공개 식당 목록 데모'),
      ('재이용 조건 확인 전 · 로컬 연구용 · 외부 배포 금지', '수업 시연용 · 원문·세부 지출정보 미제공'),
      ('상세 이용기록은 아직 준비 중입니다.', '세부 지출정보는 이 공개 화면에 포함하지 않았습니다.'),
      ("'상세자료 준비 중'", "'집계 이용기록 ' + item.record_count + '건 · 세부정보 비공개'"),
      ('공개 지출내역이며 실제 방문을 보증하지 않습니다. 기관명은 확인된 범위만 표시하며, 출처 부서는 실제 참석 부서와 다를 수 있습니다.', '이 화면은 자체 집계 수치만 표시합니다. 원문·지출일·기관·부서·목적 등 세부 지출정보를 포함하지 않으며, 실제 방문을 보증하지 않습니다.'),
    )
    for before, after in replacements:
        page = replace_once(page, before, after)
    notice = '<aside class="public-scope"><strong>공개 식당 목록 데모 · 16곳 · 217건</strong><br>전체 로컬 연구 결과 17곳 · 229건 중 담양 관련 1곳 · 12건은 공개 보류했습니다.<br>실제 상호·주소·자체 집계 수치만 표시합니다. 원문·세부 지출정보 미제공.<br><small>기관별 재이용 조건 확인 중이며, 이 데모가 원기관의 재공개 허락을 증명하지는 않습니다.</small></aside>'
    source_links = ''.join('<li><a target="_blank" rel="noopener noreferrer" href="' + html.escape(url, quote=True) + '">' + html.escape(label) + '</a></li>' for label, url in SOURCES)
    credits = '<details class="source-note"><summary>자료 출처와 이용 안내</summary><p>2026년 공개 업무추진비 자료를 참고한 자체 집계입니다. 아래 링크는 대표 원문 게시물이며, 전체 자료의 완전성·현재 영업·사업장 동일성을 인증하지 않습니다. 원문 파일과 거래 행은 재배포하지 않습니다. 원기관의 공식 추천이나 승인을 의미하지 않습니다.</p><ul>' + source_links + '</ul><p>소스 코드의 MIT 라이선스는 외부 원문·자료의 이용권을 부여하지 않습니다. 비상업적 수업 시연용입니다.</p></details>'
    style = '<style>.public-scope,.source-note{width:min(100% - 36px,1040px);margin:18px auto;padding:16px 20px;border:1px solid #d9cda5;background:#fff9e8;font-size:14px;line-height:1.7;color:#4e452c}.public-scope small{font-size:12px}.source-note{background:#fffef9}.source-note summary{cursor:pointer;font-weight:700}.source-note a{overflow-wrap:anywhere}</style>'
    return replace_once(replace_once(replace_once(page, '<body>', '<body>' + notice), '</head>', style + '</head>'), '</body>', credits + '</body>')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/index.html')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_demo(), encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'use': 'selected_aggregate_only_public_demo', 'places': 16, 'records': 217}))
