"""Anonymous graph/order accessibility audit; no optimizer and no private data input."""
from pathlib import Path
import sys,json,csv,hashlib,tarfile,urllib.request,io,collections,time,subprocess,os
sys.dont_write_bytecode=True
ROOT=Path(sys.argv[1]).resolve();ROOT.mkdir(parents=True,exist_ok=False);START=time.monotonic();downloads=[]
BASE='https://huggingface.co/datasets/SoroushVahidi/mwfas-benchmark-extension/resolve/'
SREV='c34b0e08119db316100d7bc2bde8ddf81943492b';OLD='1e9db1daa5401b56398e9807d4e48d989d9f0eab'
def digest(b):return hashlib.sha256(b).hexdigest()
def fetch(url,name,expected=None):
 p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True)
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'MWFAS-anonymous-access-audit/1'}),timeout=60) as r:b=r.read();status=r.status
 h=digest(b);assert expected is None or h==expected,(name,h);p.write_bytes(b);downloads.append({'url':url,'sha256':h,'bytes':len(b),'authentication':False,'http_status':status});return p
archives=[('supplement',SREV+'/releases/benchmark-supplement-v1.0.0/benchmark-supplement-v1.0.0.tar.gz','eb8f4b1802d312c6762a0365166f5ac96d4a2f0e1d9c9f69aa728bc780018b79'),('table45','33902c7cc409794a43c17fc5428cf022f440da48/releases/table45-v2-20261019/table45.tar.gz','b74e37bed3a91ec986fe8526a73f5a990a144ca931ee013cc1a8fe4f882f3e2d'),('remaining','667e164d0768d635a73692cd594801f10fe12382/releases/remaining-v1-20261019/remaining.tar.gz','152b8ac7917eebaa66d9df4facc3500911ff67ce65f5c50df3c3e2bd1609d6c7')]
for name,url,h in archives:
 p=fetch(BASE+url,'downloads/'+name+'.tar.gz',h);d=ROOT/name;d.mkdir()
 with tarfile.open(p) as t:
  for m in t.getmembers():assert (m.isfile() or m.isdir()) and (d/m.name).resolve().is_relative_to(d)
  t.extractall(d,filter='data')
S=ROOT/'supplement/benchmark-supplement-v1.0.0';T=ROOT/'table45/table45';D=ROOT/'remaining';M=json.loads((S/'PACKAGE_MANIFEST.json').read_text())
for r in M['files']:assert digest((S/r['path']).read_bytes())==r['sha256']
sys.path[:0]=[str(S/'profile_tools/upstream'),str(S/'profile_tools'),str(S/'diversity/scripts')]
from sources import Fetcher,recover
from graph_features import parse
from evidence import score
rows=lambda p:list(csv.DictReader(p.open(),delimiter='\t' if p.suffix=='.tsv' else ','))
graphs=rows(S/'metadata/graphs-v1.1.csv');outcomes=rows(S/'supplied_manifests/run_outcomes.csv');refs=rows(S/'supplied_manifests/numerical_references.csv');features=rows(S/'diversity/GRAPH_DIVERSITY_FEATURES.tsv');remaining=json.loads((D/'data.json').read_text());specs={g['canonical']:g for pkg in remaining['packages'].values() for g in pkg['graphs']};extra=S/'supplementary-evidence/objects';f=Fetcher(ROOT/'upstream');access=[];parsed={};orderbytes={};locations={}
# Raw serialized hashes bind references to released members without trusting local paths.
for path in T.rglob('*.csv'):
 if '/orders/' in str(path):h=digest(path.read_bytes());orderbytes[h]=path;locations[h]=('table45',str(path.relative_to(ROOT/'table45')))
for path in (D/'objects').iterdir():orderbytes[path.name]=path;locations[path.name]=('remaining','objects/'+path.name)
for name in ['arwiki202512','arwiki202601','azwiki202512']:
 for suffix in ['paper_fas_ranking','wmsf_ranking']+(['dimacs_hybrid_ranking-48cpu','dimacs_scc_init'] if name!='arwiki202601' else []):
  member='data/wikimedia/'+name+'_'+suffix+'.csv';p=fetch(BASE+OLD+'/'+member,'wikimedia/'+Path(member).name);h=digest(p.read_bytes());orderbytes[h]=p;locations[h]=('wikimedia',member)
print('Downloaded archives and order witnesses',flush=True)
for g in graphs:
 h=g['serialized_graph_sha256'];cohort=g['cohort'];member='';route='PUBLIC_RELEASE_BYTES'
 if cohort in ('EXP04','EXP06'):
  member=f'mwfas-{cohort.lower()}/production-output/graphs/{g["instance_id"]}.d';p=T/member;b=p.read_bytes();package='table45';member='table45/'+member
 elif cohort=='EXP03':s=specs[g['canonical_graph_sha256']];member='objects/'+s['object'];b=(D/member).read_bytes();package='remaining'
 elif cohort=='EXP14_EXP15':member='data/wikimedia/'+g['instance_id']+'.d';b=fetch(BASE+OLD+'/'+member,'wikimedia/'+Path(member).name,h).read_bytes();package='wikimedia'
 elif (extra/h).is_file():b=(extra/h).read_bytes();package='supplement';member='benchmark-supplement-v1.0.0/supplementary-evidence/objects/'+h
 elif g['parent_id']=='openflights':member='benchmark-supplement-v1.0.0/licensed-inputs/openflights/'+g['instance_id']+'.d';b=(S/'licensed-inputs/openflights'/ (g['instance_id']+'.d')).read_bytes();package='supplement'
 else:b=recover(specs[g['canonical_graph_sha256']],f);package='upstream';route='PUBLIC_UPSTREAM_RECONSTRUCTION';member=specs[g['canonical_graph_sha256']]['path']
 v,e,ids=parse(b,'wiki' if cohort=='EXP14_EXP15' else 'ali' if cohort=='EXP12' else 'integer')
 assert ids['raw_sha256']==h and ids['weighted_sha256']==g['canonical_graph_sha256'] and ids['topology_sha256']==g['topology_sha256'],g['graph_id']
 parsed[g['graph_id']]=(v,e);url=BASE+(next(x[1] for x in archives if x[0]==package) if package in ['supplement','table45','remaining'] else OLD+'/'+member if package=='wikimedia' else '667e164d0768d635a73692cd594801f10fe12382/releases/remaining-v1-20261019/README.md')
 access.append({'graph_id':g['graph_id'],'cohort':cohort,'instance_id':g['instance_id'],'parent_id':g['parent_id'],'raw_sha256':h,'weighted_sha256':ids['weighted_sha256'],'topology_sha256':ids['topology_sha256'],'access':route,'archive_or_file_url':url,'archive_member_or_recipe_input':member,'verification':'ANONYMOUS_HASH_AND_PARSE_PASS'})
print('All graph identities checked',len(access),flush=True)
checks=[]
for o in outcomes:
 if o['status'] not in ['PASS','CERTIFIED_OPTIMAL']:
  checks.append({'outcome_id':o['outcome_id'],'graph_id':o['graph_id'],'status':o['status'],'verification':'STATUS_RETAINED_NO_FEASIBLE_ORDER_CLAIM','order_sha256':o['ordering_byte_sha256'],'objective':o['objective_active'],'package':'','member':''});continue
 h=o['ordering_byte_sha256'];assert h in orderbytes,o['outcome_id'];b=orderbytes[h].read_bytes();assert digest(b)==h
 v,e=parsed[o['graph_id']]
 if o['cohort']=='EXP14':
  rr=list(csv.DictReader(b.decode('utf-8-sig').splitlines()));pos={r['Node ID']:int(r['Order']) for r in rr};assert len(rr)==len(pos)==len(v) and set(pos)==set(v) and sorted(pos.values())==list(range(len(v)));cost=sum(w for u,z,w in e if pos[u]>pos[z])
 else:cost=score(b,'csv' if b.startswith(b'Node ID') or b.startswith(b'\xef\xbb\xbf') else 'ranks',len(v),e)
 assert cost==int(o['objective_active']),(o['outcome_id'],cost,o['objective_active'])
 package,member=locations[h];checks.append({'outcome_id':o['outcome_id'],'graph_id':o['graph_id'],'status':o['status'],'verification':'COMPLETE_ORDER_EXACT_OBJECTIVE_PASS','order_sha256':h,'objective':str(cost),'package':package,'member':member})
assert len(checks)==5254 and sum(r['verification']=='COMPLETE_ORDER_EXACT_OBJECTIVE_PASS' for r in checks)==5131
# Check the 45 separate EXP07 reference witnesses as saved feasible solutions, not rerun solver proofs.
refchecked=[]
for o in remaining['packages']['J2']['orders']:
 if o['campaign']!='EXP07':continue
 g=next(g for g in graphs if g['canonical_graph_sha256']==o['canonical_graph_sha256']);v,e=parsed[g['graph_id']];b=(D/'objects'/o['object']).read_bytes();value=score(b,o['format'],len(v),e);assert value==int(o['objective']);refchecked.append({'run_id':o['run_id'],'graph_id':g['graph_id'],'objective':value,'status':'PASS'})
assert len(refchecked)==45
for x in refs:assert int(x['lower_bound'])<=int(x['upper_bound'])
# Exercise the public candidate tool, then public supplementary saved-output replay.
key='exp04/exp04_cm_n120_k03_r01';cmd=['python','-B',str(S/'INDEPENDENT_VERIFIER_SOURCE/check_candidate.py'),str(T),key,str(S/'examples/candidate.csv')];candidate=json.loads(subprocess.check_output(cmd,text=True));assert candidate['objective']==9391 and candidate['reference']==1854
for name,args in [('hydrate',['python','-B',str(S/'supplementary-evidence/protocol/hydrate_external.py'),str(ROOT/'snap')]),('supplement',['python','-B',str(S/'supplementary-evidence/verification/guarded_verify.py')])]:
 with (ROOT/(name+'.json')).open('w') as out:subprocess.run(args,stdout=out,check=True,timeout=120)
assert json.loads((ROOT/'supplement.json').read_text())['status']=='PASS'
def save(name,rs):
 with (ROOT/name).open('w',newline='') as out:w=csv.DictWriter(out,rs[0].keys(),lineterminator='\n');w.writeheader();w.writerows(rs)
save('graph_access.csv',access);save('outcome_access.csv',checks);save('exp07_reference_witness_checks.csv',refchecked)
emp=[x for x in features if x['origin_class']=='traceable_empirical'];summary={'status':'PASS','graphs':len(graphs),'weighted_identities':len({x['canonical_graph_sha256'] for x in graphs}),'topology_identities':len({(x['topology_contract'],x['topology_sha256']) for x in graphs}),'empirical_views':len(emp),'empirical_parents':len({x['parent_id'] for x in emp}),'graph_access':dict(collections.Counter(x['access'] for x in access)),'recorded_outcomes':len(outcomes),'saved_feasible_outcomes_rescored':5131,'outcome_status_counts':dict(collections.Counter(x['status'] for x in outcomes)),'reference_records':len(refs),'reference_classes':dict(collections.Counter(x['certificate_class'] for x in refs)),'exp07_reference_orders_checked':45,'candidate':candidate,'supplementary_tables':'S1-S3 PASS','all_checksums':'PASS','failures':0,'optimizer_runs':0,'downloads':downloads,'upstream_downloads':f.receipts,'elapsed_seconds':time.monotonic()-START,'reference_qualification':'Numerical classification retained; objective rescoring is not independent optimality certification.'}
(ROOT/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k not in ['downloads','upstream_downloads','candidate']},indent=2),flush=True)
