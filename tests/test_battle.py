import json,unittest,itertools,hashlib
from pathlib import Path
from unittest.mock import Mock
from src.catalog import Catalog,TYPE_KO
from src.rag import RagService,validate_citations,cited_sources
from src.settings import Settings
from src.natural_search import NaturalSearch
from src.llm import ServiceError
from test_services import DATA

# Independently transcribed main-series modern chart (strong / resisted / immune).
EXPECTED={
'normal':('', 'rock steel','ghost'),
'fire':('grass ice bug steel','fire water rock dragon',''),
'water':('fire ground rock','water grass dragon',''),
'electric':('water flying','electric grass dragon','ground'),
'grass':('water ground rock','fire grass poison flying bug dragon steel',''),
'ice':('grass ground flying dragon','fire water ice steel',''),
'fighting':('normal ice rock dark steel','poison flying psychic bug fairy','ghost'),
'poison':('grass fairy','poison ground rock ghost','steel'),
'ground':('fire electric poison rock steel','grass bug','flying'),
'flying':('grass fighting bug','electric rock steel',''),
'psychic':('fighting poison','psychic steel','dark'),
'bug':('grass psychic dark','fire fighting poison flying ghost steel fairy',''),
'rock':('fire ice flying bug','fighting ground steel',''),
'ghost':('psychic ghost','dark','normal'),
'dragon':('dragon','steel','fairy'),
'dark':('psychic ghost','fighting dark fairy',''),
'steel':('ice rock fairy','fire water electric steel',''),
'fairy':('fighting dragon dark','fire poison steel','')}
class BattleTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.catalog=Catalog(DATA);cls.b=cls.catalog.battle;cls.settings=Settings(DATA,Path('unused-test-chroma'))
 def service(self):
  forbidden=Mock();forbidden.check_key.side_effect=AssertionError('paid API');forbidden.structured.side_effect=AssertionError('paid API')
  return RagService(self.settings,self.catalog,Mock(),forbidden)
 def test_all_324_modern_combinations(self):
  for a,d in itertools.product(TYPE_KO,repeat=2):
   strong,weak,immune=EXPECTED[a];expected=0 if d in immune.split() else 2 if d in strong.split() else .5 if d in weak.split() else 1
   self.assertEqual(self.b.multiplier(a,[d]),expected,(a,d))
 def test_every_dual_type_and_generation_multiplies(self):
  for gen in range(1,10):
   chart=self.b.chart(gen)
   for a in chart:
    for x,y in itertools.combinations(chart,2):self.assertEqual(self.b.multiplier(a,[x,y],gen),chart[a][x]*chart[a][y])
  self.assertEqual(self.b.multiplier('rock',['fire','flying']),4)
  self.assertEqual(self.b.multiplier('grass',['fire','flying']),.25)
  self.assertEqual(self.b.multiplier('electric',['water','ground']),0)
 def test_legacy_chart_differences_and_unintroduced_types(self):
  for a,d,old,new in [('ghost','psychic',0,2),('bug','poison',2,.5),('poison','bug',2,1),('ice','fire',1,.5)]:
   self.assertEqual(self.b.multiplier(a,[d],1),old);self.assertEqual(self.b.multiplier(a,[d],2),new)
  self.assertEqual(self.b.multiplier('ghost',['steel'],5),.5);self.assertEqual(self.b.multiplier('dark',['steel'],5),.5)
  self.assertEqual(self.b.multiplier('ghost',['steel'],6),1)
  with self.assertRaises(ServiceError):self.b.multiplier('fairy',['dragon'],5)
  with self.assertRaises(ServiceError):self.catalog.structured_query('5세대 페어리 타입 공격 상성')
 def test_requested_type_questions_in_both_graph_modes(self):
  s=self.service()
  questions=['피카츄의 약점 타입은 뭐야?','리자몽의 약점은?','이상해꽃에게 효과적인 타입은?','물 타입에 강한 타입은?','전기 타입 공격이 통하지 않는 타입은?','리자몽에게 바위 타입 공격을 하면 몇 배야?','피카츄와 라이츄의 약점을 비교해 줘.']
  for q in questions:
   result=s.ask_global(q);self.assertTrue(validate_citations(result['answer'],result['sources']));self.assertTrue(cited_sources(result['answer'],result['sources']));self.assertIn('일반 타입 상성',result['answer'])
  self.assertIn('땅 2배',s.ask_global(questions[0])['answer']);self.assertIn('바위 4배',s.ask_global(questions[1])['answer']);self.assertIn('땅 0배',s.ask_global(questions[4])['answer'])
  self.assertIn('4배',s.ask(6,9,questions[5])['answer'])
  self.assertIn('피카츄',s.ask_global('그럼 약점은?', [{'role':'user','content':'피카츄 타입 알려줘'}])['answer'])
 def test_pokemon_generation_type_changes(self):
  self.assertIn('노말',self.catalog.structured_query('5세대 삐삐 약점')['verified_lines'][0]);self.assertIn('페어리',self.catalog.structured_query('6세대 삐삐 약점')['verified_lines'][0])
 def test_move_aliases_and_no_model_calls(self):
  self.assertEqual(self.b.move_mentions('몸통박치기를 배우는 포켓몬')[0][2],33)
  self.assertEqual(self.b.move_mentions('tackle 배우는 포켓몬')[0][2],33)
  for q in ['몸통박치기를 배우는 포켓몬 알려줘.','피카츄는 어떤 기술을 배워?','9세대에서 몸통박치기를 배우는 포켓몬은?','레벨업으로 몸통박치기를 배우는 포켓몬은?','전기 타입 기술을 배우는 물 타입 포켓몬은?','피카츄가 10레벨에 배우는 기술은?']:
   result=self.service().ask_global(q);self.assertEqual(result['generation'],9);self.assertTrue(validate_citations(result['answer'],result['sources']));self.assertTrue(result['sources'])
  result=NaturalSearch(self.settings,self.catalog,Mock()).run('몸통박치기를 배우는 포켓몬',9)
  self.assertEqual(result['selection_mode'],'local_moves');self.assertGreater(result['candidate_count'],100)
 def test_results_are_in_original_cache_and_correct_type_method_level(self):
  query=self.catalog.structured_query('9세대 레벨업으로 몸통박치기를 배우는 포켓몬',limit=10000)
  pids={u[0]['pokemon_id'] for u in query['move_matches']};self.assertIn(1,pids);self.assertNotIn(25,pids)
  for unit in query['move_matches']:
   for m in unit:
    self.assertEqual(m['move']['id'],33);self.assertEqual(m['method'],'level-up')
   pid=unit[0]['pokemon_id'];url=f'https://pokeapi.co/api/v2/pokemon/{pid}/';raw=DATA.parent/'raw'/(hashlib.sha256(url.encode()).hexdigest()+'.json')
   moves=json.loads(raw.read_text(encoding='utf-8'))['response']['moves'];self.assertTrue(any(m['move']['name']=='tackle' for m in moves))
  water=self.catalog.structured_query('전기 타입 기술을 배우는 물 타입 포켓몬',limit=10000)
  self.assertTrue(water['move_matches'])
  for unit in water['move_matches']:
   self.assertIn('water',self.catalog.index[unit[0]['pokemon_id'],9]['types']);self.assertTrue(all(m['move']['type']=='electric' for m in unit))
 def test_version_level_historical_move_stats_pagination(self):
  result=self.catalog.structured_query('피카츄가 10레벨에 배우는 기술은?');self.assertEqual(result['generation'],9)
  self.assertNotIn('yellow',result['verified_lines'][0])
  for unit in result['move_matches']:self.assertEqual(unit[0]['level'],10);self.assertEqual(unit[0]['method'],'level-up')
  old=self.catalog.structured_query('피카츄가 yellow 버전에서 배우는 기술');self.assertEqual(old['generation'],1)
  self.assertTrue(all(m['version_group']=='yellow' for u in old['move_matches'] for m in u))
  machine=self.catalog.structured_query('피카츄가 기술머신으로 배우는 기술')
  self.assertTrue(machine['move_matches']);self.assertTrue(all(m['method']=='machine' for u in machine['move_matches'] for m in u))
  self.assertEqual(self.b.move_at(33,1)['power'],35);self.assertEqual(self.b.move_at(33,11)['power'],50);self.assertEqual(self.b.move_at(33,17)['power'],40)
  first=self.catalog.structured_query('몸통박치기를 배우는 포켓몬',limit=6);second=self.catalog.structured_query(first['more_question'],limit=6)
  self.assertEqual(second['search_context']['page'],2);self.assertTrue({u[0]['pokemon_id'] for u in first['move_matches']}.isdisjoint({u[0]['pokemon_id'] for u in second['move_matches']}))
 def test_unknown_and_unsupported_conditions_are_not_invented(self):
  for q in ['모르는기술을 배우는 포켓몬','피카츄가 가짜광선을 배워?','10세대 몸통박치기를 배우는 포켓몬','9세대 피카츄가 yellow 버전에서 배우는 기술','부유 특성이며 몸통박치기를 배우는 포켓몬']:
   with self.assertRaises(ServiceError,msg=q):self.catalog.structured_query(q)
  result=self.catalog.structured_query('9세대 피카츄가 99레벨에 배우는 기술');self.assertIn('확인하지 못했네',' '.join(result['verified_lines']))
 def test_native_dex_contains_calculated_matchups(self):
  from src.rotom_data import query_dex
  p=query_dex(self.catalog,{}, {'selected_id':6},lambda pid:'')['detail'];self.assertEqual(p['type_matchups']['rock'],4)
if __name__=='__main__':unittest.main()
