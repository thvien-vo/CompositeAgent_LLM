"""
design_cases.py - test requests for the "design a laminate in words" function, written BEFORE the code (30/10/2026).

Each case: (id, text, expected). expected["kind"] is what the request classifier must answer:
  "design"  -> expected["spec"] is the design specification the agent must read from the text (SI units);
  "refuse"  -> the agent must stop with a clear message (expected["why"] says why);
  the optimum itself is NOT written here: the benchmark compares the agent's answer with a direct call of
  optimization.optimize(...) with the parameters of expected["spec"].
Defaults when the text does not say otherwise: safety factor 1.5, plate a = b = 0.5 m, ply thickness 0.125 mm,
angles {0, +-45, 90}, the 4 design rules on (symmetric, balanced, >= 10 % per direction, <= 4 identical plies in a
row), 8-64 plies, objective "fewest plies"; with a shear load both shear directions are checked unless the text says
that the shear acts in one direction only.
"""


def S(material, row, Nx=0.0, Ny=0.0, Nxy=0.0, sf=1.5, t=0.125e-3, a=0.5, b=0.5, n_min=8, n_max=64, n_fixed=None,
      objective="min_plies", both=None, max_contiguous=4, min_fraction=0.10, note=""):
    """Expected design specification. material = group (CFRP / GFRP / KEVLAR); row = CSV row whose measured
    properties must be used ("" = ML prediction for the group). both = shear checked in both directions
    (default: True when Nxy != 0)."""
    if both is None:
        both = Nxy != 0
    if n_fixed is not None:
        n_min = n_max = n_fixed
    return {"kind": "design", "spec": {
        "material": material, "row": row, "loads": {"Nx": float(Nx), "Ny": float(Ny), "Nxy": float(Nxy)},
        "safety_factor": sf, "ply_thickness": t, "a": a, "b": b, "n_min": n_min, "n_max": n_max,
        "objective": objective, "shear_both": both, "max_contiguous": max_contiguous, "min_fraction": min_fraction},
        "note": note}


def R(why):
    return {"kind": "refuse", "why": why}


CASES = [
    # ---------------------------------------------------------------- designs that must be solved
    ("DS1 EN named material, tension, all defaults",
     "Design the lightest IM7/8552 laminate for a tensile load Nx = 600 kN/m.",
     S("CFRP", "IM7/8552", Nx=600e3)),
    ("DS2 VI group, biaxial compression, plate size",
     "Thiết kế tấm carbon/epoxy nhẹ nhất chịu nén Nx = -50 kN/m, Ny = -20 kN/m, kích thước tấm 0,6 m × 0,4 m.",
     S("CFRP", "", Nx=-50e3, Ny=-20e3, a=0.6, b=0.4)),
    ("DS3 EN named material, pure shear, safety factor 2 (both shear directions by default)",
     "Find the optimum stacking sequence for an AS4/8552 panel under a shear load Nxy = 80 kN/m, safety factor 2.",
     S("CFRP", "AS4/8552", Nxy=80e3, sf=2.0)),
    ("DS4 EN shear in one direction only",
     "Optimise the stacking sequence of an IM7/8552 plate for Nxy = 60 kN/m; the shear always acts in the positive "
     "direction.",
     S("CFRP", "IM7/8552", Nxy=60e3, both=False)),
    ("DS5 VI glass group, tension + shear, ply thickness",
     "Tối ưu thứ tự xếp lớp cho tấm sợi thủy tinh/epoxy chịu kéo Nx = 200 kN/m và lực cắt Nxy = 50 kN/m, mỗi lớp "
     "dày 0,2 mm.",
     S("GFRP", "", Nx=200e3, Nxy=50e3, t=0.2e-3)),
    ("DS6 EN fixed ply count, largest margin",
     "Which 24-ply IM7/8552 laminate has the largest safety margin under Nx = -100 kN/m and Nxy = 30 kN/m?",
     S("CFRP", "IM7/8552", Nx=-100e3, Nxy=30e3, n_fixed=24, objective="max_margin")),
    ("DS7 VI fixed ply count, strongest",
     "Với đúng 16 lớp, hãy tìm cách xếp lớp bền nhất cho tấm carbon/epoxy chịu nén Nx = -30 kN/m.",
     S("CFRP", "", Nx=-30e3, n_fixed=16, objective="max_margin")),
    ("DS8 EN loads in words, N/mm, number word",
     "Design a carbon/epoxy laminate for a compressive load of 20 N/mm in the x direction and a shear force of "
     "five N/mm.",
     S("CFRP", "", Nx=-20e3, Nxy=5e3)),
    ("DS9 EN ply-count range",
     "Lightest T700GC/TC1225 laminate with between 16 and 40 plies for Nx = 300 kN/m, Ny = 150 kN/m.",
     S("CFRP", "T700GC/TC1225", Nx=300e3, Ny=150e3, n_min=16, n_max=40)),
    ("DS10 EN Kevlar group, plate in mm, ply thickness",
     "Design a Kevlar/epoxy panel 400 mm x 300 mm with 0.15 mm plies for Ny = -10 kN/m.",
     S("KEVLAR", "", Ny=-10e3, t=0.15e-3, a=0.4, b=0.3)),
    ("DS11 EN infeasible within the ply range",
     "Design the lightest IM7/8552 laminate with at most 24 plies for Nx = 2000 kN/m and Ny = 1000 kN/m.",
     S("CFRP", "IM7/8552", Nx=2000e3, Ny=1000e3, n_max=24, note="expected: no feasible design within 24 plies")),
    ("DS12 VI safety factor, NCAMP ply thickness, shear in one direction",
     "Thiết kế tấm IM7/8552 ít lớp nhất, hệ số an toàn 2, độ dày lớp 0,18288 mm, chịu Nx = -60 kN/m và "
     "Nxy = 20 kN/m; lực cắt chỉ theo một chiều.",
     S("CFRP", "IM7/8552", Nx=-60e3, Nxy=20e3, sf=2.0, t=0.18288e-3, both=False)),
    ("DS13 EN design rule changed (at most 3 identical plies in a row)",
     "Design the lightest AS4/8552 laminate for Nx = 150 kN/m and Nxy = 40 kN/m, with no more than 3 plies of the "
     "same angle in a row.",
     S("CFRP", "AS4/8552", Nx=150e3, Nxy=40e3, max_contiguous=3)),
    ("DS20 EN weak wording (no 'design' word): 'I need a laminate that can carry ...'",
     "I need a glass/epoxy laminate that can carry Nx = 50 kN/m with a safety factor of 1.5.",
     S("GFRP", "", Nx=50e3)),
    ("DS21 VI named Kevlar row, shear + tension",
     "Thiết kế tấm Kevlar 49/epoxy nhẹ nhất chịu lực cắt Nxy = 15 kN/m và kéo Nx = 40 kN/m.",
     S("KEVLAR", "Kevlar 49/epoxy", Nx=40e3, Nxy=15e3)),
    # ---------------------------------------------------------------- requests that must be refused
    ("DS14 moment in a design request",
     "Design the lightest carbon/epoxy laminate for a bending moment Mx = 50 N.m/m.",
     R("moments are not part of the optimisation (in-plane loads only)")),
    ("DS15 unsupported objective (stiffness)",
     "Design the stiffest IM7/8552 laminate for Nx = 100 kN/m.",
     R("only 'fewest plies' and 'largest margin for a given ply count' are supported")),
    ("DS16 no material",
     "Design the lightest laminate for Nx = 100 kN/m and Nxy = 20 kN/m.",
     R("no material or fibre type given")),
    ("DS17 load without direction",
     "Design a carbon/epoxy laminate for a load of 100 kN/m.",
     R("the direction of the load is not given")),
    ("DS18 unsupported ply angles",
     "Design a carbon/epoxy laminate with 0 and ±30° plies for Nx = 100 kN/m.",
     R("only 0, +-45 and 90 degree plies are supported")),
    ("DS19 stacking sequence given AND a design asked (conflict)",
     "Optimise the laminate [0/90]2s for Nx = 1 kN/m.",
     R("the text gives a stacking sequence and asks for a design")),
]
