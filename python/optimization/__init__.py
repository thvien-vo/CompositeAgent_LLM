"""
optimization - stacking sequence optimization of composite laminates (Layer 1, no LLM).

Modules
  clt         Classical Laminate Theory (numpy, vectorised), same conventions as matlab/clt_engine.m
  failure     reserve factors: Max Stress, Tsai-Wu, Max Strain
  buckling    simply supported plate: closed-form biaxial compression, Ritz (adds shear)
  material    ply properties (measured CSV row or ML prediction, missing strengths filled by ML)
  rules       design rules (symmetry, balance, 10 % rule, contiguity), encodings, repair
  evaluate    Problem definition + batch evaluator (reserve factors, safety margin, cache, counters)
  exhaustive  exact search (enumeration / count-level enumeration) for small design spaces
  ga          single-objective genetic algorithm
  nsga2       NSGA-II (pymoo) with repair
  api         optimize(...) -> OptimizationResult  (entry point for Layer 2 / Layer 3)
  matlab_check  re-check of designs with matlab/clt_engine.m

Units: SI everywhere (Pa, m, N/m). Loads Nx, Ny, Nxy: tension positive, compression negative.
"""
_EXPORTS = {"Material": "material", "get_material": "material", "Plate": "evaluate", "Problem": "evaluate",
            "Rules": "rules", "optimize": "api", "OptimizationResult": "api", "make_problem": "api", "quasi_isotropic": "api"}


def __getattr__(name):  # lazy imports: "from optimization import optimize" without loading everything up front
    if name in _EXPORTS:
        import importlib
        return getattr(importlib.import_module(f".{_EXPORTS[name]}", __name__), name)
    raise AttributeError(name)
