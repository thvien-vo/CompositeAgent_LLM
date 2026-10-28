import itertools

import numpy as np
import pytest

from optimization import optimize
from optimization.evaluate import Evaluator, Problem
from optimization.exhaustive import arrange, count_upper_bounds, exhaustive, strength_only_exact
from optimization.ga import GAConfig, GeneticAlgorithm
from optimization.nsga2 import run_nsga2
from optimization.rules import PLY, Rules, full_laminate, satisfies

SMALL = Rules(n_min=8, n_max=20)


def brute_force_best(problem):
    """Reference without the family reduction: every 4^L ply string, ground-truth rule check."""
    ev = Evaluator(problem)
    best = {}
    for L in problem.rules.string_lengths(PLY):
        cand = [np.array(s, dtype=np.int8) for s in itertools.product(range(4), repeat=L)]
        cand = [c for c in cand if satisfies(full_laminate(c[None], True)[0], problem.rules)]
        m = ev.compute_plies(np.array(cand))["margin"]
        best[2 * L] = float(m.max())
    return best


@pytest.mark.parametrize("loads", [(-1e4, 0, 0), (-6e3, -3e3, 2e3), (4e5, 0, 2e5)])
def test_family_reduction_equals_full_enumeration(im7, loads):
    p = Problem(loads=loads, material=im7, rules=Rules(n_min=8, n_max=16))
    ref = brute_force_best(p)
    ex = exhaustive(p, objective="max_margin")
    got = {r["n"]: r["max_margin"] for r in ex["per_n"]}
    for n in ref:
        assert got[n] == pytest.approx(ref[n], rel=1e-12)


def test_strength_only_exact_equals_exhaustive(im7):
    p = Problem(loads=(1.0e6, 0.5e6, 2e5), material=im7, rules=Rules(n_max=28))
    a = strength_only_exact(p)
    b = exhaustive(p, front_to_n=28)
    assert a["best"]["n"] == b["best"]["n"]
    assert a["best"]["max_margin"] == pytest.approx(b["best"]["max_margin"], rel=1e-12)
    bn = {r["n"]: r["max_margin"] for r in b["per_n"]}
    for r in a["per_n"]:
        assert r["max_margin"] == pytest.approx(bn[r["n"]], rel=1e-12)


def test_arrangement_dp():
    p = Problem(loads=(1.0, 0, 0), material=_dummy_material())
    seq = arrange(p, (8, 1, 1, 2))                       # 8 zeros among 12: possible (<= 4*4 + 2)
    assert seq is not None and sorted(seq) == [0] * 8 + [1, 2, 3, 3]
    assert satisfies(full_laminate(np.array([seq]), True)[0], Rules(min_fraction=None))
    assert arrange(p, (10, 1, 1, 0)) is not None         # 10 zeros, 2 others: 4*2 + 2 = 10, just possible
    assert arrange(p, (11, 1, 1, 0)) is None             # 11 zeros, 2 others: impossible


def _dummy_material():
    from optimization.material import Material
    return Material(E1=1.6e11, E2=9e9, G12=5e9, nu12=0.3, Xt=2e9, Xc=1.5e9, Yt=6e7, Yc=2.5e8, S=9e7)


def test_upper_bounds_are_bounds(im7):
    p = Problem(loads=(-1e4, -5e3, 0), material=im7, rules=Rules(n_max=24))
    ub = {r["n"]: r["margin_upper_bound"] for r in count_upper_bounds(p)["per_n"]}
    ex = exhaustive(p, front_to_n=24)
    for r in ex["per_n"]:
        assert r["max_margin"] <= ub[r["n"]] * (1 + 1e-12)
    assert count_upper_bounds(p)["n_lower_bound"] <= ex["best"]["n"]


@pytest.mark.parametrize("loads", [(-1e4, 0, 0), (1.0e6, 0.5e6, 0)])
def test_ga_finds_exhaustive_optimum(im7, loads):
    p = Problem(loads=loads, material=im7)
    ex = exhaustive(p)
    target = (ex["best"]["n"], ex["best"]["max_margin"])
    hits = 0
    for seed in range(4):
        r = GeneticAlgorithm(p, GAConfig(budget=4000), seed).run(target=target)
        hits += r["hit_evals"] is not None
        full = full_laminate(PLY.decode(r["best_genes"][None]), True)[0]
        assert satisfies(full, p.rules)
    assert hits >= 3


def test_nsga2_finds_exhaustive_optimum_and_front(im7):
    p = Problem(loads=(-1e4, -5e3, 0), material=im7)
    ex = exhaustive(p, front_to_n=24)
    target = (ex["best"]["n"], ex["best"]["max_margin"])
    r = run_nsga2(p, seed=1, budget=5000, target=target)
    assert (r["n_plies"], pytest.approx(r["margin"], rel=1e-9)) == (target[0], target[1])
    exf = {q["n"]: q["max_margin"] for q in ex["per_n"]}
    for q in r["pareto"]:
        if q["n"] in exf:
            assert q["margin"] <= exf[q["n"]] * (1 + 1e-12)   # never better than the exact front


def test_seed_reproducibility(im7):
    p = Problem(loads=(-1e4, 0, 0), material=im7)
    a = GeneticAlgorithm(p, GAConfig(budget=1500), 7).run()
    b = GeneticAlgorithm(p, GAConfig(budget=1500), 7).run()
    assert np.array_equal(a["best_genes"], b["best_genes"]) and a["n_evaluations"] == b["n_evaluations"]


def test_infeasible_is_reported(im7):
    r = optimize({"Nx": 4e6, "Ny": 2e6, "Nxy": 1e6}, material=im7, method="exhaustive")
    assert not r.feasible and r.status == "infeasible"
    assert any("INFEASIBLE" in w for w in r.warnings)
    assert r.margin < 1.5 and r.n_plies <= 64


def test_api_result_structure(im7):
    r = optimize({"Nx": -1e4, "Ny": 0, "Nxy": 5e3}, material=im7, method="ga", seed=0, budget=1500,
                 buckling_model="closed_form")
    assert all(r.rules_check.values())
    assert set(r.rf) == {"max_stress", "tsai_wu", "buckling"}
    assert r.margin == pytest.approx(min(r.rf.values()))
    assert any("Nxy is not part" in w for w in r.warnings)
    with pytest.raises(ValueError):
        optimize({"Nx": 1.0, "Mx": 1.0})


def test_non_symmetric_rules_run(im7):
    r = optimize({"Nx": 5e5, "Ny": 0, "Nxy": 0}, material=im7, method="ga", seed=0, budget=1500,
                 rules=Rules(symmetric=False, n_min=8, n_max=24))
    assert all(r.rules_check.values())


def test_memetic_ga_local_search(im7):
    """GA + local search: finds the exhaustive optimum, designs always satisfy the rules, budget respected."""
    p = Problem(loads=(-1e4, -5e3, 0), material=im7)
    ex = exhaustive(p)
    target = (ex["best"]["n"], ex["best"]["max_margin"])
    hits = 0
    for seed in range(3):
        r = GeneticAlgorithm(p, GAConfig(budget=4000, local_search=True), seed).run(target=target)
        hits += r["hit_evals"] is not None
        assert satisfies(full_laminate(PLY.decode(r["best_genes"][None]), True)[0], p.rules)
        assert r["n_evaluations"] < 4000 + 1000   # may overshoot by at most one neighbourhood / generation
    assert hits == 3


def test_local_search_never_worsens(im7, rng):
    """The local search returns a design at least as good as its start (min plies ordering)."""
    from optimization.evaluate import better
    p = Problem(loads=(1.0e6, 0.5e6, 0), material=im7)
    ga = GeneticAlgorithm(p, GAConfig(budget=100000, local_search=True), 0)
    for _ in range(5):
        g = ga.repairer.random_valid(rng)
        r0 = ga.ev.evaluate(g[None])
        key0 = (int(r0["n_plies"][0]), float(r0["margin"][0]))
        g2, key2 = ga._local_search(g, key0)
        assert key2 == key0 or better(key2, key0, p.safety_factor)


def test_nsga2_keeps_the_optimum_in_the_final_population(im7):
    """Regression: with pymoo's default crowding (objective-space duplicates not filtered) the optimum of this case
    was found and then lost (seed 0 ended at 22 plies). The final answer must be the exact optimum."""
    p = Problem(loads=(1.0e6, 0.5e6, 0.0), material=im7)
    ex = strength_only_exact(p)
    r = run_nsga2(p, seed=0, budget=10000)
    assert r["n_plies"] == ex["best"]["n"]
    assert r["margin"] == pytest.approx(ex["best"]["max_margin"], rel=1e-9)
    assert len(r["pareto"]) == len(set(range(8, 66, 2)))  # one non-dominated point per ply count 8..64
