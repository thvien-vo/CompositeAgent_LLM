# LLM extraction benchmark (dev set, 10 cases, repeat 1)
Run: 2026-10-27 19:20. HF model: openai/gpt-oss-120b; Ollama model: gemma3:4b.

'fully correct' = final CLT input of the agent. 'LLM alone' = first LLM answer without the Python checks against the text (v1 has no checks).

| version | backend | fully correct | LLM alone | material | plies+angles | thickness | loads (6 each) | parse errors | mean s/case |
|---|---|---|---|---|---|---|---|---|---|
| v3 | ollama | **10/10** | 4/10 | 10/10 | 10/10 | 10/10 | 60/60 | 0 | 4.0 |

## Failures

