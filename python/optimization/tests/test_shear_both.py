"""Option shear_both_signs: a shear load that may reverse. Every design is checked for +Nxy and -Nxy (strength and
buckling) and the smaller reserve factor counts. Off by default, so the published Layer 1 results do not change."""
import itertools
from dataclasses import replace

import numpy as np
import pytest

from optimization import optimize
from optimization.api import make_problem
from optimization.evaluate import Evaluator, analyze_design
from optimization.exhaustive import _valid_mask, exact_full
from optimization.rules import Rules, full_laminate


def _evaluate(p, half):
    ev = Evaluator(p)
    ev.lazy = False
    return ev.compute_plies(half)


def test_off_by_default(im7):
    p = make_problem((1e4, 0, 5e3), material=im7)
    assert not p.shear_both_signs and not p.both_signs
    assert p.load_cases() == ((1e4, 0.0, 5e3),)
    assert "shear_both_signs" not in p.describe()        # result files of the old experiments keep their content
    assert len(Evaluator(p).ritz_models) == 1


def test_no_shear_load_means_no_change(im7, rng):
    half = rng.integers(0, 4, (40, 6)).astype(np.int8)
    off = make_problem((-1e4, -5e3, 0), material=im7, ritz_terms=8)
    on = replace(off, shear_both_signs=True)
    assert not on.both_signs and on.load_cases() == off.load_cases()
    a, b = _evaluate(off, half), _evaluate(on, half)
    assert np.array_equal(a["margin"], b["margin"]) and np.array_equal(a["rf"], b["rf"])


@pytest.mark.parametrize("symmetric", [True, False])
def test_both_signs_is_the_minimum_of_the_two_load_cases(im7, rng, symmetric):
    rules = Rules(symmetric=symmetric, balanced=False, min_fraction=None, max_contiguous=None)
    width = 6 if symmetric else 10
    plies = rng.integers(0, 4, (60, width)).astype(np.int8)
    pos = make_problem((-2e4, 1e4, 3e4), material=im7, rules=rules, ritz_terms=8)
    neg = replace(pos, loads=(-2e4, 1e4, -3e4))
    both = replace(pos, shear_both_signs=True)
    rp, rn, rb = _evaluate(pos, plies), _evaluate(neg, plies), _evaluate(both, plies)
    assert np.allclose(rb["rf"], np.minimum(rp["rf"], rn["rf"]), rtol=1e-12)
    assert np.allclose(rb["margin"], np.minimum(rp["margin"], rn["margin"]), rtol=1e-12)
    assert np.any(np.abs(rp["margin"] - rn["margin"]) > 1e-3 * rp["margin"])   # the two directions do differ


def test_balanced_symmetric_strength_does_not_depend_on_the_shear_sign(im7, rng):
    """+45 and -45 plies swap roles when the shear reverses; with as many of each (balanced, symmetric: A16 = A26
    = 0) the smallest strength RF is the same, so only buckling (D16, D26) differs."""
    p = make_problem((1e5, -2e4, 4e4), material=im7, criteria=("max_stress", "tsai_wu"))
    for _ in range(30):
        n0, n45, n90 = rng.integers(1, 4, 3)
        half = np.array([[0] * n0 + [1, 2] * n45 + [3] * n90], dtype=np.int8)
        a = _evaluate(p, half)["rf"]
        b = _evaluate(replace(p, loads=(1e5, -2e4, -4e4)), half)["rf"]
        assert np.allclose(a, b, rtol=1e-12)


@pytest.mark.parametrize("loads", [(0, 0, 4e4), (-6e3, 0, 3e3), (2e4, -3e3, 1.5e4)])
def test_exact_full_both_signs_equals_brute_force(im7, loads):
    """exact_full with both shear directions = enumeration of every valid design, margin = min over +Nxy, -Nxy."""
    p = make_problem(loads, material=im7, rules=Rules(n_min=8, n_max=16), ritz_terms=8, shear_both_signs=True)
    r = exact_full(p, time_limit=120)
    best = {}
    for L in range(4, 9):
        allp = np.array(list(itertools.product(range(4), repeat=L)), dtype=np.int8)
        allp = allp[_valid_mask(p, allp)]
        if len(allp):
            best[2 * L] = float(_evaluate(p, allp)["margin"].max())
    for rec in r["per_n"]:
        if rec.get("max_margin") is not None:
            assert rec["max_margin"] == pytest.approx(best[rec["n"]], rel=1e-9)
    feas = [n for n in sorted(best) if best[n] >= 1.5]
    if feas:
        assert r["status"] == "optimal" and r["best"]["n"] == feas[0]
    else:
        assert r["status"] == "infeasible"


def test_analyze_design_reports_the_governing_direction(im7):
    p = make_problem((0, 0, 3e5), material=im7, shear_both_signs=True)
    full = full_laminate(np.array([[2, 2, 2, 2, 1, 1, 0, 3, 1, 1, 2, 2]], dtype=np.int8), True)[0]
    det = analyze_design(p, full)
    one = replace(p, shear_both_signs=False)
    pos = analyze_design(one, full)
    neg = analyze_design(replace(one, loads=(0, 0, -3e5)), full)
    assert det["margin"] == pytest.approx(min(pos["margin"], neg["margin"]), rel=1e-12)
    for c in det["rf"]:
        assert det["rf"][c] == pytest.approx(min(pos["rf"][c], neg["rf"][c]), rel=1e-12)
    worse = "+" if pos["margin"] <= neg["margin"] else "-"
    assert det["governing_shear_sign"] == worse
    assert det["by_shear_sign"]["+"]["margin"] == pytest.approx(pos["margin"])
    assert abs(pos["margin"] - neg["margin"]) > 0.05 * min(pos["margin"], neg["margin"])  # a D16-heavy design


def test_design_for_both_directions_is_safe_for_both(im7):
    """The optimum for a shear that may reverse is feasible for +Nxy and for -Nxy; the one-direction optimum may
    not be (it uses the sign of the shear given)."""
    loads = (0, 0, 4e4)
    both = optimize(loads, material=im7, method="exhaustive", rules=Rules(n_max=32), shear_both_signs=True,
                    time_limit=120)
    assert both.status == "optimal" and both.problem["shear_both_signs"]
    p1 = make_problem(loads, material=im7)
    codes = [{0.0: 0, 45.0: 1, -45.0: 2, 90.0: 3}[a] for a in both.stacking_deg]
    for s in (1, -1):
        assert analyze_design(replace(p1, loads=(0, 0, s * 4e4)), codes)["margin"] >= 1.5
    one = optimize(loads, material=im7, method="exhaustive", rules=Rules(n_max=32), time_limit=120)
    assert one.status == "optimal" and one.n_plies <= both.n_plies   # one direction can never need more plies
