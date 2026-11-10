import itertools,math,unittest
from graph_features import parse,features,scc,stats
class Tests(unittest.TestCase):
 def test_isolates_and_empty(self):
  v,e,_=parse(b'p sp 4 1\na 1 2 7');f=features(v,e);self.assertEqual(f['isolated_vertices'],2);self.assertEqual(f['scc_count'],4);self.assertEqual(f['cyclic_vertex_fraction'],0)
  v,e,_=parse(b'p sp 0 0');f=features(v,e);self.assertEqual(f['n'],0);self.assertIsNone(f['weight_mean'])
 def test_known_components(self):
  v,e,_=parse(b'p sp 6 5\na 1 2 1\na 2 1 2\na 2 3 3\na 3 4 4\na 4 3 5');f=features(v,e)
  self.assertEqual((f['scc_count'],f['nontrivial_scc_count'],f['largest_scc_size']),(4,2,2));self.assertEqual(f['cyclic_edge_fraction'],.8);self.assertEqual(f['cyclic_vertex_fraction'],4/6);self.assertEqual(f['reciprocal_edge_fraction'],.8)
 def test_reject_invalid_graph(self):
  invalid=['','p sp 2 2\na 1 2 1','p sp 2 1\na 0 2 1','p sp 2 1\na 1 3 1','p sp 1 1\na 1 1 1','p sp 2 2\na 1 2 1\na 1 2 2','a 1 2 1','p bad 2 0','p sp 2 0\np sp 2 0','p sp -1 0']
  for s in invalid:
   with self.subTest(s=s),self.assertRaises(ValueError):parse(s.encode())
 def test_weight_validation(self):
  for w in ['nan','inf','-inf','0','-1','1.5','1e5']:
   with self.subTest(w=w),self.assertRaises(ValueError):parse(f'p sp 2 1\na 1 2 {w}'.encode())
 def test_ali_annotation_not_weight(self):
  v,e,_=parse(b'p sample-name 3 1\na 1 2 7 999','ali');self.assertEqual(features(v,e)['active_weight'],7)
  with self.assertRaises(ValueError):parse(b'p sp 3 1\na 1 2 7 999')
 def test_wiki_multiplicity_and_unicode(self):
  data="c Converted from Wikimedia clickstream TSV\nc keep_types=('link',) min_weight=5 skip_self_loops=True\na α β 5 1\na α β 5 1\na β α 10 1\nc kept_arcs=3 skipped_rows=0\n".encode()
  v,e,ids=parse(data,'wiki');f=features(v,e);self.assertEqual((f['m'],f['unique_directed_pairs'],f['parallel_record_excess']),(3,2,1));self.assertEqual(f['active_weight'],20);self.assertEqual(f['density'],1);self.assertEqual(f['arc_record_density'],1.5);self.assertEqual(f['cyclic_edge_fraction'],1)
  with self.assertRaises(ValueError):parse(data.replace(b'kept_arcs=3',b'kept_arcs=4'),'wiki')
 def test_weight_variant_identity(self):
  a=parse(b'p sp 3 1\na 1 2 5')[2];b=parse(b'p sp 3 1\na 1 2 7')[2];self.assertNotEqual(a['weighted_sha256'],b['weighted_sha256']);self.assertEqual(a['topology_sha256'],b['topology_sha256']);self.assertNotEqual(a['topology_sha256'],parse(b'p sp 2 1\na 1 2 5')[2]['topology_sha256'])
 def test_stats(self):
  s=stats([1,1,1,1]);self.assertEqual(s['cv'],0);self.assertEqual(s['gini'],0);self.assertEqual(s['hhi'],.25)
  s=stats([0,0,0,4]);self.assertEqual(s['gini'],.75);self.assertEqual(s['top_decile_share'],1)
 def test_ties(self):
  v,e,_=parse(b'p sp 3 3\na 1 2 5\na 2 3 5\na 3 1 10');f=features(v,e);self.assertEqual(f['tied_arc_fraction'],2/3);self.assertEqual(f['distinct_weights'],2)
 def test_scc_exhaustive_reachability_oracle(self):
  # All 4096 simple directed graphs on four vertices; mutual reachability oracle.
  edges=list(itertools.permutations(range(4),2))
  for mask in range(1<<12):
   adj=[[] for _ in range(4)];rev=[[] for _ in range(4)];reach=[[i==j for j in range(4)] for i in range(4)]
   for k,(u,v) in enumerate(edges):
    if mask&(1<<k):adj[u].append(v);rev[v].append(u);reach[u][v]=True
   for k in range(4):
    for i in range(4):
     for j in range(4):reach[i][j]=reach[i][j] or (reach[i][k] and reach[k][j])
   comp,sizes=scc(adj,rev)
   for i in range(4):
    for j in range(4):self.assertEqual(comp[i]==comp[j],reach[i][j] and reach[j][i])
if __name__=='__main__':unittest.main(verbosity=2)
