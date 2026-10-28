"""
Experiment 0 - checks of the buckling model used in the optimisation (Rayleigh-Ritz with D16, D26, Nxy), run
BEFORE it is used (same checks as tests/test_buckling_full.py, with the numbers written to results/):
  1. pure compression, specially orthotropic plates (D16 = D26 = 0): Ritz vs the closed form of the previous version
     (required: < 0.5 %);
  2. isotropic square plate in pure shear: k_s vs 9.34 (Stein & Neff 1947; Timoshenko & Gere 1961) (required <= 1 %);
  3. long isotropic plates in pure shear: k_s vs 5.35 (Southwell & Skan 1924; Timoshenko & Gere 1961) (<= 2 %);
  4. convergence: number of terms increased until the load factor changes by < 0.5 %;
  5. composite laminates with D16, D26 (IM7/8552): sine series vs an independent Ritz solution with Legendre
     polynomials and Gauss quadrature, and the effect of the sign of Nxy.
k_s is defined by N_cr = k_s pi^2 D / b^2 (D = bending stiffness of the isotropic plate, b = short side).
Run: python -m optimization.experiments.verify_buckling   -> results/buckling_verification.json / .csv
"""
from __future__ import annotations

import numpy as np

from optimization import buckling, clt
from optimization.experiments.cases import MATERIAL
from optimization.experiments.common import Timer, setup, write_csv, write_json
from optimization.material import get_material

PI2 = np.pi ** 2
KS_SQUARE, KS_LONG = 9.34, 5.35


def _iso(nu=0.3):
    return np.array([[1.0, nu, 0.0], [nu, 1.0, 0.0], [0.0, 0.0, (1 - nu) / 2]])


def main():
    setup()
    T = Timer()
    out, rows = {}, []
    rng = np.random.default_rng(2026)
    mat = get_material(MATERIAL, verbose=False)
    Q = clt.q_matrix(mat.E1, mat.E2, mat.G12, mat.nu12)
    ang = {0: 0.0, 1: 45.0, 2: -45.0, 3: 90.0}

    def lam_D(half, t=0.125e-3):
        full = list(half) + list(half[::-1])
        return clt.abd_matrices(np.array([ang[x] for x in full]), np.full(len(full), t), Q)[2]

    # 1) compression, D16 = D26 = 0 -----------------------------------------------------------------------
    errs = []
    for i in range(200):
        D = np.diag(rng.uniform(1, 20, 3))
        D[0, 1] = D[1, 0] = rng.uniform(0.0, 0.5) * min(D[0, 0], D[1, 1])
        Nx, Ny = -rng.uniform(0.1, 1.0), -rng.uniform(0.0, 1.0) if i % 2 else 0.0
        a, b = rng.uniform(0.3, 1.0), rng.uniform(0.3, 1.0)
        cf, m, n, _ = buckling.closed_form([D[0, 0]], [D[0, 1]], [D[1, 1]], [D[2, 2]], Nx, Ny, a, b)
        rz = buckling.ritz_full(D, Nx, Ny, 0.0, a, b, *buckling.terms_for(12, a, b))[0]
        errs.append(abs(rz - cf[0]) / cf[0])
    for name, half in (("[0/90]2s", [0, 3, 0, 3]), ("[0_2/90_2]s", [0, 0, 3, 3]), ("[90/0_2/90]s", [3, 0, 0, 3])):
        D = lam_D(half)
        for Nx, Ny in ((-1e4, 0.0), (-1e4, -5e3)):
            cf = buckling.closed_form([D[0, 0]], [D[0, 1]], [D[1, 1]], [D[2, 2]], Nx, Ny, 0.5, 0.5)[0][0]
            rz = buckling.ritz_full(D, Nx, Ny, 0.0, 0.5, 0.5, 12, 12)[0]
            errs.append(abs(rz - cf) / cf)
            rows.append({"check": "compression vs closed form", "case": f"{name} Nx={Nx:g} Ny={Ny:g}",
                         "value": rz, "reference": cf, "rel_error": abs(rz - cf) / cf, "required": "< 0.5 %"})
    out["compression_vs_closed_form"] = {"n_cases": len(errs), "max_rel_error": float(max(errs)),
                                         "pass": bool(max(errs) < 0.005)}

    # 2) square plate, pure shear -------------------------------------------------------------------------
    c = buckling.converge(_iso(), 0.0, 0.0, 1.0, 1.0, 1.0, start=6, step=2, tol=0.005)
    ks = c["lambda"] / PI2
    poly = buckling.ritz_polynomial(_iso(), 0.0, 0.0, 1.0, 1.0, 1.0, p=16) / PI2
    out["square_shear"] = {"k_s": ks, "terms": (c["M"], c["N"]), "sequence": [(M, N, l / PI2) for M, N, l in c["terms"]],
                           "last_change": c["last_change"], "k_s_polynomial_p16": poly, "reference": KS_SQUARE,
                           "rel_error": abs(ks - KS_SQUARE) / KS_SQUARE, "pass": abs(ks - KS_SQUARE) / KS_SQUARE <= 0.01}
    rows.append({"check": "square isotropic plate, pure shear (k_s)", "case": f"{c['M']}x{c['N']} terms",
                 "value": ks, "reference": KS_SQUARE, "rel_error": abs(ks - KS_SQUARE) / KS_SQUARE, "required": "<= 1 %"})
    # 3) long plates, pure shear --------------------------------------------------------------------------
    out["long_shear"] = []
    for ar in (5.0, 10.0, 20.0):
        c = buckling.converge(_iso(), 0.0, 0.0, 1.0, ar, 1.0, start=4, step=2, tol=0.005, max_terms=12)
        ks = c["lambda"] / PI2
        # a/b = 5 is not yet a "very long" plate: compare it with Timoshenko & Gere's 5.35 + 4 (b/a)^2 (information);
        # the very-long-plate check (-> 5.35, <= 2 %) is made for a/b = 10 and 20
        very_long = ar >= 10
        ref = KS_LONG if very_long else 5.35 + 4 / ar ** 2
        rec = {"a_over_b": ar, "k_s": ks, "terms": (c["M"], c["N"]), "converged": c["converged"],
               "sequence": [(M, N, l / PI2) for M, N, l in c["terms"]], "timoshenko_5.35+4(b/a)^2": 5.35 + 4 / ar ** 2,
               "reference": ref, "reference_name": "5.35" if very_long else "5.35 + 4 (b/a)^2",
               "rel_error": abs(ks - ref) / ref, "rel_error_vs_5.35": abs(ks - KS_LONG) / KS_LONG,
               "very_long_check": very_long}
        rec["pass"] = rec["rel_error"] <= 0.02
        out["long_shear"].append(rec)
        rows.append({"check": f"long isotropic plate a/b = {ar:g}, pure shear (k_s)", "case": f"{c['M']}x{c['N']} terms",
                     "value": ks, "reference": ref, "rel_error": rec["rel_error"],
                     "required": "<= 2 % vs 5.35" if very_long else "information: vs 5.35 + 4 (b/a)^2"})
    # 5) composite laminates with D16, D26 ----------------------------------------------------------------
    out["composite"] = []
    for name, half, loads in [("[90/-45/45/0/-45/45]s", [3, 2, 1, 0, 2, 1], (0, 0, 3e5)),
                              ("[(45/-45)4/0/90]s", [1, 2, 1, 2, 1, 2, 1, 2, 0, 3], (-1e4, 0, 5e3)),
                              ("[45_2/-45_2/45_2/-45_2/0/90]s", [1, 1, 2, 2, 1, 1, 2, 2, 0, 3], (0, 0, 3e5)),
                              ("[45/-45/0/90/45/-45]s", [1, 2, 0, 3, 1, 2], (-1e4, -5e3, 0))]:
        D = lam_D(half)
        c = buckling.converge(D, *loads, 0.5, 0.5, start=6, step=2, tol=0.005)
        poly = buckling.ritz_polynomial(D, *loads, 0.5, 0.5, p=16)
        neg = buckling.ritz_full(D, loads[0], loads[1], -loads[2], 0.5, 0.5, c["M"], c["N"])[0]
        no16 = buckling.ritz(D[0, 0], D[0, 1], D[1, 1], D[2, 2], *loads, 0.5, 0.5, c["M"], c["N"])[0]
        rec = {"laminate": name, "loads": loads, "D16_over_D11": D[0, 2] / D[0, 0], "D26_over_D22": D[1, 2] / D[1, 1],
               "lambda_sine": c["lambda"], "terms": (c["M"], c["N"]), "last_change": c["last_change"],
               "sequence": c["terms"], "lambda_polynomial_p16": poly,
               "sine_vs_polynomial": (c["lambda"] - poly) / poly, "lambda_opposite_shear": neg,
               "lambda_without_D16_D26": no16}
        out["composite"].append(rec)
        rows.append({"check": f"IM7/8552 {name}, loads {loads}: sine series vs Legendre polynomials",
                     "case": f"{c['M']}x{c['N']} terms vs p = 16", "value": c["lambda"], "reference": poly,
                     "rel_error": abs(c["lambda"] - poly) / poly, "required": "< 1 % (check)"})
    # 6) published composite result: Nemeth (1992), NASA TP-3195, long simply supported [(+-45)_m]s graphite-epoxy
    #    plates in shear (E1 = 18.5 Msi, E2 = 1.6 Msi, G12 = 0.832 Msi, nu12 = 0.35, t = 0.005 in; p. 4). The text
    #    (pp. 7-8) gives the difference between the anisotropic and the specially orthotropic solutions: about 48 %
    #    for m = 1, 7 % for m = 6 and 3.5 % for m = 12; positive shear lower ("from below"), negative higher; and
    #    gamma = delta = 0.52 for [+-45]s (p. 6). Infinitely long plate approximated by a/b = 10.
    psi = 6894.757293168
    Qn = clt.q_matrix(18.5e6 * psi, 1.6e6 * psi, 0.832e6 * psi, 0.35)
    quoted = {1: 0.48, 6: 0.07, 12: 0.035}
    out["nemeth_1992"] = []
    for m_ in (1, 6, 12):
        half = [45.0, -45.0] * m_
        full = half + half[::-1]
        D = clt.abd_matrices(np.array(full), np.full(len(full), 0.005 * 0.0254), Qn)[2]
        Do = D.copy()
        Do[0, 2] = Do[2, 0] = Do[1, 2] = Do[2, 1] = 0.0
        M, N = buckling.terms_for(8, 10.0, 1.0)
        lp, ln, lo = (buckling.ritz_full(X, 0, 0, s, 10.0, 1.0, M, N)[0] for X, s in ((D, 1.0), (D, -1.0), (Do, 1.0)))
        rec = {"laminate": f"[(+-45)_{m_}]s", "gamma": D[0, 2] / (D[0, 0] ** 3 * D[1, 1]) ** 0.25,
               "terms": (M, N), "diff_positive_shear": (lp - lo) / lo, "diff_negative_shear": (ln - lo) / lo,
               "quoted_difference": quoted[m_]}
        out["nemeth_1992"].append(rec)
        rows.append({"check": f"Nemeth 1992 (NASA TP-3195) long SS [(+-45)_{m_}]s, shear: anisotropic vs orthotropic",
                     "case": f"{M}x{N}, a/b = 10", "value": max(abs(rec["diff_positive_shear"]),
                                                              abs(rec["diff_negative_shear"])),
                     "reference": quoted[m_], "rel_error": abs(max(abs(rec["diff_positive_shear"]),
                                                                   abs(rec["diff_negative_shear"])) - quoted[m_]),
                     "required": "comparison (values quoted as 'approximately' in the text)"})
    out["all_pass"] = bool(out["compression_vs_closed_form"]["pass"] and out["square_shear"]["pass"]
                           and all(r["pass"] for r in out["long_shear"] if r["very_long_check"])
                           and all(abs(r["sine_vs_polynomial"]) < 0.01 for r in out["composite"]))
    out["time_s"] = T()
    write_json("buckling_verification.json", out)
    write_csv("buckling_verification.csv", rows)
    for r in rows:
        print(f"{r['check']:75s} {r['case']:22s} {r['value']:.6g} vs {r['reference']:.6g}  "
              f"{100 * r['rel_error']:.3f} % ({r['required']})")
    print("ALL PASS" if out["all_pass"] else "SOME CHECKS FAILED")
    return out


if __name__ == "__main__":
    main()
