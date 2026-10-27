"""
Load cases of the Layer-1 study (IM7/8552, simply supported 0.5 m x 0.5 m plate, safety factor 1.5).

Magnitudes were fixed BEFORE running GA / NSGA-II, from a rough sizing so that every case is non-trivial:
tension / shear strength cases in MN/m (strength governs), compression cases in tens of kN/m (a 0.5 m
unstiffened panel is buckling-critical at much lower loads than strength-critical), and one very large load.
"""
from optimization.material import DEFAULT_PLY_THICKNESS, NCAMP_IM7_8552_CPT

CASES = [
    {"id": "C1", "vi": "Kéo một phương", "en": "Uniaxial tension", "loads": (1.5e6, 0.0, 0.0)},
    {"id": "C2", "vi": "Kéo hai phương", "en": "Biaxial tension", "loads": (1.0e6, 0.5e6, 0.0)},
    {"id": "C3", "vi": "Nén một phương", "en": "Uniaxial compression", "loads": (-1.0e4, 0.0, 0.0)},
    {"id": "C4", "vi": "Nén hai phương", "en": "Biaxial compression", "loads": (-1.0e4, -0.5e4, 0.0)},
    {"id": "C5", "vi": "Cắt thuần", "en": "Pure shear", "loads": (0.0, 0.0, 3.0e5)},
    {"id": "C6", "vi": "Kéo + cắt", "en": "Tension + shear", "loads": (8.0e5, 0.0, 3.0e5)},
    {"id": "C7", "vi": "Nén + cắt", "en": "Compression + shear", "loads": (-1.0e4, 0.0, 5.0e3)},
    {"id": "C8", "vi": "Tải rất lớn", "en": "Very large load", "loads": (4.0e6, 2.0e6, 1.0e6)},
]
SHEAR_CASES = ["C5", "C6", "C7"]   # supplementary runs with Ritz buckling (includes Nxy)

THICKNESSES = {"t0125": DEFAULT_PLY_THICKNESS, "t0183": NCAMP_IM7_8552_CPT}
THICKNESS_LABEL = {"t0125": "0.125 mm (demo)", "t0183": "0.18288 mm (NCAMP IM7/8552)"}

MATERIAL = "IM7/8552"
SAFETY_FACTOR = 1.5
PLATE = (0.5, 0.5)
