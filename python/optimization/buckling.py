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

from typing import Dict, Optional, Tuple

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


# ------------------------------------------------------------------------ Ritz with D16, D26 (project model)
def _sc(m, p, L):
    """int_0^L sin(m pi x / L) cos(p pi x / L) dx (0 when m = p or m + p even)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(m != p, L / np.pi * m * (1 - (-1.0) ** (m + p)) / (m ** 2 - p ** 2), 0.0)


class RitzModel:
    """Rayleigh-Ritz buckling of a simply supported a x b plate with the FULL bending stiffness (D16, D26
    included) under combined Nx, Ny, Nxy (tension positive), double sine series w = sum A_mn sin(m pi x/a)
    sin(n pi y/b), m <= M, n <= N.

    Energy (Whitney 1987): U = 1/2 int [D11 w,xx^2 + 2 D12 w,xx w,yy + D22 w,yy^2 + 4 D66 w,xy^2
                                        + 4 D16 w,xx w,xy + 4 D26 w,yy w,xy] dA,
                           V = 1/2 int [Nx w,x^2 + Ny w,y^2 + 2 Nxy w,x w,y] dA.
    With U = 1/2 A^T K A and V = 1/2 A^T G A, buckling under lambda x (loads) means det(K + lambda G) = 0, i.e.
    the generalised eigenproblem K A = lambda (-G) A. The critical load factor is the smallest POSITIVE lambda
    (= 1 / largest positive eigenvalue mu of (-G) A = mu K A). Tension enters G with the stabilising sign; if no
    eigenvalue is positive the load cannot buckle the plate and lambda = inf. The sign of Nxy matters when
    D16, D26 != 0 (it does not when they are 0).
    D16 and D26 couple modes (m, n), (p, q) with m + p odd and n + q odd, like Nxy, so the problem still splits
    into the two independent blocks m + n even / odd.
    The sine series does not satisfy the natural (zero-moment) edge condition when D16, D26 != 0
    (M_xx = -(D11 w,xx + D12 w,yy + 2 D16 w,xy) and w,xy != 0 on the edges): the Ritz value is an upper
    bound that converges more slowly as M, N grow (see converge()).
    The basis integrals depend only on a, b, M, N and the loads: they are computed once (constructor); the
    eigenvalues are computed in batches; results are cached by D matrix (lam_cached).
    """

    def __init__(self, a: float, b: float, Nx: float, Ny: float, Nxy: float, M: int = 12, N: Optional[int] = None):
        N = M if N is None else N
        self.a, self.b, self.M, self.N = float(a), float(b), int(M), int(N)
        self.loads = (float(Nx), float(Ny), float(Nxy))
        self.can_buckle = not (Nx >= 0 and Ny >= 0 and Nxy == 0)
        self.blocks = []
        c = a * b / 4.0
        for parity in (0, 1):
            modes = [(m, n) for m in range(1, M + 1) for n in range(1, N + 1) if (m + n) % 2 == parity]
            mm = np.array([p[0] for p in modes], dtype=float)
            nn = np.array([p[1] for p in modes], dtype=float)
            al, be = mm * np.pi / a, nn * np.pi / b
            # diagonal parts (orthogonality of the sines / cosines); kH multiplies D12 + 2 D66
            k11, k22, kH = c * al ** 4, c * be ** 4, c * 2.0 * al ** 2 * be ** 2
            # off-diagonal parts: i = (m, n) row, j = (p, q) column
            Sx = _sc(mm[:, None], mm[None, :], a)          # int sin(al_m x) cos(al_p x) dx
            Sy = _sc(nn[:, None], nn[None, :], b)          # int sin(be_n y) cos(be_q y) dy
            C16 = -(al[:, None] ** 2) * al[None, :] * be[None, :] * Sx * Sy   # int phi_i,xx phi_j,xy dA
            C26 = -(be[:, None] ** 2) * al[None, :] * be[None, :] * Sx * Sy   # int phi_i,yy phi_j,xy dA
            K16, K26 = 2.0 * (C16 + C16.T), 2.0 * (C26 + C26.T)
            G = np.diag(c * (Nx * al ** 2 + Ny * be ** 2))
            if Nxy != 0.0:
                E = al[:, None] * be[None, :] * (Sx.T * Sy)    # int phi_i,x phi_j,y dA
                G = G + Nxy * (E + E.T)
            self.blocks.append({"m": mm, "n": nn, "k11": k11, "k22": k22, "kH": kH, "K16": K16, "K26": K26,
                                "mG": -G})
        self.cache: Dict[bytes, float] = {}
        self.n_solved = 0

    def stiffness(self, Dvec: np.ndarray, blk: Dict) -> np.ndarray:
        """K (P, k, k) of one block; Dvec (P, 6) = D11, D12, D22, D66, D16, D26."""
        D11, D12, D22, D66, D16, D26 = Dvec.T
        diag = D11[:, None] * blk["k11"] + D22[:, None] * blk["k22"] + (D12 + 2 * D66)[:, None] * blk["kH"]
        K = D16[:, None, None] * blk["K16"][None] + D26[:, None, None] * blk["K26"][None]
        idx = np.arange(diag.shape[1])
        K[:, idx, idx] += diag
        return K

    def _mu_max(self, Dvec: np.ndarray, blk: Dict, vectors: bool = False):
        L = np.linalg.cholesky(self.stiffness(Dvec, blk))
        Linv = np.linalg.inv(L)
        Cm = Linv @ blk["mG"][None] @ np.swapaxes(Linv, 1, 2)          # L^-1 (-G) L^-T
        Cm = 0.5 * (Cm + np.swapaxes(Cm, 1, 2))
        if not vectors:
            return np.linalg.eigvalsh(Cm)[:, -1], None
        w, v = np.linalg.eigh(Cm)
        modes = np.einsum("pji,pj->pi", Linv, v[:, :, -1])            # A = L^-T v
        return w[:, -1], modes

    def lam(self, Dvec, vectors: bool = False):
        """Critical load factors (P,) for D vectors (P, 6) [N m]; inf = the loads cannot buckle the plate.
        vectors=True also returns, per design, (block index, mode vector A) of the critical mode."""
        Dvec = np.atleast_2d(np.asarray(Dvec, dtype=float))
        P = len(Dvec)
        if not self.can_buckle:
            return (np.full(P, np.inf), [None] * P) if vectors else np.full(P, np.inf)
        lam = np.full(P, np.inf)
        crit = [None] * P
        for bi, blk in enumerate(self.blocks):
            mu, modes = self._mu_max(Dvec, blk, vectors)
            with np.errstate(divide="ignore"):
                lb = np.where(mu > 1e-300, 1.0 / np.where(mu > 1e-300, mu, 1.0), np.inf)
            if vectors:
                for p in np.where(lb < lam)[0]:
                    crit[p] = (bi, modes[p])
            lam = np.minimum(lam, lb)
        self.n_solved += P
        return (lam, crit) if vectors else lam

    def lam_cached(self, Dvec) -> np.ndarray:
        """lam() with a cache keyed by the D matrix (identical D -> identical answer, computed once)."""
        Dvec = np.atleast_2d(np.asarray(Dvec, dtype=float))
        keys = [r.tobytes() for r in Dvec]
        first = {}
        for i, k in enumerate(keys):
            if k not in self.cache and k not in first:
                first[k] = i
        if first:
            vals = self.lam(Dvec[list(first.values())])
            for k, v in zip(first, vals):
                self.cache[k] = float(v)
        return np.array([self.cache[k] for k in keys])

    def quotient_terms(self, blk_index: int, A: np.ndarray) -> Optional[np.ndarray]:
        """Rayleigh quotient of a FIXED mode A, R(A; D) = sum_c D_c r_c (linear in D): returns r (6,) for
        D11, D12, D22, D66, D16, D26. lambda_cr(D) <= R(A; D) for every D when A^T (-G) A > 0."""
        blk = self.blocks[blk_index]
        den = A @ blk["mG"] @ A
        if den <= 0:
            return None
        a2 = A ** 2
        r11, r22, rH = a2 @ blk["k11"], a2 @ blk["k22"], a2 @ blk["kH"]
        return np.array([r11, rH, r22, 2 * rH, A @ blk["K16"] @ A, A @ blk["K26"] @ A]) / den


def d_vector(D: np.ndarray) -> np.ndarray:
    """(P, 3, 3) bending stiffness -> (P, 6) = D11, D12, D22, D66, D16, D26."""
    D = np.asarray(D, dtype=float).reshape(-1, 3, 3)
    return np.stack([D[:, 0, 0], D[:, 0, 1], D[:, 1, 1], D[:, 2, 2], D[:, 0, 2], D[:, 1, 2]], axis=1)


def ritz_full(D, Nx: float, Ny: float, Nxy: float, a: float, b: float, M: int = 12,
              N: Optional[int] = None) -> np.ndarray:
    """Critical load factor (P,) with the full D (D16, D26 included); D: (P, 3, 3) or (3, 3)."""
    return RitzModel(a, b, Nx, Ny, Nxy, M, N).lam(d_vector(D))


def terms_for(k: int, a: float, b: float) -> Tuple[int, int]:
    """(M, N) for a 'size' k: M : N follows a : b so that long plates get enough half-waves along x."""
    return int(np.ceil(k * max(1.0, a / b))), int(np.ceil(k * max(1.0, b / a)))


def converge(D, Nx: float, Ny: float, Nxy: float, a: float, b: float, start: int = 6, step: int = 2,
             tol: float = 0.005, max_terms: int = 40) -> Dict:
    """Increase the number of terms (size k = start, start + step, ...) until the critical load factor changes by
    less than tol (relative) between two consecutive sizes. Returns {"terms": [(M, N, lambda), ...], "M", "N",
    "lambda", "converged", "last_change"}."""
    out, prev = [], None
    for k in range(start, max_terms + 1, step):
        M, N = terms_for(k, a, b)
        lam = float(ritz_full(D, Nx, Ny, Nxy, a, b, M, N)[0])
        out.append((M, N, lam))
        if prev is not None and ((np.isinf(lam) and np.isinf(prev)) or abs(lam - prev) <= tol * abs(lam)):
            return {"terms": out, "M": M, "N": N, "lambda": lam, "converged": True,
                    "last_change": 0.0 if np.isinf(lam) else abs(lam - prev) / abs(lam)}
        prev = lam
    return {"terms": out, "M": out[-1][0], "N": out[-1][1], "lambda": out[-1][2], "converged": False,
            "last_change": abs(out[-1][2] - out[-2][2]) / abs(out[-1][2]) if len(out) > 1 else None}


# --------------------------------------------------------------- independent check: Ritz with polynomials
def ritz_polynomial(D, Nx: float, Ny: float, Nxy: float, a: float, b: float, p: int = 12) -> float:
    """Independent Rayleigh-Ritz solution used only to CHECK RitzModel: w = sum c_ij X_i(x) Y_j(y) with
    X_i = (1 - xi^2) P_i(xi) (Legendre P_i, xi in [-1, 1]): w = 0 on the edges (geometric condition of simple
    support), moments left free, every integral by Gauss-Legendre quadrature. Other functions and another way of
    integrating than the sine series; both are upper bounds of the same exact value."""
    from scipy.linalg import eigh
    D = np.asarray(D, dtype=float).reshape(3, 3)
    xg, wg = np.polynomial.legendre.leggauss(p + 8)

    def basis_1d(L):
        V = np.zeros((3, p + 1, len(xg)))     # X_i and its first two x-derivatives at the Gauss points
        for i in range(p + 1):
            f = np.polynomial.Polynomial([1, 0, -1]) * np.polynomial.Legendre.basis(i).convert(
                kind=np.polynomial.Polynomial)
            for d in range(3):
                V[d, i] = f.deriv(d)(xg) * (2.0 / L) ** d
        return V, wg * L / 2.0

    def ints(V, w):  # I[d1][d2]_ik = int X_i^(d1) X_k^(d2) dx
        return [[(V[d1] * w) @ V[d2].T for d2 in range(3)] for d1 in range(3)]

    Ix, Iy = ints(*basis_1d(a)), ints(*basis_1d(b))
    kr = np.kron
    D11, D12, D22, D66, D16, D26 = D[0, 0], D[0, 1], D[1, 1], D[2, 2], D[0, 2], D[1, 2]
    K = (D11 * kr(Ix[2][2], Iy[0][0]) + D12 * (kr(Ix[2][0], Iy[0][2]) + kr(Ix[0][2], Iy[2][0]))
         + D22 * kr(Ix[0][0], Iy[2][2]) + 4 * D66 * kr(Ix[1][1], Iy[1][1])
         + 2 * D16 * (kr(Ix[2][1], Iy[0][1]) + kr(Ix[1][2], Iy[1][0]))
         + 2 * D26 * (kr(Ix[0][1], Iy[2][1]) + kr(Ix[1][0], Iy[1][2])))
    G = (Nx * kr(Ix[1][1], Iy[0][0]) + Ny * kr(Ix[0][0], Iy[1][1])
         + Nxy * (kr(Ix[1][0], Iy[0][1]) + kr(Ix[0][1], Iy[1][0])))
    K, G = 0.5 * (K + K.T), 0.5 * (G + G.T)
    mu = eigh(-G, K, eigvals_only=True)[-1]
    return float(1.0 / mu) if mu > 1e-300 else float("inf")
