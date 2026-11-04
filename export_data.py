"""Export only genuine source-backed rows and a private local map preview."""
import collections, csv, hashlib, html, json, re
from pathlib import Path
from pipeline import ROOT, START, END, in_window, prepare_entry, to_feature

OUT=ROOT/'output'

def save_json(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def save_csv(name,rows,fields):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
        for row in rows:
            w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items() if k in fields})

def main():
    OUT.mkdir(exist_ok=True)
    manifest=json.loads((ROOT/'manifest.json').read_text())
    rows=json.loads((ROOT/'transactions_unique.json').read_text())
    places=json.loads((ROOT/'places_verified.json').read_text()) if (ROOT/'places_verified.json').exists() else []
    chosen=[];place_review=[]
    for place in places:
        try:entry=prepare_entry(place,rows)
        except (KeyError,ValueError,TypeError) as e:entry=None;place=dict(place,error=str(e))
        if entry:chosen.append(entry)
        else:place_review.append(place)
    assert len({x['id'] for x in chosen})==len(chosen)
    features=[to_feature(x) for x in chosen]
    save_json('map_ready.geojson',{'type':'FeatureCollection','features':features})
    save_csv('map_ready.csv',chosen,['id','name','address','longitude','latitude','region'])
    save_json('selection_audit.private.json',chosen)
    save_json('place_review.private.json',place_review)
    save_csv('normalized_transactions.private.csv',rows,['source_id','source_url','file','sheet','row','department','date','time','merchant','purpose','amount','classification','transaction_key'])
    linked={r['transaction_key'] for x in chosen for r in x['evidence']}
    review=[];excluded=[]
    for row in rows:
        if row['classification'] in ('non_meal','missing_merchant','out_of_window'):excluded.append(dict(row,review_reason=row['classification']))
        elif row['transaction_key'] not in linked:review.append(dict(row,review_reason='ambiguous_merchants' if row['classification']=='ambiguous_merchants' else 'location_or_selection_not_verified'))
    fields=['source_id','source_url','file','sheet','row','department','date','time','merchant','purpose','amount','classification','review_reason']
    save_csv('review_queue.private.csv',review,fields);save_csv('excluded.private.csv',excluded,fields)
    filecoverage=[]
    for m in manifest:
        observed=[r for r in rows if r['file']==m['local_path']]
        filecoverage.append({'source_id':m['source_id'],'filename':m['filename'],'department_source':m['publisher'],'source_url':m['url'],'download_url':m['download_url'],'sha256':m['sha256'],'parsed_rows':len(observed),'observed_months':','.join(sorted({r['date'][:7] for r in observed if in_window(r['date'])})),'status':'some_rows_parsed_not_complete_coverage' if observed else 'no_rows_parsed_review_required','reuse_status':'unresolved_private_research_only'})
    save_csv('source_coverage.csv',filecoverage,list(filecoverage[0]))
    summary={'source_board':'https://www.jeonnam-gwangju.go.kr/boardList.do?boardId=JG_0000000018&pageId=jngj50','window_start':START,'window_end':END,'latest_activity_start':'2026-04-01','scope':'deterministic pilot of parseable attachments from integrated government board; not all departments/municipalities/police/fire','files':len(manifest),'posts':len({m['source_id'] for m in manifest}),'normalized_rows':len(rows),'in_window_rows':sum(in_window(x['date']) for x in rows),'classification':dict(collections.Counter(x['classification'] for x in rows)),'map_ready_places':len(chosen),'place_review_count':len(place_review),'review_rows':len(review),'excluded_rows':len(excluded),'selected_evidence_rows':len(linked),'sources_without_parsed_rows':sum(not x['parsed_rows'] for x in filecoverage),'complete_coverage':False,'reuse_cleared':False,'use':'local_private_research_only','caveats':['Expense merchant names lack addresses; location matches require identity/branch review.','Payment records do not establish taste, actual in-person visits, price value, or present business operation.','Quarterly source availability is partial; zero/missing publication not inferred.','Canonical source department groups are conservative collection units, not a fully verified historic organization chart.','No-name coffee shop/chain list is illustrative, not exhaustive.']}
    assert len(rows)==len(linked)+len(review)+len(excluded)
    save_json('summary.json',summary)
    # User-facing properties contain only restaurant identity and location, never institutions or counts.
    payload=json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False).replace('</','<\\/')
    body='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>공개기록 식당 지도 · 비공개 연구용</title><link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"><style>body{margin:0;font-family:system-ui,sans-serif;color:#09223f;background:#f3eee2}header{padding:18px 24px;border-bottom:1px solid #c7c7bd}h1{font-size:23px;margin:0 0 8px}p{margin:0;font-size:13px;line-height:1.5}main{display:grid;grid-template-columns:330px 1fr;height:calc(100vh - 130px);min-height:480px}aside{overflow:auto;padding:12px}#map{height:100%;min-height:480px}button.place{display:block;width:100%;text-align:left;padding:14px;background:#faf7ee;border:1px solid #d7d0c1;margin-bottom:9px;cursor:pointer}button b{display:block;margin-bottom:7px}button span{font-size:13px}#fallback{display:none;padding:30px}#fallback.visible{display:block}@media(max-width:700px){main{grid-template-columns:1fr;grid-template-rows:220px 480px;height:auto}}</style></head><body><header><h1>광고 말고, 기록으로 찾는 식당</h1><p>2026년 1–9월 공개자료 일부를 가공한 비공개 연구용 지도입니다. 전체 기관 조사·맛 보증·재이용 허락 완료를 뜻하지 않습니다.</p></header><main><aside id="list"></aside><div><div id="map"></div><div id="fallback">지도 라이브러리를 불러오지 못했습니다. 왼쪽 목록의 주소와 map_ready.geojson을 확인하세요.</div></div></main><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><script>const data=PAYLOAD;window.dataset=data;const list=document.querySelector('#list');const markers=[];let map;if(window.L){map=L.map('map').setView([35.15,126.85],12);L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors',maxZoom:19}).addTo(map)}else{document.querySelector('#fallback').className='visible'}for(const f of data.features){const p=f.properties;const button=document.createElement('button');button.className='place';const title=document.createElement('b');title.textContent=p.name;const address=document.createElement('span');address.textContent=p.address;button.append(title,address);list.append(button);if(map){const popup=document.createElement('div');const n=title.cloneNode(true),a=address.cloneNode(true);popup.append(n,document.createElement('br'),a);const marker=L.marker([f.geometry.coordinates[1],f.geometry.coordinates[0]]).addTo(map).bindPopup(popup);markers.push(marker);button.onclick=()=>{map.setView(marker.getLatLng(),16);marker.openPopup()}}}if(map&&markers.length)map.fitBounds(L.featureGroup(markers).getBounds().pad(.15));window.map=map;window.markers=markers;</script></body></html>'''.replace('PAYLOAD',payload)
    (OUT/'map_preview.html').write_text(body,encoding='utf-8')
    readme=f'''# 업무추진비 지도용 데이터 — 비공개 연구 파일럿

실제 공개 원본 {summary['files']}개(게시물 {summary['posts']}건)를 내려받아 가공했다. 정규화 행 {summary['normalized_rows']}건 중 사용일이 2026-01-01~2026-09-30인 행은 {summary['in_window_rows']}건이다. 현재 위치 증거·기초 선정 조건을 통과한 식당은 {summary['map_ready_places']}곳이다.

## 사용 파일
- map_preview.html: 브라우저에서 여는 로컬 지도. 사용자 화면은 상호·주소만 표시한다. 지도 바탕과 라이브러리는 인터넷 연결이 필요하다.
- map_ready.geojson: GeoJSON Point, 좌표 순서는 [경도, 위도]. 속성은 id/name/address/region뿐이다.
- map_ready.csv: UTF-8 BOM CSV. id/name/address/longitude/latitude/region.
- selection_audit.private.json: 내부 증거. 원문 URL, 원본 파일, 시트·행, 위치 검증 출처, 집계 근거.
- normalized_transactions.private.csv / review_queue.private.csv / excluded.private.csv: 정규화 결과·보류·제외 로그. 외부 공개 금지.
- source_coverage.csv: 다운로드 원본 해시, 일부 관측 월, 파싱 상태. 월이 관측됐다는 사실이 월 전체 완전 수집을 뜻하지 않는다.
- summary.json: 실제 실행에서 계산한 범위·건수·제한.

## 범위와 선정
- 본청 통합 게시판에서 3분기 우선, 그다음 1·2분기, 게시물 번호 오름차순으로 고른 파싱 가능 첨부 {summary['files']}개의 파일럿이다. 지자체 전체·경찰·소방의 완전한 수집 결과가 아니다.
- 수집 목표 기간은 2026-01-01~09-30. 게시일 아닌 사용일로 판정한다. 초기 최근 활동 창은 04-01~09-30.
- 기관·부서는 직함이 아니라 원본 파일/게시물의 공개 주체로 보수적으로 구분했다. 같은 원본에서 여러 직함이 등장해도 단순히 별개 부서로 세지 않는다. 조직개편에 따른 역사적 부서 동일성은 추가 검증 대상이다.
- 지도 후보는 출처가 있는 주소·경위도, 음식점 여부·지점 확인, 모호하지 않은 상호 매칭, 최소 3개 원본 부서 단위, 최근 활동 기록을 요구한다.
- 거래 원문은 종종 상호만 제공하므로 위치 정보 확인은 원문 자체의 주소 확인과 다르다. 거래-지점 연결이 불분명한 경우 보류해야 한다. 원문 표기는 보존하고 업체명·부서 별칭 정리는 감사 파일에 명시한다.
- 음식점에서 간담회비를 썼다는 기록은 맛/가성비나 실제 대면 방문의 보증이 아니다. 현재 영업 여부·폐업 누락·광고성 여부의 완전 검증도 아니다.
- 분기별 자료 수가 다르고 확인하지 못한 부서·PDF/HWP 원본이 남아 있으므로 결과를 지역 전체 인기순위로 해석하지 않는다.

## 데이터 품질과 보류
- 본문이 자동 추출되지 않은 원본은 {summary['sources_without_parsed_rows']}개다. 사용내역 없음이 아니라 검토 필요 상태다.
- 후보 검토 행 {summary['review_rows']}건, 제외 행 {summary['excluded_rows']}건. 위치 미검증, 다중 상호, 불명확한 사용목적 등은 임의로 채우지 않았다.
- 원본 엑셀 일부는 시트 정의 관련 openpyxl 경고가 있다. 원본은 수정하지 않았다.
- 원본은 ../raw/, 다운로드 출처·SHA256은 ../manifest.json, 원본 표 추출 결과는 ../parsed_tables.json에 있다.

## 이용 조건 — 중요
공개 다운로드 가능 여부와 재이용 허락은 별개다. 본청 저작권정책은 공공누리가 부착되지 않은 자료의 이용에 사전 협의를 안내한다. 현재 자료별 허락은 확인되지 않았으므로 본 결과는 개인 로컬 연구·내부 검증용이다. 상업용 서비스, 클래스룸 또는 외부 웹에 원본/가공자료를 게시하지 않았다. 공개 서비스로 전환하기 전 지출자료와 위치 출처 각각의 이용조건을 확인해야 한다.
정책: https://www.jeonnam-gwangju.go.kr/contentsView.do?pageId=jngj139

## 재실행
작업 폴더 /home/urikkiri/mvp-research/expense-pilot 에서 실행한다.
.venv/bin/python -m unittest -v
.venv/bin/python pipeline.py extract
.venv/bin/python export_data.py
위치 검증 입력은 작업 폴더의 places_verified.json이다.
좌표와 근거가 없는 항목을 채워 넣지 않는다. 테스트의 synthetic fixture는 실제 결과 데이터와 분리돼 있다.
'''
    (OUT/'README.md').write_text(readme,encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
