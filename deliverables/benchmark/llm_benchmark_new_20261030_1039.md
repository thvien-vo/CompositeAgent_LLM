# LLM extraction benchmark (new set, 16 cases, repeat 1)
Run: 2026-10-30 10:39. HF model: openai/gpt-oss-120b; Ollama model: gemma3:4b.

'fully correct' = final CLT input of the agent (for the 'new' set also the source of the ply properties; 'must refuse' cases are correct only if the agent stops with a clear error). 'LLM alone' = first LLM answer without the Python checks against the text (v1 has no checks). Component columns count only the cases that must not be refused. 'source' = measured CSV row or ML group as expected (old sets: information only, not in 'fully correct').

| version | backend | fully correct | LLM alone | material | plies+angles | thickness | loads (6 each) | source | refused correctly | parse errors | mean s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v5 | ollama | **16/16** | 3/16 | 14/14 | 14/14 | 14/14 | 84/84 | 14/14 | 2/2 | 0 | 2.9 |

## Failures

