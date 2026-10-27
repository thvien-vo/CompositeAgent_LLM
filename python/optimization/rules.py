"""
rules.py - ply codes, encodings, design rules and the repair operator.

Ply codes: 0 -> 0 deg, 1 -> +45, 2 -> -45, 3 -> 90; EMPTY = -1 (padding). Families: 0 deg, +-45, 90 deg.

A DESIGN STRING is what the optimizers manipulate: a sequence of SYMBOLS of an encoding,
  * ply encoding:   symbols 0, +45, -45, 90 (one ply each);
  * stack encoding: symbols 0_2, +-45 (= +45/-45), 90_2 (two plies each, as in Le Riche & Haftka 1993/1995;
                    balance is then automatic).
With the symmetry rule ON the string is the half laminate from the OUTER surface to the mid-plane, and the full
laminate is half + mirror(half). With symmetry OFF it is the whole laminate from ply 1 (z = -h/2) upward.
Canonical form: symbols right-aligned, EMPTY padding at the start (outer side). Two strings decode to the same
laminate if and only if their canonical forms are equal, so the canonical form is used as cache key.

Rules (each can be switched off): symmetric, balanced (#+45 = #-45), min_fraction (each family 0 / +-45 / 90
>= 10 % of the plies, counted on the full laminate), max_contiguous (no more than k identical angles in a row,
counted on the full laminate, i.e. across the mid-plane when symmetric). check_rules() is the ground truth used by
tests and by the final verification; repair() maps any string to one that satisfies every active rule.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

ANGLES = np.array([0.0, 45.0, -45.0, 90.0])
EMPTY = -1
FAMILY_OF_PLY = np.array([0, 1, 1, 2])
FAMILY_NAMES = ("0", "+-45", "90")


class RepairError(RuntimeError):
    pass


@dataclass(frozen=True)
class Encoding:
    name: str
    symbols: Tuple[Tuple[int, ...], ...]  # ply codes of each symbol

    @property
    def n_symbols(self) -> int:
        return len(self.symbols)

    @property
    def plies_per_symbol(self) -> int:
        return len(self.symbols[0])

    @property
    def family(self) -> np.ndarray:
        return np.array([FAMILY_OF_PLY[s[0]] for s in self.symbols])

    @property
    def single_angle(self) -> np.ndarray:
        """True for symbols made of one angle only (subject to the contiguity rule at symbol level)."""
        return np.array([len(set(s)) == 1 for s in self.symbols])

    def symbol_of(self, ply_codes: Sequence[int]) -> int:
        return self.symbols.index(tuple(ply_codes))

    def decode(self, genes: np.ndarray) -> np.ndarray:
        """(P, Lg) symbols with EMPTY -> (P, Lg * pps) ply codes, EMPTY kept in place (same alignment)."""
        g = np.atleast_2d(np.asarray(genes))
        table = np.array(self.symbols + ((EMPTY,) * self.plies_per_symbol,))  # last row = EMPTY
        return table[np.where(g >= 0, g, len(self.symbols))].reshape(g.shape[0], -1)


PLY = Encoding("ply", ((0,), (1,), (2,), (3,)))
STACK = Encoding("stack", ((0, 0), (1, 2), (3, 3)))
ENCODINGS = {"ply": PLY, "stack": STACK}


@dataclass(frozen=True)
class Rules:
    """Design rules; None / False switches a rule off. n_min, n_max: allowed range of the total ply count."""
    symmetric: bool = True
    balanced: bool = True
    min_fraction: Optional[float] = 0.10
    max_contiguous: Optional[int] = 4
    n_min: int = 8
    n_max: int = 64

    def multiplier(self) -> int:
        return 2 if self.symmetric else 1

    def required_family_plies(self, n: int) -> int:
        """Minimum number of plies of each family in an n-ply laminate (0 if the rule is off)."""
        if not self.min_fraction:
            return 0
        return int(math.ceil(self.min_fraction * n - 1e-9))

    def string_lengths(self, enc: Encoding) -> List[int]:
        """Allowed lengths L of the design string (symbols) such that n = L * pps * mult lies in [n_min, n_max]
        and the family minimums can be met."""
        unit = enc.plies_per_symbol * self.multiplier()
        out = []
        for L in range(1, self.n_max // unit + 1):
            n = L * unit
            if self.n_min <= n <= self.n_max and sum(self.family_minimum_symbols(enc, n)) <= L:
                out.append(L)
        return out

    def allowed_ply_counts(self, enc: Encoding) -> List[int]:
        unit = enc.plies_per_symbol * self.multiplier()
        return [L * unit for L in self.string_lengths(enc)]

    def family_minimum_symbols(self, enc: Encoding, n: int) -> List[int]:
        """Minimum number of symbols of each family in the design string for an n-ply laminate."""
        unit = enc.plies_per_symbol * self.multiplier()
        req = self.required_family_plies(n)
        mins = [int(math.ceil(req / unit)) for _ in range(3)]
        if enc is PLY and self.balanced:
            mins[1] = max(mins[1] + mins[1] % 2, 2 if req > 0 else 0)  # +45 and -45 come in pairs
        return mins

    def run_limits(self, enc: Encoding) -> Tuple[Optional[int], Optional[int]]:
        """(limit of a run of one single-angle symbol, limit of the run touching the mid-plane) in symbols."""
        if not self.max_contiguous:
            return None, None
        k, pps = self.max_contiguous, enc.plies_per_symbol
        if k < pps or (self.symmetric and k < 2 * pps):
            raise ValueError("max_contiguous too small for this encoding / symmetry")
        return k // pps, (k // (2 * pps) if self.symmetric else None)


# ----------------------------------------------------------------------------------------------- checks
def full_laminate(plies: np.ndarray, symmetric: bool) -> np.ndarray:
    """Ply codes of the full laminate (ply 1 first) from a (P, W) array; EMPTY entries are dropped per row.
    Rows may have different lengths -> returns a list-like object array if lengths differ, else (P, n)."""
    rows = []
    for r in np.atleast_2d(plies):
        r = r[r >= 0]
        rows.append(np.concatenate([r, r[::-1]]) if symmetric else r)
    lens = {len(r) for r in rows}
    if len(lens) == 1:
        return np.array(rows)
    return np.array(rows, dtype=object)


def max_run(seq: np.ndarray) -> int:
    best = run = 0
    prev = None
    for x in seq:
        run = run + 1 if x == prev else 1
        prev = x
        best = max(best, run)
    return best


def check_rules(full: Sequence[int], rules: Rules) -> Dict[str, bool]:
    """Ground-truth check of ONE full laminate (ply codes, ply 1 first) against every active rule."""
    f = np.asarray(full, dtype=int)
    n = len(f)
    out = {"ply_count": rules.n_min <= n <= rules.n_max}
    if rules.symmetric:
        out["symmetric"] = bool(np.array_equal(f, f[::-1]))
    if rules.balanced:
        out["balanced"] = int(np.sum(f == 1)) == int(np.sum(f == 2))
    if rules.min_fraction:
        req = rules.required_family_plies(n)
        fam = np.bincount(FAMILY_OF_PLY[f], minlength=3)
        out["min_fraction"] = bool(np.all(fam >= req))
    if rules.max_contiguous:
        out["contiguity"] = max_run(f) <= rules.max_contiguous
    return out


def satisfies(full: Sequence[int], rules: Rules) -> bool:
    return all(check_rules(full, rules).values())


def contiguity_ok_batch(full: np.ndarray, k: int) -> np.ndarray:
    """Vectorised contiguity check for (P, n) ply codes (no EMPTY): True if no run longer than k."""
    P, n = full.shape
    if n <= k:
        return np.ones(P, bool)
    same = full[:, 1:] == full[:, :-1]          # (P, n-1)
    # a run of k+1 identical plies = k consecutive "same" flags
    acc = np.ones((P, n - k), bool)
    for i in range(k):
        acc &= same[:, i:i + n - k]
    return ~acc.any(axis=1)


# ----------------------------------------------------------------------------------------------- repair
class Repairer:
    """Maps any design string to a canonical string that satisfies every active rule (projection-like:
    the string is changed as little as the simple heuristics below allow)."""

    def __init__(self, enc: Encoding, rules: Rules, n_genes: Optional[int] = None):
        self.enc, self.rules = enc, rules
        self.lengths = rules.string_lengths(enc)
        if not self.lengths:
            raise ValueError("no ply count in [n_min, n_max] can satisfy the rules")
        self.Lmin, self.Lmax = self.lengths[0], self.lengths[-1]
        self.n_genes = n_genes or self.Lmax
        self.unit = enc.plies_per_symbol * rules.multiplier()
        self.family = enc.family
        self.single = enc.single_angle
        self.rl, self.el = rules.run_limits(enc)
        self.ply_balanced = enc is PLY and rules.balanced
        self.stats = {"calls": 0, "rebuilds": 0}

    # -- helpers
    def _fam_counts(self, s: List[int]) -> np.ndarray:
        return np.bincount(self.family[np.array(s, int)], minlength=3) if s else np.zeros(3, int)

    def _family_symbols(self, f: int) -> List[int]:
        return [k for k in range(self.enc.n_symbols) if self.family[k] == f]

    def _put_family(self, s: List[int], idx: List[int], f: int, rng) -> None:
        """Set positions idx to family f (for +-45 with the ply encoding: alternate +45 / -45)."""
        syms = self._family_symbols(f)
        if f == 1 and self.enc is PLY:
            for j, i in enumerate(idx):
                s[i] = 1 if j % 2 == 0 else 2
        else:
            for i in idx:
                s[i] = syms[rng.integers(len(syms))]

    def _take(self, s: List[int], f: int, k: int, rng) -> Optional[List[int]]:
        """k random positions of family f (for +-45 ply encoding with balance: equal numbers of +45 and -45)."""
        if f == 1 and self.ply_balanced:
            plus = [i for i, x in enumerate(s) if x == 1]
            minus = [i for i, x in enumerate(s) if x == 2]
            h = (k + 1) // 2
            if len(plus) < h or len(minus) < h:
                return None
            return list(rng.choice(plus, h, replace=False)) + list(rng.choice(minus, h, replace=False))
        pos = [i for i, x in enumerate(s) if self.family[x] == f]
        if len(pos) < k:
            return None
        return list(rng.choice(pos, k, replace=False))

    # -- steps
    def _fix_length(self, s: List[int], rng) -> None:
        L = len(s)
        if L < self.Lmin or L > self.Lmax or L not in self.lengths:
            target = min(self.lengths, key=lambda x: (abs(x - L), x))
            while len(s) < target:
                s.insert(int(rng.integers(len(s) + 1)), int(rng.integers(self.enc.n_symbols)))
            while len(s) > target:
                s.pop(int(rng.integers(len(s))))

    def _fix_balance(self, s: List[int], rng) -> bool:
        if not self.ply_balanced:
            return False
        changed = False
        d = s.count(1) - s.count(2)
        while abs(d) >= 2:
            sur = 1 if d > 0 else 2
            pos = [i for i, x in enumerate(s) if x == sur]
            s[pos[rng.integers(len(pos))]] = 3 - sur
            d = s.count(1) - s.count(2)
            changed = True
        if d != 0:
            sur, deficit = (1, 2) if d > 0 else (2, 1)
            others = [i for i, x in enumerate(s) if x in (0, 3)]
            if others and rng.random() < 0.5:
                s[others[rng.integers(len(others))]] = deficit
            else:
                pos = [i for i, x in enumerate(s) if x == sur]
                fam = self._fam_counts(s)
                s[pos[rng.integers(len(pos))]] = 0 if (fam[0] < fam[2] or (fam[0] == fam[2] and rng.random() < .5)) else 3
            changed = True
        return changed

    def _fix_minimums(self, s: List[int], rng) -> bool:
        n = len(s) * self.unit
        need = self.rules.family_minimum_symbols(self.enc, n)
        changed = False
        for _ in range(4 * len(s) + 4):
            fam = self._fam_counts(s)
            lack = [f for f in range(3) if fam[f] < need[f]]
            if not lack:
                return changed
            f = lack[0]
            if f == 1 and self.ply_balanced:
                # one +45 and one -45, each taken from the 0 / 90 family with the largest surplus
                for sign in (1, 2):
                    fam = self._fam_counts(s)
                    g = max((0, 2), key=lambda h: fam[h] - need[h])
                    if fam[g] - need[g] < 1:
                        raise RepairError(f"cannot meet the +-45 minimum with {len(s)} symbols")
                    cand = [i for i, x in enumerate(s) if self.family[x] == g]
                    s[cand[rng.integers(len(cand))]] = sign
            else:
                for g in sorted((g for g in range(3) if g != f), key=lambda g: -(fam[g] - need[g])):
                    step = 2 if (g == 1 and self.ply_balanced) else 1  # +-45 donated as a pair
                    if fam[g] - need[g] >= step:
                        self._put_family(s, self._take(s, g, step, rng), f, rng)
                        break
                else:
                    raise RepairError(f"cannot meet the minimum of family {FAMILY_NAMES[f]} with {len(s)} symbols")
            changed = True
        raise RepairError("family minimums: no convergence")

    def _fix_run_counts(self, s: List[int], rng) -> bool:
        """Make the contiguity rule possible for the counts: c <= rl * (L - c) + (el if symmetric else rl)."""
        if self.rl is None:
            return False
        changed = False
        L = len(s)
        end = self.el if self.rules.symmetric else self.rl
        for sym in range(self.enc.n_symbols):
            if not self.single[sym]:
                continue
            while s.count(sym) > self.rl * (L - s.count(sym)) + end:
                pos = [i for i, x in enumerate(s) if x == sym]
                if self.family[sym] == 1:   # ply encoding, +45 or -45 alone in excess (balance off): other sign
                    s[pos[rng.integers(len(pos))]] = 3 - sym
                elif self.enc is PLY and self.rules.balanced:
                    a, b_ = rng.choice(pos, 2, replace=False)
                    s[a], s[b_] = 1, 2
                else:
                    s[pos[rng.integers(len(pos))]] = self._family_symbols(1)[0]
                changed = True
        return changed

    def _excess(self, s: List[int]) -> int:
        """Total number of plies (in symbols) beyond the run limits."""
        if self.rl is None:
            return 0
        tot, i, L = 0, 0, len(s)
        while i < L:
            j = i
            while j + 1 < L and s[j + 1] == s[i]:
                j += 1
            if self.single[s[i]]:
                lim = self.el if (self.rules.symmetric and j == L - 1) else self.rl
                tot += max(0, j - i + 1 - lim)
            i = j + 1
        return tot

    def _fix_arrangement(self, s: List[int], rng) -> List[int]:
        if self.rl is None or self._excess(s) == 0:
            return s
        L = len(s)
        stall = 0
        for _ in range(60):
            ex = self._excess(s)
            if ex == 0:
                return s
            # positions inside violating runs
            bad, i = [], 0
            while i < L:
                j = i
                while j + 1 < L and s[j + 1] == s[i]:
                    j += 1
                if self.single[s[i]]:
                    lim = self.el if (self.rules.symmetric and j == L - 1) else self.rl
                    if j - i + 1 > lim:
                        bad.extend(range(i, j + 1))
                i = j + 1
            p = bad[rng.integers(len(bad))]
            best, best_q = ex, []
            for q in range(L):
                if s[q] == s[p]:
                    continue
                s[p], s[q] = s[q], s[p]
                e = self._excess(s)
                s[p], s[q] = s[q], s[p]
                if e < best:
                    best, best_q = e, [q]
                elif e == best:
                    best_q.append(q)
            if best_q:
                q = best_q[rng.integers(len(best_q))]
                s[p], s[q] = s[q], s[p]
            stall = stall + 1 if best >= ex else 0
            if stall > 8:
                break
        if self._excess(s) == 0:
            return s
        return self._rebuild(s, rng)

    def _rebuild(self, s: List[int], rng) -> List[int]:
        """Greedy construction with the same symbol counts, built from the mid-plane end (symmetric) so that the
        mid-plane run limit applies to the first run. Randomised restarts; raises if no arrangement is found."""
        self.stats["rebuilds"] += 1
        counts = np.bincount(np.array(s, int), minlength=self.enc.n_symbols)
        for attempt in range(60):
            rem = counts.copy()
            out: List[int] = []
            run_sym, run_len, first_run = None, 0, True
            ok = True
            for _ in range(len(s)):
                allowed = []
                for k in range(self.enc.n_symbols):
                    if rem[k] == 0:
                        continue
                    if self.single[k] and k == run_sym:
                        lim = self.el if (first_run and self.rules.symmetric) else self.rl
                        if run_len + 1 > lim:
                            continue
                    allowed.append(k)
                if not allowed:
                    ok = False
                    break
                if attempt == 0 or rng.random() < 0.8:
                    top = max(rem[k] for k in allowed)
                    allowed = [k for k in allowed if rem[k] == top]
                k = allowed[rng.integers(len(allowed))]
                if k == run_sym:
                    run_len += 1
                else:
                    if run_sym is not None:
                        first_run = False
                    run_sym, run_len = k, 1
                rem[k] -= 1
                out.append(k)
            if ok:
                return out[::-1] if self.rules.symmetric else out
        raise RepairError("could not arrange the plies within the contiguity limit")

    # -- public
    def repair(self, genes: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        """Repair one design string (symbols with EMPTY anywhere) -> canonical valid string of length n_genes."""
        self.stats["calls"] += 1
        g = np.asarray(genes)
        s = [int(x) for x in g if x >= 0]
        self._fix_length(s, rng)
        for _ in range(12):
            c1 = self._fix_balance(s, rng)
            c2 = self._fix_minimums(s, rng)
            c3 = self._fix_run_counts(s, rng)
            if not (c1 or c2 or c3):
                break
        s = self._fix_arrangement(s, rng)
        out = np.full(self.n_genes, EMPTY, dtype=np.int8)
        out[self.n_genes - len(s):] = s
        full = full_laminate(self.enc.decode(out[None]), self.rules.symmetric)[0]
        chk = check_rules(full, self.rules)
        if not all(chk.values()):
            raise RepairError(f"repair failed {chk} for {s}")
        return out

    def random_valid(self, rng: np.random.Generator, length: Optional[int] = None) -> np.ndarray:
        """Random valid canonical string (random length among the allowed ones unless given)."""
        L = length if length is not None else self.lengths[rng.integers(len(self.lengths))]
        raw = np.full(self.n_genes, EMPTY, dtype=np.int8)
        raw[self.n_genes - L:] = rng.integers(self.enc.n_symbols, size=L)
        return self.repair(raw, rng)


def canonical(genes: np.ndarray) -> np.ndarray:
    """Strip EMPTY (keeping order) and right-align. genes: (P, Lg)."""
    g = np.atleast_2d(genes)
    out = np.full_like(g, EMPTY)
    for i, r in enumerate(g):
        r = r[r >= 0]
        if len(r):
            out[i, g.shape[1] - len(r):] = r
    return out


def notation(full: Sequence[int], symmetric: bool) -> str:
    """Compact stacking notation, e.g. [45/-45/0_2/90]s (half shown when symmetric)."""
    f = [int(x) for x in full]
    if symmetric:
        f = f[:len(f) // 2]
    parts, i = [], 0
    while i < len(f):
        j = i
        while j + 1 < len(f) and f[j + 1] == f[i]:
            j += 1
        a = int(ANGLES[f[i]])
        parts.append(f"{a}" + (f"_{j - i + 1}" if j > i else ""))
        i = j + 1
    return "[" + "/".join(parts) + "]" + ("s" if symmetric else "")
