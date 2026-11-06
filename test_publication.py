import csv,io,json,re,unittest
from pathlib import Path
from build_demo import render_demo
ROOT=Path(__file__).resolve().parent
class PublicationTests(unittest.TestCase):
 def read(self,name):
  p=ROOT/name;self.assertTrue(p.is_file(),f'Missing publication artifact: {name}');return p.read_text()
 def test_builder_uses_reviewed_public_example(self):
  s=render_demo();self.assertIn('공개 비식별 데모',s);self.assertEqual(s,self.read('docs/index.html'))
 def test_current_demo_counts_and_regions(self):
  s=self.read('docs/index.html');rows=json.loads(re.search(r'<script type="application/json" id="restaurants">(.*?)</script>',s,re.S).group(1));self.assertEqual(len(rows),17);self.assertEqual(sum(r['record_count'] for r in rows),229);self.assertEqual(len({r['region'] for r in rows}),8)
 def test_presentation_has_no_grading_discussion(self):
  s=self.read('docs/presentation.html');self.assertEqual(len(re.findall(r'<section class="slide',s)),7)
  for term in ['평가표','배점','가산점','PRIVATE','점수 획득']:self.assertNotIn(term,s)
  self.assertIn('https://urikkiri0919.github.io/local-table-map/',s)
 def test_only_redacted_fields_in_public_demo(self):
  s=self.read('docs/index.html');rows=json.loads(re.search(r'<script type="application/json" id="restaurants">(.*?)</script>',s,re.S).group(1));details=json.loads(re.search(r'<script type="application/json" id="record-details">(.*?)</script>',s,re.S).group(1))
  for row in rows:self.assertTrue(row['name'].startswith('[비식별]'));self.assertIn('비공개',row['address'])
  for arr in details.values():
   for r in arr:self.assertEqual(r['date'],'2000-01-01');self.assertEqual(r['source_url'],'https://example.com/');self.assertIn('시연용',r['purpose'])
 def test_standalone_assets_have_no_local_dependency(self):
  for name in ['docs/index.html','docs/presentation.html']:
   s=self.read(name)
   for u in re.findall(r'(?:href|src)=["\']([^"\']+)',s):self.assertTrue(u.startswith(('https://','data:','#')),u)
   self.assertNotIn('/home/urikkiri',s);self.assertNotIn('localhost:',s)
 def test_pages_jekyll_disabled(self):self.assertTrue((ROOT/'docs/.nojekyll').is_file())
if __name__=='__main__':unittest.main()
