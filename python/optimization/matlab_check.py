"""
matlab_check.py - re-check laminates with the agent's MATLAB engine (matlab/clt_engine.m, unchanged).

Relative errors (Python vs MATLAB) used everywhere in this project:
  ABD     e = max( max|dA| / max|A| ,  max|dB| / (max|A| h) ,  max|dD| / max|D| )
          (B is normalised by A*h because B = 0 in exact arithmetic for symmetric laminates, so max|B| would
           only measure round-off; A*h is the natural scale of B)
  stress  e = max|d sigma| / max|sigma|      over all plies and the three components
  FI      e = max|d FI_k| / max FI            over all plies
  RF      e = |RF_py - RF_matlab| / RF_matlab for each criterion (RF from MATLAB = 1 / max FI for Max Stress;
          Tsai-Wu RF computed from MATLAB's ply stresses; buckling RF computed from MATLAB's D matrix)
critical ply: same index, or a tie (Python FI at MATLAB's critical ply equals the Python maximum within 1e-12,
which happens for symmetric laminates where mirrored plies have the same stress).
"""
from __future__ import annotations

import os
from typing import Dict, Optional, Sequence

import numpy as np

from . import buckling, clt, failure

MATLAB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "matlab")
TOL = 1e-9

_eng = None
_available = None


def available(timeout: float = 120.0) -> bool:
    """Probe in a child process whether the MATLAB engine can start (an import that hangs cannot be
    interrupted in-process). Result cached for this process."""
    global _available
    if _available is None:
        import subprocess
        import sys
        code = ("import sys; sys.modules['_wmi'] = None\nimport matlab.engine\n"
                "e = matlab.engine.start_matlab(); print(e.sqrt(4.0)); e.quit()")
        proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True)
        try:
            out, _ = proc.communicate(timeout=timeout)
            _available = proc.returncode == 0 and "2.0" in out
        except subprocess.TimeoutExpired:
            # a venv python.exe is a launcher with a child interpreter: kill the whole tree
            # (taskkill /T needs WMI, which may be the very thing that hangs -> Toolhelp32 snapshot instead)
            _kill_tree(proc.pid)
            proc.kill()
            proc.communicate()
            _available = False
    return _available


def _kill_tree(pid: int) -> None:
    """Terminate pid and all its descendants (Windows: Toolhelp32 snapshot, no WMI)."""
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_char * 260)]

    k32 = ctypes.windll.kernel32
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    parent_of = {}
    e = PROCESSENTRY32()
    e.dwSize = ctypes.sizeof(PROCESSENTRY32)
    ok = k32.Process32First(snap, ctypes.byref(e))
    while ok:
        parent_of[e.th32ProcessID] = e.th32ParentProcessID
        ok = k32.Process32Next(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    tree, frontier = [], [pid]
    while frontier:
        p = frontier.pop()
        tree.append(p)
        frontier += [c for c, par in parent_of.items() if par == p and c not in tree]
    for p in reversed(tree):
        h = k32.OpenProcess(0x0001, False, p)  # PROCESS_TERMINATE
        if h:
            k32.TerminateProcess(h, 1)
            k32.CloseHandle(h)


def engine():
    """Start (once) a MATLAB session in the matlab/ folder."""
    global _eng
    if _eng is None:
        import matlab.engine
        print("Starting MATLAB engine (10-30 s) ...", flush=True)
        _eng = matlab.engine.start_matlab()
        _eng.cd(MATLAB_DIR, nargout=0)
    return _eng


def close():
    global _eng
    if _eng is not None:
        _eng.quit()
        _eng = None


def run_matlab(angles: Sequence[float], thicknesses, mat, loads: Dict[str, float]) -> Dict[str, np.ndarray]:
    """Call clt_engine.m exactly as matlab_clt.run_clt does (plies as a list of dicts -> cell array)."""
    ang = [float(a) for a in angles]
    t = np.broadcast_to(np.asarray(thicknesses, dtype=float), (len(ang),))
    problem = {"plies": [{"angle": a, "thickness": float(ti)} for a, ti in zip(ang, t)],
               "loads": {k: float(loads.get(k, 0.0)) for k in ("Nx", "Ny", "Nxy", "Mx", "My", "Mxy")}}
    r = engine().clt_engine(problem, mat.as_matlab_dict(), nargout=1)
    out = {}
    for k, v in r.items():
        out[k] = np.array(v, dtype=float)
    out["ply_stress"] = out["ply_stress"].reshape(len(ang), 3)
    out["failure_index"] = out["failure_index"].reshape(-1)
    out["critical_ply"] = int(round(float(out["critical_ply"])))
    out["max_failure_index"] = float(out["max_failure_index"])
    return out


def compare(angles: Sequence[float], thicknesses, mat, loads: Dict[str, float]) -> Dict:
    """Python CLT vs MATLAB for one laminate -> relative errors and pass flag (all <= 1e-9)."""
    py = clt.analyze(angles, thicknesses, mat, **{k: float(loads.get(k, 0.0)) for k in
                                                  ("Nx", "Ny", "Nxy", "Mx", "My", "Mxy")})
    ml = run_matlab(angles, thicknesses, mat, loads)
    A, B, D = py["ABD"][:3, :3], py["ABD"][:3, 3:], py["ABD"][3:, 3:]
    Am, Bm, Dm = ml["ABD"][:3, :3], ml["ABD"][:3, 3:], ml["ABD"][3:, 3:]
    h = float(np.sum(np.broadcast_to(np.asarray(thicknesses, float), (len(angles),))))
    e_abd = max(np.abs(A - Am).max() / np.abs(Am).max(), np.abs(B - Bm).max() / (np.abs(Am).max() * h),
                np.abs(D - Dm).max() / np.abs(Dm).max())
    e_stress = np.abs(py["ply_stress"] - ml["ply_stress"]).max() / np.abs(ml["ply_stress"]).max()
    e_fi = np.abs(py["failure_index"] - ml["failure_index"]).max() / ml["max_failure_index"]
    k_ml = ml["critical_ply"]
    same_ply = (py["critical_ply"] == k_ml) or (
        abs(py["failure_index"][k_ml - 1] - py["max_failure_index"]) <= 1e-12 * py["max_failure_index"])
    return {"n_plies": len(angles), "e_ABD": float(e_abd), "e_stress": float(e_stress), "e_FI": float(e_fi),
            "max_FI_py": py["max_failure_index"], "max_FI_matlab": ml["max_failure_index"],
            "critical_ply_py": py["critical_ply"], "critical_ply_matlab": k_ml, "critical_ply_ok": bool(same_ply),
            "pass": bool(max(e_abd, e_stress, e_fi) <= TOL and same_ply)}


def verify_design(problem, full_codes: Sequence[int], python_detail: Optional[Dict] = None) -> Dict:
    """Re-check an optimised design with clt_engine.m: CLT errors + RFs recomputed from MATLAB output."""
    from .evaluate import analyze_design
    from .rules import ANGLES
    ang = ANGLES[np.asarray(full_codes, int)]
    Nx, Ny, Nxy = problem.loads
    loads = {"Nx": Nx, "Ny": Ny, "Nxy": Nxy}
    mat = problem.material
    cmp_ = compare(ang, problem.ply_thickness, mat, loads)
    ml = run_matlab(ang, problem.ply_thickness, mat, loads)
    det = python_detail or analyze_design(problem, full_codes)
    rf_ml = {}
    stress = ml["ply_stress"]
    if "max_stress" in problem.criteria:
        rf_ml["max_stress"] = (1.0 / ml["max_failure_index"]) / problem.criterion_factors.get("max_stress", 1.0)
    if "tsai_wu" in problem.criteria:
        rf_ml["tsai_wu"] = float(failure.rf_tsai_wu(stress, mat, problem.f12_star).min()) / \
            problem.criterion_factors.get("tsai_wu", 1.0)
    if "buckling" in problem.criteria:
        Dm = ml["ABD"][3:, 3:]
        a, b = problem.plate.a, problem.plate.b
        if problem.buckling_model == "ritz":
            lam = float(buckling.ritz([Dm[0, 0]], [Dm[0, 1]], [Dm[1, 1]], [Dm[2, 2]], Nx, Ny, Nxy, a, b, 20, 20)[0])
        else:
            lam = float(buckling.closed_form([Dm[0, 0]], [Dm[0, 1]], [Dm[1, 1]], [Dm[2, 2]], Nx, Ny, a, b,
                                             problem.buckling_modes)[0][0])
        rf_ml["buckling"] = lam / problem.criterion_factors.get("buckling", 1.0)
    e_rf = {}
    for c, v in rf_ml.items():
        pv = det["rf"][c]
        e_rf[c] = 0.0 if (np.isinf(v) and np.isinf(pv)) else float(abs(pv - v) / abs(v))
    margin_ml = min(rf_ml.values()) if rf_ml else float("nan")
    ok = cmp_["pass"] and all(e <= TOL for e in e_rf.values())
    return {"clt": cmp_, "rf_matlab": rf_ml, "rf_python": det["rf"], "e_rf": e_rf,
            "margin_matlab": float(margin_ml), "margin_python": det["margin"], "pass": bool(ok)}
