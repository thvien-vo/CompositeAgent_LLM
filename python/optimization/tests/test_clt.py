import numpy as np
import pytest

from optimization import clt
from optimization.evaluate import Evaluator, Problem
from optimization.rules import PLY, Repairer, Rules, full_laminate


def test_cosd_sind_exact_at_multiples_of_90():
    x = np.array([0, 90, 180, 270, -90, 360, 450])
    assert np.array_equal(clt.cosd(x), [1, 0, -1, 0, 0, 1, 0])
    assert np.array_equal(clt.sind(x), [0, 1, 0, -1, -1, 0, 1])
    y = np.linspace(-400, 400, 81) + 0.37
    assert np.allclose(clt.cosd(y), np.cos(np.deg2rad(y)), atol=1e-15)
    assert np.allclose(clt.sind(y), np.sin(np.deg2rad(y)), atol=1e-15)


def test_qbar_zero_and_ninety(im7):
    Q = clt.q_matrix(im7.E1, im7.E2, im7.G12, im7.nu12)
    assert np.allclose(clt.qbar(Q, 0.0), Q)
    Q90 = clt.qbar(Q, 90.0)
    assert Q90[0, 0] == pytest.approx(Q[1, 1]) and Q90[1, 1] == pytest.approx(Q[0, 0])
    assert Q90[0, 2] == 0.0 and Q90[1, 2] == 0.0     # exact thanks to cosd / sind


def test_qbar_invariants(im7, rng):
    """U1 = (3Q11 + 3Q22 + 2Q12 + 4Q66)/8 = (3Qb11 + 3Qb22 + 2Qb12 + 4Qb66)/8 for any angle (Tsai-Pagano)."""
    Q = clt.q_matrix(im7.E1, im7.E2, im7.G12, im7.nu12)
    U1 = (3 * Q[0, 0] + 3 * Q[1, 1] + 2 * Q[0, 1] + 4 * Q[2, 2]) / 8
    for th in rng.uniform(-90, 90, 20):
        Qb = clt.qbar(Q, th)
        assert (3 * Qb[0, 0] + 3 * Qb[1, 1] + 2 * Qb[0, 1] + 4 * Qb[2, 2]) / 8 == pytest.approx(U1, rel=1e-13)
        assert np.allclose(Qb, Qb.T)


def test_unidirectional_laminate_hand_calculation(im7):
    """[0]_8 under Nx: sigma1 = Nx / h, sigma2 = tau12 = 0."""
    t, Nx = 0.125e-3, 1.0e5
    r = clt.analyze([0] * 8, t, im7, Nx=Nx)
    assert np.allclose(r["ply_stress"][:, 0], Nx / (8 * t), rtol=1e-12)
    assert np.allclose(r["ply_stress"][:, 1:], 0.0, atol=1e-6)
    assert np.allclose(r["B"], 0.0, atol=1e-6 * np.abs(r["A"]).max() * 8 * t)


def test_demo_reference_numbers(cfrp_ml):
    """Same numbers as demo.py / MATLAB: max FI ~ 0.00238, critical ply 4, ABD(1,1) ~ 5.94e7 N/m."""
    r = clt.analyze([0, 45, -45, 90, 90, -45, 45, 0], 0.000125, cfrp_ml, 1000, 500, 100)
    assert abs(r["max_failure_index"] - 0.00238) < 5e-6
    assert r["critical_ply"] == 4
    assert abs(r["ABD"][0, 0] - 5.94e7) / 5.94e7 < 1e-3


def test_unsymmetric_laminate_has_coupling(im7):
    r = clt.analyze([0, 90], 0.125e-3, im7, Nx=1e4)
    assert np.abs(r["B"]).max() > 1.0
    assert np.abs(r["kappa"]).max() > 0.0


def test_fast_symmetric_path_equals_general_path(im7, rng):
    """The symmetric fast path (A from counts, D from position weights) = general CLT path."""
    for loads in [(1.5e6, 0, 0), (-1e4, -5e3, 2e3), (3e5, -2e5, 4e5)]:
        p = Problem(loads=loads, material=im7)
        rep = Repairer(PLY, p.rules)
        G = np.array([rep.random_valid(rng) for _ in range(60)])
        fast = Evaluator(p).evaluate(G)["margin"]
        full = full_laminate(PLY.decode(G), True)
        p2 = Problem(loads=loads, material=im7, rules=Rules(symmetric=False))
        padded = np.array([np.concatenate([np.full(64 - len(f), -1), f]) for f in full])
        general = Evaluator(p2).compute_plies(padded)["margin"]
        assert np.allclose(fast, general, rtol=1e-12)
