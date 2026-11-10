import csv,json,math,statistics,sys
from pathlib import Path
from collections import Counter,defaultdict
from compute_features import rows,tsv
root=Path(sys.argv[1]);rr=rows(root/'GRAPH_DIVERSITY_FEATURES.tsv');assert len(rr)==442 and all(r['feature_status']=='COMPLETE' for r in rr)
num=['n','m','density','in_degree_mean','out_degree_mean','largest_scc_fraction','cyclic_edge_fraction','cyclic_vertex_fraction','reciprocal_edge_fraction','total_degree_gini','weight_top_decile_share','weight_cv','tied_arc_fraction','observed_heuristic_spread_over_total','reference_relative_width','best_heuristic_relative_gap_to_certified','exp06_solver_process_wall_seconds']
for r in rr:
 for k in num:r[k]=None if r[k]=='NA' else float(r[k])
 r['topology_key']=(r['topology_contract'],r['topology_sha256'])
 r['difficulty_regime']='observed_timeout' if int(r['timeout_outcomes']) else 'bounded_reference' if r['reference_class']=='FEASIBLE_WITH_BOUND' else 'certified_reference_hit' if r['best_heuristic_hits_numerical_reference']=='True' else 'certified_reference_gap' if r['reference_class']=='NUMERICAL_SOLVER_CERTIFIED' else 'feasible_without_certificate'
 r['source_unit']=r['family'] if r['origin_class']=='generated' else r['parent_id']
topcounts=Counter(r['topology_key'] for r in rr);pc=Counter(r['parent_id'] for r in rr);uc=Counter(r['source_unit'] for r in rr)
def quantile_weighted(pairs,q):
 pairs=sorted(pairs);target=q*sum(w for v,w in pairs);cum=0
 for v,w in pairs:
  cum+=w
  if cum>=target-1e-12:return v
 return pairs[-1][0]
metrics=['n','density','largest_scc_fraction','cyclic_edge_fraction','cyclic_vertex_fraction','reciprocal_edge_fraction','total_degree_gini','weight_top_decile_share','weight_cv']
bins={}
for key in metrics:
 vals=[(r[key],1/topcounts[r['topology_key']]) for r in rr]
 # Feature-conditioned empirical terciles of topology-balanced distribution.
 cuts=sorted(set(quantile_weighted(vals,q) for q in [1/3,2/3]));maximum=max(v for v,w in vals);cuts=[v for v in cuts if v<maximum]
 bins[key]={'cuts':cuts,'method':'inverse topology multiplicity weighted empirical terciles; ties never split','population':'all 442 records / 343 labeled topology identities','min':min(v for v,w in vals),'max':maximum}
 def label(x):return 'lower' if x<=cuts[0] else 'middle' if len(cuts)>1 and x<=cuts[1] else 'upper' if len(cuts)>1 else 'upper'
 for r in rr:r[key+'_bin']=label(r[key]) if cuts else 'constant'
(root/'BIN_DEFINITIONS.json').write_text(json.dumps(bins,indent=2))
# Meaningful exact boundaries complement relative bins, without calling terciles universal classes.
for r in rr:
 r['cycle_support']='acyclic' if r['cyclic_edge_fraction']==0 else 'all_edges_cyclic' if r['cyclic_edge_fraction']==1 else 'mixed_cyclic_acyclic_edges'
 r['scc_support']='one_SCC' if int(r['scc_count'])==1 else 'multiple_SCCs'
 r['weight_support']='unit' if r['unit_weight']=='True' else 'constant_nonunit' if int(r['distinct_weights'])==1 else 'variable_integer'
 r['isolates_support']='isolates_present' if int(r['isolated_vertices']) else 'none_in_recorded_vertex_universe'
 r['density_support']='complete_bidirected' if r['density']==1 else 'not_complete'
fields=[k+'_bin' for k in metrics]+['cycle_support','scc_support','weight_support','isolates_support','density_support','origin_class','family','reference_class','difficulty_regime']
coverage=[]
scopes={'all':rr,'table45':[r for r in rr if r['table45']=='True'],'traceable_empirical':[r for r in rr if r['origin_class']=='traceable_empirical'],'EXP05':[r for r in rr if r['cohort']=='EXP05']}
for scope,data in scopes.items():
 ctop=Counter(r['topology_key'] for r in data);cparent=Counter(r['parent_id'] for r in data);cunit=Counter(r['source_unit'] for r in data)
 for field in fields:
  for value in sorted({r[field] for r in rr}):
   selected=[r for r in data if r[field]==value];mass=sum(1/cparent[r['parent_id']] for r in selected)
   coverage.append({'scope':scope,'dimension':field,'category':value,'records':len(selected),'denominator_records':len(data),'record_fraction':len(selected)/len(data),'distinct_labeled_topologies':len({r['topology_key'] for r in selected}),'topology_balanced_fraction':sum(1/ctop[r['topology_key']] for r in selected)/len(ctop),'registered_parent_balanced_fraction':mass/len(cparent),'family_or_empirical_parent_balanced_fraction':sum(1/cunit[r['source_unit']] for r in selected)/len(cunit),'traceable_empirical_parents':len({r['parent_id'] for r in selected if r['origin_class']=='traceable_empirical'}),'denominator_registered_parents':len(cparent),'denominator_family_or_parent_units':len(cunit)})
tsv(root/'STRUCTURAL_COVERAGE_MATRIX.tsv',coverage)
parents=[];pmeta={x['parent_id']:x for x in rows(root/'inputs/source_parents.csv')}
for pid in sorted(pc):
 data=[r for r in rr if r['parent_id']==pid];p=pmeta[pid]
 assert len(data)==int(p['scoped_graph_views'])
 parents.append({'parent_id':pid,'parent_kind':p['parent_kind'],'origin_class':data[0]['origin_class'],'records':len(data),'distinct_labeled_topologies':len({r['topology_key'] for r in data}),'weighted_identities':len({r['weighted_sha256'] for r in data}),'cohorts':','.join(sorted({r['cohort'] for r in data})),'record_fraction_all':len(data)/442,'empirical_record_fraction':len(data)/44 if data[0]['origin_class']=='traceable_empirical' else 'NA','equal_empirical_parent_mass':1/8 if data[0]['origin_class']=='traceable_empirical' else 'NA','n_min':min(r['n'] for r in data),'n_max':max(r['n'] for r in data),'density_median':statistics.median(r['density'] for r in data),'cyclic_edge_fraction_median':statistics.median(r['cyclic_edge_fraction'] for r in data),'weight_top_decile_share_median':statistics.median(r['weight_top_decile_share'] for r in data),'direct_public_graphs':sum(r['public_availability']=='PUBLIC_RELEASE_BYTES' for r in data),'reconstruction_routes':sum(r['public_availability']=='PUBLIC_RECONSTRUCTIBLE' for r in data),'timeout_graphs':sum(int(r['timeout_outcomes'])>0 for r in data),'certified_reference_graphs':sum(r['reference_class']=='NUMERICAL_SOLVER_CERTIFIED' for r in data),'independence_note':p['independence_note'],'provenance_class':p['provenance_class']})
tsv(root/'SOURCE_PARENT_DIVERSITY.tsv',parents)
# Profiles: controlled design cell medoids first, then add coverage witnesses.
# Rank features avoid scale dominance and do not require model fitting.
rankkeys=['n','density','cyclic_edge_fraction','largest_scc_fraction','total_degree_gini','weight_top_decile_share','reciprocal_edge_fraction']
ranks={}
for k in rankkeys:
 values=sorted(set(r[k] for r in rr));pos={v:i/max(1,len(values)-1) for i,v in enumerate(values)}
 for r in rr:ranks.setdefault(r['graph_id'],[]).append(pos[r[k]])
def distance(a,b):return sum(abs(x-y) for x,y in zip(ranks[a['graph_id']],ranks[b['graph_id']]))
def medoid(data,eligible=None):
 candidates=data if eligible is None else eligible
 return min(candidates,key=lambda r:(sum(distance(r,s) for s in data)/len(data),r['graph_id']))
def tokens(r):
 return {(k,r[k]) for k in [x+'_bin' for x in metrics]+['cycle_support','scc_support','weight_support','difficulty_regime']}
def profile(name,data,seed=None):
 selected=[] if seed is None else list(seed);why={r['graph_id']:'retained table45 core' for r in selected};used={r['topology_key'] for r in selected}
 if seed is None:
  groups=defaultdict(list)
  for r in data:groups[(r['family'],r['weight_regime'],r['n'])].append(r)
  # Preserve family × recorded weight regime × actual design size cells.
  for key,group in sorted(groups.items()):
   eligible=[r for r in group if r['topology_key'] not in used];assert eligible
   choice=medoid(group,eligible);selected.append(choice);used.add(choice['topology_key']);why[choice['graph_id']]='medoid of '+repr(key)
 else:
  for pid in sorted({r['parent_id'] for r in data if r['origin_class']=='traceable_empirical'}):
   group=[r for r in data if r['parent_id']==pid];choice=medoid(group);selected.append(choice);used.add(choice['topology_key']);why[choice['graph_id']]='empirical-parent medoid'
  # Ali collection is mixed-origin; retain collection subgroups, not invented parents.
  groups=defaultdict(list)
  for r in data:
   if r['origin_class']=='unresolved_collection':groups[r['weight_regime'].split('/')[0]].append(r)
  for key,group in sorted(groups.items()):
   eligible=[r for r in group if r['topology_key'] not in used]
   if eligible:
    choice=medoid(group,eligible);selected.append(choice);used.add(choice['topology_key']);why[choice['graph_id']]='Ali collection subgroup '+key+' (not an independent empirical source)'
 target=set().union(*(tokens(r) for r in data));covered=set().union(*(tokens(r) for r in selected));missing=target-covered
 while missing:
  candidates=[r for r in data if r['topology_key'] not in used and len(tokens(r)&missing)>0 and (r['origin_class']!='traceable_empirical' or sum(s['parent_id']==r['parent_id'] for s in selected)<2)]
  if not candidates:break
  choice=min(candidates,key=lambda r:(-len(tokens(r)&missing),sum(distance(r,s) for s in data)/len(data),r['graph_id']))
  why[choice['graph_id']]='covers '+repr(sorted(tokens(choice)&missing));selected.append(choice);used.add(choice['topology_key']);missing-=tokens(choice)
 return selected,why,sorted(missing)
core,cwhy,cmiss=profile('table45_core',scopes['table45']);expanded,ewhy,emiss=profile('existing_source_diverse',rr,core)
ledger={r['benchmark_record_id']:r for r in rows(root/'inputs/RECORD_AVAILABILITY_LEDGER.tsv')};manifest=[]
for name,selected,why in [('table45_core',core,cwhy),('existing_source_diverse',expanded,ewhy)]:
 for r in sorted(selected,key=lambda r:r['graph_id']):
  l=ledger[r['graph_id']];manifest.append({'profile':name,'graph_id':r['graph_id'],'cohort':r['cohort'],'instance_id':r['instance_id'],'parent_id':r['parent_id'],'family':r['family'],'weight_regime':r['weight_regime'],'n':int(r['n']),'m':int(r['m']),'weighted_sha256':r['weighted_sha256'],'topology_sha256':r['topology_sha256'],'raw_sha256':r['raw_sha256'],'public_release_reference':l['public_release_reference'],'existing_input_reference':l['original_input_reference'],'local_verified_input':l['candidate_input_file'],'public_availability':r['public_availability'],'rights_class':r['rights_class'],'selection_reason':why[r['graph_id']]})
tsv(root/'BALANCED_SUBSET_MANIFEST.tsv',manifest)
profile_stats={}
for name,data,missing in [('table45_core',core,cmiss),('existing_source_diverse',expanded,emiss)]:
 profile_stats[name]={'records':len(data),'topologies':len({r['topology_key'] for r in data}),'traceable_empirical_parents':len({r['parent_id'] for r in data if r['origin_class']=='traceable_empirical'}),'cohorts':dict(Counter(r['cohort'] for r in data)),'origins':dict(Counter(r['origin_class'] for r in data)),'public_access':dict(Counter(r['public_availability'] for r in data)),'uncovered_marginal_tokens':missing,'n_range':[min(r['n'] for r in data),max(r['n'] for r in data)]}
(root/'PROFILE_ASSESSMENT.json').write_text(json.dumps(profile_stats,indent=2))
# Summaries used in reporting. No inferred hardness label or algorithm winner.
summary={'records':len(rr),'cohorts':dict(Counter(r['cohort'] for r in rr)),'origins':dict(Counter(r['origin_class'] for r in rr)),'families':dict(Counter(r['family'] for r in rr)),'traceable_empirical_parents':8,'registered_parents':288,'topologies':len(topcounts),'records_n_gt_1000':sum(r['n']>1000 for r in rr),'records_n_gt_10000':sum(r['n']>10000 for r in rr),'parents_n_gt_10000':sorted({r['parent_id'] for r in rr if r['n']>10000}),'acyclic_records':[{k:r[k] for k in ['graph_id','instance_id','cohort','n']} for r in rr if r['cyclic_edge_fraction']==0],'timeout_graphs':sum(int(r['timeout_outcomes'])>0 for r in rr),'timeout_tasks':sum(int(r['timeout_outcomes']) for r in rr),'reference_classes':dict(Counter(r['reference_class'] for r in rr)),'difficulty_regimes':dict(Counter(r['difficulty_regime'] for r in rr)),'certified_n_range':[min(r['n'] for r in rr if r['reference_class']=='NUMERICAL_SOLVER_CERTIFIED'),max(r['n'] for r in rr if r['reference_class']=='NUMERICAL_SOLVER_CERTIFIED')],'unit_weight_records':sum(r['unit_weight']=='True' for r in rr),'all_integer_positive':True,'parallel_record_excess':sum(int(r['parallel_record_excess']) for r in rr),'isolated_vertex_graphs':sum(int(r['isolated_vertices'])>0 for r in rr),'profiles':profile_stats}
for key in ['all','table45','traceable_empirical','EXP05']:
 data=scopes[key];summary[key]={'records':len(data),'topologies':len({r['topology_key'] for r in data}),'size_range':[min(r['n'] for r in data),max(r['n'] for r in data)],'feature_ranges':{k:[min(r[k] for r in data),statistics.median(r[k] for r in data),max(r[k] for r in data)] for k in metrics},'cyclic_edges_eq_one':sum(r['cyclic_edge_fraction']==1 for r in data),'cyclic_edges_ge_09':sum(r['cyclic_edge_fraction']>=.9 for r in data),'reciprocity_zero':sum(r['reciprocal_edge_fraction']==0 for r in data),'density_half':sum(r['density']==.5 for r in data)}
(root/'DIVERSITY_SUMMARY.json').write_text(json.dumps(summary,indent=2))
# Selected cross-dimensions expose concentration hidden by balanced marginal bins.
cross=[]
for scope,data in scopes.items():
 for a,b in [('n_bin','density_bin'),('n_bin','reference_class'),('origin_class','n_bin'),('origin_class','weight_top_decile_share_bin')]:
  for av in sorted({r[a] for r in rr}):
   for bv in sorted({r[b] for r in rr}):
    cells=[r for r in data if r[a]==av and r[b]==bv];cross.append({'scope':scope,'dimension_a':a,'category_a':av,'dimension_b':b,'category_b':bv,'records':len(cells),'topologies':len({r['topology_key'] for r in cells}),'traceable_empirical_parents':len({r['parent_id'] for r in cells if r['origin_class']=='traceable_empirical'})})
tsv(root/'STRUCTURAL_CROSS_COVERAGE.tsv',cross)
print(json.dumps({'bins':bins,'profiles':profile_stats},indent=2))
# Analysis weights are supplied, not implied by a selected-record mean.
profile_weights=[]
for name,data in [('table45_core',core),('existing_source_diverse',expanded)]:
 epc=Counter(r['parent_id'] for r in data if r['origin_class']=='traceable_empirical');fc=Counter(r['family'] for r in data if r['origin_class']=='generated');unit=Counter(r['source_unit'] for r in data)
 for r in data:profile_weights.append({'profile':name,'graph_id':r['graph_id'],'equal_record_weight':1/len(data),'empirical_parent_balanced_weight':1/len(epc)/epc[r['parent_id']] if r['origin_class']=='traceable_empirical' else 'NA','synthetic_family_balanced_weight':1/len(fc)/fc[r['family']] if r['origin_class']=='generated' else 'NA','optional_family_parent_collection_balanced_weight':1/len(unit)/unit[r['source_unit']],'caution':'Empirical and synthetic weights describe separate strata; Ali remains a collection, not an empirical source.'})
tsv(root/'BALANCED_PROFILE_WEIGHTS.tsv',profile_weights)
