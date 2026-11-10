"""Small, bounded functional checks of the unchanged author executable."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import deque
from pathlib import Path


def check_dag(n: int, arcs: list[tuple[int,int,int]], ranks: list[int]) -> bool:
    adj = [[] for _ in range(n)]; indeg = [0]*n
    for u,v,_ in arcs:
        if ranks[u] < ranks[v]: adj[u].append(v); indeg[v] += 1
    q = deque(i for i in range(n) if indeg[i] == 0); seen = 0
    while q:
        u = q.popleft(); seen += 1
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:q.append(v)
    return seen == n


def main() -> None:
    p=argparse.ArgumentParser();p.add_argument("--binary",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError("refusing to overwrite fidelity output")
    a.output.mkdir(parents=True)
    cases={
        "weighted_cycle":(3,[(0,1,9),(1,2,8),(2,0,2)]),
        "acyclic":(4,[(0,1,3),(1,2,7)]),
        "opposing_arcs":(3,[(0,1,9),(1,0,2),(1,2,5),(2,0,1)]),
        "disconnected_with_isolates":(6,[(0,1,4),(1,0,1),(3,4,6),(4,3,2)])}
    checks=[]
    for name,(n,arcs) in cases.items():
        graph=a.output/(name+".w")
        graph.write_text(f"{n} {len(arcs)}\n"+"".join(f"{u} {v} {w}\n" for u,v,w in arcs))
        for seed in (1,2):
            rank_path=a.output/f"{name}_s{seed}.rank"
            result=subprocess.run([str(a.binary),str(graph),"W","RASstar","-r",str(seed),"-p","-o",str(rank_path)],
                                  check=True,capture_output=True,text=True,timeout=10)
            ranks=list(map(int,rank_path.read_text().split()))
            if len(ranks)!=n or sorted(ranks)!=list(range(n)):raise ValueError("invalid rank permutation")
            objective=sum(w for u,v,w in arcs if ranks[u]>=ranks[v])
            if objective!=int(result.stdout.strip().split(",")[1]) or not check_dag(n,arcs,ranks):
                raise ValueError("weighted objective or DAG mismatch")
            checks.append({"case":name,"seed":seed,"status":"PASS","objective":objective,
                           "rank_sha256":hashlib.sha256(rank_path.read_bytes()).hexdigest()})
    report={"format":"exp10-functional-fidelity-v1","binary_sha256":hashlib.sha256(a.binary.read_bytes()).hexdigest(),
            "checks":checks,"status":"PASS"}
    (a.output/"fidelity.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":"PASS","checks":len(checks),"binary_sha256":report["binary_sha256"]}))


if __name__=="__main__":main()
