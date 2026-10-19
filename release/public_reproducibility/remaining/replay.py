"""Independent table replay. Private mode reuses sealed order checks; public mode rescores.

No optimization algorithms, solver binaries, private fallback, or expected CSV inputs.
All manuscript comparisons happen only after the numerical results are computed.
"""
import argparse,csv,hashlib,json,os,platform,re,socket,sys,tarfile,time,traceback
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from evidence import graph,score,require
from sources import Fetcher,recover,digest
from table_stats import exp05,exp07,exp1213
import wikimedia

HF='https://huggingface.co/datasets/SoroushVahidi/mwfas-benchmark-extension/resolve/'
TABLE45='33902c7cc409794a43c17fc5428cf022f440da48'
TABLE45_SHA='b74e37bed3a91ec986fe8526a73f5a990a144ca931ee013cc1a8fe4f882f3e2d'
WIKI='1e9db1daa5401b56398e9807d4e48d989d9f0eab'
ARCHIVE_JOBS={'J1':'1430677','J2':'1430679','J3':'1430678','J4':'1430680'}

def extract(archive,directory):
    directory.mkdir(parents=True,exist_ok=False)
    with tarfile.open(archive,'r:gz') as t:
        members=t.getmembers();require(all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members),'unsafe member');require(len({m.name for m in members})==len(members),'duplicate member')
        t.extractall(directory,filter='data')

def verify_manifest(root):
    m=json.loads((root/'manifest.json').read_text());seen=set()
    for r in m['entries']:
        p=(root/r['path']).resolve();require(p.is_relative_to(root.resolve()),'external path');b=p.read_bytes();require(len(b)==r['bytes'] and digest(b)==r['sha256'],'file hash: '+r['path']);seen.add(r['path'])
    require(len(seen)==len(m['entries']),'duplicate manifest entry');return len(seen)

def topology(n,arcs):
    return digest(json.dumps({'format':'exp04-topology-v1','directed':True,'vertices':list(range(1,n+1)),'arcs':sorted((u,v) for u,v,w in arcs)},sort_keys=True,separators=(',',':')).encode())

def compare(tables,frozen):
    result=[]
    for number,rows in tables.items():
        # Read only frozen display rows, never use them as an analysis input.
        expected=[];body=False
        for line in frozen['tables'][number].splitlines():
            if line=='\\midrule':body=True;continue
            if body and ' & ' in line:
                expected.append([x.strip().replace('$','') for x in line.removesuffix('\\\\').split(' & ')])
        require(len(rows)==len(expected),f'table {number} row count {len(rows)} != {len(expected)}')
        for actual,want in zip(rows,expected):
            require(actual==want,f'Table {number} mismatch: actual {actual!r}; manuscript {want!r}')
            result.extend({'table':number,'row':actual[0],'column':i,'value':value,'status':'PASS'} for i,value in enumerate(actual) if re.search(r'\d',value))
    return result

def load_records(root,pkg,section):
    return [{**json.loads((root/'objects'/r['object']).read_text()),'__source':r['source']} for r in pkg[section] if r['source'].endswith('.json')]

def existing_table45(fetch,scratch):
    blob=fetch.get(HF+TABLE45+'/releases/table45-v2-20261019/table45.tar.gz',TABLE45_SHA)
    archive=scratch/'table45.tar.gz';archive.write_bytes(blob);dest=scratch/'table45-extracted';dest.mkdir()
    # Existing archive includes one table45/ prefix and directory members.
    with tarfile.open(archive,'r:gz') as t:
        require(all(not Path(m.name).is_absolute() and '..' not in Path(m.name).parts and (m.isfile() or m.isdir()) for m in t.getmembers()),'unsafe table45 archive');t.extractall(dest,filter='data')
    root=dest/'table45'
    if not root.exists():root=dest
    verify_manifest(root);return root

def inventory(data,root,graphs,fetch,scratch):
    t45=existing_table45(fetch,scratch);campaigns={};records={}
    for c,j in [('EXP03','J4'),('EXP05','J1')]:
        gs=data['packages'][j]['graphs'];campaigns[c]=[graphs[g['canonical']] for g in gs];records[c]=load_records(root,data['packages'][j],'records')
    for c in ['EXP04','EXP06']:
        campaign=c.lower();base=t45/f'mwfas-{campaign}'/'production-output'
        if not base.exists():
            candidates=list((t45/f'mwfas-{campaign}').glob('*'));raise ValueError(f'table45 layout changed: {c}: {candidates}')
        stats=[]
        for p in sorted((base/'graphs').glob('*.d')):
            n,arcs,h=graph(p.read_bytes());stats.append({'canonical':h,'topology':topology(n,arcs),'n':n,'m':len(arcs),'weight':sum(w for u,v,w in arcs)})
        campaigns[c]=stats;records[c]=[json.loads(p.read_text()) for p in sorted((base/'runs').glob('*.json'))]
    counts={c:[len(gs),len({g['topology'] for g in gs}),len(records[c])] for c,gs in campaigns.items()}
    require(counts=={'EXP03':[45,45,900],'EXP04':[135,135,2025],'EXP05':[38,38,760],'EXP06':[198,99,1398]},'cross campaign structure/count')
    for c in campaigns:
        require(len({g['canonical'] for g in campaigns[c]})==len(campaigns[c]),'duplicate weighted graph within contract')
        allowed={g['canonical'] for g in campaigns[c]};require(all(r['graph_sha256'] in allowed for r in records[c]),'task graph join')
        require(len({r.get('run_id',r.get('instance_id')) for r in records[c]})==len(records[c]),'duplicate task identity')
    selected=data['packages']['J2']['graphs'];hashes={g['canonical'] for g in selected};common={c:{g['canonical'] for g in gs} for c,gs in campaigns.items()}
    reuse={c:len(hashes&hs) for c,hs in common.items()};require(reuse=={'EXP03':9,'EXP05':0,'EXP04':36,'EXP06':0},'EXP07 graph reuse')
    require(not {graphs[h]['topology'] for h in hashes}&{g['topology'] for g in campaigns['EXP06']},'EXP07 topology overlap EXP06')
    require(sum(r['algorithm']=='igraph_ip' for r in records['EXP06'])==12,'EXP06 separate IP tasks')
    total=[sum(v[i] for v in counts.values()) for i in range(3)]
    rows3=[];descriptions={'EXP03':'One weight per topology','EXP04':'Five replicates per design cell','EXP05':'Four real-world parents','EXP06':'Two weights per topology'}
    for c in ['EXP03','EXP04','EXP05','EXP06']:rows3.append([c]+[f'{x:,}' for x in counts[c]]+[descriptions[c]])
    rows3.extend([['EXP03--06 total']+[f'{x:,}' for x in total]+['Repeated tasks on distinct inputs'],['EXP07, reused',str(len(hashes)),str(len({graphs[h]['topology'] for h in hashes})),'---',f"{reuse['EXP03']} EXP03 + {reuse['EXP04']} EXP04 matches"]])
    # Reuse the published Wikimedia graph/order evidence; reconstruct graph identities from bytes.
    wiki=scratch/'wiki';wiki.mkdir();url=HF+WIKI+'/'
    import urllib.request
    with urllib.request.urlopen(url+'CHECKSUMS.csv',timeout=60) as response:raw=response.read()
    (wiki/'CHECKSUMS.csv').write_bytes(raw);checks=list(csv.DictReader(raw.decode().splitlines()))
    for e in checks:
        p=wiki/e['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(fetch.get(url+e['path'],e['sha256']))
    wg=wikimedia.rows(wiki/'graph_inventory.csv');wo=wikimedia.rows(wiki/'witnesses.csv')
    for g in wg:
        arcs,vertices=wikimedia.read_graph(wiki/g['path'],g)
        # Previously accepted objective audit is reused here: Table 4 is a structural inventory.
        for o in [o for o in wo if o['graph_id']==g['graph_id']]:require(wikimedia.digest(wiki/o['path'])==o['ordering_byte_sha256'],'wiki order byte identity')
    require(len(wg)==3 and len(wo)==10 and len({g['source_parent'] for g in wg})==1,'Wikimedia scope')
    p3=data['packages']['J3'];ms=load_records(root,p3,'metadata');r3=load_records(root,p3,'records');a=next(m for m in ms if m['format']=='exp12-run-manifest-v1');b=next(m for m in ms if m['format']=='exp13-run-manifest-v1')
    g12=len(a['selected']);g13=len(b['selected']);n12=len(a['tasks']);n13=len(b['tasks']);require(n12+n13==len(r3),'EXP12/13 task roster');require(len({g['source_parent'] for g in b['selected']})==3,'EXP13 parents')
    cert=Counter(r['status'] for r in load_records(root,data['packages']['J2'],'records'))
    rows4=[['EXP03--06 common contract',str(total[0]),f'{total[2]:,}',f'{total[1]} topologies; four EXP05 empirical parents'],['EXP12 Ali collection',str(g12),str(n12),'Source-parent independence unresolved'],['EXP13 new empirical sources',str(g13),str(n13),'Three distinct source parents'],['EXP14 Wikimedia history',str(len(wg)),str(len(wo)),'One source parent; three dependent views'],['Contract-scoped total',str(total[0]+g12+g13+len(wg)),f'{total[2]+n12+n13+len(wo):,}','No verified global graph deduplication'],['EXP07 references, reused',str(len(hashes)),'---',f"{cert['CERTIFIED_OPTIMAL']} numerical optima; {cert['FEASIBLE_UNCERTIFIED']} bounded cases"]]
    return {'3':rows3,'4':rows4},{'counts':counts,'EXP07_reuse':reuse,'Wikimedia_graphs':wg,'accepted_wikimedia_order_hashes':len(wo),'graph_identities':campaigns,'EXP06_principal_tasks':len(records['EXP06'])-12}

def run(args):
    started=time.time();root=args.package.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);fetch=Fetcher(out/'upstream');receipt={'package':args.scope,'mode':args.mode,'started_utc':datetime.now(timezone.utc).isoformat(),'slurm_job_id':os.environ.get('SLURM_JOB_ID'),'python':platform.python_version(),'hostname':socket.gethostname(),'optimization_runs':0,'status':'FAIL','complete_public_table':False,'source_downloads':fetch.receipts}
    try:
        receipt['manifest_files_verified']=verify_manifest(root);data=json.loads((root/'data.json').read_text());pkg=data['packages'][args.scope]
        relevant=list(data['packages']) if args.scope=='J4' else [args.scope];graphs={};graph_receipts=[]
        for j in relevant:
            for g in data['packages'][j]['graphs']:
                if g['canonical'] in graphs:continue
                if g['kind']=='synthetic':blob=(root/'objects'/g['object']).read_bytes()
                elif args.mode=='private':
                    base=args.original/j/'payload'
                    if not base.exists():base=args.original/j/'output'/ARCHIVE_JOBS[j]/'payload'
                    blob=(base/g['path']).read_bytes()
                else:blob=recover(g,fetch)
                require(digest(blob)==g['sha256'],'exact graph bytes: '+g['path']);n,arcs,h=graph(blob);require(h==g['canonical'],'canonical graph hash');stats={'canonical':h,'topology':topology(n,arcs),'n':n,'m':len(arcs),'weight':sum(w for u,v,w in arcs)};graphs[h]={**stats,'arcs':arcs};graph_receipts.append({**stats,'sha256':digest(blob),'source':g['path']})
                if 'spec' in g:
                    s=g['spec'];require(n==s.get('n_vertices',s.get('n')) and len(arcs)==s.get('n_edges',s.get('m')),'graph dimension specification')
                    if s.get('topology_sha256'):require(stats['topology']==s['topology_sha256'],'declared topology identity')
        records=load_records(root,pkg,'records');metadata=load_records(root,pkg,'metadata');aux=load_records(root,pkg,'auxiliary');valid={};order_checks=[]
        for o in pkg['orders']:
            b=(root/'objects'/o['object']).read_bytes();require(digest(b)==o['order_sha256'],'order bytes');g=graphs[o['canonical_graph_sha256']]
            objective=score(b,o['format'],g['n'],g['arcs']) if args.mode=='public' else int(float(o['objective']))
            require(objective==float(o['objective']),'objective mismatch '+o['run_id']);valid[(o['campaign'],o['run_id'])]=o
            order_checks.append({'campaign':o['campaign'],'run_id':o['run_id'],'objective':objective,'order_sha256':o['order_sha256'],'validation':'RECOMPUTED_PERMUTATION_DAG_OBJECTIVE' if args.mode=='public' else 'SEALED_AUDIT_HASH_BOUND_REUSED'})
        invalid_originals=[]
        for item in pkg.get('unvalidated_orders',[]):
            rid=Path(item['source']).name.removesuffix('.tmp').removesuffix('.csv')
            r=next(r for r in records if r.get('run_id')==rid)
            require(r['status']=='FAIL','unvalidated original must retain FAIL')
            blob=(root/'objects'/item['object']).read_bytes();require(digest(blob)==item['original_sha256'],'invalid original byte binding')
            if args.mode=='public':
                g=graphs[r['graph_sha256']]
                try:score(blob,'csv',g['n'],g['arcs'])
                except ValueError as error:invalid_originals.append({'run_id':rid,'status':'FAIL_PRESERVED','reason':str(error),'sha256':item['original_sha256']})
                else:raise ValueError('original FAIL unexpectedly has a valid complete permutation')
        receipt['invalid_original_orders']=invalid_originals
        if args.scope=='J2':
            inv=next(m for m in metadata if 'instances' in m)
            originals={r['original_sha256'] for r in pkg['auxiliary']}
            for r in records:require(r['raw_sha256'] in originals,'original solver worker byte lineage')
            for g in inv['instances']:
                for h in g['heuristics']:
                    if h['checkpoint_sha256']:require(h['checkpoint_sha256'] in originals,'historical checkpoint byte lineage')
                    candidates=[o for o in pkg['orders'] if o['run_id']==h['run_id']];require(len(candidates)==1 and candidates[0]['order_sha256']==h['order_sha256'] and float(candidates[0]['objective'])==h['objective_weight'],'historical heuristic selection identity')
        for r in records:
            rid=r.get('run_id',r.get('task_id',r.get('instance_id')));c='EXP12' if args.scope=='J3' and r['__source'].startswith('mwfas-exp12/') else {'J1':'EXP05','J2':'EXP07','J3':'EXP13','J4':'EXP03'}[args.scope]
            if r['status'] in ['PASS','CERTIFIED_OPTIMAL','FEASIBLE_UNCERTIFIED']:
                o=valid[(c,rid)];require(o['canonical_graph_sha256']==r['graph_sha256'],'order/task graph join');require(o['order_sha256']==r['order_sha256'],'order/task hash join');require(float(o['objective'])==r.get('objective_weight',r.get('objective')),'order/task cost join')
        if args.scope=='J1':tables,inputs=exp05(pkg,records,graphs)
        elif args.scope=='J2':tables,inputs=exp07(pkg,records,metadata,aux)
        elif args.scope=='J3':tables,inputs=exp1213(pkg,records,metadata)
        else:
            # Do not serialize large adjacency lists into the statistical inventory.
            plain={h:{k:v for k,v in g.items() if k!='arcs'} for h,g in graphs.items()};tables,inputs=inventory(data,root,plain,fetch,out)
        cells=compare(tables,pkg['frozen_manuscript']);(out/'table_cells.json').write_text(json.dumps(tables,indent=2)+'\n');(out/'statistical_inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');(out/'graph_checks.json').write_text(json.dumps(graph_receipts,indent=2)+'\n');(out/'order_checks.json').write_text(json.dumps(order_checks,indent=2)+'\n')
        receipt.update(status='PASS',state='COMPLETED_SUCCESS',tables=list(tables),displayed_cells=cells,graph_checks=len(graph_receipts),available_order_checks=len(order_checks),original_statuses=dict(Counter(r['status'] for r in records)),complete_public_table=args.mode=='public',classification='PUBLIC_REPLAYABLE' if args.mode=='public' else 'PRIVATE_STATISTICAL_REPLAY_VERIFIED',limitations=['Numerical solver certificates are not exact-arithmetic proofs.','Ali historical Hugging Face graph-byte identity remains unverified; EXP12 replay uses its pinned recorded input bytes.','Third-party graphs are retrieved from pinned upstream files; no substituted sources.'])
    except Exception as e:receipt.update(error=str(e),traceback=traceback.format_exc(),state='FAILED');print(receipt['traceback'],flush=True)
    receipt['finished_utc']=datetime.now(timezone.utc).isoformat();receipt['elapsed_seconds']=time.time()-started;receipt['outputs']=[{'path':p.name,'sha256':digest(p.read_bytes())} for p in sorted(out.glob('*.json'))];(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k not in ['displayed_cells','source_downloads','traceback']}),flush=True);return receipt
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--scope',choices=list(ARCHIVE_JOBS),required=True);p.add_argument('--mode',choices=['private','public'],required=True);p.add_argument('--original',type=Path);a=p.parse_args();require(a.mode=='public' or a.original is not None,'private original root required');raise SystemExit(0 if run(a)['status']=='PASS' else 1)
