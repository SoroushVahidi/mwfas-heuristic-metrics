"""Independent deterministic weighted insertion local search for EXP05."""
from __future__ import annotations

import time
from dataclasses import dataclass

from .graph import Graph, backward_weight


@dataclass(frozen=True)
class InsertionResult:
    order: list[str]
    initial_objective: float
    final_objective: float
    accepted_moves: int
    refinement_seconds: float
    termination_reason: str


def insertion_delta(order: list[str], weights: dict[tuple[str, str], float], i: int, j: int) -> float:
    """Exact change in backward weight on moving position i to position j."""
    if i == j:
        return 0.0
    vertex = order[i]
    if i < j:
        return sum(weights.get((vertex, other), 0.0) - weights.get((other, vertex), 0.0)
                   for other in order[i + 1:j + 1])
    return sum(weights.get((other, vertex), 0.0) - weights.get((vertex, other), 0.0)
               for other in order[j:i])


def optimize(graph: Graph, initial_order: list[str], *, max_moves: int,
             deadline: float | None = None) -> InsertionResult:
    if max_moves < 0:
        raise ValueError("negative move budget")
    started = time.perf_counter()
    order = list(initial_order)
    initial = backward_weight(graph, order)
    objective = initial
    weights = {(u, v): w for u, v, w in graph.arcs}
    accepted = 0
    reason = "local_optimum"
    while accepted < max_moves:
        if deadline is not None and time.monotonic() >= deadline:
            reason = "deadline"
            break
        best_delta, best_i, best_j = 0.0, -1, -1
        for i in range(len(order)):
            delta = 0.0
            for j in range(i - 1, -1, -1):
                other = order[j]
                delta += weights.get((other, order[i]), 0.0) - weights.get((order[i], other), 0.0)
                if delta < best_delta - 1e-9 or (abs(delta - best_delta) <= 1e-9 and delta < -1e-9 and (i, j) < (best_i, best_j)):
                    best_delta, best_i, best_j = delta, i, j
            delta = 0.0
            for j in range(i + 1, len(order)):
                other = order[j]
                delta += weights.get((order[i], other), 0.0) - weights.get((other, order[i]), 0.0)
                if delta < best_delta - 1e-9 or (abs(delta - best_delta) <= 1e-9 and delta < -1e-9 and (i, j) < (best_i, best_j)):
                    best_delta, best_i, best_j = delta, i, j
        if best_i < 0:
            break
        order.insert(best_j, order.pop(best_i))
        objective += best_delta
        accepted += 1
        independently_scored = backward_weight(graph, order)
        if abs(independently_scored - objective) > 1e-7 * max(1.0, independently_scored):
            raise ValueError("insertion delta disagrees with independent objective")
        objective = independently_scored
    else:
        reason = "move_budget"
    return InsertionResult(order, initial, objective, accepted,
                           time.perf_counter() - started, reason)
