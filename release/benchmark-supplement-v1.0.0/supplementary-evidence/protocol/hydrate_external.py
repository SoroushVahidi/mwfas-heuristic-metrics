"""Download SNAP inputs anonymously, check hashes, reconstruct exact excluded objects.
Run in an extracted working copy; does not run optimization or alter published files.
"""
import sys,json,hashlib
from pathlib import Path
from reconstruct_exp05_inputs import Fetcher,exp05,require,digest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'verification'))
from evidence_fs import EvidenceFS
root=Path(__file__).resolve().parents[1];cache=Path(sys.argv[1]).resolve()
require(not cache.is_relative_to(root),'cache must be outside extracted package')
idx=json.loads((root/'witnesses/index.json').read_text());fs=EvidenceFS(root,idx['records'],idx['excluded'])
specs=json.loads(fs.Path('source/mwfas-exp05/production-output/selection.json').read_bytes())['instances']
f=Fetcher(cache);produced={}
for spec in specs:
 if spec['source_member'] or spec['instance_id']=='exp05_email_full':continue
 b,nodes=exp05(spec,f,True);require(digest(b)==spec['dimacs_sha256'],'graph reconstruction')
 produced[digest(b)]=b
 node=(json.dumps(nodes,separators=(',',':'))+'\n').encode();produced[digest(node)]=node
 # Historical external binary adapter sorts string endpoint pairs before zero-based conversion.
 arcs=[l.split()[1:] for l in b.decode().splitlines() if l.startswith('a ')]
 w=(f'{len(nodes)} {len(arcs)}\n'+''.join(f'{int(u)-1} {int(v)-1} {weight}\n' for u,v,weight in sorted(arcs,key=lambda x:(x[0],x[1])))).encode()
 produced[digest(w)]=w
report=[]
for r in json.loads((root/'EXTERNAL_OBJECTS.json').read_text())['records']:
 b=produced.get(r['storage_sha256']);require(b is not None,'unmatched external representation: '+r['original_path'])
 p=root/r['storage_path']
 if p.exists():require(p.read_bytes()==b,'existing external object differs')
 else:p.write_bytes(b)
 report.append({'logical_path':r['original_path'],'sha256':digest(b),'status':'PASS'})
print(json.dumps({'status':'PASS','objects':report,'downloads':f.receipts},indent=2))
