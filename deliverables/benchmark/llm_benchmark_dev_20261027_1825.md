# LLM extraction benchmark (dev set, 10 cases, repeat 1)
Run: 2026-10-27 18:25. HF model: openai/gpt-oss-120b; Ollama model: gemma3:4b.

| version | backend | fully correct | material | plies+angles | thickness | loads (6 each) | parse errors | mean s/case |
|---|---|---|---|---|---|---|---|---|
| v2 | ollama | **9/10** | 10/10 | 9/10 | 9/10 | 60/60 | 0 | 5.9 |
| v2 | hf | **10/10** | 10/10 | 10/10 | 10/10 | 60/60 | 0 | 1.5 |

## Failures

- v2/ollama rep0 **D7 en, different ply thickness, µm, pure bending**: angles [0.0, 45.0, -45.0] (want [0.0, 90.0, 90.0, 0.0]); thickness [0.00019999999999999998, 0.00019999999999999998, 0.00019999999999999998] (want [0.0002, 0.0001, 0.0001, 0.0002])
