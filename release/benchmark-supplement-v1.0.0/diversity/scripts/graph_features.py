"""Strict graph parsing and linear-time directed-graph features; stdlib only."""
import hashlib,json,math,re
from collections import Counter
from pathlib import Path

def sha(data):return hashlib.sha256(data).hexdigest()
def digest(x):return sha(json.dumps(x,sort_keys=True,separators=(',',':')).encode())
def number(x):
 if not re.fullmatch(r'-?[0-9]+',x):raise ValueError('integer required')
 return int(x)
def parse(data,kind='integer'):
 arcs=[];header=None;comments=[]
 for line in data.decode('utf-8').splitlines():
  f=line.split()
  if not f:continue
  if f[0]=='c':comments.append(line);continue
  if f[0]=='p' and kind!='wiki':
   if header is not None or arcs or len(f)!=4 or (kind!='ali' and f[1] not in ('sp','graph')):raise ValueError('invalid graph header')
   header=tuple(number(x) for x in f[2:]);
   if min(header)<0:raise ValueError('negative declared size')
   continue
  if f[0]!='a' or len(f) not in ((4,5) if kind in ('wiki','ali') else (4,)):raise ValueError('invalid arc record')
  if kind!='wiki' and header is None:raise ValueError('arc before header')
  u,v=f[1:3] if kind=='wiki' else (number(f[1]),number(f[2]));w=number(f[3])
  if len(f)==5:
   a=number(f[4])
   if kind=='wiki' and a!=1:raise ValueError('wiki annotation not one')
  if u==v or w<=0:raise ValueError('loop or nonpositive weight forbidden')
  arcs.append((u,v,w))
 if kind=='wiki':
  vertices=sorted({v for u,v,w in arcs}|{u for u,v,w in arcs})
  if len(comments)!=3 or comments[:2]!=['c Converted from Wikimedia clickstream TSV',"c keep_types=('link',) min_weight=5 skip_self_loops=True"]:raise ValueError('wiki transformation contract')
  if not re.match(r'^c kept_arcs=\d+',comments[2]) or int(comments[2].split()[1].split('=')[1])!=len(arcs):raise ValueError('wiki count')
  h=hashlib.sha256(b'MWFAS-WIKIMEDIA-GRAPH-v1\n');pairs=Counter()
  def label(h,s):b=s.encode();h.update(len(b).to_bytes(8,'big'));h.update(b)
  for (u,v,w),count in sorted(Counter(arcs).items()):
   label(h,u);label(h,v);h.update(f'{w}:{count}\n'.encode());pairs[u,v]+=count
  weighted=h.hexdigest();h=hashlib.sha256(b'MWFAS-WIKIMEDIA-TOPOLOGY-v1\n')
  for (u,v),count in sorted(pairs.items()):label(h,u);label(h,v);h.update(f'{count}\n'.encode())
  topology=h.hexdigest()
 else:
  if header is None or header[1]!=len(arcs):raise ValueError('missing header/count mismatch')
  vertices=list(range(1,header[0]+1))
  if any(not 1<=v<=header[0] for a in arcs for v in a[:2]):raise ValueError('endpoint out of bounds')
  if len({(u,v) for u,v,w in arcs})!=len(arcs):raise ValueError('parallel arcs forbidden')
  weighted=digest({'format':'mwfas-exp03-graph-v1','normalization':{'directed':True,'node_labels':'1-based-integers','parallel_edges':'absent','self_loops':'absent','weight_type':'positive-integer'},'vertices':vertices,'arcs':sorted(arcs)})
  topology=digest({'format':'exp04-topology-v1','directed':True,'vertices':vertices,'arcs':sorted((u,v) for u,v,w in arcs)})
 return vertices,arcs,{'raw_sha256':sha(data),'weighted_sha256':weighted,'topology_sha256':topology,'vertex_universe':'incident_UTF8_labels_no_declared_isolates' if kind=='wiki' else 'complete_declared_1_to_n','topology_contract':'MWFAS-WIKIMEDIA-TOPOLOGY-v1' if kind=='wiki' else 'exp04-topology-v1'}

def scc(adj,rev):
 n=len(adj);seen=bytearray(n);finish=[]
 # Iterative DFS with explicit next-child cursors, no recursion limit.
 for start in range(n):
  if seen[start]:continue
  seen[start]=1;stack=[(start,0)]
  while stack:
   u,i=stack[-1]
   if i==len(adj[u]):finish.append(u);stack.pop();continue
   stack[-1]=(u,i+1);v=adj[u][i]
   if not seen[v]:seen[v]=1;stack.append((v,0))
 comp=[-1]*n;sizes=[]
 for start in reversed(finish):
  if comp[start]>=0:continue
  c=len(sizes);comp[start]=c;stack=[start];size=0
  while stack:
   u=stack.pop();size+=1
   for v in rev[u]:
    if comp[v]<0:comp[v]=c;stack.append(v)
  sizes.append(size)
 return comp,sizes

def stats(values):
 n=len(values);total=sum(values)
 if not n:return dict(min=None,max=None,mean=None,cv=None,skew=None,gini=None,top_decile_share=None,hhi=None)
 mean=total/n;var=math.fsum((x-mean)**2 for x in values)/n;sd=math.sqrt(var)
 ordered=sorted(values);gini=(2*sum(i*x for i,x in enumerate(ordered,1))/(n*total)-(n+1)/n) if total else 0.0
 return dict(min=ordered[0],max=ordered[-1],mean=mean,cv=sd/mean if mean else 0.0,skew=math.fsum(((x-mean)/sd)**3 for x in values)/n if sd else 0.0,gini=gini,top_decile_share=sum(ordered[-math.ceil(n/10):])/total if total else 0.0,hhi=sum(x*x for x in values)/(total*total) if total else 0.0)

def features(vertices,arcs):
 n=len(vertices);m=len(arcs);index={v:i for i,v in enumerate(vertices)};adj=[[] for _ in vertices];rev=[[] for _ in vertices]
 for u,v,w in arcs:a=index[u];b=index[v];adj[a].append(b);rev[b].append(a)
 comp,sizes=scc(adj,rev);pairs={(index[u],index[v]) for u,v,w in arcs};weights=[w for u,v,w in arcs]
 cyc_edges=sum(comp[index[u]]==comp[index[v]] and sizes[comp[index[u]]]>1 for u,v,w in arcs)
 cyclic_weight=sum(w for u,v,w in arcs if comp[index[u]]==comp[index[v]] and sizes[comp[index[u]]]>1)
 indeg=list(map(len,rev));outdeg=list(map(len,adj));degree=[a+b for a,b in zip(indeg,outdeg)]
 freq=Counter(weights);weight=stats(weights);din=stats(indeg);dout=stats(outdeg);dtot=stats(degree)
 result={'n':n,'m':m,'unique_directed_pairs':len(pairs),'parallel_record_excess':m-len(pairs),'density':len(pairs)/(n*(n-1)) if n>1 else 0.,'arc_record_density':m/(n*(n-1)) if n>1 else 0.,'isolated_vertices':sum(x==0 for x in degree),'scc_count':len(sizes),'nontrivial_scc_count':sum(s>1 for s in sizes),'largest_scc_size':max(sizes,default=0),'largest_scc_fraction':max(sizes,default=0)/n if n else 0.,'edges_in_nontrivial_sccs':cyc_edges,'cyclic_edge_fraction':cyc_edges/m if m else 0.,'cyclic_vertex_fraction':sum(s for s in sizes if s>1)/n if n else 0.,'cyclic_weight_fraction':cyclic_weight/sum(weights) if weights else 0.,'reciprocal_edge_fraction':sum((v,u) in pairs for u,v in pairs)/len(pairs) if pairs else 0.,'active_weight':sum(weights),'distinct_weights':len(freq),'weight_range':max(weights)-min(weights) if weights else None,'weight_max_min_ratio':max(weights)/min(weights) if weights else None,'tied_arc_fraction':sum(c for c in freq.values() if c>1)/m if m else None,'weight_duplicate_excess_fraction':1-len(freq)/m if m else None,'unit_weight':bool(weights) and all(w==1 for w in weights)}
 for prefix,val in [('in_degree',din),('out_degree',dout),('total_degree',dtot),('weight',weight)]:result.update({prefix+'_'+k:v for k,v in val.items()})
 return result
