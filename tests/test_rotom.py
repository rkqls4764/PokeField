import unittest,tempfile
from pathlib import Path
from src.catalog import Catalog
from src.collection import Collection
from src.rotom_data import query_dex,DISPLAY
from test_services import DATA

class RotomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.catalog=Catalog(DATA)
    def query(self,request,records=None):return query_dex(self.catalog,records or {},request,lambda pid:f'image:{pid}')
    def test_entire_uncaught_catalog_and_pagination(self):
        first=self.query({'request_id':'one'})
        self.assertEqual(first['total'],1025);self.assertEqual(len(first['rows']),18);self.assertEqual(first['detail']['name'],'이상해씨')
        self.assertTrue(all(not r['caught'] for r in first['rows']))
        last=self.query({'page':9999});self.assertEqual(last['page'],last['pages']);self.assertTrue(last['rows'])
    def test_name_number_and_unknown_search(self):
        for query in ('피카츄','#0025','pikachu'):
            result=self.query({'query':query});self.assertEqual(result['total'],1);self.assertEqual(result['detail']['id'],25)
        result=self.query({'query':'없는포켓몬'});self.assertEqual(result['rows'],[]);self.assertIsNone(result['detail'])
    def test_combined_generation_and_type(self):
        result=self.query({'generation':1,'type':'electric'})
        self.assertTrue(result['rows']);self.assertTrue(all('전기' in r['types'] for r in result['rows']))
        self.assertEqual(result['detail']['generation'],1);self.assertIn('특수',result['detail']['stats'])
    def test_record_filters_and_detail_actual_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Collection(Path(tmp)/'captures.sqlite3');db.catch(25,'rotom-capture-001',{25});db.catch(25,'rotom-capture-002',{25})
            records=db.all();result=self.query({'ownership':'수집'},records)
            self.assertEqual(result['total'],1);self.assertEqual(result['detail']['record']['catch_count'],2)
            self.assertTrue(result['detail']['caught']);self.assertNotIn(25,{r['id'] for r in self.query({'ownership':'미수집'},records)['rows']})
    def test_selected_detail_abilities_evolutions_and_no_unknown_values(self):
        result=self.query({'selected_id':25});p=result['detail']
        self.assertEqual(p['id'],25);self.assertEqual(p['image'],'image:25');self.assertTrue(p['evolutions'])
        self.assertTrue(any(a['name']=='피뢰침' and a['hidden'] for a in p['abilities']))
        self.assertTrue(all(v is not None for v in p['stats'].values()))
    def test_invalid_filters_rejected(self):
        for request in ({'generation':99},{'type':'unknown'},{'ownership':'secret'},{'page':'one'}):
            with self.assertRaises(ValueError):self.query(request)
    def test_measured_screen_does_not_cross_outer_image(self):
        self.assertEqual((DISPLAY['image_width'],DISPLAY['image_height']),(314,325))
        self.assertEqual((DISPLAY['left'],DISPLAY['top'],DISPLAY['width'],DISPLAY['height']),(34,126,271,138))
        self.assertLess(DISPLAY['left']+DISPLAY['width'],314);self.assertLess(DISPLAY['top']+DISPLAY['height'],325)
        from PIL import Image
        root=Path(__file__).resolve().parents[1]
        image=Image.open(root/'static/rotom/open.png').convert('RGBA')
        self.assertEqual(image.getpixel((0,0))[3],0)
        # The excluded notch really contains orange artwork, while the UI side is neutral gray.
        r,g,b,a=image.getpixel((50,195));self.assertGreater(r-g,50)
        r,g,b,a=image.getpixel((60,195));self.assertLess(abs(r-g),15)

if __name__=='__main__':unittest.main()
