# LLM extraction benchmark (old28 set, 28 cases, repeat 1)
Run: 2026-10-27 21:37. HF model: openai/gpt-oss-120b; Ollama model: gemma3:4b.

'fully correct' = final CLT input of the agent (for the 'new' set also the source of the ply properties; 'must refuse' cases are correct only if the agent stops with a clear error). 'LLM alone' = first LLM answer without the Python checks against the text (v1 has no checks). Component columns count only the cases that must not be refused. 'source' = measured CSV row or ML group as expected (old sets: information only, not in 'fully correct').

| version | backend | fully correct | LLM alone | material | plies+angles | thickness | loads (6 each) | source | refused correctly | parse errors | mean s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v3-before | ollama | **24/28** | 10/28 | 25/28 | 25/28 | 25/28 | 148/168 | 20/28 | 0/0 | 3 | 4.0 |

## Failures

- v3-before/ollama rep0 **H6 en, fiberglass 5 plies different thickness**: ValueError: the LLM could not read the problem reliably: 5 ply thicknesses were given but the layup '0/45/-45/0/45/45/-45' has 7 plies
- v3-before/ollama rep0 **N4 en, graphite, load in words (no symbol)**: Nx=0 (want 2000); Nxy=2000 (want 0)
- v3-before/ollama rep0 **N5 vi, 3 plies, thickness per ply**: ValueError: the LLM could not read the problem reliably: the layup '0/45/0/90/0' has angle(s) [45.0] that are not written in the text
- v3-before/ollama rep0 **T5 vi, angles listed, µm**: ValueError: the LLM could not read the problem reliably: the layup '0/30/-30/30/90' has angle(s) [90.0] that are not written in the text
