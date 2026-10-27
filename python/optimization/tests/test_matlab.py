"""Python CLT vs MATLAB clt_engine.m (skipped when the MATLAB engine is not installed)."""
import numpy as np
import pytest

matlab = pytest.importorskip("matlab.engine")

from optimization import matlab_check  # noqa: E402


@pytest.mark.matlab
def test_python_matches_matlab_on_random_laminates(im7, rng):
    for _ in range(8):
        n = int(rng.integers(1, 16))
        ang = rng.uniform(-90, 90, n)
        t = rng.uniform(0.1e-3, 0.3e-3, n)
        loads = {"Nx": 1e5, "Ny": -3e4, "Nxy": 2e4, "Mx": 1.0, "My": -0.5, "Mxy": 0.2}
        r = matlab_check.compare(ang, t, im7, loads)
        assert r["pass"], r


@pytest.mark.matlab
def test_optimised_design_rechecked_in_matlab(im7):
    from optimization import optimize
    res = optimize({"Nx": -1e4, "Ny": -5e3, "Nxy": 0}, material=im7, method="exhaustive", verify_matlab=True)
    assert res.matlab["pass"]
    assert res.matlab["margin_matlab"] == pytest.approx(res.margin, rel=1e-9)
