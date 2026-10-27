# LLM extraction benchmark (dev set, 10 cases, repeat 1)
Run: 2026-10-27 18:33. HF model: openai/gpt-oss-120b; Ollama model: gemma3:4b.

| version | backend | fully correct | material | plies+angles | thickness | loads (6 each) | parse errors | mean s/case |
|---|---|---|---|---|---|---|---|---|
| v3 | ollama | **10/10** | 10/10 | 10/10 | 10/10 | 60/60 | 0 | 6.3 |
| v3 | hf | **10/10** | 10/10 | 10/10 | 10/10 | 60/60 | 0 | 1.5 |

## Failures

