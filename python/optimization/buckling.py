"""
buckling.py - buckling load factor of a simply supported rectangular plate a x b (x along a).

1) closed_form(): specially orthotropic plate (D16 = D26 = 0 assumed) under biaxial in-plane loads Nx, Ny
   (tension positive). Buckling with m, n half-waves when the loads are multiplied by

        lambda(m, n) = pi^2 [D11 (m/a)^4 + 2 (D12 + 2 D66) (m/a)^2 (n/b)^2 + D22 (n/b)^4]
                       ---------------------------------------------------------------
                                   (m/a)^2 (-Nx) + (n/b)^2 (-Ny)

   (only modes with a positive denominator can buckle). Source: e.g. Whitney (1987), Structural Analysis of
   Laminated Anisotropic Plates; the same expression is eq. (3.1) of Le Riche (1994) / Le Riche & Haftka (1993).
   lambda_cr = min over (m, n). The search is PROVEN complete: with mu = (m/a)^2, nu = (n/b)^2 and
   H = D12 + 2 D66 >= 0,  numerator >= min(D11, D22) (mu + nu)^2 / 2  and  denominator <= Nmax (mu + nu), so
        lambda(m, n) >= pi^2 min(D11, D22) (mu + nu) / (2 Nmax),       Nmax = max(-Nx, -Ny, 0).
   After a first estimate lambda0 from small modes, every mode with mu + nu > 2 Nmax lambda0 / (pi^2 Dmin)
   is worse than lambda0, so only m <= a sqrt(R), n <= b sqrt(R) are scanned (R = that bound).
   No compression -> lambda = inf (no buckling check, as required for Layer 1).
   Nxy is NOT used here (shear buckling is not part of the closed form).

2) ritz(): Rayleigh-Ritz with the double sine series w = sum A_mn sin(m pi x/a) sin(n pi y/b), m <= M, n <= N,
   for combined Nx, Ny, Nxy, still with D16 = D26 = 0. This is the classical energy method used for the shear
   buckling of simply supported plates (Timoshenko & Gere 1961, Theory of Elastic Stability, sec. 9.7;
   Stein & Neff 1947, NACA TN 1222; Whitney 1987 for orthotropic plates). The Ritz value is an upper bound
   that decreases as M, N grow; convergence is checked in the tests (isotropic square plate in pure shear:
   k_s = 9.34, Stein & Neff / Timoshenko & Gere). Used only as an OPTION / supplementary check.
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

PI2 = np.pi ** 2
MODE_CAP = 400  # safety cap on m or n (never reached in the cases of this project; flagged if it is)


def _lambda_grid(D11, H, D22, cx, cy, a, b, ms: np.ndarray, ns: np.ndarray):
    """lambda for all designs (P,) and all modes ms x ns -> (P, len(ms), len(ns)); invalid modes = inf."""
    mu = (ms / a) ** 2
    nu = (ns / b) ** 2
    num = (D11[:, None, None] * mu[None, :, None] ** 2
           + 2.0 * H[:, None, None] * mu[None, :, None] * nu[None, None, :]
           + D22[:, None, None] * nu[None, None, :] ** 2)
    den = cx * mu[:, None] + cy * nu[None, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        lam = np.where(den[None] > 0, PI2 * num / np.where(den > 0, den, 1.0)[None], np.inf)
    return lam


def closed_form(D11, D12, D22, D66, Nx: float, Ny: float, a: float, b: float,
                max_modes: Optional[Tuple[int, int]] = None):
    """Critical buckling factor of specially orthotropic SS plates (vectorised over designs).

    D11 ... D66: arrays (P,) [N m]. Nx, Ny: N/m (compression negative). a, b: m.
    max_modes=(M, N) restricts the scan to m <= M, n <= N (used only to reproduce papers, e.g. Le Riche:
    m, n <= 5); default None = proven-complete scan.
    Returns (lam (P,), m (P,), n (P,), capped: bool).
    """
    D11, D12, D22, D66 = (np.atleast_1d(np.asarray(v, dtype=float)) for v in (D11, D12, D22, D66))
    P = D11.shape[0]
    cx, cy = -float(Nx), -float(Ny)  # compression positive
    if cx <= 0 and cy <= 0:
        return np.full(P, np.inf), np.zeros(P, int), np.zeros(P, int), False
    H = D12 + 2.0 * D66
    if max_modes is not None:
        ms, ns = np.arange(1, max_modes[0] + 1), np.arange(1, max_modes[1] + 1)
        lam = _lambda_grid(D11, H, D22, cx, cy, a, b, ms, ns)
        return _pick(lam, ms, ns) + (False,)
    if np.any(H < 0) or np.any(D11 <= 0) or np.any(D22 <= 0):
        raise ValueError("closed_form: needs D11, D22 > 0 and D12 + 2 D66 >= 0")

    # first estimate from small modes, plus the first modes that have a positive denominator
    m0 = 1 if (cx > 0 and cy >= 0) else (int(np.floor(a / b * np.sqrt(-cy / cx))) + 1 if cx > 0 else 1)
    n0 = 1 if (cy > 0 and cx >= 0) else (int(np.floor(b / a * np.sqrt(-cx / cy))) + 1 if cy > 0 else 1)
    ms = np.arange(1, max(5, m0 + 2) + 1)
    ns = np.arange(1, max(5, n0 + 2) + 1)
    lam0 = _lambda_grid(D11, H, D22, cx, cy, a, b, ms, ns).reshape(P, -1).min(axis=1)
    if not np.all(np.isfinite(lam0)):
        raise RuntimeError("closed_form: no buckling mode with a positive denominator in the first scan")
    nmax_load = max(cx, cy, 0.0)
    R = 2.0 * nmax_load * lam0 / (PI2 * np.minimum(D11, D22))
    m_need = int(np.floor(a * np.sqrt(R.max()))) + 1
    n_need = int(np.floor(b * np.sqrt(R.max()))) + 1
    capped = m_need > MODE_CAP or n_need > MODE_CAP
    m_hi, n_hi = max(len(ms), min(m_need, MODE_CAP)), max(len(ns), min(n_need, MODE_CAP))
    ms, ns = np.arange(1, m_hi + 1), np.arange(1, n_hi + 1)
    best = np.full(P, np.inf)
    bm, bn = np.zeros(P, int), np.zeros(P, int)
    chunk = max(1, int(4e6 // max(1, P * len(ns))))
    for i in range(0, len(ms), chunk):  # chunks of m keep memory small
        lam = _lambda_grid(D11, H, D22, cx, cy, a, b, ms[i:i + chunk], ns)
        l, m, n = _pick(lam, ms[i:i + chunk], ns)
        better = l < best
        best[better], bm[better], bn[better] = l[better], m[better], n[better]
    return best, bm, bn, capped


def _pick(lam: np.ndarray, ms: np.ndarray, ns: np.ndarray):
    P = lam.shape[0]
    flat = lam.reshape(P, -1)
    k = np.argmin(flat, axis=1)
    return flat[np.arange(P), k], ms[k // len(ns)], ns[k % len(ns)]


# ----------------------------------------------------------------------------------------- Ritz (with shear)
def _ritz_blocks(Nx: float, Ny: float, Nxy: float, a: float, b: float, M: int, N: int):
    """Mode lists and load matrices G (V = 1/2 A^T G A) for the two independent parity blocks (m+n even/odd)."""
    blocks = []
    for parity in (0, 1):
        modes = [(m, n) for m in range(1, M + 1) for n in range(1, N + 1) if (m + n) % 2 == parity]
        mm = np.array([p[0] for p in modes], dtype=float)
        nn = np.array([p[1] for p in modes], dtype=float)
        G = np.diag(a * b / 4.0 * PI2 * (Nx * (mm / a) ** 2 + Ny * (nn / b) ** 2))
        if Nxy != 0.0:
            # c_ij = int int phi_i,x phi_j,y dA = (m pi/a)(q pi/b) Ix(m,p) Iy(n,q), i = (m,n), j = (p,q)
            m_i, p_j = mm[:, None], mm[None, :]
            n_i, q_j = nn[:, None], nn[None, :]
            with np.errstate(divide="ignore", invalid="ignore"):
                Ix = np.where(m_i != p_j, a / np.pi * p_j * (1 - (-1.0) ** (m_i + p_j)) / (p_j ** 2 - m_i ** 2), 0.0)
                Iy = np.where(n_i != q_j, b / np.pi * n_i * (1 - (-1.0) ** (n_i + q_j)) / (n_i ** 2 - q_j ** 2), 0.0)
            c = (m_i * np.pi / a) * (q_j * np.pi / b) * Ix * Iy
            G = G + Nxy * (c + c.T)
        blocks.append((mm, nn, G))
    return blocks


def ritz(D11, D12, D22, D66, Nx: float, Ny: float, Nxy: float, a: float, b: float,
         M: int = 16, N: int = 16) -> np.ndarray:
    """Buckling factor by Rayleigh-Ritz (double sine series, D16 = D26 = 0), combined Nx, Ny, Nxy.

    Solves K A = lambda (-G) A; K is diagonal for specially orthotropic plates. Returns lambda (P,), inf if
    the load cannot cause buckling. Upper bound converging from above as M, N increase.
    """
    D11, D12, D22, D66 = (np.atleast_1d(np.asarray(v, dtype=float)) for v in (D11, D12, D22, D66))
    P = D11.shape[0]
    if Nx >= 0 and Ny >= 0 and Nxy == 0:
        return np.full(P, np.inf)
    H = D12 + 2.0 * D66
    lam = np.full(P, np.inf)
    for mm, nn, G in _ritz_blocks(Nx, Ny, Nxy, a, b, M, N):
        kdiag = a * b / 4.0 * np.pi ** 4 * (D11[:, None] * (mm / a) ** 4 + 2 * H[:, None] * (mm / a) ** 2 * (nn / b) ** 2
                                            + D22[:, None] * (nn / b) ** 4)          # (P, k)
        s = 1.0 / np.sqrt(kdiag)
        C = -G[None, :, :] * s[:, :, None] * s[:, None, :]                           # S (-G) S
        mu = np.linalg.eigvalsh(C)[:, -1]                                              # largest eigenvalue
        with np.errstate(divide="ignore"):
            lam = np.minimum(lam, np.where(mu > 1e-300, 1.0 / np.where(mu > 1e-300, mu, 1.0), np.inf))
    return lam
