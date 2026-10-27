# LLM extraction benchmark (old28 set, 28 cases, repeat 1)
Run: 2026-10-27 21:50. HF model: openai/gpt-oss-120b; Ollama model: gemma3:4b.

'fully correct' = final CLT input of the agent (for the 'new' set also the source of the ply properties; 'must refuse' cases are correct only if the agent stops with a clear error). 'LLM alone' = first LLM answer without the Python checks against the text (v1 has no checks). Component columns count only the cases that must not be refused. 'source' = measured CSV row or ML group as expected (old sets: information only, not in 'fully correct').

| version | backend | fully correct | LLM alone | material | plies+angles | thickness | loads (6 each) | source | refused correctly | parse errors | mean s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v4-after | ollama | **24/28** | 9/28 | 25/28 | 24/28 | 25/28 | 150/168 | 25/28 | 0/0 | 3 | 4.2 |

## Failures

- v4-after/ollama rep0 **D7 en, different ply thickness, µm, pure bending**: ValueError: the LLM could not read the problem reliably: cannot read the stacking sequence '0/90/90/0/200': ply angle 200.0 outside -90..90 in '0/90/90/0/200'
- v4-after/ollama rep0 **H6 en, fiberglass 5 plies different thickness**: ValueError: the LLM could not read the problem reliably: 5 ply thicknesses were given but the layup '0/45/-45/0/45/-45/0' has 7 plies
- v4-after/ollama rep0 **N2 vi, 6 plies listed, total thickness, moment**: ValueError: the LLM could not read the problem reliably: 7 ply thicknesses were given but the layup '0/60/-60/-60/60/0' has 6 plies
- v4-after/ollama rep0 **T5 vi, angles listed, µm**: angles [0.0, 30.0, -30.0, 30.0] (want [30.0, -30.0, -30.0, 30.0])
