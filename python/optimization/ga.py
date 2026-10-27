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

Memetic variant (local_search=True, added after the baseline GA missed the optimum of the "GA-deceptive"
minimum-thickness cases of Le Riche & Haftka 1995): every time the best design improves, a steepest-ascent
local search explores its neighbourhood - every swap of two plies of different orientation, every change of one
ply to another orientation, and (fewest plies) every removal of one ply - all repaired, evaluated in one batch,
counted in the same budget; at a feasible local optimum it then tries to THIN the design: every one-ply
removal is repaired, the few thinner designs with the best margins are re-optimised at their ply count
(swaps / single-ply changes), and the first one reaching the safety factor is accepted. Local improvement of GA
designs follows Kogiso et al. (1994), cited in [P].
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from .evaluate import Evaluator, Problem, better, lexi_rank
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
    local_search: bool = False           # memetic variant: hill-climb from every new best design
    ls_max_neighbors: int = 0            # 0 = whole neighbourhood, else a random subset of this size per step
    ls_thinning: bool = True             # fewest plies: at a local optimum, try removing a ply + re-optimising
    ls_thinning_starts: int = 3          # thinner designs (best margins) from which the fixed-thickness climb starts


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

    def _neighbours(self, g: np.ndarray, deletions: bool = True) -> np.ndarray:
        s = [int(x) for x in g if x >= 0]
        L = len(s)
        out = []
        for i in range(L):
            for j in range(i + 1, L):
                if s[i] != s[j]:
                    t = s.copy()
                    t[i], t[j] = t[j], t[i]
                    out.append(t)
        for i in range(L):
            for k in range(self.nsym):
                if k != s[i]:
                    t = s.copy()
                    t[i] = k
                    out.append(t)
        if deletions and self.cfg.objective == "min_plies" and L > self.repairer.Lmin:
            out += [s[:i] + s[i + 1:] for i in range(L)]
        if self.cfg.ls_max_neighbors and len(out) > self.cfg.ls_max_neighbors:
            idx = self.rng.choice(len(out), self.cfg.ls_max_neighbors, replace=False)
            out = [out[i] for i in idx]
        arr = np.full((len(out), self.n_genes), EMPTY, dtype=np.int8)
        for r, t in enumerate(out):
            arr[r, self.n_genes - len(t):] = t
            arr[r] = self.repairer.repair(arr[r], self.rng)
        return np.unique(arr, axis=0)

    def _local_search(self, g: np.ndarray, key: tuple) -> tuple:
        """Steepest ascent from design g with (n_plies, margin) = key; stops at a local optimum or the budget."""
        sf = self.p.safety_factor
        while self.ev.n_unique < self.cfg.budget:
            nb = self._neighbours(g)
            res = self.ev.evaluate(nb)
            k = _rank(res, sf, self.cfg.objective)[0]
            cand = (int(res["n_plies"][k]), float(res["margin"][k]))
            improved = cand[1] > key[1] if self.cfg.objective == "max_margin" else better(cand, key, sf)
            if not improved:
                break
            g, key = nb[k].copy(), cand
        if (self.cfg.objective == "min_plies" and self.cfg.ls_thinning and key[1] >= sf
                and self.ev.n_unique < self.cfg.budget):
            thin = self._thin(g)
            if thin is not None:
                return self._local_search(*thin)
        return g, key

    def _climb_fixed(self, g: np.ndarray, key: tuple) -> tuple:
        """Steepest ascent of the margin at a fixed ply count (swaps and single-ply changes only)."""
        n0 = key[0]
        while self.ev.n_unique < self.cfg.budget:
            nb = self._neighbours(g, deletions=False)
            res = self.ev.evaluate(nb)
            same = np.where(res["n_plies"] == n0)[0]
            if len(same) == 0:
                break
            k = same[int(np.argmax(res["margin"][same]))]
            if res["margin"][k] <= key[1]:
                break
            g, key = nb[k].copy(), (n0, float(res["margin"][k]))
        return g, key

    def _thin(self, g: np.ndarray):
        """From a feasible local optimum: remove one ply (every position), re-optimise the margin of the best
        few thinner designs at their ply count; return the first one that becomes feasible, else None."""
        s = [int(x) for x in g if x >= 0]
        if len(s) <= self.repairer.Lmin:
            return None
        arr = np.full((len(s), self.n_genes), EMPTY, dtype=np.int8)
        for i in range(len(s)):
            t = s[:i] + s[i + 1:]
            arr[i, self.n_genes - len(t):] = t
            arr[i] = self.repairer.repair(arr[i], self.rng)
        arr = np.unique(arr, axis=0)
        res = self.ev.evaluate(arr)
        n_now = 2 * len(s) * self.p.enc.plies_per_symbol if self.p.rules.symmetric else len(s) * self.p.enc.plies_per_symbol
        thinner = np.where(res["n_plies"] < n_now)[0]
        for k in thinner[np.argsort(-res["margin"][thinner])][: self.cfg.ls_thinning_starts]:
            g2, key2 = self._climb_fixed(arr[k].copy(), (int(res["n_plies"][k]), float(res["margin"][k])))
            if key2[1] >= self.p.safety_factor:
                return g2, key2
        return None

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
        best_seen = None
        while True:
            order = _rank(res, sf, cfg.objective)
            b = order[0]
            best = (int(res["n_plies"][b]), float(res["margin"][b]))
            if cfg.local_search and (best_seen is None or (best[1] > best_seen[1] if cfg.objective == "max_margin"
                                                          else better(best, best_seen, sf))):
                g2, key2 = self._local_search(pop[b].copy(), best)
                if key2 != best:  # put the improved design in place of the worst member
                    w = order[-1]
                    pop[w] = g2
                    r2 = self.ev.evaluate(g2[None])
                    for k in res:
                        res[k][w] = r2[k][0]
                    order = _rank(res, sf, cfg.objective)
                    b = order[0]
                    best = (int(res["n_plies"][b]), float(res["margin"][b]))
                best_seen = best
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
