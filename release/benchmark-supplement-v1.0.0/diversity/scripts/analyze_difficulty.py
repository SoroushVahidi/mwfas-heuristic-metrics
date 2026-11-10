import csv,json,statistics,hashlib
from collections import Counter,defaultdict
from pathlib import Path
from compute_features import rows,tsv
root=Path(__file__).resolve().parents[1];g=rows(root/'GRAPH_DIVERSITY_FEATURES.tsv');by={x['graph_id']:x for x in g};o=rows(root/'inputs/run_outcomes.csv');refs=rows(root/'inputs/numerical_references.csv')
status=Counter((x['cohort'],x['algorithm'],x['status']) for x in o)
tsv(root/'DIFFICULTY_STATUS_COUNTS.tsv',[{'cohort':c,'algorithm':a,'status':s,'outcomes':n} for (c,a,s),n in sorted(status.items())])
summary={'original_outcome_statuses':dict(Counter(x['status'] for x in o)),'reference_graphs_by_cohort':{c:dict(Counter(x['reference_class'] for x in g if x['cohort']==c)) for c in sorted({x['cohort'] for x in g})},'timeout_graphs_by_parent':dict(Counter(x['parent_id'] for x in g if int(x['timeout_outcomes'])>0)),'solver_effort_EXP06_process_wall_by_n':{},'heuristic_certified_gaps_by_cohort':{}}
for n in sorted({int(x['n']) for x in g if x['cohort']=='EXP06'}):
 times=[float(x['exp06_solver_process_wall_seconds']) for x in g if x['cohort']=='EXP06' and int(x['n'])==n];summary['solver_effort_EXP06_process_wall_by_n'][n]={'records':len(times),'min':min(times),'median':statistics.median(times),'max':max(times)}
for c in ['EXP03','EXP04','EXP06']:
 a=[x for x in g if x['cohort']==c and x['reference_class']=='NUMERICAL_SOLVER_CERTIFIED'];vals=[float(x['best_heuristic_relative_gap_to_certified']) for x in a if x['best_heuristic_relative_gap_to_certified']!='NA'];summary['heuristic_certified_gaps_by_cohort'][c]={'graphs':len(a),'best_observed_heuristic_hits':sum(x['best_heuristic_hits_numerical_reference']=='True' for x in a),'relative_gap_median':statistics.median(vals),'relative_gap_max':max(vals)}
# Recompute the existing published source-composition sensitivity, no new arms/data.
arms=['insertion_lrta','insertion_wmsf','lrta','wmsf_l2','igraph_eades_weighted'];exp05=[x for x in g if x['cohort']=='EXP05'];complete=[];table={}
for x in exp05:
 obs={r['algorithm']:r for r in o if r['graph_id']==x['graph_id'] and r['algorithm'] in arms}
 if len(obs)==len(arms) and all(r['status']=='PASS' for r in obs.values()):complete.append(x);table[x['graph_id']]={a:int(obs[a]['objective_active'])/int(x['active_weight']) for a in arms}
means=[]
for arm in arms:
 pm={p:statistics.mean(table[x['graph_id']][arm] for x in complete if x['parent_id']==p) for p in sorted({x['parent_id'] for x in complete})}
 means.append({'arm':arm,'complete_views':len(complete),'parents':len(pm),'equal_view_mean':statistics.mean(table[x['graph_id']][arm] for x in complete),'equal_parent_mean':statistics.mean(pm.values())})
expected={'insertion_lrta':(.085449,.216708),'insertion_wmsf':(.085833,.218959),'lrta':(.090835,.226481),'wmsf_l2':(.092092,.240204),'igraph_eades_weighted':(.115093,.239209)}
assert all(tuple(round(x[k],6) for k in ['equal_view_mean','equal_parent_mean'])==expected[x['arm']] for x in means)
tsv(root/'EXISTING_EXP05_COMPOSITION_CHECK.tsv',means)
pc=Counter(x['parent_id'] for x in exp05);emp=[x for x in g if x['origin_class']=='traceable_empirical'];ep=Counter(x['parent_id'] for x in emp)
summary['EXP05']={'views':len(exp05),'parent_counts':dict(pc),'largest_parent_share':max(pc.values())/len(exp05),'inverse_parent_share_HHI':len(exp05)**2/sum(n*n for n in pc.values()),'complete_five_arm_views':len(complete),'complete_parent_counts':dict(Counter(x['parent_id'] for x in complete)),'historical_weighting_table_reproduced':True}
summary['traceable_empirical']={'views':len(emp),'parent_counts':dict(ep),'inverse_parent_share_HHI':len(emp)**2/sum(n*n for n in ep.values()),'interpretation':'composition concentration index, not statistical effective sample size'}
widths=[float(x['reference_relative_width']) for x in g if x['reference_class']=='FEASIBLE_WITH_BOUND'];summary['bounded_reference_relative_width']={'n':len(widths),'min':min(widths),'median':statistics.median(widths),'max':max(widths)}
(root/'DIFFICULTY_SUMMARY.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
# Read existing raw solver effort separately from wrapper wall time; no solver invocation.
ledger={r['benchmark_record_id']:r for r in rows(root/'inputs/RECORD_AVAILABILITY_LEDGER.tsv')};effort=[]
for r in g:
 if r['cohort']!='EXP06':continue
 base=Path(ledger[r['graph_id']]['candidate_input_file']).parent.parent;path=base/'solver_evidence'/(r['instance_id']+'__milp.json');raw=json.loads(path.read_text());run=json.loads((base/'runs'/(r['instance_id']+'__milp.json')).read_text())
 assert hashlib.sha256(path.read_bytes()).hexdigest()==run['raw_evidence_sha256']
 effort.append({'graph_id':r['graph_id'],'n':int(r['n']),'weight_regime':r['weight_regime'],'solver_runtime_seconds':raw['runtime_seconds'],'process_wall_seconds':r['exp06_solver_process_wall_seconds'],'solver_node_count':raw['solver_node_count'],'status':raw['status'],'evidence_sha256':run['raw_evidence_sha256']})
tsv(root/'DIFFICULTY_SOLVER_EFFORT.tsv',effort)
summary['EXP06_saved_solver_runtime_by_n']={n:{'records':sum(x['n']==n for x in effort),'median':statistics.median(x['solver_runtime_seconds'] for x in effort if x['n']==n),'max':max(x['solver_runtime_seconds'] for x in effort if x['n']==n)} for n in [12,20,28]}
(root/'DIFFICULTY_SUMMARY.json').write_text(json.dumps(summary,indent=2))
# Descriptive structure/difficulty associations within existing cohorts only.
assoc=[]
for label,pop,grouping in [
 ('EXP05_timeout',[r for r in g if r['cohort']=='EXP05'],lambda r:'timeout_observed' if int(r['timeout_outcomes']) else 'no_timeout_observed'),
 ('EXIOBASE_timeout',[r for r in g if r['parent_id']=='exiobase_lop_benchmark'],lambda r:'timeout_observed' if int(r['timeout_outcomes']) else 'no_timeout_observed'),
 ('EXP06_reference_hit',[r for r in g if r['cohort']=='EXP06'],lambda r:'best_heuristic_hit' if r['best_heuristic_hits_numerical_reference']=='True' else 'best_heuristic_gap')]:
 for level in sorted({grouping(r) for r in pop}):
  data=[r for r in pop if grouping(r)==level];row={'comparison':label,'group':level,'graphs':len(data),'registered_parent_units':len({r['parent_id'] for r in data})}
  for key in ['n','density','cyclic_edge_fraction','largest_scc_fraction','total_degree_gini','weight_cv','weight_top_decile_share']:
   row[key+'_median']=statistics.median(float(r[key]) for r in data)
  assoc.append(row)
tsv(root/'DIFFICULTY_STRUCTURAL_ASSOCIATIONS.tsv',assoc)
