"""Small independent table45 interface. MIT; no third-party dependencies.

Contract: all declared vertices 1..n, simple directed graph, positive integer
weights, no self-loops/parallel arcs. Empty graphs are supported. No repair.
"""
from dataclasses import dataclass
from pathlib import Path
from collections import deque
import csv, hashlib, io, json, re


def integer(text):
    if not isinstance(text,str) or re.fullmatch(r'-?[0-9]+',text) is None:
        raise ValueError('expected integer token')
    return int(text)

@dataclass(frozen=True)
class Graph:
    vertices: tuple
    arcs: tuple
    def __post_init__(self):
        if type(self.vertices) is not tuple or self.vertices != tuple(range(1,len(self.vertices)+1)) or any(type(v) is not int for v in self.vertices):
            raise ValueError('vertices must be integer tuple 1..n')
        if type(self.arcs) is not tuple: raise ValueError('arcs must be immutable tuple')
        seen=set()
        for edge in self.arcs:
            if type(edge) is not tuple or len(edge)!=3 or any(type(x) is not int for x in edge): raise ValueError('integer arc triple required')
            u,v,w=edge
            if not (1<=u<=len(self.vertices) and 1<=v<=len(self.vertices)) or u==v or w<=0: raise ValueError('invalid endpoint, loop, or weight')
            if (u,v) in seen: raise ValueError('duplicate directed arc')
            seen.add((u,v))


def parse_graph(text):
    header=None;arcs=[]
    for line in text.splitlines():
        fields=line.split()
        if not fields or fields[0]=='c': continue
        if fields[0]=='p':
            if header is not None or arcs or len(fields)!=4 or fields[1]!='sp': raise ValueError('invalid/duplicate header')
            header=tuple(integer(x) for x in fields[2:])
            if min(header)<0: raise ValueError('negative declared size')
        elif fields[0]=='a':
            if header is None or len(fields)!=4: raise ValueError('arc requires header and three integers')
            arcs.append(tuple(integer(x) for x in fields[1:]))
        else: raise ValueError('unknown graph record')
    if header is None or len(arcs)!=header[1]: raise ValueError('missing header or declared arc-count mismatch')
    return Graph(tuple(range(1,header[0]+1)),tuple(arcs))

def load_graph(path): return parse_graph(Path(path).read_text(encoding='utf-8'))

def identities(graph):
    common={'vertices':graph.vertices,'arcs':sorted(graph.arcs),'format':'mwfas-exp03-graph-v1',
            'normalization':{'directed':True,'node_labels':'1-based-integers','parallel_edges':'absent','self_loops':'absent','weight_type':'positive-integer'}}
    topology={'vertices':graph.vertices,'arcs':sorted((u,v) for u,v,w in graph.arcs),'format':'exp04-topology-v1','directed':True}
    digest=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'weighted_sha256':digest(common),'topology_sha256':digest(topology)}

def validate_order(graph,order):
    order=tuple(order)
    if any(type(v) is not int for v in order) or len(order)!=len(graph.vertices) or set(order)!=set(graph.vertices):
        raise ValueError('ordering must be a complete, duplicate-free integer permutation')
    return order

def load_order(path,graph):
    reader=csv.reader(io.StringIO(Path(path).read_text(encoding='utf-8-sig')))
    if next(reader,None)!=['Node ID','Order']: raise ValueError('ordering CSV header')
    pairs=[]
    for row in reader:
        if len(row)!=2: raise ValueError('ordering CSV row width')
        pairs.append(tuple(integer(x) for x in row))
    if sorted(rank for vertex,rank in pairs)!=list(range(len(graph.vertices))): raise ValueError('ranks must be exactly 0..n-1')
    return validate_order(graph,[v for v,r in sorted(pairs,key=lambda p:p[1])])

def evaluate(graph,order):
    order=validate_order(graph,order)
    # Eliminate vertices left to right: incoming arcs from unremoved vertices
    # must be deleted. This differs from the released rank-comparison scorer.
    incoming={v:[] for v in graph.vertices}
    for u,v,w in graph.arcs: incoming[v].append((u,w))
    unseen=set(graph.vertices);feedback=set();cost=0
    for v in order:
        unseen.remove(v)
        for u,w in incoming[v]:
            if u in unseen: cost+=w;feedback.add((u,v))
    # Independent rank formula and Kahn traversal of the retained graph.
    rank={v:i for i,v in enumerate(order)}
    if cost!=sum(w for u,v,w in graph.arcs if rank[u]>rank[v]): raise RuntimeError('cross-check mismatch')
    degree=dict.fromkeys(graph.vertices,0);children={v:[] for v in graph.vertices}
    for u,v,w in graph.arcs:
        if (u,v) not in feedback:children[u].append(v);degree[v]+=1
    ready=deque(v for v in graph.vertices if degree[v]==0);count=0
    while ready:
        v=ready.popleft();count+=1
        for u in children[v]:
            degree[u]-=1
            if degree[u]==0:ready.append(u)
    if count!=len(graph.vertices): raise ValueError('retained graph cyclic')
    return {'objective':cost,'feedback_arcs':len(feedback),'retained_dag':True,'valid_order':True}

def compare(graph,order,reference,reference_kind='saved_feasible'):
    if type(reference) is not int or reference<0: raise ValueError('nonnegative integer reference required')
    result=evaluate(graph,order);gap=result['objective']-reference
    result.update(reference=reference,reference_kind=reference_kind,absolute_gap=gap,
                  relative_gap=gap/reference if reference else (0.0 if gap==0 else None))
    return result

class Benchmark:
    """Use only a downloaded table45 directory; no historical ledger needed."""
    def __init__(self,root): self.root=Path(root)
    def instances(self):
        return sorted(f'{cohort}/{p.stem}' for cohort in ('exp04','exp06') for p in (self.root/f'mwfas-{cohort}/production-output/graphs').glob('*.d'))
    def _location(self,key):
        if key not in self.instances():raise ValueError('unknown benchmark instance')
        cohort,name=key.split('/');return self.root/f'mwfas-{cohort}/production-output',name
    def load(self,key):
        base,name=self._location(key);return load_graph(base/'graphs'/f'{name}.d')
    def saved_reference(self,key):
        base,name=self._location(key);graph=self.load(key);refs=[]
        for path in sorted((base/'runs').glob(name+'__*.json')):
            run=json.loads(path.read_text())
            if run['instance_id']!=name:continue
            if run['status'] not in ('PASS','CERTIFIED_OPTIMAL'):continue
            order=load_order(base/'orders'/f"{run['run_id']}.csv",graph)
            value=evaluate(graph,order)['objective']
            if value!=run['objective_weight']:raise ValueError('saved reference objective mismatch')
            refs.append((value,run['run_id']))
        if not refs:raise ValueError('no verified saved reference')
        value,run_id=min(refs);return {'objective':value,'run_id':run_id,'kind':'best_saved_feasible_not_optimality_proof'}
