"""
failure.py - reserve factors (RF) of plies under in-plane loads.

RF = factor by which ALL loads can be multiplied before the criterion is reached (RF >= 1: no failure at the
applied load; RF = inf: unloaded). Stresses/strains are linear in the load, so:

  Max Stress  RF = 1 / FI,   FI = max(s1/Xt | -s1/Xc, s2/Yt | -s2/Yc, |t12|/S)       (same FI as clt_engine.m)
  Max Strain  RF = min(e1u/|e1|, e2u/|e2|, g12u/|g12|)  (symmetric allowables, as in Le Riche & Haftka)
  Tsai-Wu     F1 s1 + F2 s2 + F11 s1^2 + F22 s2^2 + F66 t12^2 + 2 F12 s1 s2 = 1, stresses scaled by RF:
              a RF^2 + b RF - 1 = 0, a = quadratic part, b = linear part, RF = positive root.
              F1 = 1/Xt - 1/Xc, F2 = 1/Yt - 1/Yc, F11 = 1/(Xt Xc), F22 = 1/(Yt Yc), F66 = 1/S^2,
              F12 = F12* sqrt(F11 F22) with F12* = -0.5 by default (Tsai & Hahn 1980 recommendation).
              With |F12*| < 1 the quadratic part is positive definite, so a > 0 for any non-zero stress and
              there is exactly one positive root.
All functions broadcast over arrays; strengths are positive magnitudes (Xc, Yc > 0) in Pa.
"""
from __future__ import annotations

import numpy as np

CRITERIA = ("max_stress", "tsai_wu", "buckling")
MAX_STRESS_MODES = ("fibre (s1)", "transverse (s2)", "shear (t12)")


def _safe_inverse(x: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore"):
        return np.where(x > 0, 1.0 / np.where(x > 0, x, 1.0), np.inf)


def max_stress_ratios(stress12: np.ndarray, mat) -> np.ndarray:
    """The three Max-Stress ratios (..., 3): fibre, transverse, shear (FI = max of them)."""
    s1, s2, t12 = stress12[..., 0], stress12[..., 1], stress12[..., 2]
    r1 = np.where(s1 >= 0, s1 / mat.Xt, -s1 / mat.Xc)
    r2 = np.where(s2 >= 0, s2 / mat.Yt, -s2 / mat.Yc)
    r6 = np.abs(t12) / mat.S
    return np.stack([r1, r2, r6], axis=-1)


def rf_max_stress(stress12: np.ndarray, mat) -> np.ndarray:
    """Max-Stress reserve factor = 1 / failure index (inf if the ply is unstressed)."""
    return _safe_inverse(max_stress_ratios(stress12, mat).max(axis=-1))


def tsai_wu_coefficients(mat, f12_star: float = -0.5):
    F1 = 1.0 / mat.Xt - 1.0 / mat.Xc
    F2 = 1.0 / mat.Yt - 1.0 / mat.Yc
    F11 = 1.0 / (mat.Xt * mat.Xc)
    F22 = 1.0 / (mat.Yt * mat.Yc)
    F66 = 1.0 / mat.S ** 2
    F12 = f12_star * np.sqrt(F11 * F22)
    return F1, F2, F11, F22, F66, F12


def rf_tsai_wu(stress12: np.ndarray, mat, f12_star: float = -0.5) -> np.ndarray:
    """Tsai-Wu reserve factor: positive root of a RF^2 + b RF - 1 = 0 (numerically stable form)."""
    if not -1.0 < f12_star < 1.0:
        raise ValueError("F12* must be in (-1, 1) for a closed Tsai-Wu envelope")
    F1, F2, F11, F22, F66, F12 = tsai_wu_coefficients(mat, f12_star)
    s1, s2, t12 = stress12[..., 0], stress12[..., 1], stress12[..., 2]
    a = F11 * s1 ** 2 + F22 * s2 ** 2 + F66 * t12 ** 2 + 2.0 * F12 * s1 * s2
    b = F1 * s1 + F2 * s2
    disc = np.sqrt(b * b + 4.0 * a)
    with np.errstate(divide="ignore", invalid="ignore"):
        # b >= 0: RF = 2 / (b + disc);  b < 0: RF = (disc - b) / (2 a)   (no cancellation in either branch)
        rf = np.where(b >= 0, 2.0 / (b + disc), (disc - b) / (2.0 * np.where(a > 0, a, 1.0)))
    return np.where(a > 0, rf, np.inf)


def max_strain_ratios(strain12: np.ndarray, allowables) -> np.ndarray:
    """|e1|/e1u, |e2|/e2u, |g12|/g12u (..., 3). allowables = (e1u, e2u, g12u)."""
    e1u, e2u, g12u = allowables
    return np.stack([np.abs(strain12[..., 0]) / e1u, np.abs(strain12[..., 1]) / e2u,
                     np.abs(strain12[..., 2]) / g12u], axis=-1)


def rf_max_strain(strain12: np.ndarray, allowables) -> np.ndarray:
    """Max-Strain reserve factor with symmetric allowables (inf if unstrained)."""
    return _safe_inverse(max_strain_ratios(strain12, allowables).max(axis=-1))
