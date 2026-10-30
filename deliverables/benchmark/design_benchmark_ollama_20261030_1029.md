# Design benchmark - backend ollama - 2026-10-30 10:29

LLM: Ollama (gemma3:4b). Requests: 21 (15 to design, 6 to refuse).

| measure | result |
|---|---|
| classified as design (design requests) | 15/15 |
| specification read correctly | 14/15 |
| agent result = direct optimize(...) call | 14/15 |
| MATLAB re-check passed | 14/15 |
| refused as they should be | 6/6 |
| fully correct | 20/21 |
| explanation: LLM / after one retry / pre-built | 12 / 0 / 2 |

| id | outcome | design | plies | margin | status | MATLAB | direct call | time (s) | note |
|---|---|---|---|---|---|---|---|---|---|
| DS1 | designed | [90/-45/0/45/0_2]s | 12 | 1.644 | optimal | True | True | 11.3 |  |
| DS2 | designed | [90/45/90_2/-45/90/-45/45/-45_2/45/90/45_2/-45/90/0_2]s | 36 | 1.668 | best found | True | True | 51.7 |  |
| DS3 | designed | [45/-45_3/45_3/-45/45/-45/90/45_2/-45_2/0_2/90]s | 36 | 2.369 | best found | True | True | 20.6 |  |
| DS4 | designed | [-45_4/90/0_2/45_2/90/45_2]s | 24 | 1.518 | optimal | True | True | 7.6 |  |
| DS5 | designed | [90/0/-45/0/45/0_2]s | 14 | 1.702 | optimal | True | True | 6.2 |  |
| DS6 | designed | [-45/45_2/-45/45/-45_2/45/0_2/90_2]s | 24 | 0.2959 | infeasible | True | True | 9.5 |  |
| DS7 | designed | [-45/45_2/-45/45/-45/0/90]s | 16 | 0.2622 | infeasible | True | True | 6.1 |  |
| DS8 | designed | [-45/45_2/-45/45/-45_2/45/0_3/90_2]s | 26 | 1.64 | optimal | True | True | 16.3 |  |
| DS9 | designed | [90/-45/0/45/0/90/0_2]s | 16 | 4.771 | optimal | True | True | 6.0 |  |
| DS10 | designed | [-45/45_2/-45/45/-45/90/0]s | 16 | 1.618 | optimal | True | True | 6.3 |  |
| DS11 | refused |  |  |  |  |  |  | 3.7 | 'lightest' and a fixed number of plies (24) contradict each other: with a fixed ply count the objective is the largest s |
| DS12 | designed | [-45/45/-45_2/45/-45_2/45_3/0_2/90_2]s | 28 | 2.501 | optimal | True | True | 17.7 |  |
| DS13 | designed | [90/-45/45/0]s | 8 | 1.887 | optimal | True | True | 6.2 |  |
| DS20 | designed | [90/-45/45/0]s | 8 | 1.76 | optimal | True | True | 5.8 |  |
| DS21 | designed | [90/-45/45/0_2]s | 10 | 2.08 | optimal | True | True | 6.3 |  |
| DS14 | refused |  |  |  |  |  |  | 3.2 | the request has moment(s) Mx; the optimisation handles in-plane loads Nx, Ny, Nxy only (supported: in-plane loads Nx, Ny |
| DS15 | refused |  |  |  |  |  |  | 3.4 | objective 'stiffest' is not supported; supported: in-plane loads Nx, Ny, Nxy; objective 'lightest' (fewest plies, defaul |
| DS16 | refused |  |  |  |  |  |  | 4.1 | the text names no material or fibre type (e.g. 'IM7/8552', 'carbon/epoxy', 'glass/epoxy', 'Kevlar/epoxy'); the program d |
| DS17 | refused |  |  |  |  |  |  | 3.3 | the request is ambiguous: the text gives the load '100 kN/m' (in 'Design a carbon/epoxy laminate for a load of 100 kN/m' |
| DS18 | refused |  |  |  |  |  |  | 3.8 | ply angle(s) [30.0] deg: only 0, +45, -45 and 90 degree plies are supported |
| DS19 | refused |  |  |  |  |  |  | 0.0 | the text gives a stacking sequence ([0/90]2s) AND asks for a design ('optimis'): to check that laminate, remove the desi |
