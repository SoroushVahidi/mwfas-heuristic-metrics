"""Independent graph/order rescoring and exact Fraction aggregation; no optimizer imports."""
import csv,io,json,hashlib,collections
from fractions import Fraction as F
METHODS=['insertion_lrta','insertion_wmsf','lrta','wmsf_l2','igraph_eades_weighted']
def rows(path):return list(csv.DictReader(io.StringIO(path.read_text())))
def verify(root,fs):
 original=rows(root/'selection/exp05_original_inventory.csv');canonical={r['run_id']:r for r in rows(root/'selection/exp05_canonical_runs.csv')};graphs={r['instance_id']:r for r in rows(root/'selection/exp05_canonical_graphs.csv')}
 assert len(original)==len(canonical)==760 and len(graphs)==38
 base=fs.Path('source/mwfas-exp05/production-output')
 for r in original:
  c=canonical[r['run_id']]
  for a,b in [('original_status','status'),('instance_id','instance_id'),('algorithm','algorithm'),('objective_weight','objective_weight'),('order_sha256','order_sha256'),('checkpoint_sha256','checkpoint_sha256')]:assert r[a]==c[b],(r['run_id'],a)
  assert r['source_parent']==graphs[r['instance_id']]['source_parent']
  p=base/'runs'/(r['run_id']+'.json');raw=p.read_bytes();cp=json.loads(raw)
  assert fs.sha(raw)==r['checkpoint_sha256'],r['run_id']
  assert cp['status']==r['original_status'] and cp['run_id']==r['run_id']
 lookup={(r['instance_id'],r['algorithm']):r for r in original if r['algorithm']in METHODS}
 ids=sorted(g for g in graphs if all(lookup[g,m]['original_status']=='PASS'for m in METHODS));assert len(ids)==37
 q={};details=[]
 normal={'directed':True,'node_labels':'1-based-integers','parallel_edges':'absent','self_loops':'absent','weight_type':'positive-integer'}
 for gid in ids:
  p=base/'graphs'/(gid+'.d');raw=p.read_bytes();n=None;arcs=[]
  for line in raw.decode().splitlines():
   t=line.split()
   if not t or t[0]=='c':continue
   if t[0]=='p':assert n is None and len(t)==4;n,m=map(int,t[2:])
   else:assert t[0]=='a'and len(t)in [4,5];arcs.append(tuple(map(int,t[1:4])))
  assert n>0 and len(arcs)==m and len({(u,v)for u,v,w in arcs})==m
  assert all(1<=u<=n and 1<=v<=n and u!=v and w>0 for u,v,w in arcs)
  total=sum(w for u,v,w in arcs);g=graphs[gid]
  h=hashlib.sha256(json.dumps({'format':'mwfas-exp03-graph-v1','normalization':normal,'vertices':list(range(1,n+1)),'arcs':sorted(arcs)},sort_keys=True,separators=(',',':')).encode()).hexdigest()
  assert h==g['graph_sha256'] and total==int(g['total_weight']) and n==int(g['n']) and m==int(g['m'])
  assert hashlib.sha256(raw).hexdigest()==g['dimacs_sha256']
  for method in METHODS:
   r=lookup[gid,method];op=base/'orders'/(r['run_id']+'.csv');b=op.read_bytes();rr=list(csv.DictReader(io.StringIO(b.decode())))
   assert hashlib.sha256(b).hexdigest()==r['order_sha256']
   assert len(rr)==n and sorted(int(z['Node ID'])for z in rr)==list(range(1,n+1))
   rank={int(z['Node ID']):int(z['Order'])for z in rr};assert sorted(rank.values())==list(range(n))
   value=sum(w for u,v,w in arcs if rank[u]>rank[v]);assert value==F(r['objective_weight'])
   q[gid,method]=F(value,total)
   details.append({'graph_id':gid,'source_parent':g['source_parent'],'method':method,'objective':value,'total_weight':total,'graph_path':str(p),'order_path':str(op),'order_sha256':r['order_sha256'],'checkpoint_path':str(base/'runs'/(r['run_id']+'.json'))})
 def mean(a):return sum(a,F())/len(a)
 def aggregate(selected):
  parents=sorted({graphs[g]['source_parent']for g in selected});v={m:mean([q[g,m]for g in selected])for m in METHODS};p={m:mean([mean([q[g,m]for g in selected if graphs[g]['source_parent']==z])for z in parents])for m in METHODS}
  return {'n_views':len(selected),'n_parents':len(parents),'view_exact':{m:str(x)for m,x in v.items()},'parent_exact':{m:str(x)for m,x in p.items()},'view_ranking':sorted(v,key=v.get),'parent_ranking':sorted(p,key=p.get)}
 full=aggregate(ids);parents=sorted({graphs[g]['source_parent']for g in ids});lopo={p:aggregate([g for g in ids if graphs[g]['source_parent']!=p])for p in parents}
 assert full['view_ranking']==METHODS and full['parent_ranking']==METHODS[:3]+[METHODS[4],METHODS[3]]
 assert all(v['parent_ranking'][:3]==METHODS[:3]for v in lopo.values())
 assert lopo['wiki_vote']['view_ranking'][:2]==METHODS[1::-1]
 complete200=[]
 for gid in graphs:
  r=[x for x in original if x['instance_id']==gid and x['algorithm']=='ipsns'and x['iteration_budget']=='200']
  if len(r)==3 and all(x['original_status']=='PASS'for x in r)and all(lookup[gid,m]['original_status']=='PASS'for m in ['lrta','wmsf_l2']):complete200.append(gid)
 assert len(complete200)==18 and {graphs[g]['source_parent']for g in complete200}=={'exiobase_lop_benchmark'}
 expected=json.loads((root/'receipts/parent_weighting_reproduction.json').read_text())
 for k,v in full.items():assert v==expected['full'][k]
 for p in parents:
  for k,v in lopo[p].items():assert v==expected['leave_one_parent_out'][p][k]
 counts=dict(collections.Counter(graphs[g]['source_parent']for g in ids));assert sorted(counts.values())==[1,2,4,30]
 return {'status':'PASS','complete_views':37,'orders_rescored':len(details),'parent_counts':counts,'full':full,'leave_one_parent_out':lopo,'complete200_ids':complete200,'original_status_counts':dict(collections.Counter(r['original_status']for r in original)),'witnesses':details}
