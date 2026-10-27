import numpy as np
import pytest

from optimization import failure


def _s(s1=0.0, s2=0.0, t=0.0):
    return np.array([s1, s2, t], dtype=float)


def test_max_stress_rf_each_mode(im7):
    assert failure.rf_max_stress(_s(s1=im7.Xt / 2), im7) == pytest.approx(2.0)
    assert failure.rf_max_stress(_s(s1=-im7.Xc / 4), im7) == pytest.approx(4.0)
    assert failure.rf_max_stress(_s(s2=im7.Yt), im7) == pytest.approx(1.0)
    assert failure.rf_max_stress(_s(s2=-im7.Yc / 2), im7) == pytest.approx(2.0)
    assert failure.rf_max_stress(_s(t=-im7.S / 3), im7) == pytest.approx(3.0)
    assert failure.rf_max_stress(_s(), im7) == np.inf


def test_max_stress_is_one_over_matlab_failure_index(im7, rng):
    from optimization.clt import max_stress_index
    st = rng.normal(size=(50, 3)) * np.array([1e9, 5e7, 5e7])
    assert np.allclose(failure.rf_max_stress(st, im7), 1.0 / max_stress_index(st, im7), rtol=1e-14)


@pytest.mark.parametrize("stress", ["Xt", "-Xc", "Yt", "-Yc", "S"])
def test_tsai_wu_reaches_one_at_uniaxial_strengths(im7, stress):
    v = {"Xt": _s(s1=im7.Xt), "-Xc": _s(s1=-im7.Xc), "Yt": _s(s2=im7.Yt), "-Yc": _s(s2=-im7.Yc),
         "S": _s(t=im7.S)}[stress]
    assert failure.rf_tsai_wu(v, im7) == pytest.approx(1.0, rel=1e-12)


def test_tsai_wu_root_satisfies_criterion_and_scaling(im7, rng):
    F1, F2, F11, F22, F66, F12 = failure.tsai_wu_coefficients(im7, -0.5)
    st = rng.normal(size=(200, 3)) * np.array([8e8, 4e7, 4e7])
    rf = failure.rf_tsai_wu(st, im7)
    s = st * rf[:, None]
    val = F1 * s[:, 0] + F2 * s[:, 1] + F11 * s[:, 0] ** 2 + F22 * s[:, 1] ** 2 + F66 * s[:, 2] ** 2 \
        + 2 * F12 * s[:, 0] * s[:, 1]
    assert np.allclose(val, 1.0, rtol=1e-10)
    assert np.all(rf > 0)
    assert np.allclose(failure.rf_tsai_wu(3.0 * st, im7), rf / 3.0, rtol=1e-12)


def test_tsai_wu_f12_star_changes_biaxial_only(im7):
    uni = _s(s1=1e9)
    assert failure.rf_tsai_wu(uni, im7, -0.5) == pytest.approx(failure.rf_tsai_wu(uni, im7, 0.0))
    bi = _s(s1=1e9, s2=3e7)
    assert failure.rf_tsai_wu(bi, im7, -0.5) != pytest.approx(failure.rf_tsai_wu(bi, im7, 0.0))
    with pytest.raises(ValueError):
        failure.rf_tsai_wu(bi, im7, -1.0)


def test_max_strain():
    allow = (0.008, 0.029, 0.015)
    assert failure.rf_max_strain(np.array([0.004, 0.0, 0.0]), allow) == pytest.approx(2.0)
    assert failure.rf_max_strain(np.array([0.0, -0.029, 0.0]), allow) == pytest.approx(1.0)
    assert failure.rf_max_strain(np.array([0.0, 0.0, 0.005]), allow) == pytest.approx(3.0)
