import csv,json,sys
from pathlib import Path
from collections import Counter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
root=Path(sys.argv[1]);out=root/'figures';out.mkdir(exist_ok=True);rows=list(csv.DictReader((root/'GRAPH_DIVERSITY_FEATURES.tsv').open(),delimiter='\t'))
plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'ps.fonttype':42,'figure.dpi':160,'savefig.dpi':300,'svg.hashsalt':'mwfas-diversity-audit-v1'})
colors={'generated':'#777777','traceable_empirical':'#0072B2','unresolved_collection':'#D55E00'};labels={'generated':'Generated (378 records)','traceable_empirical':'Traceable empirical (44 views)','unresolved_collection':'Ali collection (20 records)'}
fig,axes=plt.subplots(1,2,figsize=(7.6,3.45),layout='constrained')
for ax,ykey,title,ylabel in [(axes[0],'density','(a) Size and directed density','Unique arc density'),(axes[1],'cyclic_edge_fraction','(b) Extent of cyclic structure','Fraction of arcs in cyclic SCCs')]:
 for origin in colors:
  data=[r for r in rows if r['origin_class']==origin];ax.scatter([float(r['n']) for r in data],[float(r[ykey]) for r in data],s=16 if origin=='generated' else 30,marker='x' if origin=='unresolved_collection' else 'o',color=colors[origin],alpha=.55 if origin=='generated' else .85,label=labels[origin],linewidths=.6)
 ax.set_xscale('log');ax.set_xlabel('Declared / represented vertices');ax.set_ylabel(ylabel);ax.set_title(title,loc='left',fontsize=10);ax.grid(alpha=.15)
axes[0].set_yscale('log');axes[1].set_ylim(-.035,1.04)
handles,names=axes[0].get_legend_handles_labels();fig.legend(handles,names,loc='outside lower center',ncol=3,frameon=False,fontsize=8)
for ext in ['pdf','svg','png']:fig.savefig(out/f'structural_coverage.{ext}',metadata={'CreationDate':None} if ext=='pdf' else {'Date':None} if ext=='svg' else None)
plt.close(fig)
emp=[r for r in rows if r['origin_class']=='traceable_empirical'];counts=Counter(r['parent_id'] for r in emp);short={'exiobase_lop_benchmark':'EXIOBASE-derived','college_msg':'CollegeMsg','Wikimedia_clickstream':'Wikimedia clickstream','email_eu_core':'Email-Eu-core','wiki_vote':'Wiki-Vote','census_lodes':'Census LODES','irs_soi':'IRS SOI','openflights':'OpenFlights'}
order=sorted(counts,key=lambda p:(-counts[p],p));fig,ax=plt.subplots(figsize=(7.2,3.6),layout='constrained');y=list(range(len(order)))
ax.barh(y,[100*counts[p]/44 for p in order],height=.6,color='#0072B2',label='Raw empirical record share')
ax.axvline(12.5,color='#D55E00',linestyle='--',linewidth=1.5,label='Equal-parent share (1/8)');ax.set_yticks(y,[f'{short[p]} (n={counts[p]})' for p in order]);ax.invert_yaxis();ax.set_xlim(0,75);ax.set_xlabel('Share of 44 traceable empirical views (%)');ax.set_title('Empirical coverage is concentrated in one source lineage',loc='left',fontsize=11);ax.legend(loc='lower right',frameon=False,fontsize=8);ax.grid(axis='x',alpha=.15)
for ext in ['pdf','svg','png']:fig.savefig(out/f'source_dependence.{ext}',metadata={'CreationDate':None} if ext=='pdf' else {'Date':None} if ext=='svg' else None)
plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(7.4,3.6),layout='constrained');axes[0].set_title('(a) Weight and degree concentration',loc='left',fontsize=10)
for origin in colors:
 d=[r for r in rows if r['origin_class']==origin];axes[0].scatter([float(r['total_degree_gini']) for r in d],[float(r['weight_top_decile_share']) for r in d],s=17,color=colors[origin],alpha=.6,marker='x' if origin=='unresolved_collection' else 'o')
axes[0].set_xlabel('Total-degree Gini coefficient');axes[0].set_ylabel('Weight share of heaviest 10% of arcs');axes[0].grid(alpha=.15)
classes=['NUMERICAL_SOLVER_CERTIFIED','FEASIBLE_WITH_BOUND','NO_NUMERICAL_REFERENCE'];clabels=['Numerically certified','Bounded','No numerical reference'];cc=['#0072B2','#E69F00','#BBBBBB'];groups=[('n ≤ 28',lambda x:x<=28),('28 < n ≤ 240',lambda x:28<x<=240),('n > 240',lambda x:x>240)];bottom=[0,0,0]
for c,label,color in zip(classes,clabels,cc):
 nums=[sum(r['reference_class']==c and fn(float(r['n'])) for r in rows) for _,fn in groups];axes[1].bar(range(3),nums,bottom=bottom,color=color,label=label,width=.65)
 for i,n in enumerate(nums):
  if n>=8:axes[1].text(i,bottom[i]+n/2,str(n),ha='center',va='center',fontsize=8,color='white' if c==classes[0] else 'black')
  elif n:axes[1].annotate(str(n),xy=(i,n/2+bottom[i]),xytext=(i+.48,7),ha='center',fontsize=8,color=color,arrowprops={'arrowstyle':'-','color':color,'lw':.7})
 bottom=[a+b for a,b in zip(bottom,nums)]
axes[1].set_xticks(range(3),[name for name,fn in groups],rotation=15);axes[1].set_ylabel('Graph records');axes[1].set_title('(b) Reference coverage by size',loc='left',fontsize=10);axes[1].legend(frameon=False,fontsize=7,loc='upper right');axes[1].set_ylim(0,270);axes[1].set_xlim(-.6,2.7)
from matplotlib.lines import Line2D
fig.legend([Line2D([],[],marker='o' if k!='unresolved_collection' else 'x',color=colors[k],linestyle='') for k in colors],list(labels.values()),loc='outside lower center',ncol=3,frameon=False,fontsize=7)
for ext in ['pdf','svg','png']:fig.savefig(out/f'weight_and_reference_coverage.{ext}',metadata={'CreationDate':None} if ext=='pdf' else {'Date':None} if ext=='svg' else None)
plt.close(fig)
(root/'evidence/PLOTTING_ENVIRONMENT.json').write_text(json.dumps({'python':sys.version,'executable':sys.executable,'matplotlib':matplotlib.__version__},indent=2))
