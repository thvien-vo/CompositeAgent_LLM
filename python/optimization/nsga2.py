"""
nsga2.py - NSGA-II (pymoo) for the two objectives  f1 = number of plies (min),  f2 = - safety margin (min).

The same design strings, operators and repair as the single-objective GA are plugged into pymoo's NSGA-II
(non-dominated sorting + crowding distance, binary tournament): custom Sampling (random valid designs),
two-point Crossover, Mutation (gene change / add / delete / swap) and Repair, so every design produced
satisfies the active design rules. Duplicates are eliminated by pymoo on the canonical strings.
The run is driven with pymoo's ask / tell interface so that it stops exactly on the evaluation budget
(distinct designs analysed, same definition as the GA).

Crowding distance is computed on distinct objective vectors (see run_nsga2): with pymoo's default the optimum was
sometimes found and later lost from the population (C2: final answer right in 11/20 runs only).

The answer to the "fewest plies" question is read from the final population: the feasible design
(margin >= safety factor) with the fewest plies, ties broken by the larger margin. The whole non-dominated
set is returned as the Pareto front (best margin for each ply count found).
"""
from __future__ import annotations

import time
from typing import Dict, Optional

import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.crossover import Crossover
from pymoo.core.mutation import Mutation
from pymoo.core.problem import Problem as PymooProblem
from pymoo.core.repair import Repair
from pymoo.core.sampling import Sampling
from pymoo.operators.survival.rank_and_crowding import RankAndCrowding
from pymoo.operators.survival.rank_and_crowding.metrics import FunctionalDiversity, calc_crowding_distance
from pymoo.termination.max_gen import MaximumGenerationTermination

from .evaluate import Evaluator, Problem, lexi_rank
from .ga import GAConfig, GeneticAlgorithm, _is_hit
from .rules import Repairer


class _LamProblem(PymooProblem):
    def __init__(self, ev: Evaluator, n_genes: int, n_symbols: int):
        super().__init__(n_var=n_genes, n_obj=2, xl=-1, xu=n_symbols - 1, vtype=int)
        self.ev = ev

    def _evaluate(self, X, out, *args, **kwargs):
        r = self.ev.evaluate(np.asarray(X, dtype=np.int8))
        out["F"] = np.column_stack([r["n_plies"].astype(float), -r["margin"]])


class _Sampling(Sampling):
    def __init__(self, repairer: Repairer):
        super().__init__()
        self.repairer = repairer

    def _do(self, problem, n_samples, *args, random_state=None, **kwargs):
        return np.array([self.repairer.random_valid(random_state) for _ in range(n_samples)])


class _Crossover(Crossover):
    """Two-point crossover on mid-plane-aligned strings; two children per pair."""

    def __init__(self, prob: float = 1.0):
        super().__init__(2, 2, prob=prob)

    def _do(self, problem, X, *args, random_state=None, **kwargs):
        _, n_mat, n_var = X.shape
        Y = X.copy()
        for k in range(n_mat):
            i, j = sorted(random_state.choice(n_var + 1, 2, replace=False))
            Y[0, k, i:j], Y[1, k, i:j] = X[1, k, i:j], X[0, k, i:j]
        return Y


class _Mutation(Mutation):
    def __init__(self, ga: GeneticAlgorithm):
        super().__init__()
        self.ga = ga

    def _do(self, problem, X, *args, random_state=None, **kwargs):
        self.ga.rng = random_state
        return np.array([self.ga._mutate(np.asarray(x, dtype=np.int8)) for x in X])


class _Repair(Repair):
    def __init__(self, repairer: Repairer, rng: np.random.Generator):
        super().__init__()
        self.repairer, self.rng = repairer, rng

    def _do(self, problem, X, **kwargs):
        return np.array([self.repairer.repair(np.asarray(x, dtype=np.int8), self.rng) for x in X])


def run_nsga2(problem: Problem, seed: int = 0, pop_size: int = 40, budget: int = 10000,
              ga_config: Optional[GAConfig] = None, target: Optional[tuple] = None,
              max_generations: int = 100000, stall_generations: int = 100, verbose: bool = False) -> Dict:
    """Run NSGA-II; returns the fewest-plies answer, the Pareto front, history and counters."""
    t0 = time.perf_counter()
    cfg = ga_config or GAConfig()
    helper = GeneticAlgorithm(problem, cfg, seed)       # reuses operators, repairer, evaluator
    helper.ev.lazy = False                              # exact margins for every design (Pareto front)
    repairer, ev = helper.repairer, helper.ev
    sf = problem.safety_factor
    pproblem = _LamProblem(ev, helper.n_genes, problem.enc.n_symbols)
    # NSGA-II crowding distance, computed on DISTINCT objective vectors (copies get 0): many different stacking
    # sequences share exactly the same (plies, margin); pymoo's default "cd" treats them as separate points and can
    # drop every copy of a Pareto point when the first front is truncated (observed: the optimum found, then lost).
    survival = RankAndCrowding(crowding_func=FunctionalDiversity(calc_crowding_distance, filter_out_duplicates=True))
    algo = NSGA2(pop_size=pop_size, sampling=_Sampling(repairer), crossover=_Crossover(cfg.p_crossover),
                 mutation=_Mutation(helper), repair=_Repair(repairer, np.random.default_rng(seed + 10_000)),
                 survival=survival, eliminate_duplicates=True)
    algo.setup(pproblem, termination=MaximumGenerationTermination(max_generations), seed=seed, verbose=False)
    history, hit_at, gen, stall, last = [], None, 0, 0, -1
    while algo.has_next():
        infills = algo.ask()
        if infills is None or len(infills) == 0:
            break
        algo.evaluator.eval(pproblem, infills)
        algo.tell(infills=infills)
        X = np.asarray(algo.pop.get("X"), dtype=np.int8)
        F = algo.pop.get("F")
        n, m = F[:, 0].astype(int), -F[:, 1]
        b = lexi_rank(n, m, sf)[0]
        best = (int(n[b]), float(m[b]))
        history.append({"gen": gen, "evals": ev.n_unique, "n_plies": best[0], "margin": best[1],
                        "feasible": best[1] >= sf})
        if target is not None and hit_at is None and _is_hit(best, target, "min_plies"):
            hit_at = ev.n_unique
        if verbose and gen % 20 == 0:
            print(f"  NSGA-II gen {gen:4d} evals {ev.n_unique:6d} best n={best[0]} margin={best[1]:.5g}")
        gen += 1
        stall = stall + 1 if ev.n_unique == last else 0
        last = ev.n_unique
        if ev.n_unique >= budget or stall >= stall_generations:
            break
    X = np.asarray(algo.pop.get("X"), dtype=np.int8)
    F = algo.pop.get("F")
    n, m = F[:, 0].astype(int), -F[:, 1]
    b = lexi_rank(n, m, sf)[0]
    front = {}
    for i in range(len(n)):  # best margin per ply count = non-dominated set of this bi-objective problem
        if n[i] not in front or m[i] > front[n[i]][0]:
            front[n[i]] = (float(m[i]), X[i].copy())
    pareto, best_m = [], -np.inf
    for k in sorted(front):
        if front[k][0] > best_m:  # keep only non-dominated points (more plies must give more margin)
            pareto.append({"n": int(k), "margin": front[k][0], "genes": front[k][1]})
            best_m = front[k][0]
    return {"best_genes": X[b].copy(), "n_plies": int(n[b]), "margin": float(m[b]), "feasible": bool(m[b] >= sf),
            "pareto": pareto, "history": history, "hit_evals": hit_at, "n_evaluations": ev.n_unique,
            "n_calls": ev.n_calls, "generations": gen, "time_s": time.perf_counter() - t0,
            "stopped_by": "budget" if ev.n_unique >= budget else "stall",
            "repair_stats": dict(repairer.stats)}
