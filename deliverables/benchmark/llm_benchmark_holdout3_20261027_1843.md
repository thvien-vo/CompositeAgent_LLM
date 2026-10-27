# LLM extraction benchmark (holdout3 set, 6 cases, repeat 1)
Run: 2026-10-27 18:43. HF model: openai/gpt-oss-120b; Ollama model: gemma3:4b.

'fully correct' = final CLT input of the agent. 'LLM alone' = first LLM answer without the Python checks against the text (v1 has no checks).

| version | backend | fully correct | LLM alone | material | plies+angles | thickness | loads (6 each) | parse errors | mean s/case |
|---|---|---|---|---|---|---|---|---|---|
| v1 | hf | **0/6** | - | 5/6 | 5/6 | 5/6 | 20/36 | 1 | 0.9 |
| v1 | ollama | **1/6** | - | 5/6 | 3/6 | 3/6 | 32/36 | 0 | 6.1 |
| v3 | hf | **6/6** | 6/6 | 6/6 | 6/6 | 6/6 | 36/36 | 0 | 1.3 |
| v3 | ollama | **5/6** | 2/6 | 5/6 | 5/6 | 5/6 | 30/36 | 1 | 7.3 |

## Failures

- v1/hf rep0 **T1 en, S2-glass [90/0/90], kN/m mixed, Mxy**: Nx=0 (want 900); Ny=0 (want 2400); Mxy=0 (want 0.15)
- v1/hf rep0 **T2 vi, [0/90/±45]s, kN/m + moment**: Nx=0 (want 4000); Mx=0 (want 3)
- v1/hf rep0 **T3 en, aramid [±60]s, negative shear**: Nx=0 (want 300); Nxy=0 (want -75)
- v1/hf rep0 **T4 en, imperial thickness + lbf·in/in moment**: AttributeError: 'NoneType' object has no attribute 'find'
- v1/hf rep0 **T5 vi, angles listed, µm**: Nxy=0 (want 500)
- v1/hf rep0 **T6 en, 'Nx = Ny = 1.2 kN/m'**: Nx=0 (want 1200); Ny=0 (want 1200)
- v1/ollama rep0 **T1 en, S2-glass [90/0/90], kN/m mixed, Mxy**: Mxy=15 (want 0.15)
- v1/ollama rep0 **T2 vi, [0/90/±45]s, kN/m + moment**: angles [0.0, 90.0, 45.0, -45.0] (want [0.0, 90.0, 45.0, -45.0, -45.0, 45.0, 90.0, 0.0]); thickness [0.000125, 0.000125, 0.000125, 0.000125] (want [0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002]); Mx=3000 (want 3)
- v1/ollama rep0 **T3 en, aramid [±60]s, negative shear**: angles [60.0] (want [60.0, -60.0, -60.0, 60.0]); thickness [0.000125] (want [0.000125, 0.000125, 0.000125, 0.000125])
- v1/ollama rep0 **T4 en, imperial thickness + lbf·in/in moment**: angles [0.0, 45.0, 90.0, -45.0] (want [0.0, 45.0, 90.0, -45.0, -45.0, 90.0, 45.0, 0.0]); thickness [7.2e-06, 7.2e-06, 7.2e-06, 7.2e-06] (want [0.00018287999999999998, 0.00018287999999999998, 0.00018287999999999998, 0.00018287999999999998, 0.00018287999999999998, 0.00018287999999999998, 0.00018287999999999998, 0.00018287999999999998]); Nx=5 (want 0); Mx=0 (want 22.2411)
- v1/ollama rep0 **T5 vi, angles listed, µm**: material CFRP (want GFRP)
- v3/ollama rep0 **T5 vi, angles listed, µm**: ValueError: the LLM could not read the problem reliably: the layup '0/30/-30/30/90' has angle(s) [90.0] that are not written in the text
