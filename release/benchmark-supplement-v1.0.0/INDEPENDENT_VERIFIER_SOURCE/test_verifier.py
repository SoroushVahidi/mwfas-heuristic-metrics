import itertools, tempfile, unittest
from pathlib import Path
from mwfas_benchmark import Graph,parse_graph,load_order,evaluate,compare,identities

class VerifierTests(unittest.TestCase):
    def test_known_cycle(self):
        g=parse_graph('p sp 4 3\na 1 2 7\na 2 3 5\na 3 1 2\n')
        self.assertEqual(evaluate(g,[1,2,3,4])['objective'],2)
        self.assertEqual(evaluate(g,[3,2,1,4])['objective'],12)
    def test_empty(self):self.assertEqual(evaluate(parse_graph('p sp 0 0'),[])['objective'],0)
    def test_isolates(self):self.assertEqual(evaluate(parse_graph('p sp 3 0'),[3,1,2])['objective'],0)
    def test_missing_isolate(self):
        with self.assertRaises(ValueError):evaluate(parse_graph('p sp 3 0'),[1,2])
    def test_bad_order(self):
        g=parse_graph('p sp 3 0')
        for order in [[1,1,3],[1,2],[1,2,4],[0,1,2],['1',2,3],[True,2,3],[1.,2,3],[1,2,3,3]]:
            with self.subTest(order=order),self.assertRaises(ValueError):evaluate(g,order)
    def test_bad_headers(self):
        for s in ['', 'a 1 2 1','p xx 0 0','p sp -1 0','p sp 1 -1','p sp 0 0\np sp 0 0','p sp 1 0 extra','p sp 1.0 0','p sp 2 1','p sp 2 0\na 1 2 1']:
            with self.subTest(s=s),self.assertRaises(ValueError):parse_graph(s)
    def test_bad_weights(self):
        for w in ['0','-1','NaN','nan','inf','-Infinity','1.0','1e3']:
            with self.subTest(w=w),self.assertRaises(ValueError):parse_graph('p sp 2 1\na 1 2 '+w)
    def test_self_loop(self):
        with self.assertRaises(ValueError):parse_graph('p sp 1 1\na 1 1 2')
    def test_duplicates(self):
        with self.assertRaises(ValueError):parse_graph('p sp 2 2\na 1 2 1\na 1 2 2')
    def test_antiparallel(self):self.assertEqual(evaluate(parse_graph('p sp 2 2\na 1 2 3\na 2 1 5'),[1,2])['objective'],5)
    def test_invalid_endpoints(self):
        for u,v in [('0','2'),('1','3'),('-1','2'),('a','2'),('1.0','2')]:
            with self.subTest(u=u,v=v),self.assertRaises(ValueError):parse_graph(f'p sp 2 1\na {u} {v} 1')
    def test_unknown_and_malformed_records(self):
        for line in ['e 1 2 3','a 1 2','a 1 2 3 4','n 1']:
            with self.subTest(line=line),self.assertRaises(ValueError):parse_graph('p sp 2 1\n'+line)
    def test_huge_integer_exact(self):self.assertEqual(evaluate(parse_graph(f'p sp 2 1\na 2 1 {2**100+1}'),[1,2])['objective'],2**100+1)
    def test_hash_contract(self):
        a=parse_graph('p sp 3 2\na 1 2 3\na 2 1 5');b=parse_graph('c comment\np sp 3 2\na 2 1 5\na 1 2 3');c=parse_graph('p sp 3 2\na 1 2 4\na 2 1 5')
        self.assertEqual(identities(a),identities(b));self.assertEqual(identities(a)['topology_sha256'],identities(c)['topology_sha256']);self.assertNotEqual(identities(a)['weighted_sha256'],identities(c)['weighted_sha256'])
        self.assertNotEqual(identities(a),identities(parse_graph('p sp 2 2\na 1 2 3\na 2 1 5')))
    def test_direct_graph_rejects_invalid(self):
        for arcs in [((1,1,1),),((1,2,float('nan')),),((1,2,float('inf')),),((True,2,1),),((1,2,1),(1,2,2))]:
            with self.subTest(arcs=arcs),self.assertRaises(ValueError):Graph((1,2),arcs)
    def test_csv(self):
        g=parse_graph('p sp 3 0')
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as d:
            p=Path(d)/'order.csv';p.write_text('Node ID,Order\n3,2\n1,0\n2,1\n');self.assertEqual(load_order(p,g),(1,2,3))
            for content in ['Node ID,Order\n1,0\n2,1\n2,2','Node ID,Order\n1,0\n2,0\n3,2','Node ID,Order\n1,1\n2,2\n3,3','Node ID,Order\n1,0\n2,1','Node ID,Order\n1,0,x\n2,1\n3,2','Node ID,Order\n1,0\n2,NaN\n3,2','node,rank\n1,0']:
                p.write_text(content)
                with self.subTest(content=content),self.assertRaises(ValueError):load_order(p,g)
    def test_zero_reference(self):
        g=parse_graph('p sp 2 1\na 2 1 3');self.assertIsNone(compare(g,[1,2],0)['relative_gap']);self.assertEqual(compare(g,[2,1],0)['relative_gap'],0)
    def test_negative_gap_allowed_to_feasible_reference(self):self.assertEqual(compare(parse_graph('p sp 2 1\na 1 2 3'),[1,2],3)['absolute_gap'],-3)
    def test_exhaustive_small_graphs(self):
        # All 64 directed simple labeled graphs on three vertices, all six
        # permutations. Oracle sums every right-to-left ordered vertex pair.
        edges=list(itertools.permutations(range(1,4),2))
        for mask in range(64):
            arcs=tuple((u,v,i+1) for i,(u,v) in enumerate(edges) if mask&(1<<i));g=Graph((1,2,3),arcs);weights={(u,v):w for u,v,w in arcs}
            for order in itertools.permutations(g.vertices):
                oracle=sum(weights.get((order[j],order[i]),0) for i in range(3) for j in range(i+1,3))
                self.assertEqual(evaluate(g,order)['objective'],oracle)
if __name__=='__main__':unittest.main(verbosity=2)
