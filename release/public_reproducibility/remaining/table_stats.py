"""Recompute manuscript cells from validated original records and exact graph bytes."""
from collections import Counter,defaultdict
from pathlib import Path
from statistics import median
from fractions import Fraction
from evidence import require

PARENTS={'college_msg':'CollegeMsg','email_eu_core':'Email-Eu-core','wiki_vote':'Wiki-Vote','exiobase_lop_benchmark':'EXIOBASE'}
METHODS={'lrta':'LR-TA','wmsf_l2':'WMSF/L2','igraph_eades_weighted':'Weighted Eades','insertion_lrta':'Insertion from LR-TA','insertion_wmsf':'Insertion from WMSF','ipsns':'IPSNS'}

def exp05(pkg,records,graphs):
    require(len(records)==760,'original EXP05 task count');status=Counter(r['status'] for r in records)
    require(status=={'PASS':639,'FAIL':11,'TIMEOUT':108,'SKIPPED_DEPENDENCY':2},'original EXP05 statuses')
    byid={g['spec']['instance_id']:g for g in pkg['graphs']};runs={(r['instance_id'],r['algorithm']):r for r in records if r['algorithm']!='ipsns'}
    table5=[];table8=[];table12=[];inputs=[]
    for parent,label in PARENTS.items():
        selected=[g for g in byid.values() if g['spec']['source_parent']==parent];stats=[graphs[g['canonical']] for g in selected];ns=[x['n'] for x in stats];ms=[x['m'] for x in stats];ds=[x['m']/(x['n']*(x['n']-1)) for x in stats]
        table5.append([label+' matrices' if label=='EXIOBASE' else label,str(len(selected)),f'{min(ns):,}--{max(ns):,}',f'{min(ms):,}--{max(ms):,}',f'{min(ds):.5f}--{max(ds):.5f}',{'college_msg':'Message counts','email_eu_core':'Unit','wiki_vote':'Unit','exiobase_lop_benchmark':'Published integer weights'}[parent]])
        for method in ['wmsf_l2','igraph_eades_weighted','insertion_lrta','insertion_wmsf']:
            deltas=[]
            for g in selected:
                iid=g['spec']['instance_id'];a,b=runs[(iid,'lrta')],runs[(iid,method)]
                if a['status']==b['status']=='PASS':
                    delta=Fraction(int(b['objective_weight'])-int(a['objective_weight']),graphs[g['canonical']]['weight']);deltas.append(delta);inputs.append({'graph':iid,'comparator':method,'lrta':a['objective_weight'],'comparator_objective':b['objective_weight'],'total_weight':graphs[g['canonical']]['weight'],'delta':float(delta)})
            table8.append([label,METHODS[method],f'{len(deltas)}/{len(selected)}',f'{sum(d<0 for d in deltas)}/{sum(d==0 for d in deltas)}/{sum(d>0 for d in deltas)}',f'{float(median(deltas)):+.6f}'])
    for method in METHODS:
        selected=[r for r in records if r['algorithm']==method];c=Counter(r['status'] for r in selected)
        table12.append([METHODS[method],str(len(selected))]+[str(c[s]) for s in ['PASS','FAIL','TIMEOUT','SKIPPED_DEPENDENCY']])
    table12.append(['All original tasks',str(len(records))]+[str(status[s]) for s in ['PASS','FAIL','TIMEOUT','SKIPPED_DEPENDENCY']])
    return {'5':table5,'8':table8,'12':table12},inputs

def exp07(pkg,records,metadata,auxiliary):
    inv=next(x for x in metadata if x.get('format')=='mwfas-exp07-input-inventory-v1');require(len(inv['instances'])==45,'EXP07 selection count')
    require(Counter(r['status'] for r in records)=={'CERTIFIED_OPTIMAL':20,'FEASIBLE_UNCERTIFIED':25},'solver classes')
    byid={r['instance_id']:r for r in records};inputs=[];groups=defaultdict(list)
    workers={Path(x['__source']).stem:x for x in auxiliary if 'components' in x}
    for g in inv['instances']:
        r=byid[g['instance_id']];hs=g['heuristics'];require(len(hs)==6,'historical selection size');best={a:min(int(h['objective_weight']) for h in hs if h['algorithm']==a) for a in ['lrta','wmsf_l2','igraph_eades_weighted','ipsns']}
        lb=int(r['lower_bound']);inc=int(r['objective_weight']);ub=min(inc,*best.values());cert=r['status']=='CERTIFIED_OPTIMAL'
        require(0<lb<=ub<=inc,'solver bound ordering');require(not cert or lb==ub==inc,'numerical certificate equality')
        # Original per-SCC numerical certificates are evidence, not exact-arithmetic proofs.
        worker=workers[g['instance_id']];require(worker['lower_bound']==lb and worker['objective_weight']==inc,'worker/result mismatch')
        for a,h in best.items():
            low=Fraction(h-lb,lb) if cert else Fraction(max(0,h-ub),ub);high=Fraction(h-lb,lb)
            groups[(cert,a)].append((low,high));inputs.append({'graph':g['instance_id'],'method':a,'H':h,'LB':lb,'UB':ub,'incumbent':inc,'certified':cert,'lower':float(low),'upper':float(high)})
    rows=[]
    for cert in [True,False]:
        for a in ['lrta','wmsf_l2','igraph_eades_weighted','ipsns']:
            pairs=groups[(cert,a)];lo=float(median(x[0] for x in pairs));hi=float(median(x[1] for x in pairs))
            rows.append(['Certified' if cert else 'Uncertified',METHODS[a],str(len(pairs)),f'{lo:.4f}' if cert else '---','---' if cert else ('0' if lo==0 else f'{lo:.4f}'),'---' if cert else f'{hi:.4f}'])
    return {'11':rows},inputs

def exp1213(pkg,records,metadata):
    require(len(records)==161 and Counter(r['status'] for r in records)=={'PASS':159,'TIMEOUT':2},'EXP12/13 outcome coverage')
    bygraph=defaultdict(list)
    for r in records:bygraph[r['graph_sha256']].append(r)
    m12=next(m for m in metadata if m['format']=='exp12-run-manifest-v1');m13=next(m for m in metadata if m['format']=='exp13-run-manifest-v1')
    require(len(m12['tasks'])==140 and len(m13['tasks'])==21,'assigned tasks');ties=spread0=0;inputs=[]
    for g in m12['selected']:
        rs=bygraph[g['graph_sha256']];require(len(rs)==7 and all(r['status']=='PASS' for r in rs),'Ali original complete cohort')
        costs={a:min(r['objective'] for r in rs if r['algorithm']==a) for a in {r['algorithm'] for r in rs}};best=min(costs.values());ties+=sum(c==best for c in costs.values())>1;spread0+=len(set(costs.values()))==1
        inputs.append({'graph':g['instance_id'],'family_costs':costs,'historical_HF_byte_identity':False})
    rows=[['Ali collection',str(len(m12['selected'])),'140/140',f'{ties}/20 graphs: best-family ties',f'Four graphs: zero spread' if spread0==4 else f'{spread0} graphs: zero spread']]
    labels={'openflights':'OpenFlights','census_lodes':'Census LODES','irs_soi':'IRS SOI'}
    for g in m13['selected']:
        rs=bygraph[g['graph_sha256']];passed=[r for r in rs if r['status']=='PASS'];best=min(r['objective'] for r in passed);winners=[r for r in passed if r['objective']==best];p=g['source_parent']
        if p=='openflights':
            require(any(r['algorithm']=='xiong_rasstar' and r['seed']==1 for r in winners),'OpenFlights winner');desc='RASstar seed 1';interpretation='Seven feasible orders'
        elif p=='census_lodes':
            require(any(r['algorithm']=='insertion_wmsf_l2' for r in winners),'Census winner');desc='WMSF insertion';interpretation=f"Loop constant {g['original_loop_weight_constant']:,}"
        else:
            require(any(r['algorithm']=='lrta' for r in winners),'IRS winner');require({r['algorithm'] for r in rs if r['status']=='TIMEOUT'}=={'insertion_lrta','insertion_wmsf_l2'},'IRS timeout provenance');desc='LR-TA';interpretation='Two insertion timeouts'
        rows.append([labels[p],'1',f'{len(passed)}/{len(rs)}',f'{best:,} ({desc})',interpretation]);inputs.append({'source_parent':p,'loop_constant':g['original_loop_weight_constant'],'original_records':rs})
    return {'10':rows},inputs
