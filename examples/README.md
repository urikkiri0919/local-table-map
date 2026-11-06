# 실행 예제 구분

## 현재 공개 비식별 데모

- demo-restaurants.csv:17행, 8지역, 기록 합계229. 지역/건수 구조는 현재 로컬 결과와 일치한다.
- demo-records.json:229개 시연용 대체 상세. 상호/상세주소/날짜/기관/부서/목적/원문은 실제 자료가 아니다. 2000년 날짜와 example.com은 의도적인 대체 값이다.
- python3 build_demo.py 로 docs/index.html을 생성한다. 지도·원문 링크는 공개본에서 차단한다.
- 이를 실제 사업장 조회나 실제229개 지출의 공개본으로 해석하지 않는다.

## 과거 소규모 합성 예제

synthetic-restaurants.csv와 synthetic-records.json은 가상3식당/6기록이다. export_list.py의 --input/--records로 실행한다. 현재 결과의 규모와 혼동하지 않는다.

두 예제 모두 실자료 수집이나 영수증 사업장 동일성 인증을 대신하지 않는다. 원본과 실제 거래 상세는 저장소에 포함하지 않는다.
