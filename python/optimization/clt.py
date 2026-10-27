"""
clt.py - Classical Laminate Theory in numpy, with the SAME conventions as matlab/clt_engine.m:

  * ply 1 is at the bottom, z(1) = -h/2; z grows by the ply thickness;
  * Q from E1, E2, G12, nu12 (plane stress); Qbar by the usual m^4 ... formulas (identical algebra to rotate_Q);
  * strains are engineering strains [ex, ey, gxy]; ply strains/stresses are taken at the ply MID-HEIGHT;
  * Max-Stress failure index FI = max(s1/Xt or -s1/Xc, s2/Yt or -s2/Yc, |t12|/S)  (>= 1 means failure).

Angles in degrees. cosd / sind reproduce MATLAB's argument reduction, so 90 deg gives an exact 0.
Everything is vectorised over a leading batch dimension where it matters (Qbar of many angles, many
laminates of the same ply count).
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence

import numpy as np


def _reduce_deg(x: np.ndarray):
    """MATLAB-style reduction used by sind/cosd: x = n*90 + r with n = round-half-away(x/90), |r| <= 45."""
    x = np.asarray(x, dtype=float)
    x = np.fmod(x, 360.0)  # = MATLAB rem(x, 360) (sign of x kept)
    q = x / 90.0
    n = np.where(q >= 0, np.floor(q + 0.5), np.ceil(q - 0.5))  # round half away from zero (MATLAB round)
    r = x - n * 90.0
    return n.astype(int) % 4, np.deg2rad(r)


def cosd(x) -> np.ndarray:
    """Cosine of an angle in degrees, exact 0 / +-1 at multiples of 90 deg (as MATLAB cosd)."""
    m, r = _reduce_deg(x)
    c, s = np.cos(r), np.sin(r)
    out = np.select([m == 0, m == 1, m == 2, m == 3], [c, -s, -c, s])
    return out


def sind(x) -> np.ndarray:
    """Sine of an angle in degrees, exact 0 / +-1 at multiples of 90 deg (as MATLAB sind)."""
    m, r = _reduce_deg(x)
    c, s = np.cos(r), np.sin(r)
    out = np.select([m == 0, m == 1, m == 2, m == 3], [s, c, -s, -c])
    return out


def q_matrix(E1: float, E2: float, G12: float, nu12: float) -> np.ndarray:
    """Reduced stiffness matrix Q (3x3) of one ply in its material axes (same algebra as clt_engine.m)."""
    nu21 = nu12 * E2 / E1
    denom = 1.0 - nu12 * nu21
    return np.array([[E1 / denom, nu12 * E2 / denom, 0.0],
                     [nu12 * E2 / denom, E2 / denom, 0.0],
                     [0.0, 0.0, G12]])


def qbar(Q: np.ndarray, theta_deg) -> np.ndarray:
    """Transformed stiffness Qbar for ply angle(s) theta (deg). Returns shape theta.shape + (3, 3)."""
    th = np.asarray(theta_deg, dtype=float)
    m, n = cosd(th), sind(th)
    Q11, Q12, Q22, Q66 = Q[0, 0], Q[0, 1], Q[1, 1], Q[2, 2]
    m2n2 = m ** 2 * n ** 2
    m4n4 = m ** 4 + n ** 4
    Qb11 = Q11 * m ** 4 + 2 * (Q12 + 2 * Q66) * m ** 2 * n ** 2 + Q22 * n ** 4
    Qb22 = Q11 * n ** 4 + 2 * (Q12 + 2 * Q66) * m ** 2 * n ** 2 + Q22 * m ** 4
    Qb12 = (Q11 + Q22 - 4 * Q66) * m2n2 + Q12 * m4n4
    Qb66 = (Q11 + Q22 - 2 * Q12 - 2 * Q66) * m2n2 + Q66 * m4n4
    Qb16 = (Q11 - Q12 - 2 * Q66) * m ** 3 * n - (Q22 - Q12 - 2 * Q66) * m * n ** 3
    Qb26 = (Q11 - Q12 - 2 * Q66) * m * n ** 3 - (Q22 - Q12 - 2 * Q66) * m ** 3 * n
    out = np.empty(th.shape + (3, 3))
    out[..., 0, 0], out[..., 0, 1], out[..., 0, 2] = Qb11, Qb12, Qb16
    out[..., 1, 0], out[..., 1, 1], out[..., 1, 2] = Qb12, Qb22, Qb26
    out[..., 2, 0], out[..., 2, 1], out[..., 2, 2] = Qb16, Qb26, Qb66
    return out


def strain_to_material(eps_xy: np.ndarray, theta_deg) -> np.ndarray:
    """Engineering strain [ex, ey, gxy] (laminate axes) -> [e1, e2, g12] (ply axes). Broadcasts over leading dims."""
    th = np.asarray(theta_deg, dtype=float)
    m, n = cosd(th), sind(th)
    ex, ey, gxy = eps_xy[..., 0], eps_xy[..., 1], eps_xy[..., 2]
    exy = gxy / 2.0
    e1 = ex * m ** 2 + ey * n ** 2 + 2 * exy * m * n
    e2 = ex * n ** 2 + ey * m ** 2 - 2 * exy * m * n
    g12 = 2 * (-ex * m * n + ey * m * n + exy * (m ** 2 - n ** 2))
    return np.stack([e1, e2, g12], axis=-1)


def z_coordinates(thicknesses: np.ndarray) -> np.ndarray:
    """Ply boundaries from the bottom (-h/2) upward, same loop as clt_engine.m. thicknesses: (..., n) -> (..., n+1)."""
    t = np.asarray(thicknesses, dtype=float)
    total = t.sum(axis=-1, keepdims=True)
    z = np.concatenate([-total / 2.0, -total / 2.0 + np.cumsum(t, axis=-1)], axis=-1)
    return z


def abd_matrices(angles, thicknesses, Q: np.ndarray):
    """A, B, D (3x3 each) for laminates. angles/thicknesses: (..., n) -> A, B, D with shape (..., 3, 3)."""
    ang = np.asarray(angles, dtype=float)
    t = np.broadcast_to(np.asarray(thicknesses, dtype=float), ang.shape)
    z = z_coordinates(t)
    Qb = qbar(Q, ang)                                    # (..., n, 3, 3)
    d1 = (z[..., 1:] - z[..., :-1])[..., None, None]
    d2 = ((z[..., 1:] ** 2 - z[..., :-1] ** 2) / 2.0)[..., None, None]
    d3 = ((z[..., 1:] ** 3 - z[..., :-1] ** 3) / 3.0)[..., None, None]
    A = (Qb * d1).sum(axis=-3)
    B = (Qb * d2).sum(axis=-3)
    D = (Qb * d3).sum(axis=-3)
    return A, B, D


def max_stress_index(stress12: np.ndarray, mat) -> np.ndarray:
    """Max-Stress failure index per ply (same branch logic as clt_engine.m). stress12: (..., 3)."""
    s1, s2, t12 = stress12[..., 0], stress12[..., 1], stress12[..., 2]
    r1 = np.where(s1 >= 0, s1 / mat.Xt, -s1 / mat.Xc)
    r2 = np.where(s2 >= 0, s2 / mat.Yt, -s2 / mat.Yc)
    r6 = np.abs(t12) / mat.S
    return np.maximum(np.maximum(r1, r2), r6)


def analyze(angles: Sequence[float], thicknesses, mat, Nx: float = 0.0, Ny: float = 0.0, Nxy: float = 0.0,
            Mx: float = 0.0, My: float = 0.0, Mxy: float = 0.0) -> Dict[str, np.ndarray]:
    """Full CLT analysis of ONE laminate, returning the same fields as clt_engine.m.

    angles: ply angles in deg, ply 1 = bottom (z = -h/2). thicknesses: scalar or per-ply (m).
    mat: object with E1, E2, G12, nu12, Xt, Xc, Yt, Yc, S (Pa). Loads in N/m and N*m/m.
    critical_ply is 1-based (MATLAB style) = first ply with the largest failure index.
    """
    ang = np.asarray(angles, dtype=float)
    t = np.broadcast_to(np.asarray(thicknesses, dtype=float), ang.shape).copy()
    Q = q_matrix(mat.E1, mat.E2, mat.G12, mat.nu12)
    A, B, D = abd_matrices(ang, t, Q)
    ABD = np.block([[A, B], [B, D]])
    rhs = np.array([Nx, Ny, Nxy, Mx, My, Mxy], dtype=float)
    sol = np.linalg.solve(ABD, rhs)
    eps0, kappa = sol[:3], sol[3:]
    z = z_coordinates(t)
    zmid = (z[:-1] + z[1:]) / 2.0
    eps_xy = eps0[None, :] + zmid[:, None] * kappa[None, :]
    eps12 = strain_to_material(eps_xy, ang)
    stress12 = eps12 @ Q.T
    fi = max_stress_index(stress12, mat)
    k = int(np.argmax(fi))
    return {"ABD": ABD, "A": A, "B": B, "D": D, "eps0": eps0, "kappa": kappa, "ply_angle": ang,
            "z": z, "ply_strain": eps12, "ply_stress": stress12, "failure_index": fi,
            "max_failure_index": float(fi[k]), "critical_ply": k + 1}


def midplane_strain_symmetric(A: np.ndarray, N: np.ndarray) -> np.ndarray:
    """Mid-plane strains of symmetric laminates (B = 0, no moments): eps0 = A^-1 N. A: (P,3,3), N: (3,) -> (P,3)."""
    rhs = np.broadcast_to(np.asarray(N, dtype=float), A.shape[:-1])[..., None]
    return np.linalg.solve(A, rhs)[..., 0]


def ply_stress_from_strain(eps0: np.ndarray, angles_deg: np.ndarray, Q: np.ndarray):
    """For uniform laminate strain eps0 (P,3) and a set of angles (k,), ply strains/stresses (P,k,3) in ply axes."""
    eps12 = strain_to_material(eps0[:, None, :], np.asarray(angles_deg, dtype=float)[None, :])
    return eps12, eps12 @ Q.T
