## T1. Python vs MATLAB (random laminates)

| laminates | pass | max e_ABD | max e_stress | max e_FI | non-symmetric | with moments |
|---|---|---|---|---|---|---|
| 60 | 60 | 2.1e-15 | 2.5e-15 | 2.5e-15 | 52 | 22 |

## T1b. Checks of the buckling model (Rayleigh-Ritz with D16, D26, Nxy), made before using it

| check | terms | value | reference | difference | required | result |
|---|---|---|---|---|---|---|
| compression, D16 = D26 = 0, vs closed form of the previous version | 206 cases | - | - | max 6.2e-14 % | < 0.5 % | pass |
| square isotropic plate, pure shear: k_s | 8x8 | 9.3283 | 9.34 | 0.12 % | <= 1 % | pass |
| isotropic plate a/b = 5, pure shear: k_s | 30x6 | 5.5316 | 5.5100 (5.35 + 4 (b/a)^2) | 0.39 % | information | - |
| isotropic plate a/b = 10, pure shear: k_s | 60x6 | 5.3891 | 5.3500 (5.35) | 0.73 % | <= 2 % | pass |
| isotropic plate a/b = 20, pure shear: k_s | 120x6 | 5.3508 | 5.3500 (5.35) | 0.02 % | <= 2 % | pass |
| IM7/8552 [90/-45/45/0/-45/45]s, loads (0, 0, 300000.0): sine series vs Legendre polynomials | 8x8 vs p = 16 | 0.025638 | 0.025628 | +0.04 % | check | - |
| IM7/8552 [(45/-45)4/0/90]s, loads (-10000.0, 0, 5000.0): sine series vs Legendre polynomials | 8x8 vs p = 16 | 1.6257 | 1.6233 | +0.15 % | check | - |
| IM7/8552 [45_2/-45_2/45_2/-45_2/0/90]s, loads (0, 0, 300000.0): sine series vs Legendre polynomials | 8x8 vs p = 16 | 0.10564 | 0.10498 | +0.62 % | check | - |
| IM7/8552 [45/-45/0/90/45/-45]s, loads (-10000.0, -5000.0, 0): sine series vs Legendre polynomials | 8x8 vs p = 16 | 0.2239 | 0.22354 | +0.16 % | check | - |
| Nemeth 1992 long SS [(+-45)_1]s graphite-epoxy, shear: (aniso - ortho) / ortho | 80x8, a/b = 10 | -50.3 % (+Nxy) / +43.7 % (-Nxy) | about 48 % | - | comparison | - |
| Nemeth 1992 long SS [(+-45)_6]s graphite-epoxy, shear: (aniso - ortho) / ortho | 80x8, a/b = 10 | -7.8 % (+Nxy) / +7.7 % (-Nxy) | about 7 % | - | comparison | - |
| Nemeth 1992 long SS [(+-45)_12]s graphite-epoxy, shear: (aniso - ortho) / ortho | 80x8, a/b = 10 | -3.9 % (+Nxy) / +3.9 % (-Nxy) | about 3.5 % | - | comparison | - |

Convergence of the square plate (M x N: k_s): 6x6: 9.3384, 8x8: 9.3283; Legendre polynomials p = 16: 9.3245.

## T2-t0125. Optimum per load case, ply 0.125 mm, buckling by Rayleigh-Ritz with D16, D26, Nxy

| case | Nx, Ny, Nxy (N/m) | status | n* | proven lower bound | design (half, outer->mid) | margin | governing | RF MS / TW / buck | |D16|/D11, |D26|/D22 | QI n | mass saving |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 Kéo một phương | 1.5e+06, 0, 0 | optimal | 24 | 24 | [90/0/-45/0/45/0_4/90/0_2]s | 1.6401 | tsai_wu (ply 1, 90 deg) | 1.778 / 1.64 / inf | 0.023, 0.040 | 48 | 50.0 % |
| C2 Kéo hai phương | 1e+06, 500000, 0 | optimal | 20 | 20 | [90/-45/0/45/0_3/90/0_2]s | 1.5733 | max_stress (ply 3, 0 deg) | 1.573 / 1.746 / inf | 0.044, 0.051 | 32 | 37.5 % |
| C3 Nén một phương | -10000, 0, 0 | optimal | 20 | 20 | [45/-45/45/-45_3/45_2/0/90]s | 1.7623 | buckling | 101.8 / 79.45 / 1.762 | 0.000, 0.000 | 24 | 16.7 % |
| C4 Nén hai phương | -10000, -5000, 0 | optimal | 22 | 22 | [-45/45_2/-45/45/-45/0/90/0/90_2]s | 1.5058 | buckling | 178.7 / 272.2 / 1.506 | 0.013, 0.014 | 24 | 8.3 % |
| C5 Cắt thuần | 0, 0, 300000 | n* proven by the bound; margin = best known | 42 | 42 | [-45_4/90/-45_3/0/90/0_2/45/0/45_4/90/45_2]s | 1.5915 | buckling | 9.954 / 6.073 / 1.592 | 0.402, 0.403 | 56 | 25.0 % |
| C6 Kéo + cắt | 800000, 0, 300000 | optimal | 24 | 24 | [90/-45/45/0/90/-45/45/0/-45/0/45/0]s | 1.6565 | tsai_wu (ply 1, 90 deg) | 2.194 / 1.657 / 3.093 | 0.050, 0.035 | 32 | 25.0 % |
| C7 Nén + cắt | -10000, 0, 5000 | optimal | 20 | 20 | [-45_2/45/-45/45/-45/45_2/0/90]s | 1.7513 | buckling | 101.8 / 76.76 / 1.751 | 0.278, 0.283 | 24 | 16.7 % |
| C8 Tải rất lớn | 4e+06, 2e+06, 1e+06 | infeasible | 64 | none <= 64 | [90/-45/45/0/90/-45/45/0/90/-45/45/0/90/-45/45/0/-45/45/0/-45/45/0/-45/45/0/-45/45/0/-45/45/-45/45]s | 1.0427 | max_stress (ply 1, 90 deg) | 1.043 / 1.066 / inf | 0.015, 0.015 | 104 | infeasible |

## T3-t0125. GA, GA + local search and NSGA-II against the exact optimum, ply 0.125 mm

*success* = final answer is the PROVEN global optimum; when the exact search could not prove it, *reach best known* counts the runs that end at the best design found by any run.

| case | exact search time | GA success | GA evals to hit (mean / max) | GA+LS success | GA+LS evals to hit (mean / max) | NSGA-II success | NSGA-II evals to hit (mean / max) | time per run GA / GA+LS / NSGA-II | NSGA-II exact front points |
|---|---|---|---|---|---|---|---|---|---|
| C1 | 0.2 s | 20/20 | 659 / 940 | 20/20 | 1321 / 2162 | 20/20 | 453 / 634 | 3.6 / 5.4 / 6.6 s | 97 % of 27 |
| C2 | 0.2 s | 20/20 | 348 / 582 | 20/20 | 554 / 1110 | 20/20 | 469 / 1101 | 6.2 / 6.1 / 3.5 s | 100 % of 29 |
| C3 | 6.1 s | 20/20 | 979 / 2919 | 20/20 | 826 / 1848 | 11/20 | 4335 / 7481 | 4.3 / 4.0 / 4.5 s | 52 % of 11 |
| C4 | 6.2 s | 19/20 | 4152 / 7776 | 20/20 | 991 / 1281 | 2/20 | 7812 / 9343 | 3.9 / 4.1 / 4.2 s | 54 % of 11 |
| C5 | 6.6 s | - (reach best known 0/20) | - / - | - (reach best known 9/20) | - / - | - (reach best known 0/20) | - / - | 4.2 / 4.2 / 4.7 s | 31 % of 11 |
| C6 | 0.5 s | 20/20 | 239 / 377 | 20/20 | 685 / 1255 | 20/20 | 185 / 358 | 3.2 / 3.1 / 3.6 s | 97 % of 13 |
| C7 | 7.6 s | 20/20 | 1980 / 4260 | 20/20 | 1416 / 3606 | 5/20 | 4866 / 6783 | 3.9 / 3.7 / 4.0 s | 32 % of 11 |
| C8 | 0.9 s | 20/20 | 201 / 335 | 20/20 | 2112 / 3225 | 20/20 | 1632 / 7034 | 2.1 / 2.0 / 3.6 s | 100 % of 29 |

## T2-t0183. Optimum per load case, ply 0.18288 mm (NCAMP), buckling by Rayleigh-Ritz with D16, D26, Nxy

| case | Nx, Ny, Nxy (N/m) | status | n* | proven lower bound | design (half, outer->mid) | margin | governing | RF MS / TW / buck | |D16|/D11, |D26|/D22 | QI n | mass saving |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 Kéo một phương | 1.5e+06, 0, 0 | optimal | 16 | 16 | [90/0/-45/0_2/45/0_2]s | 1.5117 | tsai_wu (ply 1, 90 deg) | 1.718 / 1.512 / inf | 0.062, 0.079 | 32 | 50.0 % |
| C2 Kéo hai phương | 1e+06, 500000, 0 | optimal | 14 | 14 | [90/0/-45/0/45/0_2]s | 1.5463 | max_stress (ply 9, 0 deg) | 1.546 / 1.724 / inf | 0.059, 0.063 | 24 | 41.7 % |
| C3 Nén một phương | -10000, 0, 0 | optimal | 14 | 14 | [45/-45_2/45/0_2/90]s | 1.8346 | buckling | 179 / 157.7 / 1.835 | 0.023, 0.029 | 16 | 12.5 % |
| C4 Nén hai phương | -10000, -5000, 0 | optimal | 16 | 16 | [-45/45_2/-45/45/-45/0/90]s | 1.8775 | buckling | 178.4 / 238.3 / 1.878 | 0.009, 0.009 | 24 | 33.3 % |
| C5 Cắt thuần | 0, 0, 300000 | optimal | 28 | 28 | [-45_4/0/-45/90_2/45_3/0/45_2]s | 1.5197 | buckling | 10.29 / 6.279 / 1.52 | 0.436, 0.433 | 40 | 30.0 % |
| C6 Kéo + cắt | 800000, 0, 300000 | optimal | 16 | 16 | [90/-45/45/0/-45/0/45/0]s | 1.6979 | tsai_wu (ply 16, 90 deg) | 2.341 / 1.698 / 2.992 | 0.092, 0.062 | 24 | 33.3 % |
| C7 Nén + cắt | -10000, 0, 5000 | optimal | 14 | 14 | [-45_2/45_2/0_2/90]s | 1.8243 | buckling | 179 / 131.3 / 1.824 | 0.234, 0.290 | 16 | 12.5 % |
| C8 Tải rất lớn | 4e+06, 2e+06, 1e+06 | optimal | 64 | 64 | [90/-45/45/0/90/-45/45/0/90/-45/45/0/90/-45/45/0/-45/45/0/-45/45/0/-45/45/0/-45/45/0/-45/45/-45/45]s | 1.5255 | max_stress (ply 64, 90 deg) | 1.526 / 1.56 / inf | 0.015, 0.015 | 72 | 11.1 % |

## T3-t0183. GA, GA + local search and NSGA-II against the exact optimum, ply 0.18288 mm (NCAMP)

*success* = final answer is the PROVEN global optimum; when the exact search could not prove it, *reach best known* counts the runs that end at the best design found by any run.

| case | exact search time | GA success | GA evals to hit (mean / max) | GA+LS success | GA+LS evals to hit (mean / max) | NSGA-II success | NSGA-II evals to hit (mean / max) | time per run GA / GA+LS / NSGA-II | NSGA-II exact front points |
|---|---|---|---|---|---|---|---|---|---|
| C1 | 0.2 s | 20/20 | 513 / 813 | 20/20 | 565 / 1178 | 20/20 | 385 / 558 | 4.5 / 6.1 / 6.3 s | 97 % of 27 |
| C2 | 0.2 s | 20/20 | 302 / 445 | 20/20 | 310 / 579 | 20/20 | 343 / 635 | 19.7 / 11.2 / 2.2 s | 100 % of 29 |
| C3 | 9.3 s | 20/20 | 527 / 1312 | 20/20 | 254 / 357 | 14/20 | 4912 / 9044 | 9.7 / 9.5 / 3.6 s | 53 % of 11 |
| C4 | 9.5 s | 20/20 | 686 / 1148 | 20/20 | 429 / 840 | 18/20 | 4954 / 9837 | 7.8 / 11.1 / 4.0 s | 55 % of 11 |
| C5 | 9.1 s | 15/20 | 6852 / 9715 | 20/20 | 1634 / 2068 | 3/20 | 6777 / 7157 | 3.6 / 3.6 / 4.1 s | 55 % of 11 |
| C6 | 1.2 s | 20/20 | 267 / 445 | 20/20 | 317 / 628 | 20/20 | 331 / 720 | 3.8 / 4.0 / 3.9 s | 100 % of 13 |
| C7 | 9.3 s | 20/20 | 794 / 2112 | 20/20 | 273 / 381 | 0/20 | - / - | 9.0 / 11.3 / 9.0 s | 33 % of 11 |
| C8 | 2.2 s | 20/20 | 209 / 337 | 20/20 | 4543 / 5704 | 20/20 | 1880 / 5997 | 6.6 / 2.7 / 3.6 s | 100 % of 29 |

## T4. Number of Ritz terms per case and convergence of the final designs

*terms study*: smallest k >= 8 with change < 0.5 % from k to k + 2 on 9 reference laminates (quasi-isotropic and +-45 outside); *final design*: series grown from 6 x 6 in steps of 2 until the change is < 0.5 % (M x N: lambda); the margin uses the lower of the two values.

| case | ply | terms in optimisation (M x N) | terms study: largest change k -> k+2 | final design: sequence | last change | buckling RF used | closed form (Nx, Ny only, D16 = D26 = 0) |
|---|---|---|---|---|---|---|---|
| C1 | t0125 | - (no compression / shear) | - | 6x6:inf; 8x8:inf | 0.000 % | inf | inf |
| C2 | t0125 | - (no compression / shear) | - | 6x6:inf; 8x8:inf | 0.000 % | inf | inf |
| C3 | t0125 | 8x8 | 0.056 % | 6x6:1.76233; 8x8:1.76233 | 0.000 % | 1.762 | 1.762 |
| C4 | t0125 | 8x8 | 0.057 % | 6x6:1.5058; 8x8:1.50579 | 0.000 % | 1.506 | 1.506 |
| C5 | t0125 | 8x8 | 0.131 % | 6x6:1.59293; 8x8:1.59155 | 0.087 % | 1.592 | inf |
| C6 | t0125 | 8x8 | 0.486 % | 6x6:3.16311; 8x8:3.10384; 10x10:3.0928 | 0.357 % | 3.093 | inf |
| C7 | t0125 | 8x8 | 0.079 % | 6x6:1.75371; 8x8:1.75134 | 0.135 % | 1.751 | 1.762 |
| C8 | t0125 | 8x8 | 0.000 % | 6x6:inf; 8x8:inf | 0.000 % | inf | inf |
| C1 | t0183 | - (no compression / shear) | - | 6x6:inf; 8x8:inf | 0.000 % | inf | inf |
| C2 | t0183 | - (no compression / shear) | - | 6x6:inf; 8x8:inf | 0.000 % | inf | inf |
| C3 | t0183 | 8x8 | 0.056 % | 6x6:1.83467; 8x8:1.83464 | 0.002 % | 1.835 | 1.835 |
| C4 | t0183 | 8x8 | 0.057 % | 6x6:1.87754; 8x8:1.87754 | 0.000 % | 1.878 | 1.878 |
| C5 | t0183 | 8x8 | 0.131 % | 6x6:1.52115; 8x8:1.5197 | 0.096 % | 1.52 | inf |
| C6 | t0183 | 8x8 | 0.486 % | 6x6:3.05768; 8x8:3.00218; 10x10:2.99186 | 0.345 % | 2.992 | inf |
| C7 | t0183 | 8x8 | 0.079 % | 6x6:1.82663; 8x8:1.82427 | 0.129 % | 1.824 | 1.835 |
| C8 | t0183 | 8x8 | 0.000 % | 6x6:inf; 8x8:inf | 0.000 % | inf | inf |

## T5b. Before / after: previous model (closed form, no shear buckling, D16 = D26 = 0) vs Rayleigh-Ritz with D16, D26, Nxy

| case | ply | before: n* (margin) | after: n* (margin) | QI n before | QI n after | mass saving before | mass saving after | status after |
|---|---|---|---|---|---|---|---|---|
| C1 Kéo một phương | t0125 | 24 (1.6401) | 24 (1.6401) | 48 | 48 | 50.0 % | 50.0 % | optimal |
| C2 Kéo hai phương | t0125 | 20 (1.5733) | 20 (1.5733) | 32 | 32 | 37.5 % | 37.5 % | optimal |
| C3 Nén một phương | t0125 | 20 (1.7623) | 20 (1.7623) | 24 | 24 | 16.7 % | 16.7 % | optimal |
| C4 Nén hai phương | t0125 | 22 (1.5060) | 22 (1.5058) | 24 | 24 | 8.3 % | 8.3 % | optimal |
| C5 Cắt thuần | t0125 | 12 (1.7352) | 42 (1.5915) | 16 | 56 | 25.0 % (shear buckling not checked) | 25.0 % | unknown (time limit) |
| C6 Kéo + cắt | t0125 | 24 (1.6565) | 24 (1.6565) | 32 | 32 | 25.0 % (shear buckling not checked) | 25.0 % | optimal |
| C7 Nén + cắt | t0125 | 20 (1.7623) | 20 (1.7513) | 24 | 24 | 16.7 % (shear buckling not checked) | 16.7 % | optimal |
| C8 Tải rất lớn | t0125 | 64 (1.0427) | 64 (1.0427) | 104 | 104 | infeasible | infeasible | infeasible |
| C1 Kéo một phương | t0183 | 16 (1.5117) | 16 (1.5117) | 32 | 32 | 50.0 % | 50.0 % | optimal |
| C2 Kéo hai phương | t0183 | 14 (1.5463) | 14 (1.5463) | 24 | 24 | 41.7 % | 41.7 % | optimal |
| C3 Nén một phương | t0183 | 14 (1.8354) | 14 (1.8346) | 16 | 16 | 12.5 % | 12.5 % | optimal |
| C4 Nén hai phương | t0183 | 16 (1.8776) | 16 (1.8775) | 24 | 24 | 33.3 % | 33.3 % | optimal |
| C5 Cắt thuần | t0183 | 12 (2.5387) | 28 (1.5197) | 16 | 40 | 25.0 % (shear buckling not checked) | 30.0 % | optimal |
| C6 Kéo + cắt | t0183 | 16 (1.6979) | 16 (1.6979) | 24 | 24 | 33.3 % (shear buckling not checked) | 33.3 % | optimal |
| C7 Nén + cắt | t0183 | 14 (1.8354) | 14 (1.8243) | 16 | 16 | 12.5 % (shear buckling not checked) | 12.5 % | optimal |
| C8 Tải rất lớn | t0183 | 64 (1.5255) | 64 (1.5255) | 72 | 72 | 11.1 % (shear buckling not checked) | 11.1 % | optimal |

## T5. MATLAB re-check of the final designs

| designs | pass | max e_ABD | max e_stress | max |RF diff| |
|---|---|---|---|---|
| 51 | 51 | 1.7e-15 | 3.1e-15 | 1.4e-14 |

## T6. Le Riche & Haftka benchmark (fixed thickness, max lambda_cr)

| case | problem | design space | valid designs | exhaustive lambda* | # optima | source value | difference | same with full mode scan | GA exact (practical 0.1 %) | GA+LS exact (practical) | evals to exact GA / GA+LS (mean) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| LH-A | buckling only, 64 plies, a/b = 2, Ny/Nx = 1 | 43,046,721 | 43,046,721 | 3973.01 | 7 | 3973.01 | +0.00009 % | 3973.01 | 14/20 (20) | 15/20 (20) | 2502 / 2663 |
| LH-B | buckling + strain + contiguity, 48 plies, Ny/Nx = 0.5 | 531,441 | 243,569 | 9998.20 | 1 | 9998.19 | +0.00009 % | 9998.20 | 18/20 (20) | 17/20 (20) | 2529 / 2679 |
| LH-C | buckling + strain + contiguity, 48 plies, Ny/Nx = 0.25 | 531,441 | 243,569 | 12678.78 | 2 | 12674.84 | +0.03106 % | 12678.78 | 17/20 (19) | 20/20 (20) | 2519 / 717 |
| LH-D | buckling + strain + contiguity, 48 plies, Ny/Nx = 0.125 | 531,441 | 243,569 | 13518.66 | 169 | 13518.66 | +0.00000 % | 13518.66 | 20/20 (20) | 20/20 (20) | 328 / 270 |

Optimal designs found by exhaustive search:

| case | design (stacks, half) | governing | mode (m,n) |
|---|---|---|---|
| LH-A | [±45/90_8/±45/90_18/±45]s | buckling | (2, 1) |
| LH-B | [90_2/(±45)_2/90_2/±45/90_2/(±45)_6]s | buckling | (3, 1) |
| LH-C | [(±45)_2/90_2/(±45)_3/0_2/±45/0_4/±45/0_2]s | max_strain | (2, 1) |
| LH-D | [±45/0_2/(±45)_4/0_2/±45/0_4/90_2/0_2]s | max_strain | (3, 1) |

## T7. Designs printed in the source, recomputed

| case | design (stacks outer->mid) | lambda_b ours | lambda_b source | rel. diff | lambda_cs ours | lambda_cs source | rel. diff |
|---|---|---|---|---|---|---|---|
| LH-A | 90 90 90 90 90 ± ± 90 ± ± ± 90 ± ± ± ± | 3973.01 | 3973.01 | +9.4e-07 | 14205.19 | 14205.18 | +5.0e-07 |
| LH-A | ± 90 90 90 90 90 ± 90 90 90 90 ± 90 90 90 90 | 3973.01 | 3973.01 | +9.4e-07 | 8935.74 | 8935.74 | -4.9e-09 |
| LH-A | 90 90 ± ± 90 90 90 90 90 90 90 90 ± 90 90 90 | 3973.01 | 3973.01 | +9.4e-07 | 8935.74 | 8935.74 | -4.9e-09 |
| LH-A | 90 ± 90 90 90 ± 90 90 90 90 ± 90 90 90 90 90 | 3973.01 | 3973.01 | +9.4e-07 | 8935.74 | 8935.74 | -4.9e-09 |
| LH-A | 90 90 90 90 ± 90 ± 90 ± 90 ± ± ± ± ± ± | 3973.01 | 3973.01 | +9.4e-07 | 14205.19 | 14205.18 | +5.0e-07 |
| LH-B | 90 ± ± 90 ± 90 ± ± ± ± ± ± | 9998.20 | 9998.19 | +8.8e-07 | 10398.14 | 10394.81 | +3.2e-04 |
| LH-B | 90 ± ± 90 ± ± 90 ± 90 ± ± ± | 9997.61 | 9997.60 | +1.5e-06 | 10187.94 | 10187.93 | +6.4e-07 |
| LH-B | ± 90 90 ± 90 ± ± ± ± ± 90 ± | 9976.59 | 9976.58 | +1.1e-06 | 10187.94 | 10187.93 | +6.4e-07 |
| LH-C | 90 ± ± ± ± ± 0 ± 0 0 ± 0 | 12674.85 | nan | - | 12678.78 | nan | - |
| LH-D | 90 ± ± ± ± 0 0 ± 0 0 ± 0 | 14168.13 | 14168.12 | +8.3e-07 | 13518.66 | 13518.66 | +4.6e-08 |
| LH-D | ± ± ± 0 ± ± 0 90 0 0 ± 0 | 14134.78 | 14134.76 | +1.4e-06 | 13518.66 | 13518.66 | +4.6e-08 |
| LH-D | 90 ± ± ± 0 ± 0 ± 0 0 ± 0 | 14013.72 | 14013.71 | +9.5e-07 | 13518.66 | 13518.66 | +4.6e-08 |
| LH-D | ± ± 0 ± ± 90 0 0 ± 0 ± 0 | 13662.62 | 13662.61 | +8.9e-07 | 13518.66 | 13518.66 | +4.6e-08 |

## T8. Le Riche & Haftka (1995) minimum-thickness cases

| case | Nx, Ny (lb/in) | n* (exhaustive) | lambda_cr | design | best lambda at 44 / 48 / 52 | source | GA exact | GA+LS exact |
|---|---|---|---|---|---|---|---|---|
| LC1 | 13000, 1625 | 48 | 1.0399 | [±45/0_2/(±45)_4/0_2/±45/0_4/90_2/0_2]s | 0.879 / 1.040 / 1.262 | n* = 48; 0.879 / 1.040 / 1.201 | 20/20 | 20/20 |
| LC2 | 12500, 3125 | 48 | 1.0143 | [(±45)_2/90_2/(±45)_3/0_2/±45/0_4/±45/0_2]s | 0.807 / 1.014 / 1.193 | n* = 48 | 6/20 | 20/20 |
| LC3 | 9800, 4900 | 48 | 1.0202 | [90_2/(±45)_2/90_2/±45/90_2/(±45)_6]s | 0.786 / 1.020 / 1.262 | n* = 48 | 2/20 | 3/20 |
