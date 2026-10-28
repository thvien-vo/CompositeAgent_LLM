# LLM extraction benchmark (old28 set, 28 cases, repeat 1)
Run: 2026-10-28 15:45. HF model: openai/gpt-oss-120b; Ollama model: gemma3:4b.

'fully correct' = final CLT input of the agent (for the 'new' set also the source of the ply properties; 'must refuse' cases are correct only if the agent stops with a clear error). 'LLM alone' = first LLM answer without the Python checks against the text (v1 has no checks). Component columns count only the cases that must not be refused. 'source' = measured CSV row or ML group as expected (old sets: information only, not in 'fully correct').

| version | backend | fully correct | LLM alone | material | plies+angles | thickness | loads (6 each) | source | refused correctly | parse errors | mean s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v5 | ollama | **28/28** | 9/28 | 28/28 | 28/28 | 28/28 | 168/168 | 28/28 | 0/0 | 0 | 3.9 |

## Failures

