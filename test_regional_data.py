"""Synthetic tests only; never included in collected records."""
import copy
import unittest
import regional_data as data


def row(department='총무과', date='2026-05-01', **extra):
    result=dict(source_id='synthetic:1',source_url='https://example.com/',
                department=department,department_basis='합성 표제의 명시 부서',
                date=date,time='12:00',merchant='합성식당',purpose='합성 식사 검증',
                amount=10000,file='synthetic.xlsx',sheet='표',row=2)
    result.update(extra)
    return result


class DepartmentTests(unittest.TestCase):
    def test_verified_department_is_retained(self):
        self.assertEqual(data.sanitize_department(' 총무과 ',{'총무과'}),'총무과')

    def test_unverified_name_is_not_a_department_even_if_ending_in_dong(self):
        self.assertIsNone(data.sanitize_department('홍길동',{'중앙동'}))
        self.assertEqual(data.sanitize_department('중앙동',{'중앙동'}),'중앙동')

    def test_spender_roles_are_rejected_even_if_erroneously_allowlisted(self):
        for role in ['시장','부시장','군수','부군수','읍장','면장','국장','과장','보건소장']:
            with self.subTest(role=role):
                self.assertIsNone(data.sanitize_department(role,{role}))

    def test_parent_bureau_units_do_not_manufacture_independence(self):
        self.assertIsNone(data.sanitize_department('관광문화교육국',{'관광문화교육국'}))

    def test_missing_source_qualification_is_explicit(self):
        with self.assertRaisesRegex(ValueError,'qualification|verified'):
            data.normalize_batches({'county':[row()]},{})

    def test_basis_required_and_reported_label_is_preserved_without_input_mutation(self):
        batches={'county':[row(department_basis='')]};before=copy.deepcopy(batches)
        result=data.normalize_batches(batches,{'county':{'총무과'}})
        self.assertIn('county',result,'normalization must return each source batch')
        actual=result['county'][0]
        self.assertEqual(actual['department'],'')
        self.assertEqual(actual['reported_department'],'총무과')
        self.assertEqual(batches,before)


class SourceScopeTests(unittest.TestCase):
    def test_same_name_from_two_sources_is_not_combined_to_reach_three_units(self):
        batches={'alpha':[row('총무과'),row('문화과')], 'beta':[row('복지과')]}
        actual=data.analyze_sources(batches,{'alpha':{'총무과','문화과'},'beta':{'복지과'}})
        self.assertEqual(actual.get('candidate_group_count'),0)
        self.assertEqual(actual['source_count'],2)
        self.assertEqual(actual['cross_source_names'],[{'merchant_key':'합성식당','sources':['alpha','beta']}])

    def test_qualifying_sources_stay_separate_and_same_name_flags_ambiguity(self):
        units={'총무과','문화과','복지과'}
        batches={bucket:[row(unit) for unit in sorted(units)] for bucket in ['alpha','beta']}
        actual=data.analyze_sources(batches,{'alpha':units,'beta':units})
        self.assertEqual(actual.get('candidate_group_count'),2)
        self.assertEqual(actual.get('normalized_rows'),6)
        self.assertEqual([len(actual['sources'][b]['candidates']) for b in ['alpha','beta']],[1,1])
        a=actual['sources']['alpha']['merge']['rows'];b=actual['sources']['beta']['merge']['rows']
        self.assertTrue({r['record_key'] for r in a}.isdisjoint(r['record_key'] for r in b))

    def test_repeated_quarters_do_not_manufacture_department_diversity(self):
        actual=data.analyze_sources({'alpha':[row(date=d) for d in ['2026-02-01','2026-05-01','2026-08-01']]},{'alpha':{'총무과'}})
        self.assertEqual(actual.get('candidate_group_count'),0)
        self.assertEqual(actual.get('normalized_rows'),3)

    def test_repeat_publication_preserves_provenance_and_deduplicates(self):
        a=row();b=row(source_id='synthetic:2',file='another-synthetic.xlsx')
        actual=data.analyze_sources({'alpha':[a,b]},{'alpha':{'총무과'}})
        self.assertEqual(actual.get('normalized_rows'),1)
        self.assertEqual(actual['sources']['alpha']['merge']['duplicate_rows'],1)
        self.assertEqual(len(actual['sources']['alpha']['merge']['rows'][0]['provenance']),2)


if __name__=='__main__':unittest.main()
