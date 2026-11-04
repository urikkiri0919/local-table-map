"""Unit fixtures are synthetic; exported restaurant data must use real evidence."""
import unittest
try:
    import pipeline as p
except ModuleNotFoundError:
    p = None

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(p, 'pipeline implementation is missing')

    def test_dates_and_window(self):
        self.assertEqual(p.parse_date('2026. 09. 30. 12:00'), '2026-09-30')
        self.assertEqual(p.parse_date('26.1.2'), '2026-01-02')
        self.assertEqual(p.parse_date('20260701.0'), '2026-07-01')
        self.assertIsNone(p.parse_date('합계'))
        self.assertFalse(p.in_window('2026-10-01'))
        self.assertTrue(p.in_window('2026-01-01'))

    def test_safe_meal_classification(self):
        self.assertEqual(p.classify('식당A', '간담회 식사 제공'), 'meal_candidate')
        self.assertEqual(p.classify('마트A', '격려 물품 구입'), 'non_meal')
        self.assertEqual(p.classify('식당A, 식당B', '간담회 식사'), 'ambiguous_merchants')
        self.assertEqual(p.classify('카페A', '간담회 차류'), 'non_meal')
        self.assertEqual(p.classify('식당A', '직원 격려'), 'review_purpose')

    def test_transaction_dedup_crosspost(self):
        a={'department':'부서A','date':'2026-07-01','merchant':'식당A','amount':10000,'purpose':'식사','time':'12:00'}
        b=dict(a, source_id='crosspost')
        self.assertEqual(p.transaction_key(a),p.transaction_key(b))
        self.assertNotEqual(p.transaction_key(a),p.transaction_key(dict(a,department='부서B')))

    def test_geojson_has_no_private_fields(self):
        r={'id':'r1','name':'식당A','address':'광주광역시 서구 테스트로 1','longitude':126.85,'latitude':35.15,'region':'서구','geo_source':'https://example.org/evidence','department_count':3,'place_verified':True}
        f=p.to_feature(r)
        self.assertEqual(f['geometry']['coordinates'],[126.85,35.15])
        self.assertNotIn('department_count',f['properties'])
        self.assertEqual(set(f['properties']),{'id','name','address','region'})
        with self.assertRaises(ValueError):
            p.to_feature(dict(r,latitude=126.85,longitude=35.15))
        with self.assertRaises(ValueError):
            p.to_feature(dict(r,place_verified=False))

    def test_map_entry_requires_diverse_recent_evidence(self):
        place={'name':'검사식당','address':'광주광역시 서구 검사로 1','longitude':126.85,'latitude':35.15,'region':'서구','geo_source':'https://example.org/place','place_verified':True,'ambiguous':False,'is_restaurant':True}
        rows=[{'merchant':'검사식당','department':d,'date':'2026-06-01','classification':'meal_candidate','purpose':'오찬','amount':10000,'source_url':'https://example.org/source','file':'raw/fixture.xls','sheet':'s','row':i+1} for i,d in enumerate(['부서A','부서B','부서C'])]
        ready=p.prepare_entry(place,rows)
        self.assertEqual(ready['department_count'],3)
        self.assertIsNone(p.prepare_entry(dict(place,ambiguous=True),rows))
        self.assertIsNone(p.prepare_entry(place,rows[:2]))
        self.assertIsNone(p.prepare_entry(place,[dict(x,date='2026-01-01') for x in rows]))
        self.assertIsNone(p.prepare_entry(dict(place,is_restaurant=False),rows))

    def test_source_department_not_spender_title(self):
        self.assertEqual(p.source_department({'filename':'2026년 1~2분기 업무추진비 집행내역(기후대기정책과).xls','publisher':'기후대기정책과','title':''}), '기후대기정책과')
        self.assertEqual(p.source_department({'filename':'2026년 2분기 업무추진비 집행현황(통합기획과).xls','publisher':'통합지원과','title':''}), '통합기획과')
        self.assertEqual(p.source_department({'filename':'2026년 1분기 업무추진비 집행내역(동부소방서).xls','publisher':'소방행정과','title':''}), '동부소방서')

    def test_yearless_date_requires_explicit_context(self):
        self.assertIsNone(p.parse_date('4. 21.'))
        self.assertEqual(p.parse_date('4. 21.', default_year=2026), '2026-04-21')

    def test_header_synonyms(self):
        mapping=p.header_map(['번호','사용일','적 요','집행금액(원)','대상','사용처','집행구분'])
        self.assertEqual(mapping,{'date':1,'merchant':5,'purpose':2,'amount':3})
        self.assertEqual(p.classify('투썸플레이스','간담회'), 'non_meal')

    def test_post_links_dedup(self):
        html='<table><tr><td><a href="boardView.do?seq=9&amp;boardId=X">2026년 9월 사용내역</a></td><td>행정과</td><td>2026-10-01</td></tr></table>'
        rows=p.parse_posts(html,'https://www.jeonnam-gwangju.go.kr/')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['source_id'],'9')
        self.assertEqual(rows[0]['published'],'2026-10-01')

if __name__=='__main__': unittest.main()
