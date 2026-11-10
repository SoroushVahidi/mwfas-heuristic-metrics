import csv,json,math,sys
from pathlib import Path
from collections import Counter,defaultdict
root=Path(sys.argv[1]);read=lambda p:list(csv.DictReader((root/p).open(),delimiter='\t' if p.endswith('.tsv') else ','))
g=read('GRAPH_DIVERSITY_FEATURES.tsv');orig=read('inputs/graphs.csv');p=read('SOURCE_PARENT_DIVERSITY.tsv');subset=read('BALANCED_SUBSET_MANIFEST.tsv');w=read('BALANCED_PROFILE_WEIGHTS.tsv');by={r['graph_id']:r for r in g}
assert len(g)==len(by)==442 and set(by)=={r['graph_id'] for r in orig}
assert len(p)==288 and sum(int(x['records']) for x in p)==442
assert sum(x['origin_class']=='traceable_empirical' for x in p)==8
assert sum(x['origin_class']=='unresolved_collection' for x in p)==1
assert all(x['feature_status']=='COMPLETE' and not x['error'] for x in g)
assert len({(x['normalization_contract'],x['weighted_sha256']) for x in g})==442
assert len({(x['topology_contract'],x['topology_sha256']) for x in g})==343
assert Counter(x['public_availability'] for x in g)=={'PUBLIC_RELEASE_BYTES':381,'PUBLIC_RECONSTRUCTIBLE':61}
assert sum(int(x['saved_outcomes_verified']) for x in g)==5131
assert Counter(x['reference_class'] for x in g)=={'NUMERICAL_SOLVER_CERTIFIED':218,'FEASIBLE_WITH_BOUND':25,'NO_NUMERICAL_REFERENCE':199}
for profile in {r['profile'] for r in subset}:
 selected=[r for r in subset if r['profile']==profile];assert len(selected)==len({r['graph_id'] for r in selected})==len({r['topology_sha256'] for r in selected})
 assert all(r['weighted_sha256']==by[r['graph_id']]['weighted_sha256'] and r['raw_sha256']==by[r['graph_id']]['raw_sha256'] for r in selected)
 if profile=='table45_core':
  assert all(by[r['graph_id']]['table45']=='True' for r in selected)
  cells=lambda data:{(r['family'],r['weight_regime'],int(r['n'])) for r in data}
  assert cells(selected)==cells([r for r in g if r['table45']=='True'])
 else:assert {by[r['graph_id']]['parent_id'] for r in selected if by[r['graph_id']]['origin_class']=='traceable_empirical'}=={r['parent_id'] for r in g if r['origin_class']=='traceable_empirical'}
 for col in ['equal_record_weight','empirical_parent_balanced_weight','synthetic_family_balanced_weight','optional_family_parent_collection_balanced_weight']:
  vals=[float(r[col]) for r in w if r['profile']==profile and r[col]!='NA']
  if vals:assert math.isclose(sum(vals),1,abs_tol=1e-12),(profile,col)
coverage=read('STRUCTURAL_COVERAGE_MATRIX.tsv');groups=defaultdict(list)
for r in coverage:groups[r['scope'],r['dimension']].append(r)
for key,group in groups.items():
 assert sum(int(x['records']) for x in group)==int(group[0]['denominator_records'])
 for col in ['record_fraction','topology_balanced_fraction','registered_parent_balanced_fraction','family_or_empirical_parent_balanced_fraction']:assert math.isclose(sum(float(x[col]) for x in group),1,abs_tol=1e-12)
cons=read('evidence/INDEPENDENT_CONSISTENCY.tsv');assert len(cons)==442 and all(x['status']=='PASS' for x in cons)
print(json.dumps({'status':'PASS','authoritative_records':442,'complete_features':442,'registered_parent_joins':288,'traceable_empirical_parent_lineages':8,'unresolved_collection':1,'topology_identities':343,'weighted_identities':442,'profile_checks':'PASS','coverage_weights':'PASS','independent_consistency_records':len(cons)},indent=2))
