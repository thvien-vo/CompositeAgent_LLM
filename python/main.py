from llm import parse_input, explain_result
from ml import predict_material
from matlab_clt import run_clt


def main(user_text):

    # -------------------------
    # 1 LLM
    # -------------------------

    problem = parse_input(user_text)

    print("Parsed input:")
    print(problem)

    # -------------------------
    # 2 ML
    # -------------------------

    material = predict_material(problem.material)

    # -------------------------
    # 3 MATLAB CLT
    # -------------------------

    result = run_clt(
        problem,
        material
    )

    # -------------------------
    # 4 LLM
    # -------------------------

    answer = explain_result(
        problem,
        result
    )

    print("DEBUG max_failure_index:", result["max_failure_index"])
    print("DEBUG critical_ply:", result["critical_ply"])
    return answer


if __name__ == "__main__":

    user_text = """
    CFRP laminate.
    Ply angles: 0, 45, -45, 90.
    Ply thickness: 0.125 mm.
    Nx=1000 N/m.
    Ny=500 N/m.
    Nxy=100 N/m.
    """

    answer = main(user_text)

    print("\n===== RESULT =====")
    print(answer)
