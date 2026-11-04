"""Synthetic fixtures only; no network calls or real restaurant fixtures."""
import importlib.util
import json
import unittest
import tempfile
import inspect
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.buttons = []
        self.dialogs = []
        self.scripts = []
        self.script = None
        self.text = []
        self.names = []
        self.counts = []
        self.in_name = False
        self.in_count = False
        self.in_restaurant = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'li' and attrs.get('class') == 'restaurant':
            self.in_restaurant = True
        if tag == 'h3' and self.in_restaurant:
            self.names.append('')
            self.in_name = True
        if tag in ('div', 'button') and attrs.get('class') == 'record-count':
            self.counts.append('')
            self.in_count = True
        if tag == 'button':
            self.buttons.append(attrs)
        if tag == 'dialog':
            self.dialogs.append(attrs)
        if tag == 'a':
            self.links.append(attrs)
        if tag == 'script':
            self.script = attrs
            self.scripts.append({'attrs': attrs, 'text': ''})

    def handle_endtag(self, tag):
        if tag == 'li':
            self.in_restaurant = False
        if tag == 'h3':
            self.in_name = False
        if tag in ('div', 'button'):
            self.in_count = False
        if tag == 'script':
            self.script = None

    def handle_data(self, data):
        if self.in_name:
            self.names[-1] += data
        if self.in_count:
            self.counts[-1] += data
        if self.script is not None:
            self.scripts[-1]['text'] += data
        else:
            self.text.append(data)


class ListTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.find_spec('export_list')
        self.assertIsNotNone(spec, 'list exporter is not implemented yet')
        import export_list
        self.app = export_list
        self.rows = [
            {'id': 'test-a', 'name': '테스트식당 A & B', 'address': '검증시 검증로 1',
             'region': '서구', 'record_count': '2', 'department': 'PRIVATE_DEPARTMENT', 'amount': 918273},
            {'id': 'test-b', 'name': '테스트식당 C', 'address': '다른시 검증로 2', 'region': '나주시', 'record_count': '1'},
        ]

    def test_user_address_example_does_not_include_business_name(self):
        # The user's expected search: only the clicked street address.
        url = self.app.naver_url('광주광역시 서구 천변좌하로 270')
        self.assertEqual(unquote(urlsplit(url).path),
                         '/p/search/광주광역시 서구 천변좌하로 270')

    def test_link_uses_only_full_address_on_naver(self):
        # Reserved characters must remain in the search term, not URL metadata.
        url = self.app.naver_url('검증시 검사/길 1 #2')
        parsed = urlsplit(url)
        self.assertEqual(parsed.scheme, 'https')
        self.assertEqual(parsed.netloc, 'map.naver.com')
        self.assertEqual(unquote(parsed.path), '/p/search/검증시 검사/길 1 #2')
        self.assertEqual(parsed.fragment, '')
        self.assertEqual(parsed.query, '')
        self.assertIn('%2F', parsed.path)

    def test_page_contains_address_links_and_no_external_dependencies(self):
        parser = PageParser()
        parser.feed(self.app.render_page(self.rows))
        links = parser.links
        self.assertEqual(len(links), 2)
        self.assertEqual(unquote(urlsplit(links[0]['href']).path),
                         '/p/search/검증시 검증로 1')
        self.assertEqual(links[0]['target'], '_blank')
        self.assertIn('noopener', links[0]['rel'])
        self.assertIn('noreferrer', links[0]['rel'])
        self.assertIn('검증시 검증로 1', ''.join(parser.text))
        self.assertFalse(any(s['attrs'].get('src') for s in parser.scripts))

    def test_payload_contains_no_institution_amount_or_coordinates(self):
        page = self.app.render_page(self.rows)
        parser = PageParser()
        parser.feed(page)
        data = next(s for s in parser.scripts if s['attrs'].get('id') == 'restaurants')
        rows = json.loads(data['text'])
        self.assertEqual(len(rows), 2)
        self.assertEqual(set(rows[0]), {'id', 'name', 'address', 'region', 'record_count'})
        self.assertEqual(rows[0]['record_count'], 2)
        self.assertNotIn('PRIVATE_DEPARTMENT', page)
        self.assertNotIn('918273', page)

    def test_untrusted_names_cannot_inject_script_or_html(self):
        rows = [dict(self.rows[0], name='</script><img src=x onerror=alert(1)>')]
        parser = PageParser()
        parser.feed(self.app.render_page(rows))
        data = next(s for s in parser.scripts if s['attrs'].get('id') == 'restaurants')
        self.assertEqual(json.loads(data['text'])[0]['name'], rows[0]['name'])
        self.assertNotIn('<img src=x', self.app.render_page(rows))
        self.assertEqual(len(parser.scripts), 3)

    def test_address_required_but_coordinates_are_not(self):
        self.assertIn('테스트식당', self.app.render_page(self.rows))
        with self.assertRaises(ValueError):
            self.app.render_page([dict(self.rows[0], address=' ')])
        with self.assertRaises(ValueError):
            self.app.render_page([dict(self.rows[0], name='')])

    def test_empty_input_is_honest_and_does_not_create_restaurants(self):
        parser = PageParser()
        parser.feed(self.app.render_page([]))
        data = next(s for s in parser.scripts if s['attrs'].get('id') == 'restaurants')
        self.assertEqual(json.loads(data['text']), [])
        self.assertEqual(parser.links, [])
        self.assertIn('준비 중', ''.join(parser.text))
        self.assertNotIn('4곳을 확인', ''.join(parser.text))

    def test_default_input_prefers_reviewed_list_over_legacy_map(self):
        self.assertTrue(hasattr(self.app, 'default_input'),
                        'reviewed list input selection is not implemented')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'output').mkdir()
            legacy = root/'output'/'map_ready.csv'
            legacy.touch()
            self.assertEqual(self.app.default_input(root), legacy)
            reviewed = root/'output'/'list_ready.csv'
            reviewed.touch()
            self.assertEqual(self.app.default_input(root), reviewed)

    def test_records_are_sorted_numerically_descending_with_visible_counts(self):
        rows = [self.rows[0], dict(self.rows[1], record_count='10'),
                dict(self.rows[0], id='test-c', name='테스트식당 D', record_count='9')]
        parser = PageParser()
        parser.feed(self.app.render_page(rows))
        self.assertEqual(parser.names, ['테스트식당 C', '테스트식당 D', '테스트식당 A & B'])
        self.assertEqual(parser.counts, ['이용기록10건', '이용기록9건', '이용기록2건'])
        self.assertEqual(rows[0]['record_count'], '2')

    def test_equal_counts_have_deterministic_name_order(self):
        rows = [dict(self.rows[0], name='하식당', record_count=3),
                dict(self.rows[1], name='가식당', record_count=3)]
        parser = PageParser()
        parser.feed(self.app.render_page(rows))
        self.assertEqual(parser.names, ['가식당', '하식당'])

    def test_unknown_count_is_not_invented_as_zero_and_sorts_last(self):
        rows = [dict(self.rows[0], record_count=None), self.rows[1]]
        parser = PageParser()
        parser.feed(self.app.render_page(rows))
        self.assertEqual(parser.names, ['테스트식당 C', '테스트식당 A & B'])
        self.assertEqual(parser.counts, ['이용기록1건', '기록 수 확인 중'])

    def test_invalid_counts_are_rejected_and_explicit_zero_is_valid(self):
        for count in ['-1', '1.5', 'many', True, 1.0, '<img src=x>']:
            with self.subTest(count=count), self.assertRaises(ValueError):
                self.app.render_page([dict(self.rows[0], record_count=count)])
        parser = PageParser()
        parser.feed(self.app.render_page([dict(self.rows[0], record_count=0)]))
        self.assertEqual(parser.counts, ['이용기록0건'])

    def render_details(self, details):
        self.assertIn('record_details', inspect.signature(self.app.render_page).parameters,
                      'safe popup details are not implemented')
        page = self.app.render_page(self.rows, record_details=details)
        parser = PageParser()
        parser.feed(page)
        data = next(s for s in parser.scripts if s['attrs'].get('id') == 'record-details')
        return page, parser, json.loads(data['text'])

    def fixture_details(self):
        return {'test-a': [
            {'date': '2026-06-01', 'organization': None, 'department': '테스트부서',
             'purpose': '업무 협의 간담회', 'source_url': 'https://example.org/post/1',
             'amount': 987654321, 'spender_role': 'PRIVATE_PERSON', 'file': 'PRIVATE_PATH'},
            {'date': '2026-07-02', 'organization': '테스트기관', 'department': '테스트과',
             'purpose': '현안업무 논의', 'source_url': 'https://example.org/post/2'},
        ]}

    def test_count_is_a_named_dialog_button_not_a_noninteractive_badge(self):
        parser = PageParser()
        parser.feed(self.app.render_page(self.rows))
        buttons = [b for b in parser.buttons if b.get('class') == 'record-count']
        self.assertEqual(len(buttons), 2)
        self.assertEqual(buttons[0]['type'], 'button')
        self.assertEqual(buttons[0]['aria-haspopup'], 'dialog')
        self.assertIn('테스트식당 A & B', buttons[0]['aria-label'])
        self.assertEqual(buttons[0]['aria-controls'], 'record-dialog')
        self.assertEqual(parser.dialogs[0]['id'], 'record-dialog')
        self.assertEqual(parser.dialogs[0]['aria-labelledby'], 'record-title')

    def test_detail_payload_is_whitelisted_and_newest_first(self):
        page, parser, data = self.render_details(self.fixture_details())
        self.assertEqual([r['date'] for r in data['test-a']], ['2026-07-02', '2026-06-01'])
        self.assertEqual(set(data['test-a'][0]),
                         {'date', 'organization', 'department', 'purpose', 'source_url'})
        self.assertEqual(data['test-a'][1]['organization'], None)
        for secret in ['987654321', 'PRIVATE_PERSON', 'PRIVATE_PATH']:
            self.assertNotIn(secret, page)

    def test_detail_count_mismatch_does_not_silently_show_partial_evidence(self):
        self.assertIn('record_details', inspect.signature(self.app.render_page).parameters)
        with self.assertRaises(ValueError):
            self.app.render_page(self.rows, record_details={'test-a': self.fixture_details()['test-a'][:1]})

    def test_unsafe_source_urls_are_rejected(self):
        self.assertIn('record_details', inspect.signature(self.app.render_page).parameters)
        for url in ['javascript:alert(1)', 'file:///private/file', 'https://user:pass' + '@' + 'example.org/post']:
            details = self.fixture_details()
            details['test-a'][0]['source_url'] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.app.render_page(self.rows, record_details=details)

    def test_detail_text_is_script_safe_and_contact_details_are_masked(self):
        details = self.fixture_details()
        phone = '010-' + '1234-' + '5678'
        email = 'person' + '@' + 'example.org'
        details['test-a'][0]['purpose'] = '담당자: 홍길동 / ' + phone + ' / ' + email
        details['test-a'][1]['purpose'] = '</script><img src=x onerror=alert(1)>'
        page, parser, data = self.render_details(details)
        self.assertEqual(data['test-a'][0]['purpose'], '</script><img src=x onerror=alert(1)>')
        self.assertNotIn('<img src=x', page)
        self.assertNotIn(phone, page)
        self.assertNotIn(email, page)
        self.assertNotIn('홍길동', page)
        self.assertEqual(len(parser.scripts), 3)


if __name__ == '__main__':
    unittest.main()
