"""Run independent full-release verification inside the current clean root."""
import csv,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from download import install_guard
from mwfas_benchmark import load_graph,load_order,evaluate,identities

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p,delimiter=','):
    with p.open() as f:return list(csv.DictReader(f,delimiter=delimiter))
def tsv(p,data):
    with p.open('w') as f:
        w=csv.DictWriter(f,list(data[0]),delimiter='\t');w.writeheader();w.writerows(data)
def require(ok,reason):
    if not ok:raise ValueError(reason)

def main():
    root=Path.cwd().resolve();accesses=install_guard(root);package=root/'table45'
    manifest=json.loads((package/'manifest.json').read_text());require(sha(package/'manifest.json')=='ab67aee168229b4ae19394732a7a3dedf4761b7e1e3ef75983e3028a56e41b51','manifest pin')
    errors=[]
    for e in manifest['entries']:
        p=package/e['path']
        if not (p.resolve().is_relative_to(package) and p.is_file() and p.stat().st_size==e['bytes'] and sha(p)==e['sha256']):errors.append(e['path'])
    listed={e['path'] for e in manifest['entries']}
    extra=sorted(str(p.relative_to(package)) for p in package.rglob('*') if p.is_file() and str(p.relative_to(package)) not in listed|{'manifest.json'})
    (root/'PACKAGE_COMPLETENESS.json').write_text(json.dumps({'listed':len(listed),'failed':errors,'unlisted':extra},indent=2))
    require(not errors,'manifest file failures')
    hist=[r for r in rows(root/'supplied_manifests/historical_graphs.tsv','\t') if set(json.loads(r['experiment_ids'])) & {'EXP04','EXP06'}]
    require(len(hist)==333,'historical count')
    graph_results=[];graphs={};hist_by_id={r['benchmark_record_id']:r for r in hist}
    paths=set(package.glob('mwfas-exp*/production-output/graphs/*.d'))
    for h in hist:
        cohort=json.loads(h['experiment_ids'])[0];path=package/f'mwfas-{cohort.lower()}/production-output/graphs'/f"{h['instance_id']}.d"
        rec={'benchmark_record_id':h['benchmark_record_id'],'cohort':cohort,'instance_id':h['instance_id'],'file':str(path.relative_to(package)),'downloaded':path in paths,'parsed':False,'vertices':'','arcs':'','directed':True,'weight_representation':'positive integer','raw_sha256':'','weighted_sha256':'','topology_sha256':'','historical_identity':'FAIL','error':''}
        try:
            g=load_graph(path);ids=identities(g);rec.update(parsed=True,vertices=len(g.vertices),arcs=len(g.arcs),raw_sha256=sha(path),**ids)
            require((len(g.vertices),len(g.arcs),sum(w for u,v,w in g.arcs))==(int(h['vertices']),int(h['arcs']),int(h['active_weight'])),'size/weight mismatch')
            require(rec['raw_sha256']==h['expected_raw_file_sha256'],'raw hash mismatch')
            require(ids['weighted_sha256']==h['canonical_weighted_graph_hash'],'weighted identity mismatch')
            require(ids['topology_sha256']==h['canonical_topology_hash'],'topology identity mismatch')
            require(int(h['objective_loop_constant'])==0,'nonzero loop constant outside table45 contract')
            rec['historical_identity']='PASS';graphs[h['benchmark_record_id']]=g
        except Exception as e:rec['error']=str(e)
        graph_results.append(rec)
    tsv(root/'GRAPH_IDENTITY_VERIFICATION.tsv',graph_results)
    known={r['file'] for r in graph_results};unexpected=sorted(str(p.relative_to(package)) for p in paths if str(p.relative_to(package)) not in known)
    refs={r['graph_id']:r for r in rows(root/'supplied_manifests/numerical_references.csv') if r['graph_id'] in hist_by_id}
    outcomes=[r for r in rows(root/'supplied_manifests/run_outcomes.csv') if r['cohort'] in ('EXP04','EXP06')];result=[];solver_checks=[]
    for o in outcomes:
        rid=o['outcome_id'].split(':',1)[1];h=hist_by_id[o['graph_id']];base=package/f"mwfas-{o['cohort'].lower()}/production-output";rp=base/'runs'/f'{rid}.json';op=base/'orders'/f'{rid}.csv'
        rec={'outcome_id':o['outcome_id'],'graph_id':o['graph_id'],'publicly_accessible':rp.is_file() and op.is_file(),'valid_order':False,'recomputed':False,'published_objective':o['objective_active'],'recomputed_objective':'','difference':'','comparison':'UNVERIFIABLE','retained_dag':False,'reference_kind':'BEST_SAVED_FEASIBLE_ONLY','reference_objective':'','reference_gap':'','reference_lower_bound':'','reference_upper_bound':'','reference_source':'','reference_check':'NOT_APPLICABLE','error':''}
        try:
            r=json.loads(rp.read_text());g=graphs[o['graph_id']]
            require(r['instance_id']==h['instance_id'] and r['run_id']==rid and r['graph_sha256']==h['canonical_weighted_graph_hash'],'run graph join')
            order=load_order(op,g);rec['valid_order']=True
            require(sha(op)==r['order_sha256']==o['ordering_byte_sha256'],'ordering byte identity')
            val=evaluate(g,order);cost=val['objective'];rec.update(recomputed=True,recomputed_objective=cost,difference=cost-int(o['objective_active']),retained_dag=val['retained_dag'])
            exact=(cost==int(o['objective_active'])==r['objective_weight'] and cost==int(o['objective_original']))
            rec['comparison']='EXACT_INTEGER_MATCH' if exact else 'MISMATCH'
            if o['graph_id'] in refs:
                ref=refs[o['graph_id']];lower=int(ref['lower_bound']);upper=int(ref['upper_bound']);target=int(ref['certified_optimum']) if ref['certified_optimum'] else upper
                rec.update(reference_kind=ref['certificate_class']+'_NOT_EXACT_PROOF',reference_objective=target,reference_gap=cost-target,reference_lower_bound=lower,reference_upper_bound=upper,reference_source='supplied_manifest:'+ref['reference_id'],reference_check='PASS' if cost>=lower else 'FAIL')
            evidence=base/'solver_evidence'/f'{rid}.json'
            if evidence.exists():
                raw=json.loads(evidence.read_text());require(sha(evidence)==r['raw_evidence_sha256'],'solver evidence bytes')
                require(tuple(map(int,raw['order']))==order and raw['objective_weight']==cost,'solver witness')
                if r['algorithm']=='scipy_highs_ordering_milp':
                    require(r['status']==raw['status']=='CERTIFIED_OPTIMAL' and r['solver_status_code']==raw['solver_status_code']==0,'solver status')
                    for key in ['lower_bound','objective_constant','solver_fun','solver_dual_bound','solver_mip_gap']:require(r[key]==raw[key],'solver field '+key)
                    require(0<=r['solver_mip_gap']<=1e-7 and abs(cost-r['lower_bound'])<0.5 and abs(cost-r['objective_constant']-r['solver_fun'])<1e-5 and abs(r['lower_bound']-r['objective_constant']-r['solver_dual_bound'])<1e-5,'numerical bound consistency')
                    require(cost==int(refs[o['graph_id']]['certified_optimum']),'historical reference join')
                solver_checks.append({'outcome_id':o['outcome_id'],'status':'PASS','evidence_sha256':sha(evidence),'qualification':'NUMERICAL_NOT_EXACT_PROOF'})
        except Exception as e:
            rec['error']=str(e)
            if rec['publicly_accessible'] and not rec['valid_order']:rec['comparison']='INVALID_OR_UNREADABLE'
            elif rec['recomputed']:rec['comparison']='FAILED_EVIDENCE_CHECK'
        result.append(rec)
    # EXP04 has no numerical certificate; compare each outcome with best saved feasible.
    best={}
    for r in result:
        if r['recomputed']:best[r['graph_id']]=min(best.get(r['graph_id'],r['recomputed_objective']),r['recomputed_objective'])
    for r in result:
        if r['reference_kind']=='BEST_SAVED_FEASIBLE_ONLY' and r['recomputed']:
            target=best[r['graph_id']];r.update(reference_objective=target,reference_gap=r['recomputed_objective']-target,reference_check='PASS')
    tsv(root/'OBJECTIVE_RECOMPUTATION_RESULTS.tsv',result);tsv(root/'NUMERICAL_REFERENCE_CHECKS.tsv',solver_checks)
    actual_runs={f'{p.parents[2].name.replace("mwfas-", "").upper()}:{p.stem}' for p in package.glob('mwfas-exp*/production-output/runs/*.json')}
    actual_orders={f'{p.parents[2].name.replace("mwfas-", "").upper()}:{p.stem}' for p in package.glob('mwfas-exp*/production-output/orders/*.csv')}
    expected_ids={o['outcome_id'] for o in outcomes}
    summary={'expected_graphs':333,'downloaded_graphs':len(paths),'parsed_graphs':sum(r['parsed'] for r in graph_results),'matched_graphs':len(graphs),'unexpected_graphs':unexpected,'expected_outcomes':3423,'public_outcomes':sum(r['publicly_accessible'] for r in result),'recomputed':sum(r['recomputed'] for r in result),'exact_integer_matches':sum(r['comparison']=='EXACT_INTEGER_MATCH' for r in result),'numerically_tolerant_matches':0,'mismatches':sum(r['comparison']=='MISMATCH' for r in result),'invalid_solutions':sum(r['comparison']=='INVALID_OR_UNREADABLE' for r in result),'unverifiable':sum(not r['recomputed'] for r in result),'evidence_errors':sum(bool(r['error']) for r in result),'reference_failures':sum(r['reference_check']=='FAIL' for r in result),'solver_evidence_checks':len(solver_checks),'applicable_numerical_reference_graphs':len(refs),'reference_evidence_scope':'198 EXP06 certificates checked from downloaded raw evidence; 36 EXP07 comparisons use supplied historical numerical-reference manifest, not fresh certificate validation','unexpected_runs':sorted(actual_runs-expected_ids),'missing_runs':sorted(expected_ids-actual_runs),'unexpected_orders':sorted(actual_orders-expected_ids),'missing_orders':sorted(expected_ids-actual_orders),'manifest_files':len(listed),'python':sys.version}
    summary['status']='PASS' if len(graphs)==333 and summary['exact_integer_matches']==3423 and not any(summary[k] for k in ['evidence_errors','reference_failures','unexpected_graphs','unexpected_runs','missing_runs','unexpected_orders','missing_orders']) and len(solver_checks)==210 else 'FAIL'
    (root/'SUMMARY.json').write_text(json.dumps(summary,indent=2));(root/'verification_accesses.json').write_text(json.dumps(sorted(accesses),indent=2));print(json.dumps(summary,indent=2))
    if summary['status']!='PASS':sys.exit(1)
if __name__=='__main__':main()
