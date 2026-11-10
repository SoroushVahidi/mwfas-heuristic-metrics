"""Resolve both profiles from pinned public or upstream bytes. No optimizer.
Usage: python profile_tools/resolve_profiles.py /fresh/output-directory
"""
import csv,json,hashlib,sys,tarfile,urllib.request
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'diversity/scripts'))
sys.path.insert(0,str(Path(__file__).parent/'upstream'))
from graph_features import parse
from sources import Fetcher,recover

def main():
 out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False);cache=out/'cache';fetch=Fetcher(cache)
 table_url='https://huggingface.co/datasets/SoroushVahidi/mwfas-benchmark-extension/resolve/33902c7cc409794a43c17fc5428cf022f440da48/releases/table45-v2-20261019/table45.tar.gz'
 archive=fetch.get(table_url,'b74e37bed3a91ec986fe8526a73f5a990a144ca931ee013cc1a8fe4f882f3e2d','table45.tar.gz')
 table=out/'table45';table.mkdir()
 with tarfile.open(cache/'table45.tar.gz') as t:
  for m in t.getmembers():
   if not (m.isfile() or m.isdir()) or not (table/m.name).resolve().is_relative_to(table):raise ValueError('unsafe archive')
  t.extractall(table,filter='data')
 table=table/'table45' if (table/'table45').is_dir() else table
 rows=list(csv.DictReader((ROOT/'diversity/BALANCED_SUBSET_MANIFEST.tsv').open(),delimiter='\t'))
 specs=json.loads((ROOT/'profile_tools/upstream_specs.json').read_text());loaded={};receipts=[]
 for r in rows:
  gid=r['graph_id'];kind='wiki' if r['cohort']=='EXP14_EXP15' else 'ali' if r['cohort']=='EXP12' else 'integer'
  if gid not in loaded:
   if r['cohort'] in ('EXP04','EXP06'):b=(table/r['existing_input_reference']).read_bytes();route='PUBLIC_TABLE45'
   elif kind=='wiki':
    url='https://huggingface.co/datasets/SoroushVahidi/mwfas-benchmark-extension/resolve/1e9db1daa5401b56398e9807d4e48d989d9f0eab/data/wikimedia/'+r['instance_id']+'.d'
    b=fetch.get(url,r['raw_sha256']);route='PUBLIC_WIKIMEDIA'
   else:
    obj=ROOT/'supplementary-evidence/objects'/r['raw_sha256'];odbl=ROOT/'licensed-inputs/openflights'/ (r['instance_id']+'.d')
    if obj.is_file():b=obj.read_bytes();route='PUBLIC_SUPPLEMENTARY_OBJECT'
    elif odbl.is_file():b=odbl.read_bytes();route='PUBLIC_ODBL_DERIVATIVE'
    else:b=recover(specs[r['weighted_sha256']],fetch);route='PINNED_UPSTREAM_RECONSTRUCTION'
   vertices,arcs,ids=parse(b,kind)
   for field in ['raw_sha256','weighted_sha256','topology_sha256']:assert ids[field]==r[field],(gid,field)
   assert len(vertices)==int(r['n']) and len(arcs)==int(r['m'])
   (out/'graphs').mkdir(exist_ok=True);(out/'graphs'/(gid+'.d')).write_bytes(b);loaded[gid]=route
  receipts.append({'profile':r['profile'],'graph_id':gid,'instance_id':r['instance_id'],'parent_id':r['parent_id'],'route':loaded[gid],'raw_sha256':r['raw_sha256'],'weighted_sha256':r['weighted_sha256'],'topology_sha256':r['topology_sha256'],'status':'PASS'})
 counts={p:sum(r['profile']==p for r in rows) for p in {r['profile'] for r in rows}}
 assert counts=={'table45_core':34,'existing_source_diverse':47}
 result={'status':'PASS','counts':counts,'unique_graphs':len(loaded),'records':receipts,'downloads':fetch.receipts,'scope':'Input identity and resolution only; no optimization'}
 (out/'PROFILE_RESOLUTION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':'PASS','counts':counts,'unique_graphs':len(loaded)}))
if __name__=='__main__':main()
