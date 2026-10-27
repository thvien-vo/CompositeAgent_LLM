"""
material.py - ply properties for the optimizer, built on the agent's existing mechanism (materials.py, ml.py):

  * a name that matches exactly one row of composite_lamina_dataset_v4.csv (e.g. "IM7/8552") -> MEASURED values
    of that row (materials.ply_properties); missing / excluded values of that row -> ML prediction + warning;
  * otherwise -> ML prediction for the group (CFRP / GFRP / KEVLAR) + the reason;
  * a user dict (material_from_dict) with missing strengths -> those strengths from the ML prediction + warning.

The Material object is a plain parameter of every analysis, so Layer 2 can replace it by samples of a
probability distribution. Existing files are only imported, never modified.
"""
from __future__ import annotations

import os
import sys
import types
from dataclasses import asdict, dataclass, field, replace
from typing import Dict, Optional, Tuple

PYTHON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

KEYS = ("E1", "E2", "G12", "nu12", "Xt", "Xc", "Yt", "Yc", "S")
STRENGTH_KEYS = ("Xt", "Xc", "Yt", "Yc", "S")

# Nominal cured ply thickness of Hexcel 8552/IM7 unitape (190 g/m^2) used by NCAMP: 0.0072 in = 0.18288 mm.
# Source: NCAMP report NCP-RP-2009-028 Rev B, as recorded in the project dataset
# (composite_lamina_dataset_v4.csv, row IM7/8552, column Vf_note: "FAW 190 gsm / (rho_f 1.78 g/cc x tply 0.0072 in)").
NCAMP_IM7_8552_CPT = 0.0072 * 0.0254
DEFAULT_PLY_THICKNESS = 0.125e-3  # same as demo.py


@dataclass(frozen=True)
class Material:
    """Ply properties in SI units (Pa). Strengths are positive magnitudes."""
    E1: float
    E2: float
    G12: float
    nu12: float
    Xt: float
    Xc: float
    Yt: float
    Yc: float
    S: float
    name: str = "custom"
    source: str = ""
    warnings: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        for k in KEYS:
            v = getattr(self, k)
            if not (v == v) or v <= 0:  # NaN or non-positive
                raise ValueError(f"material {self.name}: {k} = {v} is not a positive number")
        if not self.nu12 ** 2 < self.E1 / self.E2:  # positive-definite Q: nu12 * nu21 < 1
            raise ValueError(f"material {self.name}: nu12 = {self.nu12} is not admissible")

    def as_matlab_dict(self) -> Dict[str, float]:
        """Fields expected by matlab/clt_engine.m."""
        return {k: float(getattr(self, k)) for k in KEYS}

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["warnings"] = list(self.warnings)
        return d


def _print_warnings(m: Material, verbose: bool) -> None:
    if verbose:
        for w in m.warnings:
            print(f"  [warning] material: {w}")


def get_material(name: str = "IM7/8552", group: str = "CFRP", verbose: bool = True) -> Material:
    """Material by name using the agent's mechanism (measured CSV row if the name identifies exactly one row,
    else the ML prediction for `group`). Missing strengths are replaced by the ML prediction with a warning."""
    import materials  # existing module (python/materials.py)
    from ml import predict_material

    row, note = materials.resolve(name, name)
    warnings = []
    if row:
        props, source, notes = materials.ply_properties(types.SimpleNamespace(material_name=row, material=group))
        warnings += list(notes)
        mname = row
    else:
        props = predict_material(group)
        source = f"ML prediction (group {group})"
        warnings.append(f"'{name}' -> {note}; ML prediction for group {group} used")
        mname = f"{group} (ML)"
    m = Material(**{k: float(props[k]) for k in KEYS}, name=mname, source=source, warnings=tuple(warnings))
    _print_warnings(m, verbose)
    return m


def material_from_dict(values: Dict[str, Optional[float]], group: str = "CFRP", name: str = "custom",
                       source: str = "user input", verbose: bool = True) -> Material:
    """Material from user values. Elastic constants are required; any missing strength (None / absent / NaN)
    is replaced by the ML prediction for `group`, with a printed warning naming the property."""
    missing = [k for k in KEYS if values.get(k) is None or values.get(k) != values.get(k)]
    bad_elastic = [k for k in missing if k not in STRENGTH_KEYS]
    if bad_elastic:
        raise ValueError(f"material {name}: elastic constants missing: {bad_elastic}")
    props = {k: float(values[k]) for k in KEYS if k not in missing}
    warnings = []
    if missing:
        from ml import predict_material
        ml = predict_material(group)
        for k in missing:
            props[k] = float(ml[k])
            warnings.append(f"{k} of {name} not given -> ML prediction for group {group} used: {ml[k] / 1e6:.4g} MPa")
    m = Material(**props, name=name, source=source, warnings=tuple(warnings))
    _print_warnings(m, verbose)
    return m


def scaled(m: Material, **factors: float) -> Material:
    """Copy of m with some properties multiplied (helper for sensitivity studies / Layer 2)."""
    return replace(m, **{k: getattr(m, k) * f for k, f in factors.items()})
