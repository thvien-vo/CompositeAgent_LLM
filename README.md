# CompositeAgent

An AI agent for the analysis of composite laminates. An engineer writes a laminate problem in plain English or
Vietnamese; the agent reads it with a large language model (LLM), obtains the ply properties (measured data or a
machine-learning prediction), computes the laminate with Classical Laminate Theory (CLT) in MATLAB and explains the
result. A retrieval-augmented generation (RAG) module answers questions about the material database and cites the
source report and page. An optimisation module chooses the stacking sequence of a laminate (Layer 1, no LLM), and the
agent can use it to **design a laminate from a request in words** ("Design the lightest IM7/8552 laminate for
Nx = -20 kN/m"): the optimum is checked again and explained.

Author: **Võ Nguyễn Thanh Viên**, Ho Chi Minh City University of Technology (HCMUT).
Supervisor: **Dr. Sy-Ngoc Nguyen**, Faculty of Mechanical Engineering, HCMUT.
Partner: **Prof. Masaaki Nishikawa**, Kyoto University.

## Design principle

The LLM only reads and explains. Every number is computed and checked by deterministic code:

- the LLM copies values and units from the text into a fixed JSON schema;
- Python expands the stacking sequence, converts the units and checks every value against the original text
  (a value must be written there with its unit; a load without a clear direction is refused, not guessed);
- MATLAB computes the laminate; the explanation is accepted only if every number in it matches the CLT data.

## Architecture

```
 problem text ──► 1 LLM reads ──► Python checks ──► 2 ply properties ──► 3 MATLAB CLT ──► 4 LLM explains
 (EN / VI)        fixed JSON      layup, units,      measured CSV values   ABD, ply stresses,  + guardrail:
                  schema          values vs text     or ML prediction      Max Stress FI       numbers must match
```

| Step | Files | What it does |
|---|---|---|
| 1. Extraction | `python/llm.py`, `python/schemas.py` | `openai/gpt-oss-120b` through Hugging Face Inference Providers (default); automatic fallback to `gemma3:4b` on Ollama when offline. Schema-enforced JSON, one retry with the list of problems found. |
| Checks | `python/layup.py`, `python/numwords.py`, `python/llm.py` | Layup expansion (`[0/90]2s` → 8 plies), unit conversion, number words (EN / VI), load direction from the wording, ply count and thickness consistency. |
| 2. Properties | `python/materials.py`, `python/ml.py`, `python/model/` | Measured values when the text names one of the 25 materials of the database (fibre **and** matrix must match one row); otherwise Random Forest predictions for the material group (CFRP, GFRP, Kevlar). |
| 3. CLT | `matlab/clt_engine.m`, `python/matlab_clt.py` | Q → Q̄ → ABD → mid-plane strain and curvature → ply stresses → Max Stress failure index. |
| 4. Explanation | `python/llm.py` | Explanation in English or Vietnamese; every number must be in the CLT data and be named as what it is (meaning check, English and Vietnamese); one retry, else a pre-built explanation. |
| RAG | `python/rag.py` | `nomic-embed-text` embeddings + cosine similarity + exact material-name match; Python looks up exact values and rankings and prints the sources; each report number must be the source of its material. |
| Request type | `python/router.py` | Python rules decide: analysis of a given laminate, design request, or material question; the LLM only confirms weak wording ("I need a laminate that can carry ..."); unclear text is refused with a hint. |
| Design | `python/design.py` | Design request in words → LLM copies the values, Python checks them against the text and prints the defaults used → optimiser (exact search, else GA + local search) → checks (MATLAB `clt_engine.m`, independent polynomial Ritz buckling, smallest quasi-isotropic laminate) → explanation with the same checks. |
| Optimisation | `python/optimization/` | Layer 1 stacking-sequence optimisation: Max Stress, Tsai-Wu, Rayleigh-Ritz buckling with D16, D26 and Nxy (optionally for both shear directions); exact search with proven bounds, genetic algorithm (GA), GA + local search, NSGA-II. |

## Repository layout

```
run_demo.bat                    one-command demo (environment check, reference check, agent, RAG, design)
python/
  main.py                       agent pipeline (command line)
  router.py                     request type: analysis / design / material question
  design.py                     design a laminate from a request in words (command line)
  design_cases.py, benchmark_design.py, test_design_checks.py   design test requests, benchmark, checks
  llm.py, schemas.py            LLM extraction, explanation and guardrails
  layup.py, numwords.py         deterministic parsing helpers
  materials.py, ml.py, model/   measured properties and Random Forest models
  composite_lamina_dataset_v4.csv   25 unidirectional lamina systems with their sources
  matlab_clt.py                 Python - MATLAB bridge
  rag.py                        material questions with sources
  demo.py                       reference check (prints PASS / FAIL)
  run_demo.py                   demo driver used by run_demo.bat
  benchmark_llm.py, benchmark_rag.py, test_checks.py, test_ml.py, evaluate_model.py, check_ollama.py
  llm_v1_baseline.py, llm_hf_old.py   earlier versions, kept for comparison
  optimization/                 Layer 1 optimisation: CLT (numpy), failure criteria, buckling, design rules,
                                exhaustive search, GA, NSGA-II, experiments, pytest suite
matlab/clt_engine.m             CLT engine
deliverables/
  benchmark/                    benchmark results of the LLM and RAG steps
  optimization/                 Layer 1 report (BAO_CAO_LOP1.md; section 9 is an English summary),
                                result tables (results/) and figures (figures/)
  demo_log_backup_*.txt         logs of complete demo runs
PROGRESS.md                     progress log (Vietnamese)
```

## Requirements

- Windows 10 / 11 (developed and tested on Windows 11).
- Python 3.12 (tested with 3.12.10) in a virtual environment `venv\` at the repository root; the batch files call
  `venv\Scripts\python.exe`.
- MATLAB (tested with R2025a) and the MATLAB Engine API for Python (`matlabengine` 25.1.2 for R2025a; the engine
  version must match the MATLAB release).
- [Ollama](https://ollama.com) with the models `gemma3:4b` (offline LLM) and `nomic-embed-text` (RAG embeddings).
  A GPU is recommended (tested on an RTX 3060 Laptop GPU, 6 GB).
- Optional: a Hugging Face account with Inference Providers credits. The token is read from the environment variable
  `HF_TOKEN`; it is never stored in the repository. Without a token the agent uses Ollama only.

## Installation

```bat
git clone https://github.com/thvien-vo/CompositeAgent.git
cd CompositeAgent
py -3.12 -m venv venv
venv\Scripts\python.exe -m pip install -r python\requirements.txt
venv\Scripts\python.exe -m pip install -r python\optimization\requirements-opt.txt
ollama pull gemma3:4b
ollama pull nomic-embed-text
set HF_TOKEN=<your Hugging Face token>
```

The Random Forest models are included in `python/model/`. The RAG index (`python/rag_index.json`) is built
automatically on first use.

## Usage

### Demo

```bat
run_demo.bat                  full demo: environment check, reference check, 4 problems, 4 RAG questions,
                              2 design requests
run_demo.bat --offline        local model only (Ollama), no internet needed
run_demo.bat --interactive    afterwards, type your own problem, design request or question
run_demo.bat --lang vi        explanation in Vietnamese
run_demo.bat --parts 2        run only part 2 (agent); --parts 4 only the design part; --no-wait skips the pauses
```

Each run is also saved in `logs\demo_<date>_<time>.log`.

### Reference check

```bat
venv\Scripts\python.exe python\demo.py
```

CFRP `[0/45/-45/90]s`, 0.125 mm plies, Nx = 1000, Ny = 500, Nxy = 100 N/m. Expected: maximum failure index
≈ 0.00238, critical ply 4, ABD(1,1) ≈ 5.94 × 10⁷ N/m; the script prints `PASS` or `FAIL`.

### Agent and RAG

```bat
venv\Scripts\python.exe python\main.py "CFRP [0/90]s, 0.125 mm plies, Nx = 1 kN/m"
venv\Scripts\python.exe python\main.py --backend ollama --lang vi "<problem text>"
venv\Scripts\python.exe python\rag.py "What is Xt of IM7/8552?"
```

### Design a laminate from a request in words

```bat
venv\Scripts\python.exe python\design.py "Design the lightest IM7/8552 laminate for a shear load Nxy = 40 kN/m."
venv\Scripts\python.exe python\design.py --backend ollama --lang vi "Thiết kế tấm carbon/epoxy nhẹ nhất chịu nén Nx = -20 kN/m."
venv\Scripts\python.exe python\design.py "Which 24-ply AS4/8552 laminate has the largest safety margin under Nx = -10 kN/m?"
```

What the request may contain (anything not given takes the default, and the defaults used are printed):

| Item | How to write it | Default |
|---|---|---|
| Material | a material of the database (`IM7/8552`, `AS4/8552`, `T700GC/TC1225`...) → measured values; or a fibre type (`carbon/epoxy`, `glass/epoxy`, `Kevlar/epoxy`) → ML prediction, printed with a warning that the result is for reference only | none: a request without material is refused |
| Loads | `Nx = -20 kN/m`, `a compressive load of 20 N/mm in the x direction`, `shear force 5 kN/m`; N/m, kN/m, N/mm, numbers in words; compression is negative | none; moments (Mx, My, Mxy) are refused |
| Objective | `lightest` / `nhẹ nhất` (fewest plies); `largest safety margin` / `bền nhất` with a fixed ply count (`a 24-ply laminate`) | lightest |
| Ply count | `between 16 and 40 plies`, `at most 24 plies`, `24-ply` | 8-64 plies |
| Safety factor, ply thickness, plate | `safety factor 2`, `0.15 mm plies`, `0.6 m x 0.4 m` | 1.5; 0.125 mm; 0.5 m x 0.5 m |
| Shear direction | `the shear acts in one direction only` / `chỉ một chiều` | both directions (+Nxy and -Nxy) |
| Design rules | `no more than 3 plies of the same angle in a row`, `at least 15 % of the plies in each direction` | symmetric, balanced, >= 10 % per direction, <= 4 identical plies in a row; angles 0, ±45, 90 |

The answer gives the stacking sequence (e.g. `[45/-45_2/0_2/90]s`) and the plies of each angle, says whether it is a
**proven optimum** (exact search) or the **best design found** (GA + local search, with the proven lower bound of the
ply count), prints the reserve factor of Max Stress, Tsai-Wu and buckling with the governing criterion, the MATLAB
re-check, the independent buckling check and the comparison with the smallest quasi-isotropic laminate (fewer plies
in %; no mass in kg, the data have no density). Unsupported requests (another objective, other angles, moments,
unsymmetric laminates) are refused with the reason.

### Tests and benchmarks

```bat
venv\Scripts\python.exe python\test_checks.py                          checks without any LLM -> ALL PASS
venv\Scripts\python.exe python\test_explain_checks.py                  explanation checks -> ALL PASS
venv\Scripts\python.exe python\test_design_checks.py                   design checks (no LLM) -> ALL PASS
venv\Scripts\python.exe python\benchmark_llm.py --set new --backends ollama
venv\Scripts\python.exe python\benchmark_rag.py --set holdout
venv\Scripts\python.exe python\benchmark_design.py --backend ollama --explain
```

### Stacking-sequence optimisation (Layer 1)

```bat
python\optimization\run_optimization.bat           pytest + all experiments (about 1-1.5 h on 20 cores)
python\optimization\run_optimization.bat --quick   reduced run (3 seeds, smaller budget) -> results_quick\, figures_quick\
```

Single steps, from the `python` folder:

```bat
..\venv\Scripts\python.exe -m optimization.run_tests                      pytest suite
..\venv\Scripts\python.exe -m optimization.experiments.run_cases          8 load cases x 2 ply thicknesses
..\venv\Scripts\python.exe -m optimization.experiments.matlab_recheck     re-check the final designs in MATLAB
..\venv\Scripts\python.exe -m optimization.experiments.leriche_haftka_exp Le Riche & Haftka benchmark
```

Python API:

```python
from optimization import optimize, Rules, Plate

res = optimize({"Nx": -1e4, "Ny": -5e3, "Nxy": 0}, material="IM7/8552", method="ga", seed=1,
               rules=Rules(max_contiguous=4), plate=Plate(0.5, 0.5), safety_factor=1.5)
print(res.summary())    # stacking sequence, ply count, reserve factors, governing criterion and ply
```

## Main verification results

Agent (details in `PROGRESS.md` and `deliverables/benchmark/`):

- Reference check (`demo.py`): PASS after every change.
- LLM extraction, final version, 28 + 16 hand-written problems with known answers: 28/28 and 16/16 with both
  `gpt-oss-120b` and `gemma3:4b` (the Python checks bring `gemma3:4b` alone from 9/28 to 28/28); no silently wrong
  answer in the 88 final runs. The first version gave 0/28 with Hugging Face because the loads were silently set to zero.
- RAG: development set 12/12 (Hugging Face) and 11/12 (`gemma3:4b`); hold-out set 6/6 and 5/6; the right material
  retrieved in 18/18 questions.
- ML, leave-one-out over 25 materials: R² = 0.44 (E1), 0.30 (G12), 0.31 (Xt); negative for E2, ν12, Xc and S.

Optimisation (IM7/8552, simply supported 0.5 m × 0.5 m plate, safety factor 1.5; details in
`deliverables/optimization/BAO_CAO_LOP1.md`):

- Python CLT vs MATLAB `clt_engine.m`: 60/60 random laminates, maximum relative error 2.5 × 10⁻¹⁵.
- GA, GA + local search and NSGA-II reach the exhaustive-search optimum in 20/20 runs on all 16 problems
  (8 load cases × 2 ply thicknesses, 960 runs).
- Le Riche & Haftka benchmark: exhaustive search reproduces the published optima 3973.01, 9998.19 and 13518.66;
  minimum-thickness problem of 1995: 48 plies, as published.
- MATLAB re-check of the 83 final designs: 83/83 pass. pytest: 78/78 pass.
- Mass saving against the smallest quasi-isotropic `[0/±45/90]ns` laminate with the same margin (0.125 mm plies,
  load cases without shear): −50 % in uniaxial tension, −37.5 % in biaxial tension, −8.3 % to −16.7 % in compression.
  No saving is claimed for the load cases with shear (see below).

## Limitations

- Small dataset (25 lamina systems); several ML properties have a negative R²; measured values only for these 25
  materials, at room temperature and dry.
- CLT in the agent: linear elastic, Max Stress criterion, first-ply failure; no hygrothermal stresses, no delamination.
- The test sets are small and written by the author; load directions are read with keyword rules (English and
  Vietnamese), so unusual wording is refused.
- Offline mode (`gemma3:4b`): the explanation can use a wrong term (for example call ABD(1,1) a load) although every
  number is correct, because the guardrail checks numbers only.
- RAG indexes the table rows only; the vectors are stored in a JSON file (no vector database yet).
- Optimisation: shear buckling is not in the main model (a Ritz check shows that the 12-ply pure-shear design buckles
  at 2.3 % of the load and about 46 plies are needed); D16 / D26 are neglected; strengths are mean values, not
  B-basis allowables; one load case at a time; the "GA-deceptive" Le Riche & Haftka case is solved exactly in only
  3/20 runs.

## Next steps

- Layer 2: optimisation that accounts for the ML prediction error of the ply properties.
- Layer 3: the optimiser as a tool of the agent; comparison of designs proposed by the LLM with the GA.
- Shear buckling (and D16 / D26) in the main optimisation model.
- More data and features, prediction intervals; PostgreSQL + pgvector for RAG; a larger independent test set;
  checking the meaning of the explanation, not only its numbers.

## Data sources

- NCAMP qualification reports (Wichita State University, NIAR): 15 material systems, values checked on the PDF page.
- S.W. Tsai, H.T. Hahn, *Introduction to Composite Materials*, 1980: 5 material systems.
- P.D. Soden, M.J. Hinton, A.S. Kaddour, World-Wide Failure Exercise (1998): 5 material systems.
- R. Le Riche, R.T. Haftka (1993, 1995) and R. Le Riche (PhD thesis, 1994): optimisation benchmark.
