# LLM extraction benchmark (holdout2 set, 6 cases, repeat 1)
Run: 2026-10-27 19:21. HF model: openai/gpt-oss-120b; Ollama model: gemma3:4b.

'fully correct' = final CLT input of the agent. 'LLM alone' = first LLM answer without the Python checks against the text (v1 has no checks).

| version | backend | fully correct | LLM alone | material | plies+angles | thickness | loads (6 each) | parse errors | mean s/case |
|---|---|---|---|---|---|---|---|---|---|
| v3 | ollama | **4/6** | 1/6 | 5/6 | 5/6 | 5/6 | 28/36 | 1 | 4.1 |

## Failures

- v3/ollama rep0 **N4 en, graphite, load in words (no symbol)**: Nx=0 (want 2000); Nxy=2000 (want 0)
- v3/ollama rep0 **N5 vi, 3 plies, thickness per ply**: ValueError: the LLM could not read the problem reliably: the layup '0/45/0/90/0' has angle(s) [45.0] that are not written in the text
