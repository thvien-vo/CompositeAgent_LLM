# LLM extraction benchmark (dev set, 10 cases, repeat 1)
Run: 2026-10-27 18:21. HF model: openai/gpt-oss-120b; Ollama model: gemma3:4b.

| version | backend | fully correct | material | plies+angles | thickness | loads (6 each) | parse errors | mean s/case |
|---|---|---|---|---|---|---|---|---|
| v1 | ollama | **4/10** | 8/10 | 5/10 | 4/10 | 55/60 | 0 | 11.4 |
| v2 | ollama | **4/10** | 8/10 | 9/10 | 8/10 | 51/60 | 0 | 7.2 |

## Failures

- v1/ollama rep0 **D2 en, [..]s 8 plies (= demo.py case)**: angles [0.0, 45.0, -45.0, 90.0] (want [0.0, 45.0, -45.0, 90.0, 90.0, -45.0, 45.0, 0.0]); thickness [0.000125, 0.000125, 0.000125, 0.000125] (want [0.000125, 0.000125, 0.000125, 0.000125, 0.000125, 0.000125, 0.000125, 0.000125])
- v1/ollama rep0 **D3 en, [..]2s, kN/m, negative load**: material CFRP (want GFRP); angles [0.0, 90.0] (want [0.0, 90.0, 0.0, 90.0, 90.0, 0.0, 90.0, 0.0]); thickness [0.0002, 0.0002] (want [0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002])
- v1/ollama rep0 **D5 vi, [0/±45]s, decimal comma, moment**: material CFRP (want GFRP); angles [0.0, 45.0, -45.0, 90.0] (want [0.0, 45.0, -45.0, -45.0, 45.0, 0.0]); thickness [0.00015, 0.00015, 0.00015, 0.00015] (want [0.00015, 0.00015, 0.00015, 0.00015, 0.00015, 0.00015])
- v1/ollama rep0 **D6 en, total thickness, N/mm**: angles [0.0, 90.0, 45.0, -45.0] (want [0.0, 90.0, 45.0, -45.0, -45.0, 45.0, 90.0, 0.0]); thickness [0.000125, 0.000125, 0.000125, 0.000125] (want [0.00015, 0.00015, 0.00015, 0.00015, 0.00015, 0.00015, 0.00015, 0.00015]); Nx=1.5 (want 1500); Ny=0.5 (want 500)
- v1/ollama rep0 **D8 en, T300/5208, [±30]2s, negative shear**: angles [30.0, 30.0] (want [30.0, -30.0, 30.0, -30.0, -30.0, 30.0, -30.0, 30.0]); thickness [0.000127, 0.000127] (want [0.000127, 0.000127, 0.000127, 0.000127, 0.000127, 0.000127, 0.000127, 0.000127]); Nx=-250 (want 0); Nxy=0 (want -250)
- v1/ollama rep0 **D9 vi, 5 plies list, kN/m, N·mm/m**: thickness [0.000125, 0.000125, 0.000125, 0.000125, 0.000125] (want [0.00025, 0.00025, 0.00025, 0.00025, 0.00025]); Mxy=1500 (want 1.5)
- v2/ollama rep0 **D3 en, [..]2s, kN/m, negative load**: material CFRP (want GFRP)
- v2/ollama rep0 **D5 vi, [0/±45]s, decimal comma, moment**: material CFRP (want GFRP); Ny=300 (want 0); Nxy=5 (want 300)
- v2/ollama rep0 **D6 en, total thickness, N/mm**: thickness [0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002] (want [0.00015, 0.00015, 0.00015, 0.00015, 0.00015, 0.00015, 0.00015, 0.00015])
- v2/ollama rep0 **D7 en, different ply thickness, µm, pure bending**: Ny=-4 (want 0); Nxy=1 (want 0); My=0 (want -4); Mxy=0 (want 1)
- v2/ollama rep0 **D8 en, T300/5208, [±30]2s, negative shear**: angles [30.0, -30.0, -30.0, 30.0] (want [30.0, -30.0, 30.0, -30.0, -30.0, 30.0, -30.0, 30.0]); thickness [0.000127, 0.000127, 0.000127, 0.000127] (want [0.000127, 0.000127, 0.000127, 0.000127, 0.000127, 0.000127, 0.000127, 0.000127]); Nx=-250 (want 0); Nxy=0 (want -250)
- v2/ollama rep0 **D9 vi, 5 plies list, kN/m, N·mm/m**: Nxy=1.5e+06 (want 0)
