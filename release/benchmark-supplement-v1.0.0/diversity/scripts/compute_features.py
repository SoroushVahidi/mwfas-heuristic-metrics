import argparse,csv,hashlib,json,math,sys,time
from pathlib import Path
from collections import defaultdict,Counter
from graph_features import parse,features

def rows(p):
 with Path(p).open() as f:return list(csv.DictReader(f,delimiter='\t' if str(p).endswith('.tsv') else ','))
def tsv(path,data):
 keys=list(dict.fromkeys(k for r in data for k in r))
 with Path(path).open('w') as f:
  w=csv.DictWriter(f,keys,delimiter='\t',lineterminator='\n');w.writeheader();w.writerows({k:('NA' if v is None else v) for k,v in r.items()} for r in data)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(exist_ok=True)
 graphs=rows(a.inputs/'graphs.csv');ledger={r['benchmark_record_id']:r for r in rows(a.inputs/'RECORD_AVAILABILITY_LEDGER.tsv')};parents={r['parent_id']:r for r in rows(a.inputs/'source_parents.csv')};coverage={r['benchmark_record_id']:r for r in rows(a.inputs/'SOLUTION_REFERENCE_COVERAGE.tsv')}
 assert len(graphs)==len(ledger)==442 and len({r['graph_id'] for r in graphs})==442
 outcomes=defaultdict(list);refs={r['graph_id']:r for r in rows(a.inputs/'numerical_references.csv')}
 for r in rows(a.inputs/'run_outcomes.csv'):outcomes[r['graph_id']].append(r)
 result=[];started=time.time();receipt=[]
 for g in sorted(graphs,key=lambda x:x['graph_id']):
  gid=g['graph_id'];l=ledger[gid];p=parents[g['parent_id']];cov=coverage[gid];kind='wiki' if g['cohort']=='EXP14_EXP15' else 'ali' if g['cohort']=='EXP12' else 'integer';path=Path(l['candidate_input_file'])
  origin='generated' if p['parent_kind']=='GENERATED_TOPOLOGY_GROUP' else 'unresolved_collection' if g['parent_id']=='alidasdan/graph-benchmarks' else 'traceable_empirical'
  row={'graph_id':gid,'cohort':g['cohort'],'instance_id':g['instance_id'],'parent_id':g['parent_id'],'parent_kind':p['parent_kind'],'origin_class':origin,'family':g['family'],'weight_regime':g['source_view'],'weight_semantics':g['weight_semantics'],'normalization_contract':g['normalization_contract'],'objective_loop_constant':g['objective_loop_constant'],'public_availability':l['public_availability_status'],'rights_class':l['rights_classification'],'redistribution_permission':l['redistribution_permission'],'table45':g['cohort'] in ('EXP04','EXP06'),'saved_outcomes_verified':int(cov['new_objective_checks_passed']),'reference_class':refs.get(gid,{}).get('certificate_class','NO_NUMERICAL_REFERENCE'),'feature_status':'FAIL','error':''}
  try:
   data=path.read_bytes();v,e,ids=parse(data,kind);f=features(v,e)
   assert ids['raw_sha256']==g['serialized_graph_sha256']==l['expected_raw_file_sha256'],'raw identity'
   assert ids['weighted_sha256']==g['canonical_graph_sha256']==l['canonical_weighted_graph_hash'],'weighted identity'
   assert ids['topology_sha256']==l['canonical_topology_hash'],'topology identity'
   assert (f['n'],f['m'],f['active_weight'])==(int(g['vertices']),int(g['arcs']),int(g['active_weight'])),'authoritative size/weight mismatch'
   assert l['source_parent_id']==g['parent_id'],'parent join'
   row.update(ids,**f,feature_status='COMPLETE')
   receipt.append({'graph_id':gid,'input_path':str(path),'bytes':len(data),'sha256':ids['raw_sha256'],'identity_status':'PASS'})
  except Exception as ex:row['error']=repr(ex);receipt.append({'graph_id':gid,'input_path':str(path),'identity_status':'FAIL','error':repr(ex)})
  obs=outcomes[gid];feasible=[r for r in obs if r['status'] in ('PASS','CERTIFIED_OPTIMAL')];heur=[r for r in feasible if r['algorithm'] not in ('scipy_highs_ordering_milp','igraph_ip')];counts=Counter(r['status'] for r in obs)
  assert len(feasible)==int(cov['new_objective_checks_passed']),'prior outcome coverage'
  vals=[int(r['objective_active']) for r in heur];ref=refs.get(gid);lb=int(ref['lower_bound']) if ref else None;ub=int(ref['upper_bound']) if ref else None
  row.update(outcome_count=len(obs),timeout_outcomes=counts['TIMEOUT'],failed_outcomes=counts['FAIL'],skipped_outcomes=counts['SKIPPED_DEPENDENCY'],heuristic_feasible_outcomes=len(heur),heuristic_arms=len({r['algorithm'] for r in heur}),best_heuristic_objective=min(vals) if vals else None,worst_heuristic_objective=max(vals) if vals else None,reference_lower_bound=lb,reference_upper_bound=ub,reference_relative_width=(ub-lb)/ub if ub else 0. if ub==0 else None)
  total=int(g['active_weight']);row['observed_heuristic_spread_over_total']=(max(vals)-min(vals))/total if vals and total else None
  row['best_heuristic_gap_to_certified']=(min(vals)-ub) if vals and ref and ref['certificate_class']=='NUMERICAL_SOLVER_CERTIFIED' else None
  row['best_heuristic_relative_gap_to_certified']=(min(vals)-ub)/ub if vals and ub and ref['certificate_class']=='NUMERICAL_SOLVER_CERTIFIED' else None
  row['best_heuristic_hits_numerical_reference']=row['best_heuristic_gap_to_certified']==0 if row['best_heuristic_gap_to_certified'] is not None else None
  times=[float(r['process_wall_seconds']) for r in feasible if r['algorithm']=='scipy_highs_ordering_milp' and r['process_wall_seconds']]
  row['exp06_solver_process_wall_seconds']=times[0] if len(times)==1 else None
  result.append(row)
 tsv(a.out/'GRAPH_DIVERSITY_FEATURES.tsv',result);tsv(a.out/'GRAPH_INPUT_VERIFICATION.tsv',receipt)
 summary={'records':len(result),'complete':sum(r['feature_status']=='COMPLETE' for r in result),'failures':[{'graph_id':r['graph_id'],'error':r['error']} for r in result if r['feature_status']!='COMPLETE'],'weighted_identities':len({(r['normalization_contract'],r.get('weighted_sha256')) for r in result}),'topology_identities':len({(r.get('topology_contract'),r.get('topology_sha256')) for r in result}),'seconds':time.time()-started,'python':sys.version}
 (a.out/'COMPUTATION_RECEIPT.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
 if summary['complete']!=442:sys.exit(1)
if __name__=='__main__':main()
