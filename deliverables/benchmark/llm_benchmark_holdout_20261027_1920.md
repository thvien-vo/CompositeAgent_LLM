# LLM extraction benchmark (holdout set, 6 cases, repeat 1)
Run: 2026-10-27 19:20. HF model: openai/gpt-oss-120b; Ollama model: gemma3:4b.

'fully correct' = final CLT input of the agent. 'LLM alone' = first LLM answer without the Python checks against the text (v1 has no checks).

| version | backend | fully correct | LLM alone | material | plies+angles | thickness | loads (6 each) | parse errors | mean s/case |
|---|---|---|---|---|---|---|---|---|---|
| v3 | ollama | **5/6** | 3/6 | 5/6 | 5/6 | 5/6 | 30/36 | 1 | 3.9 |

## Failures

- v3/ollama rep0 **H6 en, fiberglass 5 plies different thickness**: ValueError: the LLM could not read the problem reliably: 5 ply thicknesses were given but the layup '0/45/-45/0/45/45/-45' has 7 plies
