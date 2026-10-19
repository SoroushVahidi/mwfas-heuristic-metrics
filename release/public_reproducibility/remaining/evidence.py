"""Verify a frozen archive; optionally replay available orders in an extracted tree.

--replay is intended for a later clean public-only replay, and is deliberately
not invoked by archival jobs that reuse accepted independent audit receipts.
"""
import argparse
import csv
import hashlib
import json
import tarfile
from collections import deque
from pathlib import Path


def require(condition,message):
    if not condition: raise ValueError(message)


def verify_archive(archive,manifest):
    with Path(manifest).open(newline='') as f: rows=list(csv.DictReader(f))
    expected={r['path']:r for r in rows}
    require(len(expected)==len(rows),'duplicate manifest path')
    seen=set()
    with tarfile.open(archive,'r|gz') as tar:
        for member in tar:
            require(member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts,'unsafe archive member')
            require(member.name in expected and member.name not in seen,'unexpected or duplicate archive member')
            row=expected[member.name]
            require(member.size==int(row['bytes']),'archive size mismatch')
            h=hashlib.sha256()
            stream=tar.extractfile(member)
            while chunk:=stream.read(1024*1024):h.update(chunk)
            require(h.hexdigest()==row['sha256'],'archive checksum mismatch: '+member.name)
            seen.add(member.name)
    require(seen==set(expected),'missing archive member')
    return {'status':'PASS','verified_files':len(seen)}


def graph(data):
    n=m=None;arcs=[]
    for line in data.decode().splitlines():
        f=line.split()
        if not f or f[0]=='c':continue
        if f[0]=='p' and len(f)==4 and n is None:n,m=map(int,f[2:])
        elif f[0]=='a' and len(f) in [4,5] and n is not None:
            if len(f)==5:int(f[4]) # Historical Ali annotation is not an edge weight.
            arcs.append(tuple(map(int,f[1:4])))
        else:raise ValueError('malformed graph')
    require(n is not None and n>0 and len(arcs)==m and len({(u,v) for u,v,w in arcs})==m,'invalid graph counts')
    require(all(1<=u<=n and 1<=v<=n and u!=v and w>0 for u,v,w in arcs),'invalid arc contract')
    normalization={'directed':True,'node_labels':'1-based-integers','parallel_edges':'absent','self_loops':'absent','weight_type':'positive-integer'}
    canonical={'format':'mwfas-exp03-graph-v1','normalization':normalization,'vertices':list(range(1,n+1)),'arcs':sorted(arcs)}
    digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return n,arcs,digest


def score(data,fmt,n,arcs):
    if fmt=='ranks':ranks=list(map(int,data.decode().split()))
    else:
        rows=list(csv.DictReader(data.decode().splitlines()));nodes=[int(r['Node ID']) for r in rows]
        require(sorted(nodes)==list(range(1,n+1)),'incomplete or duplicate vertices')
        ranks=[0]*n
        for row in rows:ranks[int(row['Node ID'])-1]=int(row['Order'])
    require(sorted(ranks)==list(range(n)),'not a complete permutation')
    adj=[[] for _ in range(n)];degree=[0]*n;cost=0
    for u,v,w in arcs:
        if ranks[u-1]>ranks[v-1]:cost+=w
        else:adj[u-1].append(v-1);degree[v-1]+=1
    todo=deque(i for i in range(n) if degree[i]==0);seen=0
    while todo:
        u=todo.popleft();seen+=1
        for v in adj[u]:
            degree[v]-=1
            if degree[v]==0:todo.append(v)
    require(seen==n,'retained graph is not a DAG')
    return cost


def replay(root):
    root=Path(root).resolve()
    def read(relative):
        p=(root/relative).resolve();require(p.is_relative_to(root),'private/external input path refused');return p.read_bytes()
    rows=list(csv.DictReader(read('recovery/available_order_checks.csv').decode().splitlines()))
    current=None;checked=0;graphs=set()
    for r in sorted(rows,key=lambda r:(r['graph_path'],r['order_path'])):
        if current!=r['graph_path']:
            data=read(r['graph_path']);require(hashlib.sha256(data).hexdigest()==r['graph_sha256'],'graph bytes differ')
            n,arcs,digest=graph(data);require(digest==r['canonical_graph_sha256'],'canonical graph differs')
            current=r['graph_path'];graphs.add(current)
        data=read(r['order_path']);require(hashlib.sha256(data).hexdigest()==r['order_sha256'],'order bytes differ')
        require(score(data,r['format'],n,arcs)==float(r['objective']),'objective differs');checked+=1
    return {'status':'PASS','graphs':len(graphs),'available_orders':checked,'classification':'AVAILABLE_ORDER_REPLAY_ONLY',
            'complete_public_table':False,'remaining':'Frozen manuscript statistical/displayed-cell comparison and anonymous provenance gate'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path);p.add_argument('--manifest',type=Path);p.add_argument('--replay',type=Path)
    a=p.parse_args()
    if a.replay:result=replay(a.replay)
    else:
        p.error('--archive and --manifest are required') if not(a.archive and a.manifest) else None
        result=verify_archive(a.archive,a.manifest)
    print(json.dumps(result,sort_keys=True))
