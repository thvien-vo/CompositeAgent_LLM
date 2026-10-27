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