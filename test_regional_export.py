"""Synthetic fixtures only; no network or actual transaction data."""
import copy, csv, hashlib, io, json, tempfile, unittest
from pathlib import Path
from regional_export import validate_staged, validate_inputs

def digest(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

class ExportContract(unittest.TestCase):
    def setUp(self):
        self.csv=b'id,name,address,region,record_count\nx,Synthetic,Example road,Example,1\n'
        self.details={'x':[dict(date='2026-05-01', organization=None, department='',purpose='합성 식사',source_url='https://www.yeongam.go.kr/example') ]}
        self.keys={'x':['key1']}
        self.review=dict(csv_sha256=hashlib.sha256(self.csv).hexdigest(),details_sha256=digest(self.details),record_keys_by_id=copy.deepcopy(self.keys))
        self.urls={'https://www.yeongam.go.kr/example'}
    def check(self): return validate_staged(self.csv,self.details,self.keys,self.review,self.urls)
    def test_valid_review(self): self.check()
    def test_same_count_stale_purpose(self):
        self.details['x'][0]['purpose']='다른 문장'
        with self.assertRaises(ValueError): self.check()
    def test_changed_key_same_count(self):
        self.keys['x']=['key2']
        with self.assertRaises(ValueError): self.check()
    def test_missing_detail_group(self):
        self.details={}
        with self.assertRaises(ValueError): self.check()
    def test_extra_private_field(self):
        self.details['x'][0]['amount']=100
        with self.assertRaises(ValueError): self.check()
    def test_unlisted_official_url(self):
        self.details['x'][0]['source_url']='https://www.yeongam.go.kr/unlisted'
        with self.assertRaises(ValueError): self.check()
    def test_nonofficial_url_even_if_registered(self):
        self.details['x'][0]['source_url']='https://example.com/fake';self.urls.add('https://example.com/fake')
        with self.assertRaises(ValueError): self.check()
    def test_credentials_in_url_rejected(self):
        u='https://'+'synthetic-user'+'@'+'www.yeongam.go.kr/example';self.details['x'][0]['source_url']=u;self.urls.add(u)
        with self.assertRaises(ValueError): self.check()
    def test_outside_period(self):
        self.details['x'][0]['date']='2025-05-01'
        with self.assertRaises(ValueError): self.check()
    def test_changed_csv(self):
        self.csv=self.csv.replace(b'Example road',b'Other road')
        with self.assertRaises(ValueError): self.check()
    def test_count_mismatch(self):
        self.csv=self.csv.replace(b'Example,1',b'Example,2')
        with self.assertRaises(ValueError): self.check()
    def test_original_hash_drift(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source';p.write_bytes(b'original');snap=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())]
            validate_inputs(snap);p.write_bytes(b'changed')
            with self.assertRaises(ValueError):validate_inputs(snap)

if __name__=='__main__':unittest.main()
