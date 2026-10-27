# LLM extraction benchmark (holdout set, 6 cases, repeat 1)
Run: 2026-10-27 18:30. HF model: openai/gpt-oss-120b; Ollama model: gemma3:4b.

| version | backend | fully correct | material | plies+angles | thickness | loads (6 each) | parse errors | mean s/case |
|---|---|---|---|---|---|---|---|---|
| v1 | hf | **0/6** | 6/6 | 5/6 | 5/6 | 25/36 | 0 | 1.4 |
| v1 | ollama | **2/6** | 5/6 | 4/6 | 2/6 | 31/36 | 0 | 6.1 |
| v3 | hf | **6/6** | 6/6 | 6/6 | 6/6 | 36/36 | 0 | 1.6 |
| v3 | ollama | **4/6** | 6/6 | 5/6 | 4/6 | 36/36 | 0 | 6.5 |

## Failures

- v1/hf rep0 **H1 en, IM7/8552 [45/0/-45/90]2s 16 plies, kN/m, Mxy**: angles [45.0, 0.0, -45.0, 90.0, 90.0, -45.0, 0.0, 45.0] (want [45.0, 0.0, -45.0, 90.0, 45.0, 0.0, -45.0, 90.0, 90.0, -45.0, 0.0, 45.0, 90.0, -45.0, 0.0, 45.0]); thickness [0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183] (want [0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183]); Nx=0 (want 25000); Mxy=0 (want -0.8)
- v1/hf rep0 **H2 vi, Kevlar, total thickness 0,8 mm**: Ny=0 (want 750); Nxy=0 (want -120)
- v1/hf rep0 **H3 en, imperial units (in, lbf/in)**: Nx=0 (want 17512.7)
- v1/hf rep0 **H4 en, compact style, compression + moment**: Nx=0 (want -800); Nxy=0 (want 200); Mx=0 (want 0.3)
- v1/hf rep0 **H5 vi, [0/90]s, only moment in N·mm/mm**: Mx=0 (want 2.5)
- v1/hf rep0 **H6 en, fiberglass 5 plies different thickness**: Nx=0 (want 4000); Ny=0 (want 1000)
- v1/ollama rep0 **H1 en, IM7/8552 [45/0/-45/90]2s 16 plies, kN/m, Mxy**: angles [0.0, 45.0, -45.0, 90.0] (want [45.0, 0.0, -45.0, 90.0, 45.0, 0.0, -45.0, 90.0, 90.0, -45.0, 0.0, 45.0, 90.0, -45.0, 0.0, 45.0]); thickness [0.000183, 0.000183, 0.000183, 0.000183] (want [0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183, 0.000183]); Mxy=-800 (want -0.8)
- v1/ollama rep0 **H2 vi, Kevlar, total thickness 0,8 mm**: thickness [4e-05, 4e-05, 4e-05, 4e-05] (want [0.0002, 0.0002, 0.0002, 0.0002]); Nx=750 (want 0); Ny=-120 (want 750); Nxy=0 (want -120)
- v1/ollama rep0 **H3 en, imperial units (in, lbf/in)**: material CFRP (want GFRP); thickness [1.524e-06, 1.524e-06, 1.524e-06] (want [0.000127, 0.000127, 0.000127]); Nx=9.80665 (want 17512.7)
- v1/ollama rep0 **H5 vi, [0/90]s, only moment in N·mm/mm**: angles [0.0] (want [0.0, 90.0, 90.0, 0.0]); thickness [0.000125] (want [0.000125, 0.000125, 0.000125, 0.000125])
- v3/ollama rep0 **H2 vi, Kevlar, total thickness 0,8 mm**: thickness [0.0008, 0.0008, 0.0008, 0.0008] (want [0.0002, 0.0002, 0.0002, 0.0002])
- v3/ollama rep0 **H6 en, fiberglass 5 plies different thickness**: angles [0.0, 45.0, -45.0, 0.0, 45.0, -45.0, 0.0] (want [45.0, -45.0, 0.0, -45.0, 45.0]); thickness [0.0003, 0.0003, 0.0003, 0.0003, 0.0003, 0.0003, 0.0003] (want [0.0003, 0.0003, 0.0005, 0.0003, 0.0003])
