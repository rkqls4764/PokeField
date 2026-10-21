import unittest
from process_pokemon import reconstruct
def ref(n): return {'url':f'https://pokeapi.co/api/v2/generation/{n}/'}
class HistoryTests(unittest.TestCase):
    def test_sparse_boundaries(self):
        p={'stats':[{'stat':{'name':'defense'},'base_stat':40},{'stat':{'name':'hp'},'base_stat':35}], 'abilities':[{'slot':1,'is_hidden':False,'ability':{'name':'new'}},{'slot':3,'is_hidden':True,'ability':{'name':'hidden'}}], 'types':[{'slot':1,'type':{'name':'fairy'}}], 'past_stats':[{'generation':ref(5),'stats':[{'stat':{'name':'defense'},'base_stat':30}]},{'generation':ref(1),'stats':[{'stat':{'name':'special'},'base_stat':50}]}], 'past_types':[{'generation':ref(5),'types':[{'slot':1,'type':{'name':'normal'}}]}], 'past_abilities':[{'generation':ref(6),'abilities':[{'slot':1,'is_hidden':False,'ability':{'name':'old'}}]},{'generation':ref(4),'abilities':[{'slot':3,'is_hidden':True,'ability':None}]}]}
        t,s,a,_=reconstruct(p,1); self.assertEqual(t,['normal']); self.assertEqual(s['special'],50); self.assertIsNone(s['special_attack']); self.assertEqual(s['hp'],35); self.assertEqual(a,[])
        self.assertEqual(reconstruct(p,5)[1]['defense'],30)
        self.assertEqual(reconstruct(p,6)[1]['defense'],40)
        self.assertEqual([x['name'] for x in reconstruct(p,4)[2]],['old'])
        self.assertEqual([x['name'] for x in reconstruct(p,7)[2]],['new','hidden'])
    def test_absent_history_is_unknown(self):
        t,s,a,status=reconstruct({'types':[],'stats':[],'abilities':[]},6)
        self.assertIsNone(t); self.assertIsNone(a); self.assertTrue(all(v is None for v in s.values()))
        self.assertTrue(all(v=='unverified' for v in status.values()))
    def test_empty_history_retains_unchanged_value(self):
        p={'types':[{'slot':1,'type':{'name':'electric'}}], 'stats':[], 'abilities':[], 'past_types':[], 'past_stats':[], 'past_abilities':[]}
        self.assertEqual(reconstruct(p,3)[0],['electric'])
if __name__=='__main__': unittest.main()
