"""Read-only independent witness checker; never imports or invokes method/auditor code.
Usage: python - EXP29|EXP30_SIMPLE|EXP30_WIKI|EXP30_LODES|EXP30_IRS < this_file
Executed over SSH with stdout captured only in the new local audit directory.
All event-associated saved orders are rescored, not merely final summaries.
"""
import sys,json,csv,io,hashlib,time,collections,re

import numpy as np
START=time.monotonic();MODE=MODE_ARGUMENT;EXP='exp29'if MODE=='EXP29'else'exp30'
BASE=Path('source/mwfas-overnight-20261019')
VIEW=BASE/f'recovery-20261019/output/{EXP}-70ab586-v2/independent_combined_view'
FILES={};CACHE={};ERR=[]
def sha(b):return fs.sha(b)  # Original identity for sanitized provenance; storage bytes checked separately.
def read(p):
 p=Path(p);b=p.read_bytes();FILES[str(p)]={'sha256':sha(b),'bytes':len(b),'mtime_ns':p.stat().st_mtime_ns};return b
def obj(p):return json.loads(read(p))
def check(c,msg):
 if not c:raise ValueError(msg)
M=obj(VIEW/'manifest.json');P=obj(M['protocol_path']);OM=obj(Path(M['original_output'])/'manifest.json')
SEL={x['task_id']:x for x in csv.DictReader(io.StringIO(read(VIEW/'recovery_selection.csv').decode()))}
INVENTORY={x['task_id']:x for x in csv.DictReader(io.StringIO(read(VIEW/'task_inventory.csv').decode()))}
A=obj(VIEW/'audit_report.json');GLOBAL=[]
try:
 check(sha(Path(M['protocol_path']).read_bytes())==M['protocol_sha256'],'protocol hash')
 check(M['tasks']==P['tasks']==OM['tasks'],'frozen task roster')
 check(len(P['tasks'])==P['max_tasks'] and sum(x['cap_seconds']for x in P['tasks'])==P['nominal_cap_seconds'],'roster totals')
 check(sha(Path(OM['protocol_path']).read_bytes())==OM['protocol_sha256']==M['protocol_sha256'],'original protocol hash')
 check(sha(Path(M['original_output'],'manifest.json').read_bytes())==M['original_manifest_sha256'],'original manifest pin')
 check(sha(read(M['graph_paths_file']))==M['graph_paths_sha256'],'graph path map')
 check(sha(read(M['recovery_plan_path']))==M['recovery_plan_sha256'],'recovery selection pin')
 for manifest,version in [(OM,'v1'),(M,'v2')]:
  release=Path(manifest['release'])/'experiments/overnight_20261019'
  names=[('worker.py','worker_sha256'),('ipsns_pinned_instrumented.py','instrumented_ipsns_sha256'),('campaign.py'if version=='v1'else'campaign_v2.py','controller_sha256')]
  if version=='v2':names.append(('deadline_v2.py','deadline_module_sha256'))
  for fn,key in names:check(sha(read(release/fn))==manifest[key],version+' '+fn+' source pin')
 for key in ['worker_sha256','instrumented_ipsns_sha256','ipsns_file_sha256','xiong_binary_sha256','baseline_revision','xiong_revision','adapter_release_revision']:
  check(M[key]==OM[key],'algorithm differs across controller: '+key)
 check(sha(read('source/mwfas-exp05/sources/pinned-upstream/src/mwfas/ipsns.py'))==M['ipsns_file_sha256'],'IPSNS baseline pin')
 check(fs.records['source/mwfas-exp10-xiong/build/fas_alg']['sha256']==M['xiong_binary_sha256'],'RAS recorded executable identity (binary excluded)')
except Exception as e:GLOBAL.append(str(e))
NORMAL={'directed':True,'node_labels':'1-based-integers','parallel_edges':'absent','self_loops':'absent','weight_type':'positive-integer'}
GRAPHS={}
def graph(gid):
 if gid in CACHE:return CACHE[gid]
 cfg=P['graphs'][gid];ip=M['inputs'][gid];path=Path(ip['path']);raw=read(path);n=None;m=None;arcs=[]
 for line in raw.decode().splitlines():
  t=line.split()
  if not t or t[0]=='c':continue
  if t[0]=='p':check(n is None and len(t)==4 and t[1]in ['sp','graph'],'graph header');n,m=map(int,t[2:])
  else:
   check(t[0]=='a'and n is not None and len(t)in [4,5],'arc format')
   if len(t)==5:int(t[4])
   arcs.append(tuple(map(int,t[1:4])))
 check(n>0 and len(arcs)==m,'declared vertices/arc count');check(len({(u,v)for u,v,w in arcs})==m,'parallel arcs')
 check(all(1<=u<=n and 1<=v<=n and u!=v and w>0 for u,v,w in arcs),'positive loop-free graph')
 total=sum(w for u,v,w in arcs);check(total<2**63,'integer accumulator bound')
 canonical=sha(json.dumps({'format':'mwfas-exp03-graph-v1','normalization':NORMAL,'vertices':list(range(1,n+1)),'arcs':sorted(arcs)},sort_keys=True,separators=(',',':')).encode())
 check((sha(raw),canonical,n,m,total)==(cfg['dimacs_sha256'],cfg['canonical_graph_sha256'],cfg['n'],cfg['m'],cfg['total_weight']),'graph identity/config mismatch')
 check(canonical==ip['graph_sha256'],'manifest weighted identity')
 GRAPHS[gid]={'path':str(path),'file_sha256':sha(raw),'graph_sha256':canonical,'n':n,'m':m,'total_weight':total,'family':cfg['family'],'source_parent':cfg['source_parent'],'protocol_topology_sha256':cfg.get('topology_sha256'),'generation_seed':cfg.get('generation_seed_actual'),'weight_seed':cfg.get('weight_seed')}
 aa=np.array(arcs,dtype=np.int64);CACHE[gid]=(n,arcs,aa[:,0]-1,aa[:,1]-1,aa[:,2]);return CACHE[gid]
def ranks(raw,arm,n):
 if arm.startswith('xiong'):values=list(map(int,raw.split()))
 else:
  rs=list(csv.DictReader(io.StringIO(raw.decode())));check(len(rs)==n,'CSV length');ids=[int(r['Node ID'])for r in rs];check(sorted(ids)==list(range(1,n+1)),'vertex coverage');values=[None]*n
  for row in rs:values[int(row['Node ID'])-1]=int(row['Order'])
 check(sorted(values)==list(range(n)),'complete rank permutation');return np.array(values,dtype=np.int64)
def scalar_dag_check(rank,arcs,n):
 cost=0;adj=[[]for _ in range(n)];deg=[0]*n
 for u,v,w in arcs:
  if int(rank[u-1])>int(rank[v-1]):cost+=w
  else:adj[u-1].append(v-1);deg[v-1]+=1
 queue=collections.deque(i for i,x in enumerate(deg)if x==0);cnt=0
 while queue:
  u=queue.popleft();cnt+=1
  for v in adj[u]:
   deg[v]-=1
   if deg[v]==0:queue.append(v)
 check(cnt==n,'retained DAG');return cost
TASKS=[]
for t in P['tasks']:
 if MODE=='EXP29':keep=(t['arm']=='ipsns'and t['seed']==2901)or(t['arm']=='xiong_single'and t['seed']==1)
 elif MODE=='EXP30_SIMPLE':keep=t['arm']!='xiong_restarts'
 else:keep=t['arm']=='xiong_restarts'and {'EXP30_WIKI':'wiki','EXP30_LODES':'lodes','EXP30_IRS':'irs'}[MODE]in t['graph_id']
 if keep:TASKS.append(t)
RESULTS=[]
for t in TASKS:
 tid=t['task_id'];row={'task_id':tid,'graph_id':t['graph_id'],'arm':t['arm'],'seed':t['seed'],'cap_seconds':t['cap_seconds'],'validation':'FAIL','errors':[]}
 try:
  sel=SEL[tid];root=Path(sel['selected_output']);version=sel['controller_stratum'];row.update(controller=version,selection=sel['selection'],original_status=sel['original_status'],selected_output=str(root))
  if MODE=='EXP29':check(version=='v1'and sel['selection']=='PRESERVE'and root==Path(M['original_output']),'posthoc subset must use original v1 only')
  cpp=root/'checkpoints'/f'{tid}.json';cp=obj(cpp);cph=FILES[str(cpp)]['sha256'];row['checkpoint_path']=str(cpp);row['checkpoint_sha256']=cph
  check(cph==sel['selected_checkpoint_sha256']==sha(read(VIEW/'checkpoints'/f'{tid}.json')),'checkpoint selection identity')
  if sel['selection']=='PRESERVE':check(cph==sel['original_checkpoint_sha256'],'original checkpoint changed')
  for k,v in t.items():check(cp.get(k)==v,'task configuration '+k)
  check(cp['status']in ['PASS','TIMEOUT']and cp['status']==sel['selected_status']==INVENTORY[tid]['status'],'valid status')
  row['recorded_status']=cp['status'];check(0<=cp['task_wall_seconds']<=t['cap_seconds']and cp['wall_budget_compliant'],'task cap')
  check(abs((cp['end_unix_ns']-cp['start_unix_ns'])/1e9-cp['task_wall_seconds'])<=2,'clock agreement')
  check(abs(cp['deadline_monotonic']-cp['start_monotonic']-t['cap_seconds'])<1e-6,'monotonic cap')
  end=cp['start_unix_ns']+t['cap_seconds']*10**9;check(cpp.stat().st_mtime_ns<=end,'final checkpoint publication beyond deadline')
  pub_elapsed=(cpp.stat().st_mtime_ns-cp['start_unix_ns'])/1e9
  if version=='v2':
   pub=obj(cpp.with_suffix('.publication.json'));check(pub['task_id']==tid and pub['checkpoint_sha256']==cph and pub['effective_status']==cp['status'],'publication receipt identity')
   check(0<=pub['published_elapsed_seconds']<t['cap_seconds']and pub['publication_observed_unix_ns']<=end,'publication receipt deadline');pub_elapsed=max(pub_elapsed,pub['published_elapsed_seconds'])
  row.update(task_wall_seconds=cp['task_wall_seconds'],checkpoint_publication_seconds=pub_elapsed,deadline_margin_seconds=t['cap_seconds']-max(pub_elapsed,cp['task_wall_seconds']))
  cmd=cp['command'];options={cmd[i]:cmd[i+1]for i in range(len(cmd)-1)if cmd[i].startswith('--')}
  for arg,val in [('arm',t['arm']),('seed',str(t['seed'])),('task-id',tid),('graph-sha256',t['graph_sha256'])]:check(options['--'+arg]==val,'invocation '+arg)
  check(Path(options['--graph'])==Path(M['inputs'][t['graph_id']]['path']),'command graph');check(Path(options['--folder'])==root/'tasks'/tid,'command output origin')
  check(float(options['--internal-reserve-seconds'])==P['worker_internal_reserve_seconds'],'worker timing config')
  folder=root/'tasks'/tid;check(sha(read(folder/'process.log'))==cp['log_sha256'],'process log hash');n,arcs,u,v,w=graph(t['graph_id'])
  if t['arm'].startswith('xiong'):
   wr=[tuple(map(int,l.split()))for l in read(folder/'input.w').decode().splitlines()];check(wr[0]==(n,len(arcs))and collections.Counter(wr[1:])==collections.Counter((a-1,b-1,c)for a,b,c in arcs),'weighted conversion')
  events=sorted(folder.glob('event_*.json'));check(len(events)==cp['event_count']and len(events)>0,'event count')
  if t['arm']=='xiong_single':check(len(events)==1,'single-run invocation count')
  horizons=[120]if MODE=='EXP29'else[120,300];best={h:None for h in horizons};ordercache={};prev=None;chain=hashlib.sha256();first=None
  for ix,ep in enumerate(events):
   eraw=ep.read_bytes();event=json.loads(eraw);check(ep.name==f'event_{ix:06d}.json'and event['index']==ix and event['task_id']==tid,'event identity')
   seed=t['seed']if ix==0 or not t['arm'].startswith('xiong')else 1+((t['seed']*1000003+ix*104729)%2147483646);check(event['seed']==seed,'event seed')
   check(0<=event['elapsed_seconds']<t['cap_seconds']and cp['start_monotonic']<=event['saved_monotonic']<cp['deadline_monotonic'],'event deadline')
   check(abs(event['saved_monotonic']-cp['start_monotonic']-event['elapsed_seconds'])<1e-6,'event clock')
   op=folder/event['order_file'];check(op.parent==folder,'order path escape');raw=op.read_bytes();digest=sha(raw);check(digest==event['order_sha256'],'order hash')
   observed=max(event['elapsed_seconds'],(max(ep.stat().st_mtime_ns,op.stat().st_mtime_ns)-cp['start_unix_ns'])/1e9);check(observed<=t['cap_seconds'],'order/event publication after cap')
   if digest not in ordercache:
    rank=ranks(raw,t['arm'],n);value=int(w[rank[u]>rank[v]].sum(dtype=np.int64));ordercache[digest]=value
   value=ordercache[digest];check(value==event['reported_objective'],'rescored objective mismatch')
   if t['arm']=='ipsns':
    x=event['extra'];check(x['graph_sha256']==t['graph_sha256']and x['kind']in ['wmsf_seed','lr_seed_improvement','complete_initializer','refinement_improvement']and 0<=x['iteration']<=P['ipsns']['iters'],'IPSNS phase/config')
    if ix==0:check(x['kind']=='wmsf_seed'and x['iteration']==0,'first initializer')
    if prev:
     check(value<=prev['reported_objective']and event['elapsed_seconds']>=prev['elapsed_seconds']and x['iteration']>=prev['extra']['iteration'],'incumbent sequence')
     if x['kind']in ['lr_seed_improvement','refinement_improvement']:check(value<prev['reported_objective'],'non-strict improvement')
   else:
    stdout=folder/f'xiong_{ix:06d}.stdout';sr=stdout.read_bytes();check(sha(sr)==event['extra']['stdout_sha256'],'native stdout hash');parts=sr.decode().strip().split(',');check(len(parts)==3 and int(parts[1])==value,'native reported score')
   entry={'objective':value,'observed_seconds':observed,'event_index':ix,'event_path':str(ep),'event_sha256':sha(eraw),'order_path':str(op),'order_sha256':digest}
   for h in horizons:
    if observed<=h and (best[h]is None or value<best[h]['objective']):best[h]=entry
   chain.update(json.dumps([str(ep),sha(eraw),str(op),digest,value,observed],separators=(',',':')).encode()+b'\n');first=observed if first is None else min(first,observed);prev=event
  check(all(best.values()),'no available horizon witness')
  for h,x in best.items():check(scalar_dag_check(ranks(Path(x['order_path']).read_bytes(),t['arm'],n),arcs,n)==x['objective'],'scalar/DAG crosscheck')
  if t['arm']=='ipsns'and cp['status']=='PASS':
   c=obj(folder/'ipsns_completion.json');check(c['termination_reason']=='completed'and c['iterations']<=P['ipsns']['iters'],'IPSNS completion');raw=read(folder/'raw_order.csv');check(sha(raw)==c['raw_order_sha256'],'raw final pin');rs=list(csv.DictReader(io.StringIO(raw.decode())));ids={int(x['Node ID'])for x in rs};missing=set(range(1,n+1))-ids;check(not(missing & {z for a,b,c in arcs for z in [a,b]}),'raw omitted incident vertex')
   # A raw method output may omit isolated vertices; publication must cover all n.
   row['raw_final_omitted_isolates']=len(missing)
  check(best[max(horizons)]['objective']==int(INVENTORY[tid]['objective']),'inventory objective')
  row.update(validation='PASS',event_orders_checked=len(events),unique_order_bytes=len(ordercache),event_order_validation_chain_sha256=chain.hexdigest(),first_observed_seconds=first,horizons=best)
 except Exception as e:row['errors'].append(str(e));ERR.append({'task_id':tid,'error':str(e)})
 RESULTS.append(row)
RESULT = {'mode':MODE,'experiment':EXP,'independent_validator':'independent_witness_validator.py','elapsed_seconds':time.monotonic()-START,'numpy':np.__version__,'global_errors':GLOBAL,'task_errors':ERR,'graphs':GRAPHS,'tasks':RESULTS,'source_files':FILES,'original_manifest':OM,'recovery_manifest':M,'protocol':P,'retained_overall_campaign_audit':A}
