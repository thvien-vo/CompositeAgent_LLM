"""Python CLT vs MATLAB clt_engine.m. Skipped (with the reason) when the MATLAB engine cannot start: the probe runs
in a child process with a time-out, because a hanging `import matlab.engine` cannot be interrupted in-process."""
import pytest

from optimization import matlab_check

if not matlab_check.available(timeout=90):
    pytest.skip("MATLAB engine could not start within 90 s (probe in a child process)", allow_module_level=True)


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


@pytest.mark.matlab
def test_both_shear_directions_rechecked_in_matlab(im7):
    from optimization import optimize
    from optimization.rules import Rules
    res = optimize({"Nx": 0, "Ny": 0, "Nxy": 4e4}, material=im7, method="exhaustive", rules=Rules(n_max=32),
                   shear_both_signs=True, verify_matlab=True)
    assert res.matlab["pass"] and set(res.matlab["clt"]["by_shear_sign"]) == {"+", "-"}
    assert res.matlab["margin_matlab"] == pytest.approx(res.margin, rel=1e-9)
