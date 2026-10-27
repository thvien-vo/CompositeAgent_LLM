"""
ga.py - single-objective genetic algorithm for stacking sequences.

Objective "min_plies" (default): fewest plies with margin >= safety factor; equal ply count -> larger margin.
Selection uses the lexicographic order of evaluate.lexi_rank (feasible first; feasible by ply count then margin;
infeasible by constraint violation) through binary tournaments. Objective "max_margin": largest margin
(fixed-thickness problems such as Le Riche & Haftka 1993).

Design strings are canonical (right-aligned at the mid-plane, EMPTY on the outer side), so genes at the same
index are at the same distance from the mid-plane in both parents. Operators:
  two-point crossover (prob p_crossover), gene mutation (each ply with prob p_mutation -> another symbol),
  ply addition / deletion (thickness change), swap of two plies of different orientation (the "stack swap" /
  permutation operator of Le Riche & Haftka, changes D without changing A), repair (rules always satisfied).
Elitism keeps the n_elite best designs. Children that duplicate a population member get extra swaps (diversity).
The budget is the number of DISTINCT designs analysed (repeated designs come from the cache for free).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from .evaluate import Evaluator, Problem, lexi_rank
from .rules import EMPTY, Repairer


@dataclass
class GAConfig:
    pop_size: int = 30
    n_elite: int = 2
    tournament: int = 2
    p_crossover: float = 1.0
    p_mutation: Optional[float] = None   # per ply; default 1 / n_genes
    p_add: float = 0.10
    p_delete: float = 0.10
    p_swap: float = 0.7                  # probability of one swap (a second one with p_swap^2 ...)
    budget: int = 10000                  # distinct designs analysed
    max_generations: int = 100000
    stall_generations: int = 100         # stop early if no NEW design was analysed for this many generations
    objective: str = "min_plies"


def _rank(res: Dict[str, np.ndarray], sf: float, objective: str) -> np.ndarray:
    if objective == "max_margin":
        return np.argsort(-res["margin"], kind="stable")
    return lexi_rank(res["n_plies"], res["margin"], sf)


class GeneticAlgorithm:
    def __init__(self, problem: Problem, config: Optional[GAConfig] = None, seed: int = 0):
        self.p = problem
        self.cfg = config or GAConfig()
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.repairer = Repairer(problem.enc, problem.rules)
        self.ev = Evaluator(problem, n_genes=self.repairer.n_genes)
        self.n_genes = self.repairer.n_genes
        self.nsym = problem.enc.n_symbols
        self.pm = self.cfg.p_mutation if self.cfg.p_mutation is not None else 1.0 / self.n_genes

    # ------------------------------------------------------------------ operators
    def _crossover(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        i, j = sorted(self.rng.choice(self.n_genes + 1, 2, replace=False))
        c = a.copy()
        c[i:j] = b[i:j]
        return c

    def _mutate(self, g: np.ndarray) -> np.ndarray:
        rng = self.rng
        s = [int(x) for x in g if x >= 0]
        for k in range(len(s)):
            if rng.random() < self.pm:
                s[k] = int((s[k] + rng.integers(1, self.nsym)) % self.nsym)
        if rng.random() < self.cfg.p_add and len(s) < self.repairer.Lmax:
            s.insert(int(rng.integers(len(s) + 1)), int(rng.integers(self.nsym)))
        if rng.random() < self.cfg.p_delete and len(s) > self.repairer.Lmin:
            s.pop(int(rng.integers(len(s))))
        p = self.cfg.p_swap
        while rng.random() < p and len(s) > 1:
            self._swap(s)
            p *= self.cfg.p_swap
        out = np.full(self.n_genes, EMPTY, dtype=np.int8)
        out[self.n_genes - len(s):] = s
        return out

    def _swap(self, s: List[int]) -> None:
        if len(set(s)) < 2:
            return
        for _ in range(10):
            i, j = self.rng.choice(len(s), 2, replace=False)
            if s[i] != s[j]:
                s[i], s[j] = s[j], s[i]
                return

    def _tournament(self, rank_pos: np.ndarray) -> int:
        cand = self.rng.choice(len(rank_pos), self.cfg.tournament, replace=False)
        return int(cand[np.argmin(rank_pos[cand])])

    # ------------------------------------------------------------------ main loop
    def run(self, target: Optional[tuple] = None, verbose: bool = False) -> Dict:
        """target = (n*, margin*) of a known optimum: records the first evaluation count at which it is hit."""
        t0 = time.perf_counter()
        cfg, sf = self.cfg, self.p.safety_factor
        pop = np.array([self.repairer.random_valid(self.rng) for _ in range(cfg.pop_size)], dtype=np.int8)
        res = self.ev.evaluate(pop)
        history, hit_at, gen, stall, last_unique = [], None, 0, 0, self.ev.n_unique
        while True:
            order = _rank(res, sf, cfg.objective)
            b = order[0]
            best = (int(res["n_plies"][b]), float(res["margin"][b]))
            history.append({"gen": gen, "evals": self.ev.n_unique, "n_plies": best[0], "margin": best[1],
                            "feasible": best[1] >= sf})
            if target is not None and hit_at is None and _is_hit(best, target, cfg.objective):
                hit_at = self.ev.n_unique
            if verbose and gen % 20 == 0:
                print(f"  GA gen {gen:4d} evals {self.ev.n_unique:6d} best n={best[0]} margin={best[1]:.5g}")
            stall = stall + 1 if self.ev.n_unique == last_unique else 0
            last_unique = self.ev.n_unique
            if self.ev.n_unique >= cfg.budget or gen >= cfg.max_generations or stall >= cfg.stall_generations:
                break
            gen += 1
            rank_pos = np.empty(len(order), int)
            rank_pos[order] = np.arange(len(order))
            children = [pop[i].copy() for i in order[:cfg.n_elite]]
            seen = {c.tobytes() for c in children}
            while len(children) < cfg.pop_size:
                i = self._tournament(rank_pos)
                j = self._tournament(rank_pos)
                if np.array_equal(pop[i], pop[j]):
                    j = self._tournament(rank_pos)
                child = self._crossover(pop[i], pop[j]) if self.rng.random() < cfg.p_crossover else pop[i].copy()
                child = self.repairer.repair(self._mutate(child), self.rng)
                for _ in range(3):  # avoid clones inside the new population
                    if child.tobytes() not in seen:
                        break
                    s = [int(x) for x in child if x >= 0]
                    self._swap(s)
                    tmp = np.full(self.n_genes, EMPTY, dtype=np.int8)
                    tmp[self.n_genes - len(s):] = s
                    child = self.repairer.repair(self._mutate(tmp), self.rng)
                seen.add(child.tobytes())
                children.append(child)
            pop = np.array(children, dtype=np.int8)
            res = self.ev.evaluate(pop)
        order = _rank(res, sf, cfg.objective)
        b = order[0]
        return {"best_genes": pop[b].copy(), "n_plies": int(res["n_plies"][b]), "margin": float(res["margin"][b]),
                "feasible": bool(res["margin"][b] >= sf), "history": history, "hit_evals": hit_at,
                "n_evaluations": self.ev.n_unique, "n_calls": self.ev.n_calls, "generations": gen,
                "stopped_by": "budget" if self.ev.n_unique >= cfg.budget else ("stall" if stall >= cfg.stall_generations
                                                                                else "generations"),
                "time_s": time.perf_counter() - t0, "repair_stats": dict(self.repairer.stats)}


def _is_hit(best: tuple, target: tuple, objective: str, rtol: float = 1e-9) -> bool:
    n, m = best
    nt, mt = target
    if objective == "max_margin":
        return m >= mt * (1 - rtol)
    return n == nt and m >= mt * (1 - rtol)
