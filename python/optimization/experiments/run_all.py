"""
Run every Layer-1 experiment in order and write deliverables/optimization/results + figures.
  python -m optimization.experiments.run_all            full run (about 1.5 hours, at most 4 processes)
  python -m optimization.experiments.run_all --quick    a few minutes: fewer seeds, smaller budgets
"""
from __future__ import annotations

import argparse

from optimization import matlab_check
from optimization.experiments import (leriche_haftka_exp, make_figures, matlab_recheck, run_cases, verify_buckling,
                                      verify_matlab)
from optimization.experiments.common import Timer, setup


def main(quick: bool = False):
    setup()
    T = Timer()
    print("=== 0/5 checks of the buckling model (Ritz with D16, D26, Nxy) ===", flush=True)
    if not verify_buckling.main()["all_pass"]:
        raise SystemExit("buckling model checks FAILED - the model is not used in the optimisation")
    print("\n=== 1/5 Python CLT vs MATLAB clt_engine.m ===", flush=True)
    if matlab_check.available():
        verify_matlab.main(n_cases=60)
    else:
        print("MATLAB engine not available -> step skipped (previous results kept, if any)")
    print("\n=== 2/5 eight load cases: exact search, GA, NSGA-II, quasi-isotropic ===", flush=True)
    run_cases.main(quick=quick, recompute=not quick)  # full mode recomputes every exhaustive search
    print("\n=== 3/5 MATLAB re-check of the final designs ===", flush=True)
    matlab_recheck.main()
    print("\n=== 4/5 Le Riche & Haftka benchmark ===", flush=True)
    leriche_haftka_exp.main(quick=quick)
    print("\n=== 5/5 figures ===", flush=True)
    make_figures.main()
    print(f"\nALL DONE in {T() / 60:.1f} min ({'quick' if quick else 'full'} mode)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    main(ap.parse_args().quick)
