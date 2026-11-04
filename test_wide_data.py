"""Synthetic fixtures only; never copied into real research outputs."""
import copy
import hashlib
import json
import unittest
import wide_data as data


def row(**changes):
    value = dict(source_id='synthetic:1', source_url='https://www.seogu.gwangju.kr/?fixture=1',
                 department='총무과', date='2026-05-01', time='12:00', merchant='합성식당',
                 purpose='합성 검증용 식사', amount=10000, file='synthetic.xlsx', sheet='표', row=2)
    value.update(changes)
    return value


class MergeTests(unittest.TestCase):
    def merge(self, batches):
        self.assertTrue(callable(getattr(data, 'merge_transactions', None)), 'merge_transactions missing')
        return data.merge_transactions(batches)

    def groups(self, rows):
        self.assertTrue(callable(getattr(data, 'group_candidates', None)), 'group_candidates missing')
        return data.group_candidates(rows)

    def test_same_department_in_different_governments_is_distinct(self):
        result = self.merge({'seogu': [row()], 'gwangsan': [row()]})
        self.assertEqual(len(result['rows']), 2)
        self.assertEqual({r['department_key'] for r in result['rows']}, {'seogu|총무과', 'gwangsan|총무과'})
        self.assertEqual(len({r['record_key'] for r in result['rows']}), 2)

    def test_repeat_publication_deduplicates_and_retains_both_sources(self):
        result = self.merge({'seogu': [row(), row(source_id='synthetic:2', file='cumulative.xlsx')]})
        self.assertEqual(len(result['rows']), 1)
        self.assertEqual(len(result['rows'][0]['provenance']), 2)
        self.assertEqual(result['duplicate_rows'], 1)

    def test_different_time_is_not_deduplicated(self):
        result = self.merge({'seogu': [row(), row(time='19:00', row=3)]})
        self.assertEqual(len(result['rows']), 2)

    def test_conflicting_participant_counts_are_held(self):
        result = self.merge({'seogu': [row(attendees=8), row(attendees=9, source_id='synthetic:2')]})
        self.assertEqual(result['rows'], [])
        self.assertEqual(len(result['conflicts']), 1)
        self.assertEqual(len(result['conflicts'][0]['records']), 2)

    def test_actual_year_is_not_relabelled_and_fractional_amount_is_rejected(self):
        result = self.merge({'seogu': [row(date='2025-05-01'), row(date='2029-05-01'),
                                       row(amount=1.5), row(amount=True), row()]})
        self.assertEqual(len(result['rows']), 1)
        self.assertEqual(len(result['excluded']), 4)

    def test_quarters_do_not_manufacture_independent_departments(self):
        result = self.merge({'seogu': [row(), row(date='2026-07-01'), row(date='2026-08-01')]})
        self.assertEqual(self.groups(result['rows']), [])

    def test_spender_roles_are_not_department_units(self):
        result = self.merge({'seogu': [row(department='구청장'), row(department='부구청장'),
                                       row(department='총무과장')]})
        self.assertTrue(all(r['department_key'] is None for r in result['rows']))
        self.assertEqual(self.groups(result['rows']), [])

    def test_candidates_require_three_units_and_recent_activity(self):
        result = self.merge({'seogu': [row(department='총무과'), row(department='문화예술과'),
                                       row(department='주민자치과')]})
        groups = self.groups(result['rows'])
        self.assertEqual([(g['merchant_key'], g['record_count'], g['department_count']) for g in groups],
                         [('합성식당', 3, 3)])
        older = self.merge({'seogu': [row(department=x, date='2026-02-01')
                                    for x in ['총무과', '문화예술과', '주민자치과']]})
        self.assertEqual(self.groups(older['rows']), [])

    def test_non_meals_and_multi_merchant_rows_do_not_become_candidates(self):
        result = self.merge({'seogu': [row(department=x, purpose='다과 구입')
                                     for x in ['총무과', '문화예술과', '주민자치과']]})
        self.assertEqual(self.groups(result['rows']), [])
        result = self.merge({'seogu': [row(department=x, merchant='합성식당/다른식당')
                                     for x in ['총무과', '문화예술과', '주민자치과']]})
        self.assertEqual(self.groups(result['rows']), [])


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.csv = ('id,name,address,region,record_count\r\n'
                    'fixture,합성식당,합성 주소,서구,1\r\n').encode('utf-8-sig')
        self.url = 'https://www.seogu.gwangju.kr/?fixture=1'
        self.details = {'fixture': [dict(date='2026-05-01', organization=None,
                                       department='총무과', purpose='합성 검증용 식사', source_url=self.url)]}
        self.keys = {'fixture': ['synthetic-record-1']}
        self.review = dict(csv_sha256=hashlib.sha256(self.csv).hexdigest(),
                           details_sha256=hashlib.sha256(json.dumps(self.details, ensure_ascii=False,
                                                   sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                           record_keys_by_id=self.keys)

    def validate(self, csv=None, details=None, review=None, urls=None, keys=None):
        self.assertTrue(callable(getattr(data, 'validate_bundle', None)), 'validate_bundle missing')
        return data.validate_bundle(self.csv if csv is None else csv,
                                    self.details if details is None else details,
                                    self.review if review is None else review,
                                    {self.url} if urls is None else urls,
                                    self.keys if keys is None else keys)

    def test_valid_reviewed_utf8_bom_bundle_is_accepted(self):
        self.assertIsNone(self.validate())

    def test_same_count_stale_details_rejected(self):
        stale = copy.deepcopy(self.details)
        stale['fixture'][0]['purpose'] = '未承認の合成テキスト'
        with self.assertRaisesRegex(ValueError, 'review|hash'):
            self.validate(details=stale)

    def test_missing_detail_group_rejected(self):
        with self.assertRaisesRegex(ValueError, 'group'):
            self.validate(details={})

    def test_non_manifest_or_private_host_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'source|URL'):
            self.validate(urls=set())
        private = copy.deepcopy(self.details)
        private['fixture'][0]['source_url'] = 'http://127.0.0.1:1/private'
        with self.assertRaisesRegex(ValueError, 'source|URL'):
            self.validate(details=private, urls={'http://127.0.0.1:1/private'})

    def test_changed_transaction_selection_rejected(self):
        with self.assertRaisesRegex(ValueError, 'record|selection'):
            self.validate(keys={'fixture': ['synthetic-record-2']})

    def test_count_mismatch_rejected_even_if_review_hash_is_updated(self):
        changed_csv = self.csv.replace(b',1\r\n', b',2\r\n')
        review = dict(self.review, csv_sha256=hashlib.sha256(changed_csv).hexdigest())
        with self.assertRaisesRegex(ValueError, 'count'):
            self.validate(csv=changed_csv, review=review)


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.places = [dict(name='합성식당', address='합성 주소 (서구)', region='서구',
                            merchant_keys=['합성식당'], is_restaurant=True, ambiguous=False)]
        self.records = [dict(row(department=unit, row=i), classification='meal_candidate',
                             source_bucket='seogu', department_key='seogu|' + unit,
                             record_key='synthetic-' + str(i), institution='추정하면 안 되는 표기')
                        for i, unit in enumerate(['총무과', '문화예술과', '주민자치과'], 2)]

    def prepare(self, places=None, records=None):
        self.assertTrue(callable(getattr(data, 'prepare_bundle', None)), 'prepare_bundle missing')
        return data.prepare_bundle(self.places if places is None else places,
                                   self.records if records is None else records, {}, {})

    def test_prepares_full_count_without_coordinates_or_unreviewed_institution(self):
        import csv, io
        csv_bytes, details, audit = self.prepare()
        rows = list(csv.DictReader(io.StringIO(csv_bytes.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['record_count'], '3')
        self.assertEqual(len(details[rows[0]['id']]), 3)
        self.assertTrue(all(d['organization'] is None for d in details[rows[0]['id']]))
        self.assertTrue(all(set(d) == {'date', 'organization', 'department', 'purpose', 'source_url'}
                            for d in details[rows[0]['id']]))
        self.assertEqual(audit[0]['department_count'], 3)
        self.assertEqual(len(audit[0]['record_keys']), 3)

    def test_rejects_overlapping_place_aliases_instead_of_double_counting(self):
        other = dict(self.places[0], name='다른 합성식당', address='다른 합성 주소 (서구)')
        with self.assertRaisesRegex(ValueError, 'overlap|ambiguous'):
            self.prepare(places=self.places + [other])

    def test_rejects_places_without_three_verified_units(self):
        records = [dict(r, department_key='seogu|총무과') for r in self.records]
        with self.assertRaisesRegex(ValueError, 'department|diversity'):
            self.prepare(records=records)


if __name__ == '__main__':
    unittest.main()
