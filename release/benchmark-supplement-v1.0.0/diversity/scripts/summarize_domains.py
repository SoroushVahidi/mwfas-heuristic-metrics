import json,csv
from pathlib import Path
from collections import Counter
root=Path(__file__).resolve().parents[1];domains=json.loads((root/'inputs/source_domains.json').read_text());g=list(csv.DictReader((root/'GRAPH_DIVERSITY_FEATURES.tsv').open(),delimiter='\t'));output=[]
for parent,domain in sorted(domains.items()):
 selected=[r for r in g if r['parent_id']==parent];output.append({'parent_id':parent,'application_domain':domain,'records':len(selected),'origin_class':selected[0]['origin_class'],'domain_classification':'curated from authoritative source description; not a statistical independence claim'})
with (root/'SOURCE_DOMAIN_MAP.tsv').open('w') as f:
 w=csv.DictWriter(f,output[0].keys(),delimiter='\t');w.writeheader();w.writerows(output)
