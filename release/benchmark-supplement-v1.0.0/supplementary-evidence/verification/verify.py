#!/usr/bin/env python3
"""Offline, saved-output verification. Run python verification/verify.py > report.json.
No algorithm execution, network access or private-path filesystem resolution.
"""
import sys
sys.dont_write_bytecode=True
import json,hashlib,collections,csv,io,time,platform,re
from pathlib import Path
from fractions import Fraction
import numpy
from evidence_fs import EvidenceFS
import exp05
ROOT=Path(__file__).resolve().parents[1]
def hash_bytes(b):return hashlib.sha256(b).hexdigest()
def verify_manifest():
 manifest=json.loads((ROOT/'PACKAGE_MANIFEST.json').read_text());paths=set()
 for r in manifest['files']:
  p=ROOT/r['path'];assert p.resolve().is_relative_to(ROOT),'unsafe manifest path';b=p.read_bytes()
  assert len(b)==r['bytes']and hash_bytes(b)==r['sha256'],'manifest mismatch: '+r['path'];paths.add(r['path'])
 actual={str(p.relative_to(ROOT))for p in ROOT.rglob('*')if p.is_file()and'__pycache__'not in p.parts}
 external={r['storage_path'] for r in json.loads((ROOT/'EXTERNAL_OBJECTS.json').read_text())['records']}
 assert actual==paths|{'PACKAGE_MANIFEST.json','SHA256SUMS'}|external,'unlisted/missing payload or run hydrate_external.py first'
 for line in (ROOT/'SHA256SUMS').read_text().splitlines():
  digest,name=line.split('  ',1);assert hash_bytes((ROOT/name).read_bytes())==digest,'SHA256SUMS mismatch: '+name
 return {'status':'PASS','payload_files':len(paths),'manifest_sha256':hash_bytes((ROOT/'PACKAGE_MANIFEST.json').read_bytes())}
def run():
 start=time.monotonic();integrity=verify_manifest();index=json.loads((ROOT/'witnesses/index.json').read_text());fs=EvidenceFS(ROOT,index['records'],index['excluded'])
 for r in index['records']:
  b=(ROOT/r['storage_path']).read_bytes();assert hash_bytes(b)==r['storage_sha256']
  if not r['sanitized']:assert hash_bytes(b)==r['sha256']
 # Audited source-identity aliases are used only for redacted provenance, never for graph/order scoring.
 code=(ROOT/'verification/witness_checks.py').read_text();checks=[]
 filenames={'EXP29':'exp29_validation.json','EXP30_SIMPLE':'exp30_simple_validation.json','EXP30_WIKI':'exp30_wiki_validation.json','EXP30_LODES':'exp30_lodes_validation.json','EXP30_IRS':'exp30_irs_validation.json'}
 for mode in filenames:
  g={'Path':fs.Path,'fs':fs,'MODE_ARGUMENT':mode};exec(compile(code,'witness_checks.py','exec'),g);v=g['RESULT']
  assert not v['global_errors']and not v['task_errors'],(mode,v['global_errors'],v['task_errors'])
  old=json.loads((ROOT/'receipts'/filenames[mode]).read_text());prior={t['task_id']:t for t in old['tasks']}
  for t in v['tasks']:
   a=prior[t['task_id']];a['horizons']={int(k):v for k,v in a['horizons'].items()}
   for k in ['controller','recorded_status','original_status','checkpoint_sha256','event_orders_checked','unique_order_bytes','horizons']:assert t[k]==a[k],(t['task_id'],k)
  checks.append(v)
 r29=checks[0];r30=[t for v in checks[1:]for t in v['tasks']];pairs={};counts=collections.defaultdict(lambda:[0,0,0]);paired=[]
 for t in r29['tasks']:pairs.setdefault(t['graph_id'],{})[t['arm']]=t
 for gid,arms in sorted(pairs.items()):
  a=arms['ipsns']['horizons'][120]['objective'];b=arms['xiong_single']['horizons'][120]['objective'];sign='win'if a<b else'tie'if a==b else'loss';i=['win','tie','loss'].index(sign);family=r29['graphs'][gid]['family'];counts[family][i]+=1;counts['All'][i]+=1
  paired.append({'graph_id':gid,'family':family,'ipsns_seed':2901,'rasstar_seed':1,'ipsns_objective':a,'rasstar_objective':b,'ipsns_sign':sign,'ipsns_task':arms['ipsns']['task_id'],'rasstar_task':arms['xiong_single']['task_id']})
 assert len(pairs)==45 and counts['All']==[33,5,7]
 assert counts['erdos_renyi_directed']==[12,0,3]and counts['directed_community']==[14,0,1]and counts['directed_scale_free']==[7,5,3]
 history={}
 for exp,v in [('exp29',r29),('exp30',checks[1])]:
  view=fs.Path('source/mwfas-overnight-20261019/recovery-20261019/output/'+exp+'-70ab586-v2/independent_combined_view')
  selection=list(csv.DictReader(io.StringIO((view/'recovery_selection.csv').read_bytes().decode())));inventory=list(csv.DictReader(io.StringIO((view/'task_inventory.csv').read_bytes().decode())))
  assert {r['task_id']for r in selection}=={r['task_id']for r in v['protocol']['tasks']}=={r['task_id']for r in inventory}
  original=dict(collections.Counter(r['original_status']for r in selection));selected=dict(collections.Counter(r['selected_status']for r in selection));audit=v['retained_overall_campaign_audit'];assert original==audit['original_status_counts']
  audited=dict(collections.Counter(r['status']for r in inventory));assert audited==audit['status_counts'];inv={r['task_id']:r for r in inventory};changes=[{'task_id':r['task_id'],'selected_checkpoint_status':r['selected_status'],'audited_status':inv[r['task_id']]['status']}for r in selection if r['selected_status']!=inv[r['task_id']]['status']];assert all(x['audited_status']=='INVALID'and any(z['task_id']==x['task_id']for z in audit['violations'])for x in changes)
  history[exp]={'original':original,'selected_checkpoint_status_counts':selected,'combined':audited,'selection_to_audit_reclassifications':changes,'campaign_status':audit['status'],'roster_size':len(selection),'violations':audit['violations'],'homogeneous_runtime_inference_permitted':audit['homogeneous_runtime_inference_permitted']}
 assert history['exp29']['campaign_status']=='FAIL'and history['exp29']['roster_size']==180
 assert history['exp29']['original']=={'INVALID':1,'MISSING':60,'PASS':105,'TIMEOUT':14}
 assert history['exp29']['combined']=={'INVALID':5,'PASS':135,'TIMEOUT':40}
 assert len(r30)==12 and collections.Counter(t['recorded_status']for t in r30)=={'PASS':3,'TIMEOUT':9}and collections.Counter(t['controller']for t in r30)=={'v1':7,'v2':5}
 p05=exp05.verify(ROOT,fs)
 # Supplemental table rows are parsed from the immutable author manuscript excerpt.
 tex=(ROOT/'tables/manuscript_supplementary_evidence.tex').read_text();tables=tex.split('\\begin{tabular}')[1:];assert len(tables)==3
 def numeric_rows(t):
  return [[x.strip()for x in line.split('\\\\')[0].split('&')]for line in t.splitlines()if'&'in line and re.search(r'&\s*\d',line)]
 s1=numeric_rows(tables[0]);assert [list(map(int,r[1:]))for r in s1]==[[15,12,0,3],[15,14,0,1],[15,7,5,3],[45,33,5,7]]
 s2=numeric_rows(tables[1]);expected=[]
 parent_order=['wiki','irs','lodes'];arm_order=[('ipsns',2901),('ipsns',2902),('xiong_restarts',1),('xiong_single',1)]
 for parent in parent_order:
  for arm,seed in arm_order:
   t=next(t for t in r30 if parent in t['graph_id']and t['arm']==arm and t['seed']==seed)
   expected.append([str(seed),t['controller'],str(t['horizons'][120]['objective']),str(t['horizons'][300]['objective']),'TO'if t['recorded_status']=='TIMEOUT'else'PASS'])
 assert [r[2:]for r in s2]==expected,'S2 manuscript mismatch'
 s3=numeric_rows(tables[2]);full=p05['full'];s3expected=[]
 for m in exp05.METHODS:s3expected.append([format(float(Fraction(full['view_exact'][m])),'.6f'),format(float(Fraction(full['parent_exact'][m])),'.6f'),str(full['view_ranking'].index(m)+1),str(full['parent_ranking'].index(m)+1)])
 assert [r[1:]for r in s3]==s3expected,'S3 manuscript mismatch'
 for name,generated in [('S1',s1),('S2',s2),('S3',s3)]:
  assert list(csv.reader(io.StringIO((ROOT/'tables'/(name+'.csv')).read_text())))==generated,'packaged table differs: '+name
 # Independent parser negative control: duplicates cannot be accepted as a complete order.
 try:g['ranks'](b'0 0','xiong_single',2)
 except ValueError:negative='PASS'
 else:raise AssertionError('duplicate rank accepted')
 return {'status':'PASS','scope':'saved-output reconstruction; no optimization rerun or mathematical optimality proof','elapsed_seconds':time.monotonic()-start,'environment':{'python':platform.python_version(),'numpy':numpy.__version__},'integrity':integrity,'negative_control_duplicate_order':negative,'history':history,'EXP29':{'pairs':paired,'counts':dict(counts),'tasks':r29['tasks'],'event_orders':sum(t['event_orders_checked']for t in r29['tasks'])},'EXP30':{'observations':r30,'event_orders':sum(t['event_orders_checked']for t in r30),'horizon_values':24,'controllers':dict(collections.Counter(t['controller']for t in r30))},'EXP05':p05,'tables':{'S1':s1,'S2':s2,'S3':s3,'manuscript_sha256':hash_bytes((ROOT/'tables/manuscript_supplementary_evidence.tex').read_bytes())},'timestamp_limitation':index['timestamp_semantics'],'binary_check':'RASstar bytes excluded; recorded hash agrees across manifests and collection receipt; no clean-room binary validation claimed'}
if __name__=='__main__':
 try:
  result=run()
  if '--tables-dir'in sys.argv:
   destination=Path(sys.argv[sys.argv.index('--tables-dir')+1]).resolve();assert not destination.is_relative_to(ROOT);destination.mkdir(parents=True,exist_ok=True)
   for name in ['S1','S2','S3']:
    with(destination/(name+'.csv')).open('w',newline='')as stream:csv.writer(stream).writerows(result['tables'][name])
  print(json.dumps(result,sort_keys=True,indent=2))
 except Exception as e:
  print(json.dumps({'status':'FAIL','error':str(e)}));raise
