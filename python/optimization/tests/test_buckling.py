import numpy as np
import pytest

from optimization import buckling

PI2 = np.pi ** 2


def _iso(D=1.0, nu=0.3):
    return np.array([D]), np.array([nu * D]), np.array([D]), np.array([(1 - nu) / 2 * D])


def test_isotropic_square_uniaxial_k4():
    lam, m, n, _ = buckling.closed_form(*_iso(), -1.0, 0.0, 1.0, 1.0)
    assert lam[0] == pytest.approx(4 * PI2) and (m[0], n[0]) == (1, 1)


def test_isotropic_long_plate_mode_number():
    """a/b = 3.0: k = 4 with m = 3 half-waves (classical result)."""
    lam, m, n, _ = buckling.closed_form(*_iso(), -1.0, 0.0, 3.0, 1.0)
    assert lam[0] == pytest.approx(4 * PI2) and m[0] == 3 and n[0] == 1


def test_isotropic_square_equal_biaxial():
    lam, *_ = buckling.closed_form(*_iso(), -1.0, -1.0, 1.0, 1.0)
    assert lam[0] == pytest.approx(2 * PI2)


def test_no_compression_no_buckling():
    lam, *_ = buckling.closed_form(*_iso(), 1.0, 2.0, 1.0, 1.0)
    assert np.isinf(lam[0])


def test_proven_mode_scan_matches_brute_force(rng):
    """Random orthotropic D and load ratios (incl. transverse tension): the bounded scan = 60 x 60 brute force."""
    for _ in range(200):
        D11, D22 = rng.uniform(1, 50, 2)
        D12, D66 = rng.uniform(0.1, 5), rng.uniform(0.1, 5)
        a, b = rng.uniform(0.2, 2.0), rng.uniform(0.2, 2.0)
        Nx, Ny = rng.choice([-1, 1]) * rng.uniform(0, 1), rng.choice([-1, 1]) * rng.uniform(0, 1)
        if Nx >= 0 and Ny >= 0:
            Nx = -abs(Nx) - 0.01
        lam, *_ = buckling.closed_form([D11], [D12], [D22], [D66], Nx, Ny, a, b)
        ref, *_ = buckling.closed_form([D11], [D12], [D22], [D66], Nx, Ny, a, b, max_modes=(60, 60))
        assert lam[0] <= ref[0] * (1 + 1e-12)
        assert lam[0] == pytest.approx(ref[0], rel=1e-12)


def test_ritz_equals_closed_form_without_shear(rng):
    for _ in range(20):
        D = [np.array([v]) for v in (rng.uniform(5, 20), rng.uniform(0.5, 2), rng.uniform(1, 5), rng.uniform(0.5, 3))]
        Nx, Ny = -1.0, rng.uniform(-1, 0.5)
        cf, *_ = buckling.closed_form(*D, Nx, Ny, 1.5, 1.0)
        rz = buckling.ritz(*D, Nx, Ny, 0.0, 1.5, 1.0, 12, 12)
        assert rz[0] == pytest.approx(cf[0], rel=1e-12)


def test_ritz_shear_isotropic_square_converges_near_published():
    """Pure shear, SS square plate: k_s = 9.34 (Stein & Neff 1947; Timoshenko & Gere 1961, sec. 9.7).
    Ritz values decrease with more terms (upper bounds) and converge to 9.3245, i.e. 0.17 % below the
    rounded published value, consistent with the published value coming from a coarser approximation."""
    ks = [buckling.ritz(*_iso(), 0, 0, 1.0, 1.0, 1.0, M, M)[0] / PI2 for M in (6, 10, 16, 24)]
    assert all(x >= y - 1e-12 for x, y in zip(ks, ks[1:]))
    assert ks[-1] == pytest.approx(9.34, rel=2.5e-3)
    assert abs(ks[-1] - ks[-2]) / ks[-1] < 1e-4


def test_ritz_shear_sign_symmetric_for_orthotropic():
    D = [np.array([v]) for v in (10.0, 1.0, 3.0, 1.5)]
    assert buckling.ritz(*D, 0, 0, 1.0, 1.2, 1.0)[0] == pytest.approx(buckling.ritz(*D, 0, 0, -1.0, 1.2, 1.0)[0])


def test_ritz_compression_shear_interaction_lowers_load():
    D = list(_iso())
    pure_c = buckling.ritz(*D, -1.0, 0.0, 0.0, 1.0, 1.0)[0]
    comb = buckling.ritz(*D, -1.0, 0.0, 0.5, 1.0, 1.0)[0]
    assert comb < pure_c
