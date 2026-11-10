"""Independent parser + SciPy SCC implementation; does not import feature code."""
import csv,json,math,hashlib,sys
from pathlib import Path
import numpy as np
import scipy
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
root=Path(sys.argv[1]);features=list(csv.DictReader((root/'GRAPH_DIVERSITY_FEATURES.tsv').open(),delimiter='\t'));ledger={r['benchmark_record_id']:r for r in csv.DictReader((root/'inputs/RECORD_AVAILABILITY_LEDGER.tsv').open(),delimiter='\t')};checks=[]
for r in features:
 raw=Path(ledger[r['graph_id']]['candidate_input_file']).read_bytes();wiki=r['cohort']=='EXP14_EXP15';edges=[];declared=None
 for line in raw.decode().splitlines():
  f=line.split()
  if not f or f[0]=='c':continue
  if f[0]=='p':declared=(int(f[2]),int(f[3]));continue
  assert f[0]=='a';edges.append((f[1],f[2],int(f[3])))
 vertices=sorted({v for u,v,w in edges}|{u for u,v,w in edges}) if wiki else [str(i) for i in range(1,declared[0]+1)]
 assert wiki or declared[1]==len(edges)
 index={v:i for i,v in enumerate(vertices)};u=np.array([index[u] for u,v,w in edges]);v=np.array([index[v] for u,v,w in edges]);n=len(vertices);m=len(edges)
 matrix=csr_matrix((np.ones(m,dtype=np.int64),(u,v)),shape=(n,n));count,labels=connected_components(matrix,directed=True,connection='strong');sizes=np.bincount(labels);indeg=np.bincount(v,minlength=n);outdeg=np.bincount(u,minlength=n);internal=(labels[u]==labels[v])&(sizes[labels[u]]>1);weights=[w for u,v,w in edges]
 expected={'n':n,'m':m,'scc_count':count,'largest_scc_size':int(max(sizes,default=0)),'nontrivial_scc_count':int(sum(sizes>1)),'isolated_vertices':int(sum(indeg+outdeg==0)),'in_degree_max':int(max(indeg,default=0)),'out_degree_max':int(max(outdeg,default=0)),'active_weight':sum(weights),'weight_min':min(weights),'weight_max':max(weights),'distinct_weights':len(set(weights)),'edges_in_nontrivial_sccs':int(sum(internal))}
 assert all(int(r[k])==val for k,val in expected.items()),(r['graph_id'],expected)
 assert math.isclose(float(r['cyclic_vertex_fraction']),sum(sizes[sizes>1])/n,abs_tol=1e-14)
 assert math.isclose(float(r['weight_mean']),sum(weights)/m,abs_tol=1e-12)
 assert math.isclose(float(r['in_degree_mean']),m/n,abs_tol=1e-12)
 assert r['raw_sha256']==hashlib.sha256(raw).hexdigest()
 l=ledger[r['graph_id']];assert r['parent_id']==l['source_parent_id'];assert r['public_availability']==l['public_availability_status'];assert r['rights_class']==l['rights_classification'];assert int(r['saved_outcomes_verified'])==int(l['independently_checked_objective_count'])
 checks.append({'graph_id':r['graph_id'],'status':'PASS','method':'independent parser + scipy.sparse.csgraph SCC + degree/weight/provenance checks'})
with (root/'evidence/INDEPENDENT_CONSISTENCY.tsv').open('w') as f:
 w=csv.DictWriter(f,checks[0].keys(),delimiter='\t');w.writeheader();w.writerows(checks)
print(json.dumps({'records':len(checks),'status':'PASS','numpy':np.__version__,'scipy':scipy.__version__,'python':sys.version},indent=2))
