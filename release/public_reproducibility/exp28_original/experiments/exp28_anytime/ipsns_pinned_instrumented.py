"""
Versioned EXP28 instrumentation of the pinned IPSNS source at 40209c269662.

Only callback invocations and absolute dependency imports are added to the
optimization path. The original source and EXP27 release remain untouched.

Incumbent-Protected SCC-Neighborhood Search (IPSNS) for weighted MFAS.

Combines WMSF and LR-TA seeds, then improves via Large Neighborhood Search
(LNS) applied to one SCC at a time.

Guarantee: the output is never worse than the best of the two base solutions.
"""

import heapq
import random
import time
from collections import defaultdict, deque

from mwfas.io import read_graph_dimacs_agg
from mwfas.evaluation import compute_forward_backward
from mwfas.lrta import topo_order_active, make_reachability_checker
from mwfas.wmsf import (
    build_eid_graph_inout, kosaraju_scc, edges_by_scc, _is_acyclic_active,
    _build_local_scc_graph, _wmsf_pipeline_scc,
)


# ---------------------------------------------------------------------------
# Graph representation with mutable weights (needed for LR seed)
# ---------------------------------------------------------------------------

def build_eid_graph_inout_with_W(edges_indexed, n_nodes, tol=1e-12):
    """Build edge-ID arrays with out/in adjacency and mutable weight array W."""
    m = len(edges_indexed)
    U = [0] * m
    V = [0] * m
    W0 = [0.0] * m
    W = [0.0] * m
    active = bytearray(m)
    out_adj = [[] for _ in range(n_nodes)]
    in_adj = [[] for _ in range(n_nodes)]

    for eid, (u, v, w) in enumerate(edges_indexed):
        U[eid] = u
        V[eid] = v
        W0[eid] = float(w)
        W[eid] = float(w)
        if w > tol:
            active[eid] = 1
        out_adj[u].append(eid)
        in_adj[v].append(eid)

    return U, V, W0, W, active, out_adj, in_adj


# ---------------------------------------------------------------------------
# SCC-restricted cycle finder, topo sort, and reachability
# ---------------------------------------------------------------------------

def find_any_cycle_eids_restricted(n_nodes, out_adj, V, active, allowed_nodes, allowed_eids):
    """Find a directed cycle restricted to the given SCC (allowed_nodes/allowed_eids)."""
    state = bytearray(n_nodes)
    parent = [-1] * n_nodes
    parent_eid = [-1] * n_nodes
    next_ptr = [0] * n_nodes
    touched = []

    def reset():
        for x in touched:
            state[x] = 0
            parent[x] = -1
            parent_eid[x] = -1
            next_ptr[x] = 0
        touched.clear()

    for s in range(n_nodes):
        if not allowed_nodes[s] or state[s] != 0:
            continue

        stack = [s]
        state[s] = 1
        touched.append(s)

        while stack:
            u = stack[-1]
            i = next_ptr[u]
            out = out_adj[u]

            while i < len(out):
                eid = out[i]
                if active[eid] and allowed_eids[eid] and allowed_nodes[V[eid]]:
                    break
                i += 1
            next_ptr[u] = i

            if i >= len(out):
                state[u] = 2
                stack.pop()
                continue

            eid = out[i]
            v = V[eid]
            next_ptr[u] = i + 1

            if state[v] == 0:
                parent[v] = u
                parent_eid[v] = eid
                state[v] = 1
                touched.append(v)
                stack.append(v)
            elif state[v] == 1:
                cycle = [eid]
                cur = u
                while cur != v:
                    pe = parent_eid[cur]
                    if pe == -1:
                        break
                    cycle.append(pe)
                    cur = parent[cur]
                    if cur == -1:
                        break
                if cur == v:
                    cycle.reverse()
                    reset()
                    return cycle

    reset()
    return None


def topo_order_active_restricted(n_nodes, out_adj, V, active, allowed_nodes, allowed_eids):
    """Kahn topo sort restricted to the SCC subgraph."""
    nodes = [i for i in range(n_nodes) if allowed_nodes[i]]
    indeg = [0] * n_nodes

    for u in nodes:
        for eid in out_adj[u]:
            if active[eid] and allowed_eids[eid] and allowed_nodes[V[eid]]:
                indeg[V[eid]] += 1

    heap = [u for u in nodes if indeg[u] == 0]
    heapq.heapify(heap)

    order = []
    while heap:
        u = heapq.heappop(heap)
        order.append(u)
        for eid in out_adj[u]:
            if not (active[eid] and allowed_eids[eid]):
                continue
            v = V[eid]
            if not allowed_nodes[v]:
                continue
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(heap, v)

    if len(order) != len(nodes):
        raise RuntimeError("Restricted topo failed: SCC subgraph is cyclic.")

    rank = [-1] * n_nodes
    for r, u in enumerate(order):
        rank[u] = r
    return order, rank


def make_reachability_checker_restricted(n_nodes, out_adj, V, active, allowed_nodes, allowed_eids):
    """Stamp-based reachability checker restricted to the SCC subgraph."""
    visited = [0] * n_nodes
    stamp = 0

    def reachable(src, target, rank, rank_limit):
        nonlocal stamp
        stamp += 1
        st = stamp
        if src == target:
            return True
        if not (allowed_nodes[src] and allowed_nodes[target]):
            return False
        if rank[src] < 0 or rank[target] < 0 or rank[src] > rank_limit:
            return False

        stack = [src]
        visited[src] = st
        while stack:
            x = stack.pop()
            for eid in out_adj[x]:
                if not (active[eid] and allowed_eids[eid]):
                    continue
                y = V[eid]
                if not allowed_nodes[y] or rank[y] > rank_limit:
                    continue
                if y == target:
                    return True
                if visited[y] != st:
                    visited[y] = st
                    stack.append(y)
        return False

    return reachable


# ---------------------------------------------------------------------------
# SCC-local LR repair + minimize add-back
# ---------------------------------------------------------------------------

def local_ratio_repair_inside_scc(U, V, W0, active, out_adj, allowed_nodes, allowed_eids, tol=1e-12):
    """Run local-ratio cycle reduction restricted to one SCC. Returns newly removed edge IDs."""
    W = {eid: W0[eid] for eid in range(len(U)) if allowed_eids[eid]}
    F_add = set()
    n_nodes = len(out_adj)

    while True:
        cyc = find_any_cycle_eids_restricted(
            n_nodes, out_adj, V, active, allowed_nodes, allowed_eids
        )
        if cyc is None:
            break

        eps = min(W.get(eid, W0[eid]) for eid in cyc)

        if eps <= tol:
            e0 = cyc[0]
            if active[e0]:
                active[e0] = 0
                F_add.add(e0)
            continue

        for eid in cyc:
            new_w = W.get(eid, W0[eid]) - eps
            W[eid] = new_w
            if new_w <= tol and active[eid]:
                active[eid] = 0
                F_add.add(eid)

    return F_add


def minimize_addback_inside_scc(U, V, W0, active, out_adj, F, allowed_nodes, allowed_eids):
    """Minimize the FAS inside one SCC via heavy-first add-back."""
    n_nodes = len(out_adj)
    _, rank = topo_order_active_restricted(n_nodes, out_adj, V, active, allowed_nodes, allowed_eids)
    reachable = make_reachability_checker_restricted(n_nodes, out_adj, V, active, allowed_nodes, allowed_eids)

    cand = sorted(
        [eid for eid in F if allowed_eids[eid]],
        key=lambda eid: (-W0[eid], U[eid], V[eid], eid),
    )

    for eid in cand:
        u, v = U[eid], V[eid]
        if not (allowed_nodes[u] and allowed_nodes[v]):
            continue

        if rank[u] < rank[v]:
            active[eid] = 1
            F.discard(eid)
            continue

        if not reachable(v, u, rank=rank, rank_limit=rank[u]):
            active[eid] = 1
            F.discard(eid)
            _, rank = topo_order_active_restricted(
                n_nodes, out_adj, V, active, allowed_nodes, allowed_eids
            )
            reachable = make_reachability_checker_restricted(
                n_nodes, out_adj, V, active, allowed_nodes, allowed_eids
            )


# ---------------------------------------------------------------------------
# Base solution A: WMSF seed (global removeArcs + minimize)
# ---------------------------------------------------------------------------

def wmsf_removeArcs_global(n_nodes, U, V, W0, active, out_adj, in_adj, ordering="L2"):
    """Global arc-removal phase matching paper049 Section 2.1."""
    Win = [0.0] * n_nodes
    Wout = [0.0] * n_nodes
    for eid in range(len(U)):
        if not active[eid]:
            continue
        Wout[U[eid]] += W0[eid]
        Win[V[eid]] += W0[eid]

    eids = [eid for eid in range(len(U)) if active[eid]]

    if ordering.upper() == "L1":
        eids.sort(key=lambda eid: (W0[eid], U[eid], V[eid], eid))
    else:
        def keyL2(eid):
            denom = Win[U[eid]] + Wout[V[eid]]
            if denom <= 0.0:
                denom = 1.0
            return (W0[eid] / denom, W0[eid], U[eid], V[eid], eid)
        eids.sort(key=keyL2)

    F = set()
    pos = {eid: i for i, eid in enumerate(eids)}
    pair_to_eid = {(U[eid], V[eid]): eid for eid in eids}

    for eid in eids:
        if not active[eid]:
            continue
        u, v = U[eid], V[eid]
        rev = pair_to_eid.get((v, u))
        if rev is not None and active[rev] and pos[eid] < pos[rev]:
            active[eid] = 0
            F.add(eid)

    indeg = [0] * n_nodes
    outdeg = [0] * n_nodes
    for u in range(n_nodes):
        for eid in out_adj[u]:
            if active[eid]:
                outdeg[u] += 1
                indeg[V[eid]] += 1

    q = deque()
    for eid in range(len(U)):
        if not active[eid]:
            continue
        u, v = U[eid], V[eid]
        if indeg[u] == 0 or outdeg[v] == 0:
            q.append(eid)

    safe_tmp = []
    while q:
        eid = q.popleft()
        if not active[eid]:
            continue
        u, v = U[eid], V[eid]
        if not (indeg[u] == 0 or outdeg[v] == 0):
            continue
        active[eid] = 0
        safe_tmp.append(eid)
        outdeg[u] -= 1
        indeg[v] -= 1
        for ee in out_adj[u]:
            if active[ee]:
                q.append(ee)
        for ee in in_adj[v]:
            if active[ee]:
                q.append(ee)

    m_act = sum(1 for eid in range(len(U)) if active[eid])
    alpha = max(1, m_act // max(1, n_nodes))
    since = 0

    for eid in eids:
        if not active[eid]:
            continue
        active[eid] = 0
        F.add(eid)
        since += 1
        if since >= alpha:
            since = 0
            ok, _ = _is_acyclic_active(n_nodes, out_adj, V, active)
            if ok:
                break

    ok, _ = _is_acyclic_active(n_nodes, out_adj, V, active)
    if not ok:
        for eid in eids:
            if not active[eid]:
                continue
            active[eid] = 0
            F.add(eid)
            ok, _ = _is_acyclic_active(n_nodes, out_adj, V, active)
            if ok:
                break

    for eid in safe_tmp:
        active[eid] = 1

    return F


def wmsf_minimize_global(n_nodes, U, V, W0, active, out_adj, F):
    """Global heavy-first add-back for WMSF seed."""
    for eid in F:
        active[eid] = 0

    _, rank = topo_order_active(n_nodes, out_adj, V, active)

    visited = [0] * n_nodes
    stamp = 0

    def reachable(src, target, rank_limit):
        nonlocal stamp
        stamp += 1
        st = stamp
        if src == target:
            return True
        if rank[src] > rank_limit:
            return False
        stack = [src]
        visited[src] = st
        while stack:
            x = stack.pop()
            for eid in out_adj[x]:
                if not active[eid]:
                    continue
                y = V[eid]
                if rank[y] > rank_limit:
                    continue
                if y == target:
                    return True
                if visited[y] != st:
                    visited[y] = st
                    stack.append(y)
        return False

    cand = sorted(F, key=lambda eid: (-W0[eid], U[eid], V[eid], eid))
    for eid in cand:
        u, v = U[eid], V[eid]
        if rank[u] < rank[v]:
            active[eid] = 1
            F.discard(eid)
            continue
        if not reachable(v, u, rank_limit=rank[u]):
            active[eid] = 1
            F.discard(eid)
            _, rank = topo_order_active(n_nodes, out_adj, V, active)

    return F


def wmsf_seed_solution(n_nodes, U, V, W0, active, out_adj, in_adj, ordering="L2"):
    F = wmsf_removeArcs_global(n_nodes, U, V, W0, active, out_adj, in_adj, ordering=ordering)
    F = wmsf_minimize_global(n_nodes, U, V, W0, active, out_adj, F)
    return F, active


def wmsf_seed_solution_full(
    n_nodes, edges_indexed, V, active_init, out_adj,
    comps, by_scc, ordering="L2", tol=1e-12,
):
    """
    Full WMSF seed using the same pipeline as standalone wmsf_ranking_from_dimacs_fast:
    per-SCC removeArcs -> Minimize -> Stabilize -> Minimize.
    For whole-single-SCC graphs, tries both L1 and L2 and keeps the better result.

    This guarantees IPSNS never starts from a seed weaker than the standalone WMSF.
    """
    nontrivial = [c for c in comps if len(c) > 1]
    whole_single_scc = len(nontrivial) == 1 and len(nontrivial[0]) == n_nodes

    def run_one(ordering_choice):
        active_glob = bytearray(active_init)
        F_global = set()
        for scc_idx, verts in enumerate(comps):
            e_list = by_scc.get(scc_idx, [])
            if len(verts) <= 1:
                for (u, v, w, eid) in e_list:
                    if u == v and w > tol:
                        F_global.add(eid)
                        active_glob[eid] = 0
                continue
            if not e_list:
                continue
            k, U2, V2, W02, eidG, active2, out2, in2 = _build_local_scc_graph(verts, e_list, tol=tol)
            F2, _ = _wmsf_pipeline_scc(k, U2, V2, W02, active2, out2, in2, ordering=ordering_choice, tol=tol)
            for eid2 in F2:
                F_global.add(eidG[eid2])
                active_glob[eidG[eid2]] = 0
        _, rank = topo_order_active(n_nodes, out_adj, V, active_glob)
        scores = {i: int(rank[i]) for i in range(n_nodes)}
        _, _, bw = compute_forward_backward(edges_indexed, scores)
        return bw, F_global, active_glob

    if whole_single_scc:
        bw1, F1, active1 = run_one("L1")
        bw2, F2, active2 = run_one("L2")
        if bw1 <= bw2:
            return F1, active1
        else:
            return F2, active2
    else:
        _, F_global, active_glob = run_one(ordering)
        return F_global, active_glob


# ---------------------------------------------------------------------------
# Base solution B: LR-TA seed (global cycle reduction + minimize)
# ---------------------------------------------------------------------------

def find_any_cycle_eids_global(n_nodes, out_adj, V, active):
    """Find any directed cycle in the global active graph."""
    state = bytearray(n_nodes)
    parent = [-1] * n_nodes
    parent_eid = [-1] * n_nodes
    next_ptr = [0] * n_nodes
    touched = []

    def reset():
        for x in touched:
            state[x] = 0
            parent[x] = -1
            parent_eid[x] = -1
            next_ptr[x] = 0
        touched.clear()

    for s in range(n_nodes):
        if state[s] != 0:
            continue
        stack = [s]
        state[s] = 1
        touched.append(s)

        while stack:
            u = stack[-1]
            i = next_ptr[u]
            out = out_adj[u]
            while i < len(out) and active[out[i]] == 0:
                i += 1
            next_ptr[u] = i

            if i >= len(out):
                state[u] = 2
                stack.pop()
                continue

            eid = out[i]
            v = V[eid]
            next_ptr[u] = i + 1

            if state[v] == 0:
                parent[v] = u
                parent_eid[v] = eid
                state[v] = 1
                touched.append(v)
                stack.append(v)
            elif state[v] == 1:
                cycle = [eid]
                cur = u
                while cur != v:
                    pe = parent_eid[cur]
                    if pe == -1:
                        break
                    cycle.append(pe)
                    cur = parent[cur]
                    if cur == -1:
                        break
                if cur == v:
                    cycle.reverse()
                    reset()
                    return cycle

    reset()
    return None


def lr_cycle_reduction_global(n_nodes, U, V, W0, W, active, out_adj, tol=1e-12):
    F = set()
    while True:
        cyc = find_any_cycle_eids_global(n_nodes, out_adj, V, active)
        if cyc is None:
            break

        eps = min(W[eid] for eid in cyc)

        if eps <= tol:
            e0 = cyc[0]
            if active[e0]:
                active[e0] = 0
                W[e0] = 0.0
                F.add(e0)
            continue

        for eid in cyc:
            new_w = W[eid] - eps
            W[eid] = new_w
            if new_w <= tol and active[eid]:
                active[eid] = 0
                W[eid] = 0.0
                F.add(eid)

    return F, active, W


def lr_seed_solution(n_nodes, U, V, W0, W, active, out_adj, tol=1e-12):
    F, active, W = lr_cycle_reduction_global(n_nodes, U, V, W0, W, active, out_adj, tol=tol)
    F = wmsf_minimize_global(n_nodes, U, V, W0, active, out_adj, F)
    return F, active


# ---------------------------------------------------------------------------
# SCC scoring and LNS step
# ---------------------------------------------------------------------------

def score_scc_backward_weight(edges_in_scc, rank):
    return sum(w for u, v, w, _ in edges_in_scc if rank[u] > rank[v])


def lns_step_on_scc(
    scc_nodes,
    scc_edges,
    U, V, W0,
    active,
    out_adj,
    F,
    destroy_addback_frac=0.25,
    destroy_remove_frac=0.02,
    tol=1e-12,
):
    """
    Destroy-and-repair move on one SCC.

    Destroy A: reactivate a fraction of removed (heavy) edges.
    Destroy B: forcibly remove a fraction of active (light) edges.
    Repair 1 : LR cycle reduction inside SCC.
    Repair 2 : minimize add-back inside SCC.

    Returns True on success; reverts SCC state and returns False on failure.
    """
    n_nodes = len(out_adj)
    allowed_nodes = bytearray(n_nodes)
    for x in scc_nodes:
        allowed_nodes[x] = 1

    allowed_eids = bytearray(len(U))
    for (_, _, _, eid) in scc_edges:
        allowed_eids[eid] = 1

    internal_eids = [eid for (_, _, _, eid) in scc_edges]
    old_states = [(eid, 1 if active[eid] else 0, 1 if (eid in F) else 0) for eid in internal_eids]

    removed_in_scc = sorted(
        [eid for eid in internal_eids if eid in F],
        key=lambda eid: (-W0[eid], U[eid], V[eid], eid),
    )
    k_add = int(destroy_addback_frac * len(removed_in_scc))
    for eid in removed_in_scc[:k_add]:
        active[eid] = 1
        F.discard(eid)

    active_in_scc = sorted(
        [eid for eid in internal_eids if active[eid]],
        key=lambda eid: (W0[eid], U[eid], V[eid], eid),
    )
    k_rem = int(destroy_remove_frac * len(active_in_scc))
    for eid in active_in_scc[:k_rem]:
        active[eid] = 0
        F.add(eid)

    F_add = local_ratio_repair_inside_scc(
        U=U, V=V, W0=W0, active=active, out_adj=out_adj,
        allowed_nodes=allowed_nodes, allowed_eids=allowed_eids, tol=tol,
    )
    F.update(F_add)

    try:
        minimize_addback_inside_scc(
            U=U, V=V, W0=W0, active=active, out_adj=out_adj, F=F,
            allowed_nodes=allowed_nodes, allowed_eids=allowed_eids,
        )
    except RuntimeError:
        for eid, a0, f0 in old_states:
            active[eid] = 1 if a0 else 0
            if f0:
                F.add(eid)
            else:
                F.discard(eid)
        return False

    return True


# ---------------------------------------------------------------------------
# Full IPSNS driver
# ---------------------------------------------------------------------------

def lns_merge_wmsf_lr_best_incumbent(
    dimacs_path,
    output_ranking_csv_path,
    seed_ordering="L2",
    iters=400,
    topK_scc=15,
    destroy_addback_frac=0.30,
    destroy_remove_frac=0.02,
    tol=1e-12,
    rng_seed=1,
    log_every=10,
    wmsf_seed_mode="full",
    scc_select_mode="weighted",
    return_info=False,
    incumbent_callback=None,
    iteration_callback=None,
):
    """
    Run IPSNS: seed with WMSF and LR-TA, keep the better incumbent, then
    improve via SCC-local LNS destroy+repair moves.

    The output is guaranteed to be no worse than the better of the two seeds.

    Args:
        dimacs_path              : path to the DIMACS input file
        output_ranking_csv_path  : path to write the ranking CSV
        seed_ordering            : "L1" or "L2" for the WMSF seed (legacy mode only)
        iters                    : number of LNS iterations
        topK_scc                 : candidate pool size for SCC selection
        destroy_addback_frac     : fraction of removed SCC edges to reactivate
        destroy_remove_frac      : fraction of active SCC edges to forcibly remove
        tol                      : numerical zero tolerance
        rng_seed                 : random seed for reproducibility
        log_every                : print progress every N iterations (0 = silent)
        wmsf_seed_mode           : "full" (default) uses the same per-SCC pipeline
                                   as standalone wmsf_ranking_from_dimacs_fast
                                   (removeArcs->Minimize->Stabilize->Minimize, L1+L2
                                   for single-SCC graphs); "legacy" uses the simpler
                                   global removeArcs+minimize, L2-only seed.
        scc_select_mode          : "weighted" (default) selects SCCs by BW-weighted
                                   random choice from the top-K highest-BW SCCs;
                                   "random" uses uniform random selection from all
                                   non-zero-BW SCCs (ablation: isolates contribution
                                   of the priority heuristic).
        return_info              : if True, also return a diagnostic dict as the
                                   sixth element with keys lr_seed_bw, wmsf_seed_bw,
                                   best_seed_bw, final_bw, improved, n_iters, status.

    Returns:
        edges_indexed, node_to_index, index_to_node, scores, F_removed_pairs
        (and info dict if return_info=True)
    """
    import pandas as pd

    random.seed(rng_seed)

    edges_indexed, node_to_index, index_to_node = read_graph_dimacs_agg(dimacs_path)
    n = len(node_to_index)

    U, V, W0, W_init, active_init, out_adj, in_adj = build_eid_graph_inout_with_W(
        edges_indexed, n, tol=tol
    )

    comps, comp_id = kosaraju_scc(n, edges_indexed)
    by_scc = edges_by_scc(edges_indexed, comp_id)
    scc_list = [
        (verts, by_scc[scc_idx])
        for scc_idx, verts in enumerate(comps)
        if len(verts) > 1 and by_scc.get(scc_idx)
    ]

    # Base solution A: WMSF seed
    if wmsf_seed_mode == "full":
        F_A, active_A = wmsf_seed_solution_full(
            n, edges_indexed, V, active_init, out_adj,
            comps, by_scc, ordering=seed_ordering, tol=tol,
        )
    else:
        active_A = bytearray(active_init)
        F_A, active_A = wmsf_seed_solution(n, U, V, W0, active_A, out_adj, in_adj, ordering=seed_ordering)
    _, rank_A = topo_order_active(n, out_adj, V, active_A)
    scores_A = {i: int(rank_A[i]) for i in range(n)}
    total_w, fw_A, bw_A = compute_forward_backward(edges_indexed, scores_A)
    if incumbent_callback is not None:
        incumbent_callback(index_to_node, rank_A, bw_A, "wmsf_seed", 0)

    # Base solution B: LR-TA seed
    active_B = bytearray(active_init)
    W_B = list(W_init)
    F_B, active_B = lr_seed_solution(n, U, V, W0, W_B, active_B, out_adj, tol=tol)
    _, rank_B = topo_order_active(n, out_adj, V, active_B)
    scores_B = {i: int(rank_B[i]) for i in range(n)}
    _, fw_B, bw_B = compute_forward_backward(edges_indexed, scores_B)
    if incumbent_callback is not None and bw_B < bw_A - 1e-12:
        incumbent_callback(index_to_node, rank_B, bw_B, "lr_seed_improvement", 0)

    # Incumbent: best of the two seeds
    if bw_A <= bw_B:
        best_bw = bw_A
        best_snapshot = (bytearray(active_A), set(F_A))
        active = bytearray(active_A)
        F = set(F_A)
    else:
        best_bw = bw_B
        best_snapshot = (bytearray(active_B), set(F_B))
        active = bytearray(active_B)
        F = set(F_B)

    _, rank = topo_order_active(n, out_adj, V, active)
    if incumbent_callback is not None:
        incumbent_callback(index_to_node, rank, best_bw, "complete_initializer", 0)

    best_bw_initial = best_bw  # for return_info: best seed BW before LNS
    n_iters_done = 0
    # Diagnostic counters (populated only when return_info=True to avoid branch overhead)
    _n_accepted = 0
    _n_rejected = 0
    _n_failed_repair = 0
    _n_topo_failed = 0
    _n_noop = 0
    _best_iter = 0      # iteration at which final best was last improved (0 = seed)
    _time_to_best = 0.0 # elapsed seconds when final best was last improved

    t_start = time.perf_counter()
    if log_every:
        print(f"[base WMSF] BW={bw_A:.6f} FW={fw_A:.6f} ratio={fw_A/total_w:.6f} |F|={len(F_A)}")
        print(f"[base   LR] BW={bw_B:.6f} FW={fw_B:.6f} ratio={fw_B/total_w:.6f} |F|={len(F_B)}")
        start_label = "WMSF" if bw_A <= bw_B else "LR"
        print(f"[incumbent] best_BW={best_bw:.6f}  start_from={start_label}")
        print(f"[LNS] SCCs={len(scc_list)}  iters={iters}")

    # LNS loop (pure improving; best_snapshot always protected)
    for it in range(1, iters + 1):
        if iteration_callback is not None:
            iteration_callback(it - 1)
        n_iters_done = it
        scored = [
            (score_scc_backward_weight(e_list, rank), verts, e_list)
            for verts, e_list in scc_list
        ]
        scored = [(bw_scc, v, e) for bw_scc, v, e in scored if bw_scc > 0]
        if not scored:
            if return_info:
                _n_noop += 1
            break

        scored.sort(key=lambda x: -x[0])
        if scc_select_mode == "random":
            # Ablation: uniform random selection from all non-zero-BW SCCs.
            picked_bw_scc, verts, e_list = random.choices(scored, k=1)[0]
        else:
            pool = scored[: min(topK_scc, len(scored))]
            picked_bw_scc, verts, e_list = random.choices(pool, weights=[x[0] for x in pool], k=1)[0]

        active_before = bytearray(active)
        F_before = set(F)
        rank_before = list(rank)

        ok = lns_step_on_scc(
            scc_nodes=verts,
            scc_edges=e_list,
            U=U, V=V, W0=W0,
            active=active,
            out_adj=out_adj,
            F=F,
            destroy_addback_frac=destroy_addback_frac,
            destroy_remove_frac=destroy_remove_frac,
            tol=tol,
        )
        if not ok:
            active = active_before
            F = F_before
            rank = rank_before
            if return_info:
                _n_failed_repair += 1
            continue

        try:
            _, rank = topo_order_active(n, out_adj, V, active)
        except RuntimeError:
            active = active_before
            F = F_before
            rank = rank_before
            if return_info:
                _n_topo_failed += 1
            continue

        scores = {i: int(rank[i]) for i in range(n)}
        _, _, _bw = compute_forward_backward(edges_indexed, scores)

        if _bw < best_bw - 1e-12:
            best_bw = _bw
            best_snapshot = (bytearray(active), set(F))
            if incumbent_callback is not None:
                incumbent_callback(index_to_node, rank, best_bw, "refinement_improvement", it)
            if return_info:
                _n_accepted += 1
                _best_iter = it
                _time_to_best = time.perf_counter() - t_start
            if log_every and (it == 1 or it % log_every == 0):
                elapsed = time.perf_counter() - t_start
                print(
                    f"[it {it:4d}] NEW BEST  BW={_bw:.6f}  |F|={len(F)}"
                    f"  scc_bw={picked_bw_scc:.6f}  t={elapsed:.1f}s"
                )
        else:
            active = active_before
            F = F_before
            rank = rank_before
            if return_info:
                _n_rejected += 1

        if log_every and it % log_every == 0 and _bw >= best_bw - 1e-12:
            elapsed = time.perf_counter() - t_start
            print(f"[it {it:4d}] best_BW={best_bw:.6f}  elapsed={elapsed:.1f}s")

    # Output best_snapshot (guaranteed <= best(A, B))
    active_best, F_best = best_snapshot
    _, rank = topo_order_active(n, out_adj, V, active_best)

    rows = [{"Node ID": str(index_to_node[i]).strip(), "Order": int(rank[i])} for i in range(n)]
    rows.sort(key=lambda r: r["Order"])
    pd.DataFrame(rows).to_csv(output_ranking_csv_path, index=False)

    scores_best = {i: int(rank[i]) for i in range(n)}
    total_w, fw, bw = compute_forward_backward(edges_indexed, scores_best)
    elapsed = time.perf_counter() - t_start

    print(f"\n  Wrote ranking: {output_ranking_csv_path}")
    print(f"Graph: n={n} nodes, m={len(edges_indexed)} edges (after aggregation)")
    print(f"Total Weight: {total_w:.6f}")
    print(f"Forward Weight: {fw:.6f}")
    print(f"Backward Weight: {bw:.6f}")
    print(f"Forward Ratio: {fw/total_w:.6f}" if total_w > tol else "Forward Ratio: 0.000000 (empty graph)")
    print(f"Removed edges (count): {len(F_best)}")
    print(f"Total time: {elapsed:.3f} sec ({elapsed/60.0:.3f} min)")

    F_removed_pairs = {(U[eid], V[eid]) for eid in F_best}
    if return_info:
        info = {
            "lr_seed_bw": float(bw_B),
            "wmsf_seed_bw": float(bw_A),
            "best_seed_bw": float(best_bw_initial),
            "final_bw": float(bw),
            "improved": bw < best_bw_initial - 1e-12,
            "n_iters": n_iters_done,
            "n_accepted": _n_accepted,
            "n_rejected": _n_rejected,
            "n_failed_repair": _n_failed_repair,
            "n_topo_failed": _n_topo_failed,
            "n_noop": _n_noop,
            "best_iter": _best_iter,
            "time_to_best": float(_time_to_best),
            "status": "ok",
        }
        return edges_indexed, node_to_index, index_to_node, scores_best, F_removed_pairs, info
    return edges_indexed, node_to_index, index_to_node, scores_best, F_removed_pairs
