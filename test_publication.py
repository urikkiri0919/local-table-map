import csv,copy,hashlib,json,re,unittest
from pathlib import Path
from urllib.parse import unquote
from build_demo import render_demo
ROOT=Path(__file__).resolve().parent
class PublicationTests(unittest.TestCase):
 def read(self,name):return (ROOT/name).read_text()
 def payload(self,s,name):return json.loads(re.search(r'<script type="application/json" id="'+name+r'">(.*?)</script>',s,re.S).group(1))
 def inputs(self):
  with (ROOT/'examples/public-restaurants.csv').open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
 def test_builder_matches_current_published_artifact(self):
  s=render_demo();self.assertIn('공개 식당 목록 데모',s);self.assertEqual(s,self.read('docs/index.html'))
 def test_current_demo_counts_and_regions(self):
  rows=self.payload(self.read('docs/index.html'),'restaurants');self.assertEqual(len(rows),16);self.assertEqual(sum(r['record_count'] for r in rows),217);self.assertEqual(len({r['region'] for r in rows}),7)
 def test_presentation_is_exact_submitted_snapshot(self):
  b=(ROOT/'docs/presentation.html').read_bytes();self.assertEqual(hashlib.sha256(b).hexdigest(),'90d5a8191f3072c057eb13d22d958eb5b57dd0e639f6bfa8d8c054cc67cb8299')
 def test_real_metadata_only_no_actual_or_fake_detail_rows(self):
  s=self.read('docs/index.html');rows=self.payload(s,'restaurants');details=self.payload(s,'record-details')
  expected=[dict(r,record_count=int(r['record_count'])) for r in self.inputs()];self.assertEqual(rows,expected)
  for row in rows:self.assertEqual(set(row),{'id','name','address','region','record_count'});self.assertFalse(row['name'].startswith('[비식별]'))
  self.assertEqual(sum(map(len,details.values())),0);self.assertNotIn('2000-01-01',s);self.assertNotIn('https://example.com/',s)
 def test_standalone_assets_have_no_local_dependency(self):
  for name in ['docs/index.html','docs/presentation.html']:
   s=self.read(name)
   for u in re.findall(r'(?:href|src)=["\']([^"\']+)',s):self.assertTrue(u.startswith(('https://','data:','#')),u)
   self.assertNotIn('file://',s);self.assertNotIn('localhost:',s)
 def test_pages_jekyll_disabled(self):self.assertTrue((ROOT/'docs/.nojekyll').is_file())
 def test_actual_address_links_not_masked(self):
  s=render_demo();links=re.findall(r'<a class="address" href="([^"]+)"',s);self.assertEqual(len(links),16)
  for link,row in zip(links,self.inputs()):self.assertEqual(unquote(link.split('/p/search/')[1]),row['address'])
  self.assertNotIn('function mask()',s);self.assertNotIn('aria-disabled="true"',s)
 def test_scope_and_limitations_are_explicit(self):
  s=render_demo()
  for text in ['16곳 · 217건','17곳 · 229건','담양 관련 1곳 · 12건','원문·세부 지출정보 미제공','재이용 조건 확인 중']:self.assertIn(text,s)
  self.assertFalse(any(r['region']=='담양군' for r in self.payload(s,'restaurants')))
 def test_builder_rejects_held_region(self):
  self.assertIn('rows',__import__('inspect').signature(render_demo).parameters)
  rows=self.inputs();rows[0]['region']='담양군'
  with self.assertRaises(ValueError):render_demo(rows=rows)
 def test_builder_rejects_unapproved_extra_fields(self):
  self.assertIn('rows',__import__('inspect').signature(render_demo).parameters)
  rows=self.inputs();rows[0]['amount']='1'
  with self.assertRaises(ValueError):render_demo(rows=rows)
if __name__=='__main__':unittest.main()
