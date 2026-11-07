# 기록으로 찾는 지역 식당 목록

공공기관 업무추진비 공개기록을 식당 선택의 단서로 정리하는 목록형 MVP다. 출장자와 현지인을 대상으로 한다. 기록 수는 실제 방문 인증·지역 전체 인기순위·맛 평가가 아니다.

## 바로 실행

- 공개 식당 목록 데모: https://urikkiri0919.github.io/local-table-map/
- 구현결과 발표자료: https://urikkiri0919.github.io/local-table-map/presentation.html
- 소스: https://github.com/urikkiri0919/local-table-map

현재 공개 목록은 **16곳·217건, 7개 소재 지역**이다. 실제 상호·주소와 자체 집계 수치만 표시하고, 주소를 누르면 주소-only 네이버지도 검색이 새 탭으로 열린다. 기록 수 클릭은 집계 안내만 표시하며 **실제 또는 가상의 지출 상세 행은 포함하지 않는다**. 전체 로컬 연구17곳·229건 중 담양 관련1곳·12건을 공개 목록에서 제외했다. 원문·지출일·기관/부서·목적·금액·개인정보는 재배포하지 않는다.

기관별 원문의 재이용 조건은 확인 중이며, 이 데모가 원기관의 재공개 허락을 증명하지 않는다. 비상업적 수업 시연용이다. 제출 HTML과 클래스룸 제출본은 변경하지 않았으므로 발표자료의 캡처·파일 내 시연은 당시의 비식별17곳·229건 스냅샷으로 남아 있다.

## 현재 구현과 연구 범위

- 지역 선택 → 식당명/주소/기록 수 목록 → 기록 수 클릭 시 최신순 상세 팝업.
- 수치 내림차순, 동률 이름/id 정렬. 닫기·Esc·배경 클릭, 초점/배경 스크롤 복원, 모바일 내부 스크롤.
- 실제 로컬 부분표본: 광주 5구 12곳/160건 + 영암 3곳/53건 + 담양 1곳/12건 + 장흥 1곳/4건.
- 나머지 전남 22시군 초기 조사에서는 거래행 확보11출처/미확보11출처를 구분했다. 잠정42그룹 중 우선15개 주소 판정(5후보/10보류), 27개 미검토. 미확보는 무지출·식당 없음이 아니다.
- 원문4576행의 예비 정규화4532/중복추가44. 최종 목록에서 누적 공개 중복1행을 추가 보류했다. 거래의 실제 사업장·현재 영업·맛·완전 수집을 인증하지 않는다.
- 사용일 2026-01-01~09-30, 최근 활동04-01 이후, 확인된 독립 출처부서3개 이상이라는 초기 선정 조건을 유지했다. 지출기관 소재지를 식당 주소로 사용하지 않았다.
- 평점·예약·리뷰·결제·실시간 수집·자체 지도는 현 목록 MVP 범위 밖이다. 분기 갱신은 목표이며 자동 갱신은 미구현이다.

## 공개 범위

사용자의 요청으로 코드·자체 문서·기존 발표 스냅샷·과거 비식별 예제와 선정된16곳의 최소 목록을 공개한다. 저장소 공개와 GitHub Pages 데모 공개는 실제 원본/실거래 자료 재배포와 다르다.

제외: 다운로드 원본, 실제 거래 CSV/상세 JSON/실자료 HTML, 기관별 수집 workspace, 주소 근거 캡처, 승인/감사 파일, 자격증명·브라우저 세션. 실제 17곳/229건을 새 clone에서 그대로 복원할 수 있다고 주장하지 않는다. 기존 광주12/160 로컬 결과와 최신17/229 결과는 그대로 보존했다.

## 실행 방법

Python 3.14 / Linux·WSL에서 검증했다. 공개 UI 생성에는 표준 라이브러리와 저장소의 선정 목록만 필요하며 API 키·외부 수집·비공개 거래 자료가 필요 없다.

    git clone https://github.com/urikkiri0919/local-table-map.git
    cd local-table-map
    python3 build_demo.py
    python3 -m http.server 8000 --directory docs

브라우저에서 http://localhost:8000/ 을 연다. docs/index.html을 직접 열어도 UI는 동작한다. 발표자료는 docs/presentation.html이다. CSS·JS·시연 입력은 HTML에 포함되며 발표자료 웹폰트는 CDN을 사용한다.

원래의 소규모 합성 예제도 유지했다.

    python3 export_list.py --input examples/synthetic-restaurants.csv --records examples/synthetic-records.json --output output/demo.html

위 명령은 가상3곳/6건 예제이며 현재 공개16곳/217건 및 로컬 연구17곳/229건과 다르다.

## 전체 테스트

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.lock.txt
    PYTHONOPTIMIZE=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest -v

구현 관련66개와 공개 배포10개, 총76개 테스트를 실행한다. 테스트는 외부 수집을 하지 않는다. 새 export 게이트12개는 -O에서도 확인했으나 기존 도구 일부 assert 제약이 있으므로 전체 파이프라인은 PYTHONOPTIMIZE=0으로 실행한다. 코드 테스트는 실제 사용자 만족도·영업 상태·데이터 재이용권 검증이 아니다.

## 파일별 용도

| 파일 | 실제 용도 |
| --- | --- |
| [README.md](README.md) | 프로젝트 소개·공개 데모·실행 방법·파일 안내. |
| [LICENSE](LICENSE) | 자체 코드·문서·시연 예제의 MIT 라이선스. 외부 원본 자료의 이용권은 아님. |
| [AGENTS.md](AGENTS.md) | AI 작업 규칙. 공개 승인 이전의 보호 경계도 보존한 문서이며 최신 공개 범위는 이 README를 따름. |
| [.gitignore](.gitignore) | 기본 차단 후 검토된 파일만 허용. 원본·실자료·output·비밀정보 제외. |
| [.gitattributes](.gitattributes) | CSV 줄바꿈 LF 통일. |
| [.env.example](.env.example) | 환경 설정 안내. 현재 UI 실행에는 API 키가 필요 없음. |
| [requirements.lock.txt](requirements.lock.txt) | 전체 테스트·추출 코드의 Python 의존성 버전. |
| [export_list.py](export_list.py) | 현재 목록·정렬·주소 검색·기록 팝업의 독립 HTML 생성기. |
| [pipeline.py](pipeline.py) | 기초 수집·표 추출·날짜 정규화·분류. collect는 외부 요청을 실행하므로 주의. |
| [wide_data.py](wide_data.py) | 기관 구분·중복/충돌·선정 조건·검토된 출력 결합. |
| [regional_data.py](regional_data.py) | 출처별 명시 부서 자격·기관 간 동일상호 보류·후보 분석. |
| [regional_export.py](regional_export.py) | 정확한 선택키·출력 해시·공식 URL·원본 해시 검사. 신규 게이트는 명시적 예외 사용. |
| [export_data.py](export_data.py) | 과거 지도 파일럿 생성기. 현 목록 UI와 구분하는 보관용 코드. |
| [build_demo.py](build_demo.py) | 선정된16곳의 기본 목록만 읽어 docs/index.html을 재생성. 집계 안내·담양 제외·재이용 조건 미확정 고지 포함. |
| [test_pipeline.py](test_pipeline.py) | 날짜·헤더·분류·중복키·과거 지도 조건의 합성 테스트. |
| [test_list.py](test_list.py) | 목록·정렬·주소-only·팝업 필드·건수·HTML 안전성 테스트. |
| [test_wide_data.py](test_wide_data.py) | 부서 namespace·중복/충돌·선정·출력 승인 경계 테스트. |
| [test_regional_data.py](test_regional_data.py) | 직함/부모국 배제·부서 근거·출처별 분리 테스트. |
| [test_regional_export.py](test_regional_export.py) | stale·누락·비공식 URL·선택키·내용/원본 변경 거절 테스트. |
| [test_publication.py](test_publication.py) | 공개16/217·담양 제외·최소 필드·상세 행 미포함·제출본 불변·주소 링크·정적 배포 검사. |
| [examples/README.md](examples/README.md) | 현재 실제 목록·이전 비식별 시연·과거 소규모 합성 예제의 차이. |
| [examples/public-restaurants.csv](examples/public-restaurants.csv) | 현재 공개16곳의 id·상호·주소·지역·집계 수치만 담은 선정 목록. 상세 지출 행 없음. |
| [examples/demo-restaurants.csv](examples/demo-restaurants.csv) | 현재 지역/건수 구조를 반영한 비식별 식당 17개. 상호·상세주소는 대체. |
| [examples/demo-records.json](examples/demo-records.json) | 팝업 동작용 대체 229행. 2000년 날짜·기관/부서·목적·example.com은 실제 기록 아님. |
| [examples/synthetic-restaurants.csv](examples/synthetic-restaurants.csv) | 원래의 소규모 합성 식당 3개 예제. |
| [examples/synthetic-records.json](examples/synthetic-records.json) | 위 3개 식당의 합성 기록 6행. |
| [docs/index.html](docs/index.html) | GitHub Pages의 실제16곳·217건 기본 목록. 상세 거래 행 없음. |
| [docs/presentation.html](docs/presentation.html) | 평가표·배점 언급을 제외한 7장 구현결과 발표자료. 공개 데모와 연결. |
| [docs/.nojekyll](docs/.nojekyll) | GitHub Pages에서 정적 HTML을 그대로 제공하도록 설정. |
| [docs/verification.md](docs/verification.md) | 시기별 검증 기록. 가장 위의 최신 공개 준비 결과와 과거 실자료 연구를 구분. |
| [docs/agent-worklog.md](docs/agent-worklog.md) | 주요 요청·사람의 결정/확인·에이전트 작업·실패와 복구 기록. |
| [docs/assessment-checklist.md](docs/assessment-checklist.md) | 초기 제출 준비용 역사적 참고 문서. 제출 발표자료에는 평가표·배점을 넣지 않음. |

## 원본 수집 코드를 읽을 때

pipeline.py collect는 실제 외부 게시판 요청을 발생시킨다. 단순 데모 실행이나 테스트와 별개다. 출처 이용조건·robots·TLS·공개 링크를 확인한 허용 범위에서만 수행한다. 로그인·CAPTCHA·명시적 제한을 우회하지 않는다. 기존 수집 명령만으로 현재 실제17곳/229건이 재현되지 않는다.

## 알려진 제한

- 실제 사용자 3–5명 사용성 검증·현장 방문·현재 영업 검증은 하지 않았다.
- 순천 초기 수집은 응답 최소62개로60상한을 초과했고 미보존2개가 있다. 보존60개 검산을 상한 준수라고 주장하지 않으며 추가 수집은 동결했다. 순천 자료는 신규5곳/69건에 포함되지 않았다.
- 이미지 PDF·접근/정책 제한·불명확 행과 동명이점/지점 공백을 무지출0으로 바꾸지 않는다.
- 현재 공개본은 실제 기본 정보·자체 집계만 제공하며 상세 거래 행은 넣지 않는다. 이전 제출 스냅샷과 비식별 예제는 별도로 보존했다. 이를 완전 익명화나 재이용권 인증으로 해석하지 않는다.
- GitHub 과거 이력에는 이전 단계의 자체 연구 요약이 남아 있으며, 옛 PRIVATE/12곳 문구는 당시 상태다. 최신 공개 범위는 이 문서를 따른다. AGENTS.md는 보호된 기존 지침이라 수정하지 않았다.

## 라이선스

MIT는 자체 코드·자체 문서·명시적 시연 예제에 적용한다. 외부 업무추진비 원본, 지도 서비스, 실제 상호/주소/지출자료의 이용권을 부여하지 않는다. 현재 공개 목록은 외부 원문에 대한 자유이용허락 확인이 완료됐다는 주장이 아니다. 원본과 거래 상세는 공개하지 않으며, 외부 자료에 대한 권리를 MIT로 재부여하지 않는다.
