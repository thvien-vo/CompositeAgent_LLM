# Figures, Python and MATLAB versions

All figures and tables are generated from the stored files in deliverables\optimization\results\. Nothing is recomputed. Python and MATLAB versions share the same layout in millimetres.

## Regenerate

Python, in a VS Code terminal at D:\CompositeAgent:

```
venv_fig\Scripts\activate
python deliverables\figures_v2\python\make_all.py
python deliverables\figures_v2\compare.py
python deliverables\figures_v2\verify_numbers.py
```

MATLAB: cd to deliverables\figures_v2\matlab, then run make_all. It writes the PDF files in _raw and calls postprocess.py with venv_fig, which scales them to the journal size and makes the PNG files.

One figure only: `python deliverables\figures_v2\python\make_all.py Fig3`, or make_all("Fig3") in MATLAB.

## Fig1

- python\pdf\Fig1_workflow.pdf, python\png\Fig1_workflow.png; matlab\pdf\Fig1_workflow.pdf, matlab\png\Fig1_workflow.png; compare\Fig1_workflow_compare.png
- Slides: Fig1_workflow_slide.png (in python\slides and matlab\slides)
- Data: python\main.py, router.py, llm.py, rag.py, design.py, ml.py, materials.py, matlab_clt.py
- Regenerate: `python deliverables\figures_v2\python\make_all.py Fig1`

**Caption.** Workflow of the agent. Python rules classify a request written in English or Vietnamese; the LLM only confirms weak design wording, and unclear or contradictory text is refused with a hint. Analysis requests use classical laminate theory in MATLAB, design requests use the optimiser and a final check of the design, and questions on material data follow a separate retrieval branch. Python checks every LLM output.

## Fig2

- python\pdf\Fig2_leriche_haftka.pdf, python\png\Fig2_leriche_haftka.png; matlab\pdf\Fig2_leriche_haftka.pdf, matlab\png\Fig2_leriche_haftka.png; compare\Fig2_leriche_haftka_compare.png
- Slides: Fig2_leriche_haftka_slide.png (in python\slides and matlab\slides)
- Data: leriche_haftka_summary.csv, leriche_haftka_histories.json
- Regenerate: `python deliverables\figures_v2\python\make_all.py Fig2`

**Caption.** Convergence on the Le Riche and Haftka benchmark: share of 20 runs at the exact optimum against the number of distinct designs evaluated, for the GA (dashed line, hollow markers) and GA + local search (solid line, filled markers). The exact optimum comes from exhaustive enumeration.

## Fig3

- python\pdf\Fig3_pareto.pdf, python\png\Fig3_pareto.png; matlab\pdf\Fig3_pareto.pdf, matlab\png\Fig3_pareto.png; compare\Fig3_pareto_compare.png
- Slides: Fig3_pareto_slide.png (in python\slides and matlab\slides)
- Data: fronts.json, cases_summary.csv
- Regenerate: `python deliverables\figures_v2\python\make_all.py Fig3`

**Caption.** Pareto fronts between the number of plies n and the smallest reserve factor RF_min for four load cases, t = 0.125 mm and t = 0.183 mm. Lines: exact non-dominated front, ending at n = 28 for C4, C5 and C7. Hollow markers: final NSGA-II fronts of all seeds. Filled diamonds: optimum, the fewest plies with RF_min ≥ 1.5. The vertical axis stops at RF_min = 8 so that the region around the constraint stays readable; the fronts continue above it. In C5 with t = 0.125 mm the optimum has a proven ply count and the best known RF_min. Results are for shear of one sign.

## Fig4

- python\pdf\Fig4_qi_comparison.pdf, python\png\Fig4_qi_comparison.png; matlab\pdf\Fig4_qi_comparison.pdf, matlab\png\Fig4_qi_comparison.png; compare\Fig4_qi_comparison_compare.png
- Slides: Fig4_qi_comparison_t0125_slide.png, Fig4_qi_comparison_t0183_slide.png (in python\slides and matlab\slides)
- Data: cases_summary.csv, fronts.json (ply limit)
- Regenerate: `python deliverables\figures_v2\python\make_all.py Fig4`

**Caption.** Plies needed for RF_min ≥ 1.5: smallest quasi-isotropic [0/±45/90]ns laminate against the optimised stacking sequence, for (a) t = 0.125 mm and (b) t = 0.183 mm. Percentages under the case names are the mass saving, (n_QI − n*)/n_QI, rounded to whole numbers; both laminates use the same ply, so plies and mass are proportional. The hatched column marks C8 with t = 0.125 mm, which has no feasible design within 64 plies (largest RF_min = 1.04). The ply limit applies to the optimiser only. Results are for shear of one sign.

## Fig5

- python\pdf\Fig5_algorithms.pdf, python\png\Fig5_algorithms.png; matlab\pdf\Fig5_algorithms.pdf, matlab\png\Fig5_algorithms.png; compare\Fig5_algorithms_compare.png
- Slides: Fig5_algorithms_t0125_slide.png, Fig5_algorithms_t0183_slide.png (in python\slides and matlab\slides)
- Data: cases_summary.csv, run_cases_meta.json
- Regenerate: `python deliverables\figures_v2\python\make_all.py Fig5`

**Caption.** Runs out of 20 that end at the optimum, for each algorithm and load case, (a) t = 0.125 mm and (b) t = 0.183 mm, with a budget of 10000 distinct designs. C5 with t = 0.125 mm has no proven optimum, so its columns count the runs at the best known design (0, 0 and 9 runs for GA, NSGA-II and GA + local search). C8 with t = 0.125 mm has no feasible design, so its columns count the runs at the largest-margin 64-ply design. Median evaluations are in Table_convergence. Results are for shear of one sign.

## FigS1

- python\pdf\FigS1_pareto_all_C1_C4.pdf, python\png\FigS1_pareto_all_C1_C4.png; matlab\pdf\FigS1_pareto_all_C1_C4.pdf, matlab\png\FigS1_pareto_all_C1_C4.png; compare\FigS1_pareto_all_C1_C4_compare.png
- python\pdf\FigS1_pareto_all_C5_C8.pdf, python\png\FigS1_pareto_all_C5_C8.png; matlab\pdf\FigS1_pareto_all_C5_C8.pdf, matlab\png\FigS1_pareto_all_C5_C8.png; compare\FigS1_pareto_all_C5_C8_compare.png
- Data: fronts.json, cases_summary.csv
- Regenerate: `python deliverables\figures_v2\python\make_all.py FigS1`

**Caption.** Pareto fronts of all eight load cases, t = 0.125 mm and t = 0.183 mm, in two parts. Symbols as in Fig. 3. C8 with t = 0.125 mm has no feasible design within 64 plies, so no optimum is marked for it.

## FigS2

- python\pdf\FigS2_convergence_t0125_p1.pdf, python\png\FigS2_convergence_t0125_p1.png; matlab\pdf\FigS2_convergence_t0125_p1.pdf, matlab\png\FigS2_convergence_t0125_p1.png; compare\FigS2_convergence_t0125_p1_compare.png
- python\pdf\FigS2_convergence_t0125_p2.pdf, python\png\FigS2_convergence_t0125_p2.png; matlab\pdf\FigS2_convergence_t0125_p2.pdf, matlab\png\FigS2_convergence_t0125_p2.png; compare\FigS2_convergence_t0125_p2_compare.png
- Data: runs_history.json, cases_summary.csv
- Regenerate: `python deliverables\figures_v2\python\make_all.py FigS2`

**Caption.** Share of runs ending at the optimum against distinct designs evaluated, t = 0.125 mm, 20 seeds, in two parts. C5 has no proven optimum, so no curves can be drawn: evaluations to the best known design were not recorded.

## FigS3

- python\pdf\FigS3_convergence_t0183_p1.pdf, python\png\FigS3_convergence_t0183_p1.png; matlab\pdf\FigS3_convergence_t0183_p1.pdf, matlab\png\FigS3_convergence_t0183_p1.png; compare\FigS3_convergence_t0183_p1_compare.png
- python\pdf\FigS3_convergence_t0183_p2.pdf, python\png\FigS3_convergence_t0183_p2.png; matlab\pdf\FigS3_convergence_t0183_p2.pdf, matlab\png\FigS3_convergence_t0183_p2.png; compare\FigS3_convergence_t0183_p2_compare.png
- Data: runs_history.json, cases_summary.csv
- Regenerate: `python deliverables\figures_v2\python\make_all.py FigS3`

**Caption.** Share of runs ending at the optimum against distinct designs evaluated, t = 0.183 mm, 20 seeds, in two parts.

## FigS4

- python\pdf\FigS4_best_so_far_C4.pdf, python\png\FigS4_best_so_far_C4.png; matlab\pdf\FigS4_best_so_far_C4.pdf, matlab\png\FigS4_best_so_far_C4.png; compare\FigS4_best_so_far_C4_compare.png
- Data: runs_history.json, cases_summary.csv
- Regenerate: `python deliverables\figures_v2\python\make_all.py FigS4`

**Caption.** Plies of the best design so far, C4 Biaxial compression, t = 0.125 mm: median of 20 runs with the 25th and 75th percentiles. Curves start once every run has a best design. Odd median values are midpoints between runs at two even ply counts.

## FigS5

- python\pdf\FigS5_ritz_before_after.pdf, python\png\FigS5_ritz_before_after.png; matlab\pdf\FigS5_ritz_before_after.pdf, matlab\png\FigS5_ritz_before_after.png; compare\FigS5_ritz_before_after_compare.png
- Data: before_ritz\cases_summary.csv, cases_summary.csv
- Regenerate: `python deliverables\figures_v2\python\make_all.py FigS5`

**Caption.** Optimised plies with the previous buckling model (closed form, D_16 = D_26 = 0, shear buckling not checked) and with Rayleigh-Ritz including D_16, D_26 and N_xy, for (a) t = 0.125 mm and (b) t = 0.183 mm. Only pure shear changes the ply count. Hatched columns: C8 with t = 0.125 mm, with no feasible design within 64 plies in either model.

## Tables

tables\ holds Table_load_cases, Table_leriche_haftka, Table_convergence and Table_shear_directions, each as .csv (UTF-8 with BOM) and .tex (needs booktabs).

## Unit of λ_cr

In LH-A to LH-D, λ_cr multiplies a reference load N_x = 1 lb/in (python\optimization\leriche_haftka.py, `problem`: "Nx = 1 lb/in, so lambda is in lb/in as in the source"). Its value equals the critical N_x in lb/in.
