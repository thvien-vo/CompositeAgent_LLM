"""
exhaustive.py - exact (global) answers for small design spaces, and certified bounds for large ones.

1) exhaustive(): enumerates EVERY valid design string of each allowed length, in ascending ply count, and keeps
   the best design per ply count. Exactness argument for the default rules (symmetric + balanced, ply encoding):
   the margin depends on the ply counts (strength: A matrix) and on D11, D12, D22, D66 (closed-form or Ritz
   buckling, D16 = D26 ignored), which are identical for +45 and -45 plies. So it is enough to enumerate the
   sequences of FAMILIES (0, +-45, 90): 3^L strings instead of 4^L. Each family string with an even number of
   +-45 plies is turned into a ply string by alternating +45 / -45; this always satisfies balance and never
   creates a run of equal angles among the +-45 plies, so the family string is valid iff its 0 / 90 runs and
   family counts are. For other rule sets the full alphabet is enumerated. Time-limited (default 600 s): a
   length whose estimated cost exceeds the remaining time is not started and the result is flagged incomplete.

2) strength_only_exact(): when there is no buckling check (no compression, or buckling not a criterion) and the
   laminate is symmetric, the margin depends only on the ply counts. Enumerating count tuples, with an exact
   dynamic-programming test that the counts can be arranged within the contiguity limit, gives the exact optimum
   for ANY ply count up to n_max (64 plies) in well under a second.

3) count_upper_bounds(): for every count tuple, an UPPER bound of the margin over all arrangements: strength is
   exact (counts), and the buckling factor is bounded with an optimistic D: each of D11, D22, D12 + 2 D66 is
   maximised separately by putting the plies with the largest value of that stiffness on the outermost positions
   (rearrangement inequality). Every buckling expression used here increases with D11, D22, D12 + 2 D66, so
   lambda(D) <= lambda(D_optimistic). If the bound is below the safety factor for every count tuple of a length,
   that length is PROVEN infeasible -> certified lower bound on the optimal ply count.
"""
from __future__ import annotations

import itertools
import time
from dataclasses import replace
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import numpy as np

from .evaluate import Evaluator, Problem
from .rules import FAMILY_OF_PLY, PLY, contiguity_ok_batch, full_laminate, satisfies

CHUNK = 1 << 19


def _digits(start: int, stop: int, base: int, L: int) -> np.ndarray:
    idx = np.arange(start, stop, dtype=np.int64)
    out = np.empty((len(idx), L), dtype=np.int8)
    for pos in range(L - 1, -1, -1):
        out[:, pos] = idx % base
        idx //= base
    return out


def _family_reduction_ok(problem: Problem) -> bool:
    return problem.encoding == "ply" and problem.rules.symmetric and problem.rules.balanced


def _family_to_plies(fam: np.ndarray) -> np.ndarray:
    """(P, L) families 0 / 1 (+-45) / 2 -> ply codes with alternating +45 / -45 (first +45)."""
    is45 = fam == 1
    k = np.cumsum(is45, axis=1)
    plies = np.where(fam == 0, 0, np.where(fam == 2, 3, np.where(k % 2 == 1, 1, 2)))
    return plies.astype(np.int8)


def _valid_mask(problem: Problem, plies: np.ndarray) -> np.ndarray:
    """Rule filter for (P, W) ply strings of one length (half when symmetric)."""
    r = problem.rules
    full = np.concatenate([plies, plies[:, ::-1]], axis=1) if r.symmetric else plies
    n = full.shape[1]
    ok = np.ones(len(plies), bool)
    if r.balanced:
        ok &= (full == 1).sum(axis=1) == (full == 2).sum(axis=1)
    if r.min_fraction:
        req = r.required_family_plies(n)
        fam = FAMILY_OF_PLY[full]
        for f in range(3):
            ok &= (fam == f).sum(axis=1) >= req
    if r.max_contiguous:
        ok &= contiguity_ok_batch(full, r.max_contiguous)
    return ok


def exhaustive(problem: Problem, time_limit: float = 600.0, front_to_n: Optional[int] = None,
               objective: str = "min_plies", n_start: Optional[int] = None, verbose: bool = False) -> Dict:
    """Exact search over all valid designs, ascending ply count.

    objective "min_plies": stops after the first length with a feasible design (n*), unless front_to_n asks
    for more lengths (best margin per ply count, for Pareto-front comparisons).
    objective "max_margin": all allowed lengths are enumerated (use rules.n_min = n_max for a fixed thickness).
    n_start: skip ply counts below it (use only with a PROVEN lower bound, e.g. count_upper_bounds()).
    """
    t0 = time.perf_counter()
    enc = problem.enc
    ev = Evaluator(problem)
    reduced = _family_reduction_ok(problem)
    base = 3 if reduced else enc.n_symbols
    sf = problem.safety_factor
    per_n: List[Dict] = []
    best_overall = None
    complete = True
    rate = None  # strings per second, measured
    n_eval = 0
    chunk = CHUNK if problem.buckling_model == "closed_form" else CHUNK // 32  # Ritz: ~0.3 ms per design
    for L in problem.rules.string_lengths(enc):
        n = L * enc.plies_per_symbol * problem.rules.multiplier()
        if n_start is not None and n < n_start:
            continue
        total = base ** L
        remaining = time_limit - (time.perf_counter() - t0)
        if rate is not None and total / rate > remaining:
            complete = False
            if verbose:
                print(f"  exhaustive: n={n} skipped (estimated {total / rate:.0f} s > {remaining:.0f} s left)")
            break
        tL = time.perf_counter()
        best_m, best_plies, n_valid, n_opt = -np.inf, None, 0, 0
        aborted = False
        for start in range(0, total, chunk):
            if start == chunk:  # after the first chunk: extrapolate the cost of this length
                est = (time.perf_counter() - tL) * total / chunk
                if est > remaining:
                    aborted = True
                    if verbose:
                        print(f"  exhaustive: n={n} aborted (estimated {est:.0f} s > {remaining:.0f} s left)")
                    break
            sym = _digits(start, min(total, start + chunk), base, L)
            if reduced:
                sym = sym[(sym == 1).sum(axis=1) % 2 == 0]
                plies = _family_to_plies(sym)
            else:
                plies = enc.decode(sym)
            plies = plies[_valid_mask(problem, plies)]
            if len(plies) == 0:
                continue
            res = ev.compute_plies(plies)
            n_valid += len(plies)
            m = res["margin"]
            k = int(np.argmax(m))
            if best_plies is None or m[k] > best_m * (1 + 1e-9):
                best_m, best_plies = float(m[k]), plies[k].copy()
                n_opt = int(np.sum(m >= best_m * (1 - 1e-9)))
            elif m[k] >= best_m * (1 - 1e-9):
                n_opt += int(np.sum(m >= best_m * (1 - 1e-9)))
        dt = time.perf_counter() - tL
        n_eval += n_valid
        if aborted:
            complete = False
            break
        rate = max(total / max(dt, 1e-3), 1.0)
        if best_plies is None:
            per_n.append({"n": n, "max_margin": None, "n_valid": 0, "time_s": dt})
            continue
        full = full_laminate(best_plies[None], problem.rules.symmetric)[0]
        assert satisfies(full, problem.rules)
        rec = {"n": n, "max_margin": best_m, "n_valid": n_valid, "n_optima": n_opt, "full": full.tolist(),
               "time_s": dt}
        per_n.append(rec)
        if verbose:
            print(f"  exhaustive: n={n:3d}  valid={n_valid:>10,}  best margin={best_m:.6g}  ({dt:.1f} s)")
        if objective == "min_plies":
            if best_overall is None and best_m >= sf:
                best_overall = rec
            if best_overall is not None and (front_to_n is None or n >= front_to_n):
                break
        else:
            if best_overall is None or best_m > best_overall["max_margin"]:
                best_overall = rec
    out = {"objective": objective, "reduced_alphabet": reduced, "per_n": per_n, "complete": complete,
           "time_s": time.perf_counter() - t0, "n_evaluated": n_eval}
    if objective == "min_plies":
        out["feasible"] = best_overall is not None
        if best_overall is None:
            # infeasible within the enumerated lengths: report the best design found (largest margin)
            done = [r for r in per_n if r["max_margin"] is not None]
            best_overall = max(done, key=lambda r: r["max_margin"]) if done else None
            out["status"] = "infeasible" if complete else "unknown (time limit)"
        else:
            out["status"] = "optimal"
    else:
        out["status"] = "optimal" if complete else "unknown (time limit)"
    out["best"] = best_overall
    return out


# ------------------------------------------------------------------------- count-level enumeration (exact)
def _count_tuples(problem: Problem, L: int):
    """All symbol-count vectors of a design string of length L that satisfy balance and the family minimums."""
    enc = problem.enc
    r = problem.rules
    n = L * enc.plies_per_symbol * r.multiplier()
    need = r.family_minimum_symbols(enc, n)
    k = enc.n_symbols
    for c in itertools.product(range(L + 1), repeat=k - 1):
        last = L - sum(c)
        if last < 0:
            continue
        cnt = c + (last,)
        if enc is PLY and r.balanced and cnt[1] != cnt[2]:
            continue
        fam = np.zeros(3, int)
        for s, v in enumerate(cnt):
            fam[enc.family[s]] += v
        if np.any(fam < need):
            continue
        yield cnt


def arrange(problem: Problem, counts: Tuple[int, ...]) -> Optional[List[int]]:
    """Exact test (DP over remaining counts, last symbol, run length) whether the symbol counts can be arranged
    within the contiguity limit; returns one arrangement (outer -> mid-plane) or None."""
    enc, r = problem.enc, problem.rules
    rl, el = r.run_limits(enc)
    single = enc.single_angle
    if rl is None:
        out = []
        for s, v in enumerate(counts):
            out += [s] * v
        return out
    sym = r.symmetric

    @lru_cache(maxsize=None)
    def go(rem: Tuple[int, ...], last: int, run: int, first: bool) -> Optional[Tuple[int, ...]]:
        if sum(rem) == 0:
            return ()
        # most plentiful symbol first, preferring a change of symbol -> interleaved, readable sequences
        for s in sorted(range(len(rem)), key=lambda k: (-rem[k], k == last, k)):
            if rem[s] == 0:
                continue
            if s == last and single[s]:
                lim = el if (first and sym) else rl
                if run + 1 > lim:
                    continue
            nrem = rem[:s] + (rem[s] - 1,) + rem[s + 1:]
            if s == last:
                sub = go(nrem, s, run + 1, first)
            else:
                sub = go(nrem, s, 1, last == -1)
            if sub is not None:
                return (s,) + sub
        return None

    res = go(tuple(int(x) for x in counts), -1, 0, True)
    if res is None:
        return None
    seq = list(res)
    return seq[::-1] if sym else seq  # built from the mid-plane side when symmetric


def strength_only_exact(problem: Problem) -> Dict:
    """Exact optimum (any ply count) when there is no buckling check and the laminate is symmetric."""
    if not problem.rules.symmetric:
        raise ValueError("strength_only_exact needs symmetric laminates (margin = f(counts))")
    if "buckling" in problem.criteria and problem.has_compression:
        raise ValueError("strength_only_exact: buckling is active")
    t0 = time.perf_counter()
    enc = problem.enc
    ev = Evaluator(problem)
    per_n, best, n_eval = [], None, 0
    for L in problem.rules.string_lengths(enc):
        n = L * enc.plies_per_symbol * problem.rules.multiplier()
        tuples = list(_count_tuples(problem, L))
        if not tuples:
            continue
        n_eval += len(tuples)
        reps = []
        for cnt in tuples:  # representative arrangement (counts determine the margin)
            reps.append(np.repeat(np.arange(len(cnt)), cnt))
        plies = enc.decode(np.array(reps, dtype=np.int8))
        res = ev.compute_plies(plies)
        order = np.argsort(-res["margin"])
        for i in order:  # best counts first; keep the first that can be arranged
            seq = arrange(problem, tuples[i])
            if seq is not None:
                full = full_laminate(enc.decode(np.array([seq], dtype=np.int8)), True)[0]
                assert satisfies(full, problem.rules)
                rec = {"n": n, "max_margin": float(res["margin"][i]), "counts": tuples[i],
                       "full": full.tolist(), "n_count_tuples": len(tuples)}
                per_n.append(rec)
                if best is None and rec["max_margin"] >= problem.safety_factor:
                    best = rec
                break
    feasible = best is not None
    if not feasible:
        best = max(per_n, key=lambda r: r["max_margin"]) if per_n else None
    return {"objective": "min_plies", "status": "optimal" if feasible else "infeasible", "feasible": feasible,
            "best": best, "per_n": per_n, "complete": True, "time_s": time.perf_counter() - t0,
            "n_evaluated": n_eval, "method": "count-level enumeration (strength only)"}


def count_upper_bounds(problem: Problem) -> Dict:
    """Upper bound of the best margin for each ply count (see module doc) and the certified lower bound n_lb
    on the optimal ply count (smallest n whose bound reaches the safety factor)."""
    if not problem.rules.symmetric:
        raise ValueError("count_upper_bounds needs symmetric laminates")
    if problem.buckling_model == "ritz_full" and "buckling" in problem.criteria and problem.has_compression:
        return _count_upper_bounds_full(problem)
    enc = problem.enc
    ev = Evaluator(problem)
    t = problem.ply_thickness
    per_n, n_lb = [], None
    for L in problem.rules.string_lengths(enc):
        W = L * enc.plies_per_symbol
        n = 2 * W
        tuples = list(_count_tuples(problem, L))
        if not tuples:
            continue
        plies = enc.decode(np.array([np.repeat(np.arange(len(c)), c) for c in tuples], dtype=np.int8))
        counts = np.stack([(plies == k).sum(axis=1) for k in range(4)], axis=1)
        strength = replace(problem, criteria=tuple(c for c in problem.criteria if c != "buckling"))
        ub = Evaluator(strength).compute_plies(plies)["margin"] if strength.criteria else np.full(len(plies), np.inf)
        if "buckling" in problem.criteria and problem.has_compression:
            j = np.arange(W)[::-1]
            w = np.sort(2.0 * t ** 3 * ((j + 1.0) ** 3 - j ** 3) / 3.0)[::-1]   # outermost (largest) first
            Qb = ev.Qb
            comps = {"D11": Qb[:, 0, 0], "D22": Qb[:, 1, 1], "H": Qb[:, 0, 1] + 2 * Qb[:, 2, 2]}
            Dopt = {}
            for name, q in comps.items():
                vals = np.zeros((len(plies), W))
                for i, c in enumerate(counts):
                    v = np.repeat(q, c)          # stiffness value of every ply
                    vals[i] = np.sort(v)[::-1]   # largest on the outermost position
                Dopt[name] = vals @ w
            D = np.zeros((len(plies), 3, 3))
            D[:, 0, 0], D[:, 1, 1], D[:, 2, 2] = Dopt["D11"], Dopt["D22"], Dopt["H"] / 2.0  # D12 = 0, D66 = H/2
            lam = ev.buckling_rf(D) / problem.criterion_factors.get("buckling", 1.0)
            ub = np.minimum(ub, lam)
        bound = float(np.max(ub))
        per_n.append({"n": n, "margin_upper_bound": bound})
        if n_lb is None and bound >= problem.safety_factor:
            n_lb = n
    return {"per_n": per_n, "n_lower_bound": n_lb}


# ------------------------------------------------------- exact search with the full Ritz model (D16, D26, Nxy)
# With D16, D26 the buckling factor depends on the order AND on the sign of every +-45 ply (D16 = D26 =
# (Q11 - Q22)/4 * sum of +-1 x position weights), so the family-string reduction above no longer holds. The exact
# search below works per ply count n, in two branch-and-bound levels, with bounds that are PROVEN:
#  * Rayleigh quotient: for any fixed mode vector A of the Ritz basis with A^T (-G) A > 0, the Ritz buckling factor
#    satisfies lambda(D) <= R(A; D) = sum_c D_c r_c(A) (lambda is the minimum of R over all A), and R is LINEAR in
#    D = sum_k w_k Qbar(angle_k) (w_k = position weight of half-ply k).
#  * Count level: for fixed ply counts, max over arrangements of sum_k w_k g(angle_k) with g = sum_c r_c Qbar_c is
#    reached by putting the angles with the largest g on the outermost positions (rearrangement inequality; the
#    contiguity rule is ignored, which only raises the bound). min over several modes A_j, and over convex
#    combinations of pairs of them (max of a sum <= sum of maxima is not needed: max_D min_j R_j <= max_D
#    sum_j mu_j R_j for any weights mu on the simplex), gives an upper bound of lambda for EVERY arrangement of
#    those counts. With the exact strength RF of the counts: UB(counts) = min(RF_strength, bound).
#  * Design level: inside one count tuple, every valid arrangement is generated; its bound min_j R(A_j; D) costs a
#    dot product, and the eigenvalue problem is solved only for designs whose bound exceeds the best margin found.
# The bounds are bounds of the Ritz value with the SAME number of terms as the optimisation, so "exact" means: the
# global optimum of the model that the GA / NSGA-II optimise.
FULL_ARRANGEMENT_CAP = 3_000_000   # arrangements of one count tuple generated at once (above: not enumerated)


def _q6(ev: Evaluator) -> np.ndarray:
    """(4, 6): D11, D12, D22, D66, D16, D26 of Qbar for ply codes 0, +45, -45, 90."""
    Qb = ev.Qb
    return np.stack([Qb[:, 0, 0], Qb[:, 0, 1], Qb[:, 1, 1], Qb[:, 2, 2], Qb[:, 0, 2], Qb[:, 1, 2]], axis=1)


def _half_weights(L: int, t: float) -> np.ndarray:
    """Weights of half-plies outer -> mid-plane (both mirrored plies): D = sum_k w_k Qbar_k."""
    j = np.arange(L)[::-1].astype(float)
    return 2.0 * t ** 3 * ((j + 1.0) ** 3 - j ** 3) / 3.0


def _multinomial(cnt) -> int:
    from math import factorial
    out = factorial(sum(cnt))
    for c in cnt:
        out //= factorial(c)
    return out


def _arrangements(cnt, run_limit: Optional[int]) -> np.ndarray:
    """All strings (outer -> mid) with cnt[s] symbols s (s = 0..3), no run longer than run_limit."""
    L = int(sum(cnt))
    pre = np.zeros((1, 0), np.int8)
    rem = np.array([cnt], dtype=np.int16)
    last = np.full(1, -1, np.int16)
    run = np.zeros(1, np.int16)
    for _ in range(L):
        parts = []
        for s in range(4):
            ok = rem[:, s] > 0
            if run_limit:
                ok &= ~((last == s) & (run >= run_limit))
            k = int(ok.sum())
            if k == 0:
                continue
            r2 = rem[ok].copy()
            r2[:, s] -= 1
            parts.append((np.concatenate([pre[ok], np.full((k, 1), s, np.int8)], axis=1), r2,
                          np.full(k, s, np.int16), np.where(last[ok] == s, run[ok] + 1, 1).astype(np.int16)))
        if not parts:
            return np.zeros((0, L), np.int8)
        pre = np.concatenate([p[0] for p in parts])
        rem = np.concatenate([p[1] for p in parts])
        last = np.concatenate([p[2] for p in parts])
        run = np.concatenate([p[3] for p in parts])
    return pre


class _FullBounds:
    """Bounds of the Ritz buckling factor for one problem and one half-length L (see the comment above)."""

    def __init__(self, problem: Problem, ev: Evaluator, L: int):
        self.p, self.ev, self.model = problem, ev, ev.ritz_model
        self.q6 = _q6(ev)
        self.w = _half_weights(L, problem.ply_thickness)
        self.factor = problem.criterion_factors.get("buckling", 1.0)

    def dvec(self, arrs: np.ndarray) -> np.ndarray:
        return np.einsum("k,pkc->pc", self.w, self.q6[arrs])

    def modes(self, arrs: np.ndarray) -> List[np.ndarray]:
        """Quotient coefficient vectors r (6,) of the critical modes of the given designs."""
        lam, crit = self.model.lam(self.dvec(arrs), vectors=True)
        out = []
        for c in crit:
            if c is not None:
                r = self.model.quotient_terms(*c)
                if r is not None:
                    out.append(r)
        return out

    def count_bound(self, cnt, R: List[np.ndarray]) -> Tuple[float, np.ndarray]:
        """Upper bound of lambda over all arrangements of the counts, for the quotient vectors R; also the
        arrangement that maximises the first vector's quotient (next trial design)."""
        if not R:
            return np.inf, None
        multiset = np.repeat(np.arange(4), cnt)
        best, arg = np.inf, None

        def rearranged(r):
            g = self.q6[multiset] @ r
            order = np.argsort(-g, kind="stable")
            return float(np.sort(g)[::-1] @ np.sort(self.w)[::-1]), multiset[order]

        for r in R:
            v, arr = rearranged(r)
            if v < best:
                best, arg = v, arr
        for i in range(len(R)):           # convex combinations of pairs
            for j in range(i + 1, len(R)):
                for mu in np.linspace(0.1, 0.9, 9):
                    v, _ = rearranged(mu * R[i] + (1 - mu) * R[j])
                    best = min(best, v)
        return best / self.factor, arg


def _tuple_data(problem: Problem, ev: Evaluator, L: int, n_modes: int = 4):
    """Count tuples of half-length L that satisfy the rules and can be arranged, with their exact strength RF,
    a proven upper bound of the buckling factor, and the quotient vectors used for it."""
    enc = problem.enc
    strength = replace(problem, criteria=tuple(c for c in problem.criteria if c != "buckling"))
    fb = _FullBounds(problem, ev, L)
    out = []
    tuples = [c for c in _count_tuples(problem, L) if arrange(problem, c) is not None]
    if not tuples:
        return fb, out
    reps = enc.decode(np.array([np.repeat(np.arange(len(c)), c) for c in tuples], dtype=np.int8))
    rf_s = Evaluator(strength).compute_plies(reps)["margin"] if strength.criteria else np.full(len(tuples), np.inf)
    for cnt, rs in zip(tuples, rf_s):
        start = np.array(arrange(problem, cnt), dtype=np.int8)
        trials = [start]
        R = fb.modes(start[None])
        ub, arr = fb.count_bound(cnt, R)
        for _ in range(n_modes - 1):     # trial designs: maximisers of the current bound
            if arr is None:
                break
            trials.append(arr)
            R += fb.modes(arr[None])
            ub2, arr = fb.count_bound(cnt, R)
            if ub2 >= ub * (1 - 1e-9):
                ub = min(ub, ub2)
                break
            ub = ub2
        out.append({"counts": tuple(int(x) for x in cnt), "rf_strength": float(rs), "lam_ub": float(ub),
                    "ub": float(min(rs, ub)), "R": R, "trials": np.array(trials, dtype=np.int8)})
    return fb, out


def _count_upper_bounds_full(problem: Problem) -> Dict:
    ev = Evaluator(problem)
    per_n, n_lb = [], None
    for L in problem.rules.string_lengths(problem.enc):
        fb, data = _tuple_data(problem, ev, L)
        if not data:
            continue
        n = 2 * L
        bound = max(d["ub"] for d in data)
        per_n.append({"n": n, "margin_upper_bound": bound})
        if n_lb is None and bound >= problem.safety_factor:
            n_lb = n
    return {"per_n": per_n, "n_lower_bound": n_lb, "method": "Rayleigh-quotient / rearrangement bound (D16, D26)"}


def exact_full(problem: Problem, time_limit: float = 600.0, front_to_n: Optional[int] = None,
               verbose: bool = False) -> Dict:
    """Exact fewest-plies optimum with the full Ritz model (symmetric, balanced, ply encoding): per ply count,
    the exact maximum margin by branch and bound (count tuples by decreasing bound; inside a tuple, designs by
    decreasing quotient bound; eigenvalues only where the bound can beat the best margin found). A ply count is
    'complete' when no bound is left above the best margin. Stops after n* (or front_to_n) or at the time limit."""
    if not (problem.encoding == "ply" and problem.rules.symmetric and problem.rules.balanced):
        raise ValueError("exact_full: symmetric, balanced laminates with the ply encoding")
    t0 = time.perf_counter()
    ev = Evaluator(problem)
    rl, _ = problem.rules.run_limits(problem.enc)
    sf = problem.safety_factor
    per_n, bounds, best_overall, complete, n_lb = [], [], None, True, None
    n_eig = 0
    for L in problem.rules.string_lengths(problem.enc):
        n = 2 * L
        if time.perf_counter() - t0 > time_limit:
            complete = False
            break
        tL = time.perf_counter()
        fb, data = _tuple_data(problem, ev, L)
        if not data:
            continue
        ub_n = max(d["ub"] for d in data)
        bounds.append({"n": n, "margin_upper_bound": ub_n})
        if n_lb is None and ub_n >= sf:
            n_lb = n
        best_m, best_arr, n_valid, done_n = -np.inf, None, 0, True
        for d in sorted(data, key=lambda d: -d["ub"]):
            if d["ub"] <= best_m * (1 + 1e-12):
                break
            # trial arrangements first: if one reaches the strength RF of the counts, nothing can do better
            trial = d["trials"][_valid_mask(problem, d["trials"])] if len(d["trials"]) else d["trials"]
            if len(trial):
                lam = ev.ritz_model.lam_cached(fb.dvec(trial)) / fb.factor
                n_eig += len(trial)
                mg = np.minimum(lam, d["rf_strength"])
                k = int(np.argmax(mg))
                if mg[k] > best_m:
                    best_m, best_arr = float(mg[k]), trial[k].copy()
                if mg[k] >= d["rf_strength"] * (1 - 1e-12):
                    continue
            if _multinomial(d["counts"]) > FULL_ARRANGEMENT_CAP or time.perf_counter() - t0 > time_limit:
                done_n = False
                break
            arrs = _arrangements(d["counts"], rl)
            arrs = arrs[_valid_mask(problem, arrs)]
            if len(arrs) == 0:
                continue
            n_valid += len(arrs)
            Dv = fb.dvec(arrs)
            R = np.array(d["R"]) if d["R"] else None
            qb = (np.min(Dv @ R.T, axis=1) / fb.factor) if R is not None else np.full(len(arrs), np.inf)
            qb = np.minimum(qb, d["rf_strength"])
            order = np.argsort(-qb, kind="stable")
            pos = 0
            while pos < len(order):
                if qb[order[pos]] <= best_m * (1 + 1e-12):
                    break
                idx = order[pos:pos + 256]
                idx = idx[qb[idx] > best_m * (1 + 1e-12)]
                lam = ev.ritz_model.lam_cached(Dv[idx]) / fb.factor
                n_eig += len(idx)
                mg = np.minimum(lam, d["rf_strength"])
                k = int(np.argmax(mg))
                if mg[k] > best_m:
                    best_m, best_arr = float(mg[k]), arrs[idx[k]].copy()
                pos += 256
                if best_m >= d["rf_strength"] * (1 - 1e-12):
                    break        # the strength RF of these counts is reached: no arrangement can do better
            if time.perf_counter() - t0 > time_limit:
                done_n = False
                break
        dt = time.perf_counter() - tL
        rec = {"n": n, "max_margin": best_m if best_arr is not None else None, "n_valid": n_valid,
               "complete": done_n, "time_s": dt, "margin_upper_bound": ub_n}
        if best_arr is not None:
            full = full_laminate(best_arr[None], True)[0]
            assert satisfies(full, problem.rules)
            rec["full"] = full.tolist()
        if not done_n:
            rec["max_margin_lower"] = rec.pop("max_margin")   # best found so far; not proven to be the maximum
        per_n.append(rec)
        if verbose:
            print(f"  exact_full: n={n:3d} best={best_m:.6g} ub={ub_n:.6g} valid={n_valid:,} complete={done_n} "
                  f"({dt:.1f} s)")
        if not done_n:
            # still proven infeasible if no count tuple can reach the safety factor
            if ub_n >= sf:
                complete = False
                break
            continue
        if best_overall is None and best_m >= sf:
            best_overall = rec
        if best_overall is not None and (front_to_n is None or n >= front_to_n):
            break
    out = {"objective": "min_plies", "per_n": per_n, "complete": complete, "time_s": time.perf_counter() - t0,
           "n_evaluated": sum(r.get("n_valid", 0) for r in per_n), "n_eigen_solved": n_eig,
           "bounds": {"per_n": bounds, "n_lower_bound": n_lb}, "method": "branch and bound with proven bounds"}
    if best_overall is not None:
        out.update(status="optimal", feasible=True, best=best_overall)
    else:
        done = [r for r in per_n if r.get("max_margin") is not None]
        out.update(status="infeasible" if complete else "unknown (time limit)", feasible=False,
                   best=max(done, key=lambda r: r["max_margin"]) if done else None)
    return out
