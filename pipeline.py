"""Real public expense pilot. No fabricated transaction or geolocation values."""
from __future__ import annotations
import csv, datetime as dt, hashlib, io, json, re, time, zipfile
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
import requests

ROOT=Path(__file__).resolve().parent
START='2026-01-01'; END='2026-09-30'
BASE='https://www.jeonnam-gwangju.go.kr/'
BOARD=BASE+'boardList.do?boardId=JG_0000000018&pageId=jngj50&movePage=1&recordCnt=300'


def parse_date(value, default_year=None):
    if isinstance(value,(dt.date,dt.datetime)): return value.strftime('%Y-%m-%d')
    packed=re.fullmatch(r'(2026)(\d{2})(\d{2})(?:\.0)?',str(value).strip())
    if packed:
        try:return dt.date(int(packed[1]),int(packed[2]),int(packed[3])).isoformat()
        except ValueError:return None
    m=re.search(r'(?<!\d)(2026|26)\s*[.년/\-]\s*(\d{1,2})\s*[.월/\-]\s*(\d{1,2})',str(value))
    if not m:
        if default_year is None: return None
        short=re.fullmatch(r'\s*(\d{1,2})\s*[.월/\-]\s*(\d{1,2})\s*[.일]?\s*',str(value))
        if not short:return None
        try:return dt.date(default_year,int(short[1]),int(short[2])).isoformat()
        except ValueError:return None
    try: return dt.date(2026,int(m[2]),int(m[3])).isoformat()
    except ValueError: return None


def source_department(meta):
    for text in [meta['filename'],meta['title']]:
        for name in reversed(re.findall(r'\(([^()]*)\)',text)):
            if not re.search(r'\d|분기|사용|집행|기관|시책',name) and re.search(r'과|국|단|서|본부|청|소|관|실|부',name):
                return name.strip()
    return meta['publisher'].strip()


def header_map(row):
    compact=[re.sub(r'\s+','',c) for c in row]
    found={}
    for key,pattern in [('date',r'사용일|집행일|일시|일자|사용월일'),('merchant',r'사용장소|집행장소|가맹점|^장소$|사용처'),('purpose',r'목적|적요|집행내역|사용내역|내역'),('amount',r'금액'),('department',r'부서명|^부서$|^사용자$')]:
        match=[i for i,c in enumerate(compact) if re.search(pattern,c)]
        if match:found[key]=match[0]
    return found if 'date' in found and 'merchant' in found else {}


def in_window(date): return bool(date and START<=date<=END)


def classify(merchant,purpose):
    m=re.sub(r'\s+','',str(merchant)); s=str(purpose)
    if not m or m in ('-','없음','해당없음'): return 'missing_merchant'
    if re.search(r'[,，、/;]|외\s*\d+\s*곳|외\s*\d+\s*개',m): return 'ambiguous_merchants'
    if re.search(r'물품|구입|구매|경조|부의|축의|화환|격려금|상품권|차류|다과|음료',s): return 'non_meal'
    if re.search(r'카페|커피|커피숍|마트|편의점|백화점|쿠팡|배달의민족|요기요|스타벅스|맥도날드|버거킹|KFC|투썸|메가엠지씨|메가커피|이디야|빽다방|도미노|피자헛|서브웨이',m,re.I): return 'non_meal'
    if re.search(r'식사|식비|급식|오찬|만찬|중식|석식|조식|식대',s): return 'meal_candidate'
    if re.search(r'간담|협의|격려',s): return 'review_purpose'
    return 'review_purpose'


def transaction_key(row):
    # Different genuine same-day events with same fields remain ambiguous; keep this limitation in README.
    fields=['department','date','time','merchant','amount','purpose']
    return hashlib.sha256(json.dumps([str(row.get(k,'')).strip() for k in fields],ensure_ascii=False).encode()).hexdigest()


def to_feature(row):
    lon=float(row['longitude']);lat=float(row['latitude'])
    if not row.get('place_verified') or not row.get('geo_source') or not row.get('address'):
        raise ValueError('verified address/coordinates and source required')
    if not (125.0<=lon<=128.5 and 33.0<=lat<=36.6): raise ValueError('coordinates outside pilot region or reversed')
    return {'type':'Feature','geometry':{'type':'Point','coordinates':[lon,lat]},'properties':{k:row[k] for k in ['id','name','address','region']}}


def prepare_entry(place,transactions):
    if not place.get('place_verified') or place.get('ambiguous') or not place.get('is_restaurant'):return None
    names={re.sub(r'\s+','',v) for v in [place['name']]+place.get('merchant_aliases',[])}
    evidence=[x for x in transactions if re.sub(r'\s+','',x['merchant']) in names and in_window(x['date']) and x['classification'] in ('meal_candidate','review_purpose') and x.get('purpose') and x.get('amount',0) and x['amount']>0]
    aliases={'광주전략추진단':'전략추진단','경자청':'경제자유구역청'}
    depts={aliases.get(x['department'],x['department']) for x in evidence if x.get('department')}
    if len(depts)<3 or not any(x['date']>='2026-04-01' for x in evidence):return None
    result=dict(place,id=hashlib.sha256((place['name']+'|'+place['address']).encode()).hexdigest()[:12],department_count=len(depts),evidence_count=len(evidence),departments=sorted(depts),latest_record=max(x['date'] for x in evidence),evidence=evidence)
    to_feature(result)
    return result


def parse_posts(html,base):
    soup=BeautifulSoup(html,'html.parser');result={}
    for a in soup.select('a[href*="boardView.do"]'):
        url=urljoin(base,a['href']);sid=parse_qs(urlparse(url).query).get('seq',[''])[0]
        tr=a.find_parent('tr');cells=[c.get_text(' ',strip=True) for c in tr.find_all('td')] if tr else []
        result[sid]={'source_id':sid,'title':a.get_text(' ',strip=True),'url':url,'published':next((c for c in cells if re.fullmatch(r'20\d\d-\d\d-\d\d',c)),''),'publisher':cells[2] if len(cells)>2 else ''}
    return list(result.values())


def fetch(url):
    r=requests.get(url,timeout=60,headers={'User-Agent':'Mozilla/5.0 (local public-record research pilot)'})
    r.raise_for_status();return r


def collect(limit=48):
    raw=ROOT/'raw';raw.mkdir(exist_ok=True)
    r=fetch(BOARD);(raw/'board.html').write_bytes(r.content)
    posts=parse_posts(r.text,BASE)
    (ROOT/'source_registry.json').write_text(json.dumps(posts,ensure_ascii=False,indent=2))
    # Fixed deterministic pilot: Q2/Q3 summaries first, then individual Jan-Sep months.
    eligible=[p for p in posts if not re.search(r'10월|11월|12월',p['title']) and re.search(r'2026|26년|26\.',p['title'])]
    eligible.sort(key=lambda p:(0 if re.search(r'3분기|3/4|7[~～\-]9|7월~9|7월 ~ 9',p['title']) else 1 if '분기' in p['title'] else 2,int(p['source_id'])))
    manifest=[]
    for p in eligible:
        if len(manifest)>=limit: break
        try:
            detail=fetch(p['url']);(raw/f"post_{p['source_id']}.html").write_bytes(detail.content)
            soup=BeautifulSoup(detail.text,'html.parser')
            files=soup.select('a[href*="fileDownload.do"]')
            for a in files:
                name=a.get_text(' ',strip=True);ext=Path(name).suffix.lower()
                if ext not in ('.xls','.xlsx','.hwpx'): continue
                url=urljoin(BASE,a['href']);fid=parse_qs(urlparse(url).query).get('fileSn',['1'])[0]
                path=raw/f"{p['source_id']}_{fid}{ext}"
                data=path.read_bytes() if path.exists() else fetch(url).content
                if (ext in ('.xlsx','.hwpx') and not zipfile.is_zipfile(io.BytesIO(data))) or (ext=='.xls' and not data.startswith(bytes.fromhex('d0cf11e0a1b11ae1'))):
                    raise ValueError('unexpected file signature')
                path.write_bytes(data)
                manifest.append(dict(p,filename=name,download_url=url,local_path=str(path.relative_to(ROOT)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),license_images=[i.get('alt','') for i in soup.select('img') if re.search('누리|저작|KOGL',i.get('alt',''),re.I)],reuse_status='not_cleared_private_research_only'))
                (ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
            time.sleep(.12)
        except Exception as e:
            with (ROOT/'collection_errors.jsonl').open('a') as f:f.write(json.dumps(dict(p,error=str(e)),ensure_ascii=False)+'\n')
    print(json.dumps({'board_posts':len(posts),'eligible':len(eligible),'downloaded':len(manifest),'file_bytes':sum(f['bytes'] for f in manifest)},ensure_ascii=False))


def read_tables(path):
    ext=path.suffix.lower()
    if ext=='.xls':
        import xlrd
        book=xlrd.open_workbook(path)
        for sh in book.sheets():
            rows=[]
            for i in range(sh.nrows):
                vals=[]
                for cell in sh.row(i):
                    vals.append(xlrd.xldate_as_datetime(cell.value,book.datemode).isoformat(' ') if cell.ctype==xlrd.XL_CELL_DATE else str(cell.value) if cell.value is not None else '')
                rows.append(vals)
            yield sh.name,rows
    elif ext=='.xlsx':
        import openpyxl
        book=openpyxl.load_workbook(path,data_only=True,read_only=True)
        for sh in book:
            yield sh.title,[[str(v) if v is not None else '' for v in row] for row in sh.iter_rows(values_only=True)]
    elif ext=='.hwpx':
        import xml.etree.ElementTree as ET
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n.startswith('Contents/section') and n.endswith('.xml'):
                    root=ET.fromstring(z.read(n));rows=[]
                    for tr in root.iter():
                        if tr.tag.endswith('}tr'):
                            rows.append([' '.join(e.text for e in tc.iter() if e.tag.endswith('}t') and e.text) for tc in tr if tc.tag.endswith('}tc')])
                    yield n,rows


def amount_value(value):
    t=re.sub(r'[^0-9.\-]','',str(value))
    try:return int(float(t))
    except ValueError:return None


def extract():
    manifest=json.loads((ROOT/'manifest.json').read_text());allrows=[];sheets=[];errors=[]
    for m in manifest:
        path=ROOT/m['local_path']
        try:
            for sheet,rows in read_tables(path):
                sheets.append({'source_id':m['source_id'],'sheet':sheet,'rows':rows})
                mapping={}
                for rn,row in enumerate(rows,1):
                    new_mapping=header_map(row)
                    if new_mapping:
                        mapping=new_mapping
                        continue
                    if not mapping:continue
                    val=lambda key:row[mapping[key]].strip() if key in mapping and mapping[key]<len(row) else ''
                    date=parse_date(val('date'),default_year=2026 if re.search(r'2026|26년',m['title']) else None)
                    if not date:continue
                    spender=val('department')
                    department=source_department(m)
                    tm=re.search(r'(\d{1,2}:\d{2})',val('date'))
                    if not tm:
                        tm=next((match for c in row for match in [re.search(r'(\d{1,2}:\d{2})',c)] if match),None)
                    x={'source_id':m['source_id'],'source_url':m['url'],'file':m['local_path'],'sheet':sheet,'row':rn,'department':department,'spender_role':spender,'date':date,'time':tm[1] if tm else '', 'merchant':val('merchant'),'purpose':val('purpose'),'amount':amount_value(val('amount'))}
                    x['classification']=classify(x['merchant'],x['purpose']) if in_window(date) else 'out_of_window'
                    x['transaction_key']=transaction_key(x);allrows.append(x)
        except Exception as e:errors.append({'source_id':m['source_id'],'error':str(e)})
    (ROOT/'parsed_tables.json').write_text(json.dumps(sheets,ensure_ascii=False,indent=2))
    (ROOT/'transactions.json').write_text(json.dumps(allrows,ensure_ascii=False,indent=2))
    (ROOT/'parse_errors.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2))
    unique={};dupes=[]
    for x in allrows:
        if x['transaction_key'] in unique:dupes.append(x)
        else:unique[x['transaction_key']]=x
    (ROOT/'transactions_unique.json').write_text(json.dumps(list(unique.values()),ensure_ascii=False,indent=2))
    (ROOT/'duplicates.json').write_text(json.dumps(dupes,ensure_ascii=False,indent=2))
    from collections import Counter
    print(json.dumps({'rows':len(allrows),'unique':len(unique),'duplicates':len(dupes),'classification':dict(Counter(x['classification'] for x in unique.values())),'parse_errors':errors},ensure_ascii=False))
    groups={}
    for x in unique.values():
        if x['classification'] not in ('meal_candidate','review_purpose'):continue
        name=re.sub(r'\s+','',x['merchant']).strip('()（）')
        z=groups.setdefault(name,{'name':x['merchant'],'departments':set(),'visits':0,'explicit_meals':0,'sources':set(),'latest':'','purposes':set()})
        z['departments'].add(x['department']);z['visits']+=1;z['explicit_meals']+=x['classification']=='meal_candidate';z['sources'].add(x['source_id']);z['latest']=max(z['latest'],x['date']);z['purposes'].add(x['purpose'])
    candidate=[dict(z,departments=sorted(z['departments']),sources=sorted(z['sources']),purposes=sorted(z['purposes']),department_count=len(z['departments'])) for z in groups.values()]
    candidate.sort(key=lambda x:(-x['department_count'],-x['visits'],x['name']))
    (ROOT/'candidate_groups.json').write_text(json.dumps(candidate,ensure_ascii=False,indent=2))
    print(json.dumps(candidate[:25],ensure_ascii=False,indent=2))


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['collect','extract']);ap.add_argument('--limit',type=int,default=48);args=ap.parse_args()
    collect(args.limit) if args.action=='collect' else extract()
