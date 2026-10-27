"""Shared helpers for the experiments: output folder, UTF-8 console, CSV/JSON writers, timing."""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from typing import Dict, Iterable, List

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.join(ROOT, "deliverables", "optimization")
# --quick runs write to results_quick / figures_quick so they never overwrite the full results
QUICK = "--quick" in sys.argv[1:]
RESULTS = os.path.join(OUT, "results_quick" if QUICK else "results")
FIGS = os.path.join(OUT, "figures_quick" if QUICK else "figures")


def setup() -> None:
    """UTF-8 console on Windows (cp1252 consoles would crash on 'λ', '±', Vietnamese text)."""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    os.makedirs(RESULTS, exist_ok=True)
    os.makedirs(FIGS, exist_ok=True)


def write_csv(name: str, rows: List[Dict], fields: Iterable[str] = None) -> str:
    path = os.path.join(RESULTS, name)
    rows = list(rows)
    fields = list(fields or (rows[0].keys() if rows else []))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def write_json(name: str, obj) -> str:
    path = os.path.join(RESULTS, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False, default=_default)
    return path


def read_json(name: str):
    with open(os.path.join(RESULTS, name), encoding="utf-8") as f:
        return json.load(f)


def _default(o):
    import numpy as np
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if hasattr(o, "to_dict"):
        return o.to_dict()
    return str(o)


class Timer:
    def __init__(self):
        self.t0 = time.perf_counter()

    def __call__(self) -> float:
        return time.perf_counter() - self.t0
