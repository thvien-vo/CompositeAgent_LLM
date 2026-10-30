*One direction* = published results (shear of the given sign only; results/cases_summary.csv). *Both directions* = shear_both_signs: strength and buckling for +Nxy and -Nxy, the smaller RF counts. *margin if reversed* = margin of the one-direction optimum when Nxy changes sign. *n lower bound* = proven lower bound of the ply count (both directions). Mass saving vs the smallest quasi-isotropic [0/45/-45/90]ns laminate checked with the same option.

**Ply 0.125 mm (demo)**

| case | Nx, Ny, Nxy (N/m) | one direction: n* (margin) | margin if reversed | saving one dir. | both directions: n (margin) | status | n lower bound | design (half, outer->mid) | governing (sign) | |D16|/D11 | QI n | saving both dir. | GA+LS seeds at this answer |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C5 Pure shear | 0, 0, 300000 | 42 (1.5915) | 0.5558 | 25.0 % | 46 (1.5975) | best found (GA + local search) | 46 | [45/-45_2/45/-45/45/-45_2/45_4/-45/45/-45/0/-45/90_3/0_2/90]s | buckling (+) | 0.000 | 56 | 17.9 % | 1/5 |
| C6 Tension + shear | 800000, 0, 300000 | 24 (1.6565) | 1.6565 | 25.0 % | 24 (1.6565) | optimal | 24 | [90/-45/45/0/90/-45/45/0/-45/0/45/0]s | tsai_wu (+) | 0.050 | 32 | 25.0 % | 4/5 |
| C7 Compression + shear | -10000, 0, 5000 | 20 (1.7513) | 1.4932 | 16.7 % | 20 (1.6876) | optimal | 20 | [45/-45/45/-45_3/45_2/0/90]s | buckling (+) | 0.000 | 24 | 16.7 % | 5/5 |
| C8 Very large load | 4e+06, 2e+06, 1e+06 | 64 (1.0427) | 1.0427 | infeasible | 64 (1.0427) | infeasible |  | [90/-45/45/0/90/-45/45/0/90/-45/45/0/90/-45/45/0/-45/45/0/-45/45/0/-45/45/0/-45/45/0/-45/45/-45/45]s | max_stress (+) | 0.015 | 104 | infeasible | 5/5 |

**Ply 0.18288 mm (NCAMP IM7/8552)**

| case | Nx, Ny, Nxy (N/m) | one direction: n* (margin) | margin if reversed | saving one dir. | both directions: n (margin) | status | n lower bound | design (half, outer->mid) | governing (sign) | |D16|/D11 | QI n | saving both dir. | GA+LS seeds at this answer |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C5 Pure shear | 0, 0, 300000 | 28 (1.5197) | 0.5136 | 30.0 % | 32 (1.6911) | best found (GA + local search) | 32 | [-45_2/45_4/-45/45/-45_3/45/0/90_2/0]s | buckling (+) | 0.002 | 40 | 20.0 % | 2/5 |
| C6 Tension + shear | 800000, 0, 300000 | 16 (1.6979) | 1.6979 | 33.3 % | 16 (1.6979) | optimal | 16 | [90/-45/45/0/-45/0/45/0]s | tsai_wu (-) | 0.092 | 24 | 33.3 % | 5/5 |
| C7 Compression + shear | -10000, 0, 5000 | 14 (1.8243) | 1.5569 | 12.5 % | 14 (1.7437) | optimal | 14 | [45/-45_2/45/0_2/90]s | buckling (+) | 0.023 | 16 | 12.5 % | 5/5 |
| C8 Very large load | 4e+06, 2e+06, 1e+06 | 64 (1.5255) | 1.5255 | 11.1 % | 64 (1.5255) | optimal | 64 | [90/-45/45/0/90/-45/45/0/90/-45/45/0/90/-45/45/0/-45/45/0/-45/45/0/-45/45/0/-45/45/0/-45/45/-45/45]s | max_stress (-) | 0.015 | 72 | 11.1 % | 5/5 |
