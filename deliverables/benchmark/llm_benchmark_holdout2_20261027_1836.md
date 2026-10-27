# LLM extraction benchmark (holdout2 set, 6 cases, repeat 1)
Run: 2026-10-27 18:36. HF model: openai/gpt-oss-120b; Ollama model: gemma3:4b.

| version | backend | fully correct | material | plies+angles | thickness | loads (6 each) | parse errors | mean s/case |
|---|---|---|---|---|---|---|---|---|
| v1 | hf | **0/6** | 6/6 | 6/6 | 6/6 | 23/36 | 0 | 1.2 |
| v1 | ollama | **0/6** | 4/6 | 4/6 | 2/6 | 29/36 | 0 | 5.9 |
| v3 | hf | **6/6** | 6/6 | 6/6 | 6/6 | 36/36 | 0 | 1.4 |
| v3 | ollama | **3/6** | 5/6 | 5/6 | 5/6 | 26/36 | 1 | 7.4 |

## Failures

- v1/hf rep0 **N1 en, [..]T notation, kN/m**: Nx=0 (want 5000); Ny=0 (want 5000)
- v1/hf rep0 **N2 vi, 6 plies listed, total thickness, moment**: Nx=0 (want 600); Mx=0 (want 1.2)
- v1/hf rep0 **N3 en, Kevlar [0/90]s, shear + twisting moment**: Nxy=0 (want 150); Mxy=0 (want 0.05)
- v1/hf rep0 **N4 en, graphite, load in words (no symbol)**: Nx=0 (want 2000)
- v1/hf rep0 **N5 vi, 3 plies, thickness per ply**: Nx=0 (want 2500); Ny=0 (want 400)
- v1/hf rep0 **N6 en, [0/±45/90]s, total thickness, 4 loads**: Nx=0 (want -2000); Ny=0 (want 1000); Nxy=0 (want 500); Mx=0 (want 0.4)
- v1/ollama rep0 **N1 en, [..]T notation, kN/m**: material CFRP (want GFRP); thickness [0.000125, 0.000125, 0.000125, 0.000125] (want [0.00025, 0.00025, 0.00025, 0.00025])
- v1/ollama rep0 **N2 vi, 6 plies listed, total thickness, moment**: thickness [9e-05, 9e-05, 9e-05, 9e-05, 9e-05, 9e-05] (want [0.00015, 0.00015, 0.00015, 0.00015, 0.00015, 0.00015])
- v1/ollama rep0 **N3 en, Kevlar [0/90]s, shear + twisting moment**: angles [0.0, 90.0] (want [0.0, 90.0, 90.0, 0.0]); thickness [0.0001, 0.0001] (want [0.0001, 0.0001, 0.0001, 0.0001])
- v1/ollama rep0 **N4 en, graphite, load in words (no symbol)**: material GFRP (want CFRP); Nx=0.002 (want 2000)
- v1/ollama rep0 **N5 vi, 3 plies, thickness per ply**: Nx=2.5 (want 2500); Ny=0.4 (want 400)
- v1/ollama rep0 **N6 en, [0/±45/90]s, total thickness, 4 loads**: angles [0.0, 45.0, 90.0] (want [0.0, 45.0, -45.0, 90.0, 90.0, -45.0, 45.0, 0.0]); thickness [0.00016, 0.00016, 0.00016] (want [0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002]); Nx=0.002 (want -2000); Ny=0.001 (want 1000); Nxy=0.0005 (want 500); Mx=0.0004 (want 0.4)
- v3/ollama rep0 **N1 en, [..]T notation, kN/m**: Nx=5e+06 (want 5000); Ny=5e+06 (want 5000)
- v3/ollama rep0 **N4 en, graphite, load in words (no symbol)**: Nx=0 (want 2000); Nxy=2000 (want 0)
- v3/ollama rep0 **N5 vi, 3 plies, thickness per ply**: ValueError: the LLM could not read the problem reliably: the layup '0/45/0/90/0' has angle(s) [45.0] that are not written in the text
