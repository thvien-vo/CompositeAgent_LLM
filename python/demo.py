from schemas import CLTInput
from ml import predict_material
from matlab_clt import run_clt

problem = CLTInput.model_validate({
    "material": "CFRP",
    "plies": [{"angle": a, "thickness": 0.000125}
              for a in [0, 45, -45, 90, 90, -45, 45, 0]],
    "loads": {"Nx": 1000, "Ny": 500, "Nxy": 100,
              "Mx": 0, "My": 0, "Mxy": 0},
})
print("Input:", problem)

material = predict_material(problem.material)
print("Material (ML):", material)

result = run_clt(problem, material)
print("CLT result:", result)
# Reference numbers that must never change: max FI ~ 0.00238, critical ply 4, ABD(1,1) ~ 5.94e7 N/m
fi, ply, a11 = result["max_failure_index"], int(result["critical_ply"]), result["ABD"][0][0]
ok = abs(fi - 0.00238) < 5e-6 and ply == 4 and abs(a11 - 5.94e7) / 5.94e7 < 1e-3
print(f"\nCHECK max_failure_index={fi:.6f} (ref 0.00238), critical_ply={ply} (ref 4), "
      f"ABD(1,1)={a11:.6g} N/m (ref 5.94e7) -> {'PASS' if ok else 'FAIL'}")
