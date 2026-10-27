"""
leriche_haftka.py - the classical benchmark of Le Riche & Haftka, reproduced as its OWN mode (maximise the
failure load of a FIXED-thickness laminate), not forced into the fewest-plies problem.

SOURCES (read for this project)
  [T]  R. Le Riche, "Optimization of composite structures by genetic algorithms", PhD thesis, Virginia Tech,
       Oct. 1994, Chapter 3 "Optimization of laminate stacking sequence for buckling load maximization by
       genetic algorithms" (same title and content as Le Riche & Haftka, AIAA J. 31(5):951-956, 1993).
       Open access: https://vtechworks.lib.vt.edu/handle/10919/38270 . Problem: sec. 3.1 (thesis pp. 31-34);
       reference designs: Tables 3.1-3.3 (pp. 50-51) and Fig. 3.12 (p. 55).
  [P]  R. Le Riche, R.T. Haftka, "Improved genetic algorithm for minimum thickness composite laminate design",
       Composites Engineering 5(2):143-161, 1995 (http://www.emse.fr/~leriche/ga95.pdf): same plate, material and
       allowables (pp. 144-145, 154); minimum-thickness load cases.
  The AIAA 1993 paper itself was NOT available to us; its problem data are taken from [T] (same author, same
  chapter title, the thesis states the 1993 work as its Chapter 3) and cross-checked with [P].

PROBLEM [T sec. 3.1]
  Simply supported plate a = 20 in, b = 5 in (b = 10 in for the buckling-only case of Table 3.2), loads
  lambda*Nx, lambda*Ny (compression), graphite-epoxy E1 = 18.5e6 psi, E2 = 1.89e6 psi, G12 = 0.93e6 psi,
  nu12 = 0.3, ply t = 0.005 in. Symmetric, balanced, stacks 0_2, +-45, 90_2 (N/4 genes).
  Buckling: closed form (3.1), D16 = D26 neglected, all m, n <= 5.
  Strain failure: max principal strain, allowables e1 = 0.008, e2 = 0.029, g12 = 0.015, safety factor f = 1.5
  applied to the strains only: lambda_cs = min_i min(e1u / (f|e1|), e2u / (f|e2|), g12u / (f|g12|)).
  Objective: maximise lambda_cr = min(lambda_cb, lambda_cs) subject to at most 4 contiguous plies of the same
  orientation (penalty in the paper; here a hard constraint enforced by enumeration filter / repair).
  Buckling-only problem (Table 3.2): maximise lambda_cb, no strain or contiguity constraint.
  Note: [T] eq. (3.3) prints the shear strain as "sin 2theta (ey - ex)"; we use the standard CLT
  transformation, which is identical for gamma_xy = 0 (balanced symmetric laminate under Nx, Ny).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from .evaluate import Evaluator, Plate, Problem
from .material import Material
from .rules import STACK, Rules

PSI = 6894.757293168361          # Pa
INCH = 0.0254                    # m
LB_PER_IN = 4.4482216152605 / INCH  # N/m
INF = float("inf")

LH_MATERIAL = Material(E1=18.5e6 * PSI, E2=1.89e6 * PSI, G12=0.93e6 * PSI, nu12=0.3,
                       Xt=INF, Xc=INF, Yt=INF, Yc=INF, S=INF, name="graphite-epoxy (Le Riche & Haftka)",
                       source="Le Riche (1994) thesis sec. 3.1; Le Riche & Haftka (1995) p. 154")
LH_PLY = 0.005 * INCH
LH_STRAINS = (0.008, 0.029, 0.015)

STACK_CODE = {"0": 0, "±": 1, "90": 2}


@dataclass(frozen=True)
class LHCase:
    id: str
    title: str
    plies: int
    a_in: float
    b_in: float
    ny_over_nx: float
    with_strain: bool                     # False = buckling-only problem
    paper_lambda: float                   # best value reported in the source
    paper_ref: str
    paper_designs: Tuple[Tuple[str, float, float], ...]  # (stacks outer->mid, buckling, strength) from the source


CASES: List[LHCase] = [
    LHCase("LH-A", "buckling only, 64 plies, a/b = 2, Ny/Nx = 1", 64, 20, 10, 1.0, False, 3973.01,
           "[T] Table 3.2 (5 optima listed)",
           (("90 90 90 90 90 ± ± 90 ± ± ± 90 ± ± ± ±", 3973.01, 14205.18),
            ("± 90 90 90 90 90 ± 90 90 90 90 ± 90 90 90 90", 3973.01, 8935.74),
            ("90 90 ± ± 90 90 90 90 90 90 90 90 ± 90 90 90", 3973.01, 8935.74),
            ("90 ± 90 90 90 ± 90 90 90 90 ± 90 90 90 90 90", 3973.01, 8935.74),
            ("90 90 90 90 ± 90 ± 90 ± 90 ± ± ± ± ± ±", 3973.01, 14205.18))),
    LHCase("LH-B", "buckling + strain + contiguity, 48 plies, Ny/Nx = 0.5", 48, 20, 5, 0.5, True, 9998.19,
           "[T] Table 3.1 (global optimum and next best)",
           (("90 ± ± 90 ± 90 ± ± ± ± ± ±", 9998.19, 10394.81),
            ("90 ± ± 90 ± ± 90 ± 90 ± ± ±", 9997.60, 10187.93),
            ("± 90 90 ± 90 ± ± ± ± ± 90 ±", 9976.58, 10187.93))),
    LHCase("LH-C", "buckling + strain + contiguity, 48 plies, Ny/Nx = 0.25", 48, 20, 5, 0.25, True, 12674.84,
           "[T] Fig. 3.12 (GA design; no table for this ratio)",
           (("90 ± ± ± ± ± 0 ± 0 0 ± 0", float("nan"), float("nan")),)),
    LHCase("LH-D", "buckling + strain + contiguity, 48 plies, Ny/Nx = 0.125", 48, 20, 5, 0.125, True, 13518.66,
           "[T] Table 3.3 (multiple optima, strain critical)",
           (("90 ± ± ± ± 0 0 ± 0 0 ± 0", 14168.12, 13518.66),
            ("± ± ± 0 ± ± 0 90 0 0 ± 0", 14134.76, 13518.66),
            ("90 ± ± ± 0 ± 0 ± 0 0 ± 0", 14013.71, 13518.66),
            ("± ± 0 ± ± 90 0 0 ± 0 ± 0", 13662.61, 13518.66))),
]

# minimum-thickness load cases of [P] (lb/in); [P] text p. 149: best 44/48/52-ply designs of load case 1 have
# lambda_cr = 0.879, 1.040, 1.201 (optimum 48 plies). Table 2 of [P] lists 48-ply optima for cases 1-3.
MIN_THICKNESS_CASES = [("LC1", 13000.0, 1625.0), ("LC2", 12500.0, 3125.0), ("LC3", 9800.0, 4900.0)]
P_LC1_LAMBDAS = {44: 0.879, 48: 1.040, 52: 1.201}


def problem(case: LHCase, modes=(5, 5)) -> Problem:
    """Fixed-thickness problem of the benchmark (Nx = 1 lb/in, so lambda is in lb/in as in the source)."""
    crit = ("max_strain", "buckling") if case.with_strain else ("buckling",)
    rules = Rules(symmetric=True, balanced=True, min_fraction=None,
                  max_contiguous=4 if case.with_strain else None, n_min=case.plies, n_max=case.plies)
    return Problem(loads=(-1.0 * LB_PER_IN, -case.ny_over_nx * LB_PER_IN, 0.0), material=LH_MATERIAL, rules=rules,
                   safety_factor=0.0, plate=Plate(case.a_in * INCH, case.b_in * INCH), ply_thickness=LH_PLY,
                   encoding="stack", criteria=crit, strain_allowables=LH_STRAINS,
                   criterion_factors={"max_strain": 1.5}, buckling_modes=modes, name=case.id)


def min_thickness_problem(Nx_lbin: float, Ny_lbin: float, n_max: int = 64) -> Problem:
    """[P] minimum-thickness problem: fewest plies with lambda_cr >= 1 (strain criterion includes f = 1.5)."""
    rules = Rules(symmetric=True, balanced=True, min_fraction=None, max_contiguous=4, n_min=4, n_max=n_max)
    return Problem(loads=(-Nx_lbin * LB_PER_IN, -Ny_lbin * LB_PER_IN, 0.0), material=LH_MATERIAL, rules=rules,
                   safety_factor=1.0, plate=Plate(20 * INCH, 5 * INCH), ply_thickness=LH_PLY, encoding="stack",
                   criteria=("max_strain", "buckling"), strain_allowables=LH_STRAINS,
                   criterion_factors={"max_strain": 1.5}, buckling_modes=(5, 5))


def stacks_to_genes(stacks: str, n_genes: int) -> np.ndarray:
    s = [STACK_CODE[x] for x in stacks.split()]
    g = np.full(n_genes, -1, dtype=np.int8)
    g[n_genes - len(s):] = s
    return g


def evaluate_paper_designs(case: LHCase, modes=(5, 5)) -> List[Dict]:
    """Our lambda_b / lambda_cs for the designs printed in the source, next to the printed values."""
    p = problem(case, modes)
    p_both = problem(LHCase(**{**case.__dict__, "with_strain": True}), modes)  # strength column too
    ev = Evaluator(p_both)
    out = []
    for stacks, lb, ls in case.paper_designs:
        g = stacks_to_genes(stacks, case.plies // 4)
        r = ev.compute_plies(STACK.decode(g[None]))
        lam_s, lam_b = float(r["rf"][0, 0]), float(r["rf"][0, 1])
        lam_cr = lam_b if not case.with_strain else min(lam_b, lam_s)
        out.append({"case": case.id, "design_stacks": stacks, "lambda_b_ours": lam_b, "lambda_b_paper": lb,
                    "lambda_cs_ours": lam_s, "lambda_cs_paper": ls, "lambda_cr_ours": lam_cr,
                    "rel_diff_b": (lam_b - lb) / lb if lb == lb else None,
                    "rel_diff_cs": (lam_s - ls) / ls if ls == ls else None})
    del p
    return out
