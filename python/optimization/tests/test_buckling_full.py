"""Tests of the buckling model used in the optimisation: Rayleigh-Ritz with D16, D26 and Nxy (buckling.RitzModel),
its proven bounds and the exact search built on them (exhaustive.exact_full).

Reference values (k_s defined by N_cr = k_s pi^2 D / b^2, D = bending stiffness of the isotropic plate, b = short
side):
  * square isotropic plate in pure shear, simply supported: k_s = 9.34 (Stein & Neff 1947, NACA TN 1222;
    Timoshenko & Gere 1961, Theory of Elastic Stability, sec. 9.7);
  * very long plate: k_s -> 5.35 (Southwell & Skan 1924, Proc. R. Soc. London A 105; Timoshenko & Gere 1961,
    k_s = 5.35 + 4 (b/a)^2 for long plates).
"""
import itertools

import numpy as np
import pytest

from optimization import buckling, clt
from optimization.api import make_problem
from optimization.evaluate import Evaluator, Plate, Problem
from optimization.exhaustive import _FullBounds, _tuple_data, exact_full
from optimization.rules import Rules, full_laminate

PI2 = np.pi ** 2


def _iso_D(D=1.0, nu=0.3):
    return np.array([[D, nu * D, 0.0], [nu * D, D, 0.0], [0.0, 0.0, (1 - nu) / 2 * D]])


def _laminate_D(im7, half, t=0.125e-3):
    ang = {0: 0.0, 1: 45.0, 2: -45.0, 3: 90.0}
    full = list(half) + list(half[::-1])
    Q = clt.q_matrix(im7.E1, im7.E2, im7.G12, im7.nu12)
    return clt.abd_matrices(np.array([ang[x] for x in full]), np.full(len(full), t), Q)[2]


def test_full_ritz_equals_previous_ritz_when_D16_D26_are_zero(rng):
    for _ in range(30):
        D = np.diag(rng.uniform(1, 10, 3))
        D[0, 1] = D[1, 0] = rng.uniform(0, 2)
        Nx, Ny, Nxy = rng.uniform(-1, 1, 3) * 1e3
        a, b = rng.uniform(0.3, 1.0, 2)
        old = buckling.ritz([D[0, 0]], [D[0, 1]], [D[1, 1]], [D[2, 2]], Nx, Ny, Nxy, a, b, 10, 10)[0]
        new = buckling.ritz_full(D, Nx, Ny, Nxy, a, b, 10, 10)[0]
        assert (np.isinf(old) and np.isinf(new)) or new == pytest.approx(old, rel=1e-10)


def test_compression_orthotropic_matches_closed_form(rng, im7):
    """No shear, D16 = D26 = 0: the Ritz factor equals the closed form of the previous version (< 0.5 %)."""
    cases = [np.diag(rng.uniform(1, 20, 3)) + np.diag([0, 0, 0]) for _ in range(20)]
    cases += [_laminate_D(im7, h) for h in ([0, 3, 0, 3], [0, 0, 3, 3, 0], [3, 0, 3, 3, 0, 0])]   # cross-ply
    for D in cases:
        D = D.copy()
        D[0, 1] = D[1, 0] = D[0, 1] if D[0, 1] else 0.3 * min(D[0, 0], D[1, 1])
        assert D[0, 2] == 0 and D[1, 2] == 0
        Nx, Ny = -rng.uniform(0.1, 1.0), -rng.uniform(0.0, 1.0)
        a, b = rng.uniform(0.3, 1.0), rng.uniform(0.3, 1.0)
        cf = buckling.closed_form([D[0, 0]], [D[0, 1]], [D[1, 1]], [D[2, 2]], Nx, Ny, a, b)
        M, N = buckling.terms_for(12, a, b)
        rz = buckling.ritz_full(D, Nx, Ny, 0.0, a, b, M, N)[0]
        assert cf[1][0] <= M and cf[2][0] <= N
        assert abs(rz - cf[0][0]) / cf[0][0] < 0.005


def test_isotropic_square_plate_pure_shear_ks():
    c = buckling.converge(_iso_D(), 0.0, 0.0, 1.0, 1.0, 1.0, start=6, step=2, tol=0.005)
    ks = c["lambda"] / PI2
    assert c["converged"] and c["last_change"] < 0.005
    assert abs(ks - 9.34) / 9.34 <= 0.01
    seq = [x[2] for x in c["terms"]]
    assert all(seq[i + 1] <= seq[i] * (1 + 1e-12) for i in range(len(seq) - 1))   # upper bound, from above


def test_isotropic_long_plate_pure_shear_ks():
    c = buckling.converge(_iso_D(), 0.0, 0.0, 1.0, 10.0, 1.0, start=4, step=2, tol=0.005)
    ks = c["lambda"] / PI2
    assert c["converged"]
    assert abs(ks - 5.35) / 5.35 <= 0.02


def test_independent_polynomial_ritz_agrees(im7):
    """Sine series (closed-form integrals) vs Legendre polynomials (Gauss quadrature), laminates with D16, D26."""
    for half, loads in [([3, 2, 1, 0, 2, 1], (0, 0, 3e5)), ([1, 2, 1, 2, 1, 2, 1, 2, 0, 3], (-1e4, 0, 5e3)),
                        ([1, 1, 2, 2, 1, 1, 2, 2, 0, 3], (0, 0, -3e5)), ([1, 2, 0, 3, 1, 2], (-1e4, -5e3, 0))]:
        D = _laminate_D(im7, half)
        assert abs(D[0, 2]) > 0.05 * D[0, 0] or abs(D[1, 2]) > 0.05 * D[1, 1] or half == [1, 2, 0, 3, 1, 2]
        sine = buckling.converge(D, *loads, 0.5, 0.5, start=6, step=2, tol=0.005)["lambda"]
        poly = buckling.ritz_polynomial(D, *loads, 0.5, 0.5, p=14)
        assert abs(sine - poly) / poly < 0.01


def test_basis_integrals_by_quadrature():
    """K16, K26 and the shear load matrix of RitzModel against Gauss quadrature of the energy integrands."""
    a, b, M, N = 0.7, 0.4, 4, 3
    m = buckling.RitzModel(a, b, 0.0, 0.0, 1.0, M, N)
    xg, wg = np.polynomial.legendre.leggauss(40)
    x, wx = (xg + 1) * a / 2, wg * a / 2
    y, wy = (xg + 1) * b / 2, wg * b / 2
    X, Y = np.meshgrid(x, y, indexing="ij")
    W = np.outer(wx, wy)
    for blk in m.blocks:
        modes = list(zip(blk["m"], blk["n"]))
        f = {}
        for i, (p, q) in enumerate(modes):
            al, be = p * np.pi / a, q * np.pi / b
            s, c = np.sin, np.cos
            f[i] = {"xx": -al ** 2 * s(al * X) * s(be * Y), "yy": -be ** 2 * s(al * X) * s(be * Y),
                    "xy": al * be * c(al * X) * c(be * Y), "x": al * c(al * X) * s(be * Y),
                    "y": be * s(al * X) * c(be * Y)}
        k = len(modes)
        K16 = np.array([[2 * np.sum(W * (f[i]["xx"] * f[j]["xy"] + f[i]["xy"] * f[j]["xx"])) for j in range(k)]
                        for i in range(k)])
        K26 = np.array([[2 * np.sum(W * (f[i]["yy"] * f[j]["xy"] + f[i]["xy"] * f[j]["yy"])) for j in range(k)]
                        for i in range(k)])
        G = np.array([[np.sum(W * (f[i]["x"] * f[j]["y"] + f[i]["y"] * f[j]["x"])) for j in range(k)]
                      for i in range(k)])
        scale = np.abs(K16).max()
        assert np.allclose(blk["K16"], K16, atol=1e-9 * scale)
        assert np.allclose(blk["K26"], K26, atol=1e-9 * np.abs(K26).max())
        assert np.allclose(-blk["mG"], G, atol=1e-9 * np.abs(G).max())


def test_shear_direction_matters_with_D16_and_mirror_symmetry(im7):
    D = _laminate_D(im7, [1, 1, 2, 2, 1, 1, 2, 2, 0, 3])
    pos = buckling.ritz_full(D, 0, 0, 3e5, 0.5, 0.5, 10, 10)[0]
    neg = buckling.ritz_full(D, 0, 0, -3e5, 0.5, 0.5, 10, 10)[0]
    assert abs(pos - neg) / min(pos, neg) > 0.1              # the sign of the load given is used
    Dm = D.copy()
    Dm[0, 2] = Dm[2, 0] = -D[0, 2]
    Dm[1, 2] = Dm[2, 1] = -D[1, 2]
    assert buckling.ritz_full(Dm, 0, 0, -3e5, 0.5, 0.5, 10, 10)[0] == pytest.approx(pos, rel=1e-10)   # y -> -y


def test_tension_stabilises_and_no_buckling_gives_inf(im7):
    D = _laminate_D(im7, [1, 2, 0, 3, 1, 2])
    shear = buckling.ritz_full(D, 0, 0, 1e4, 0.5, 0.5, 10, 10)[0]
    with_tension = buckling.ritz_full(D, 5e4, 0, 1e4, 0.5, 0.5, 10, 10)[0]
    assert with_tension > shear
    assert np.isinf(buckling.ritz_full(D, 5e4, 2e4, 0, 0.5, 0.5, 10, 10)[0])     # tension only
    assert np.isinf(buckling.ritz_full(D, 1e9, 1e9, 1e3, 0.5, 0.5, 10, 10)[0])   # tension >> shear: no mu > 0


def test_count_bound_is_an_upper_bound(im7, rng):
    p = make_problem((0, 0, 3e5), material=im7, ritz_terms=8)
    ev = Evaluator(p)
    L = 8
    fb, data = _tuple_data(p, ev, L)
    for d in data[:6]:
        ms = np.repeat(np.arange(4), d["counts"])
        for _ in range(40):
            arr = rng.permutation(ms)[None]
            lam = ev.ritz_model.lam(fb.dvec(arr))[0]
            assert lam <= d["lam_ub"] * (1 + 1e-9)
            qb = np.min(fb.dvec(arr) @ np.array(d["R"]).T)
            assert lam <= qb * (1 + 1e-9)


@pytest.mark.parametrize("loads", [(0, 0, 4e4), (-6e3, 0, 3e3), (-4e3, -2e3, 0)])
def test_exact_full_equals_brute_force(im7, loads):
    """Small ply range: exact_full = enumeration of every valid design with the same model."""
    p = make_problem(loads, material=im7, rules=Rules(n_min=8, n_max=16), ritz_terms=8)
    r = exact_full(p, time_limit=120)
    ev = Evaluator(p)
    ev.lazy = False
    from optimization.exhaustive import _valid_mask
    best = {}
    for L in range(4, 9):
        allp = np.array(list(itertools.product(range(4), repeat=L)), dtype=np.int8)
        allp = allp[_valid_mask(p, allp)]
        if len(allp):
            best[2 * L] = float(ev.compute_plies(allp)["margin"].max())
    for rec in r["per_n"]:
        if rec.get("max_margin") is not None:
            assert rec["max_margin"] == pytest.approx(best[rec["n"]], rel=1e-9)
    feas = [n for n in sorted(best) if best[n] >= 1.5]
    if feas:
        assert r["status"] == "optimal" and r["best"]["n"] == feas[0]
    else:
        assert r["status"] == "infeasible"


def test_lazy_buckling_and_cache(im7):
    p = make_problem((2e5, 0, 3e5), material=im7, ritz_terms=8)
    ev = Evaluator(p)
    assert ev.lazy
    half = np.array([[1, 2, 0, 3, 1, 2], [0, 0, 0, 0, 1, 2], [1, 2, 0, 3, 1, 2]], dtype=np.int8)
    res = ev.compute_plies(half)
    strength = make_problem((2e5, 0, 3e5), material=im7, criteria=("max_stress", "tsai_wu"))
    rs = Evaluator(strength).compute_plies(half)["margin"]
    for i in range(3):
        if rs[i] < 1.5:
            assert np.isinf(res["rf"][i, 2]) and res["margin"][i] == pytest.approx(rs[i])
        else:
            assert np.isfinite(res["rf"][i, 2])
    n0 = ev.ritz_model.n_solved
    ev.compute_plies(half)
    assert ev.ritz_model.n_solved == n0            # identical D -> from the cache
