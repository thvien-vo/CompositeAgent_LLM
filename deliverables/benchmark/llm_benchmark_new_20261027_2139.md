# LLM extraction benchmark (new set, 16 cases, repeat 1)
Run: 2026-10-27 21:39. HF model: openai/gpt-oss-120b; Ollama model: gemma3:4b.

'fully correct' = final CLT input of the agent (for the 'new' set also the source of the ply properties; 'must refuse' cases are correct only if the agent stops with a clear error). 'LLM alone' = first LLM answer without the Python checks against the text (v1 has no checks). Component columns count only the cases that must not be refused. 'source' = measured CSV row or ML group as expected (old sets: information only, not in 'fully correct').

| version | backend | fully correct | LLM alone | material | plies+angles | thickness | loads (6 each) | source | refused correctly | parse errors | mean s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v3-before | hf | **5/16** | 7/16 | 14/14 | 14/14 | 14/14 | 81/84 | 8/14 | 0/2 | 0 | 3.3 |

## Failures

- v3-before/hf rep0 **M1 IM7/8552 + load in words**: properties from 'ML group' (want 'IM7/8552')
- v3-before/hf rep0 **M2 brand name, reversed order 'Hexcel 8552 / IM7'**: properties from 'ML group' (want 'IM7/8552')
- v3-before/hf rep0 **M5 T650/5250-5 (S not reported -> ML fill)**: properties from 'ML group' (want 'T650/5250-5')
- v3-before/hf rep0 **M6 T40-800/5215 (nu12 anomalous -> ML fill)**: properties from 'ML group' (want 'T40-800/5215')
- v3-before/hf rep0 **M7 T300/5208 textbook row, moment**: properties from 'ML group' (want 'T300/5208')
- v3-before/hf rep0 **M8 S2-glass/BT250E-6 (GFRP measured)**: properties from 'ML group' (want 'S2-glass/BT250E-6')
- v3-before/hf rep0 **L2 compressive y + shear, in words, kN/m**: Ny=2000 (want -2000)
- v3-before/hf rep0 **L3 English number words + unit words**: Nx=0 (want 1500)
- v3-before/hf rep0 **L4 Vietnamese number word 'hai kN/m'**: Nx=0 (want 2000)
- v3-before/hf rep0 **L7 load without direction -> must refuse**: did not refuse: loads {'Nx': 1000.0, 'Ny': 0.0, 'Nxy': 0.0, 'Mx': 0.0, 'My': 0.0, 'Mxy': 0.0}
- v3-before/hf rep0 **L8 extra load not assigned -> must refuse**: did not refuse: loads {'Nx': 1000.0, 'Ny': 0.0, 'Nxy': 0.0, 'Mx': 0.0, 'My': 0.0, 'Mxy': 0.0}
