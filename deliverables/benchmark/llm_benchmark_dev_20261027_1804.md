# LLM extraction benchmark (dev set, 10 cases, repeat 1)
Run: 2026-10-27 18:04. HF model: openai/gpt-oss-120b; Ollama model: gemma3:4b.

| version | backend | fully correct | material | plies+angles | thickness | loads (6 each) | parse errors | mean s/case |
|---|---|---|---|---|---|---|---|---|
| v1 | hf | **0/10** | 10/10 | 8/10 | 8/10 | 33/60 | 0 | 1.7 |
| v2 | hf | **10/10** | 10/10 | 10/10 | 10/10 | 60/60 | 0 | 4.2 |

## Failures

- v1/hf rep0 **D1 en, 4 plies list, mm**: Nx=0 (want 1000); Ny=0 (want 500); Nxy=0 (want 100)
- v1/hf rep0 **D2 en, [..]s 8 plies (= demo.py case)**: Nx=0 (want 1000); Ny=0 (want 500); Nxy=0 (want 100)
- v1/hf rep0 **D3 en, [..]2s, kN/m, negative load**: angles [0.0, 90.0, 90.0, 0.0] (want [0.0, 90.0, 0.0, 90.0, 90.0, 0.0, 90.0, 0.0]); thickness [0.0002, 0.0002, 0.0002, 0.0002] (want [0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002]); Nx=0 (want 2000); Ny=0 (want -1500)
- v1/hf rep0 **D4 en, Kevlar, thickness in m, moment**: Nx=0 (want 500); Mx=0 (want 2)
- v1/hf rep0 **D5 vi, [0/±45]s, decimal comma, moment**: Nx=0 (want 1200); Nxy=0 (want 300); My=0 (want 5)
- v1/hf rep0 **D6 en, total thickness, N/mm**: Nx=0 (want 1500); Ny=0 (want 500)
- v1/hf rep0 **D7 en, different ply thickness, µm, pure bending**: Mx=0 (want 10); My=0 (want -4); Mxy=0 (want 1)
- v1/hf rep0 **D8 en, T300/5208, [±30]2s, negative shear**: angles [30.0, -30.0, 30.0, -30.0] (want [30.0, -30.0, 30.0, -30.0, -30.0, 30.0, -30.0, 30.0]); thickness [0.000127, 0.000127, 0.000127, 0.000127] (want [0.000127, 0.000127, 0.000127, 0.000127, 0.000127, 0.000127, 0.000127, 0.000127]); Nxy=0 (want -250)
- v1/hf rep0 **D9 vi, 5 plies list, kN/m, N·mm/m**: Nx=0 (want 3000); Mxy=0 (want 1.5)
- v1/hf rep0 **D10 en, aramid 2 plies, all 6 loads**: Nx=0 (want 800); Ny=0 (want 200); Nxy=0 (want 50); Mx=0 (want 0.5); My=0 (want 0.2); Mxy=0 (want 0.1)
