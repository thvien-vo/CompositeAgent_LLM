import os
import json

from huggingface_hub import InferenceClient

from schemas import CLTInput
from ml import MATERIAL_DB

client = InferenceClient()

MODEL = "openai/gpt-oss-120b"


def ask_llm(prompt):

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=1000,
    )

    return response.choices[0].message.content


def parse_input(user_text):

    supported = ", ".join(MATERIAL_DB)  # "CFRP, GFRP, KEVLAR" -- lay thang tu bang vat lieu that

    prompt = f"""
You are an assistant for composite material analysis.

Please extract the information necessary for CLT calculations from the text below.

{user_text}

Please provide your answer exclusively in the following JSON format.
The "material" field must be exactly one of: {supported}.

IMPORTANT - units: convert every number into SI base units before writing it:
- "angle" in degrees (unchanged).
- "thickness" in METERS (e.g. "0.125 mm" -> 0.000125, NOT 0.125).
- "Nx","Ny","Nxy" in newtons per meter (N/m).
- "Mx","My","Mxy" in newton-meters per meter (N).

{{
  "material": "CFRP",
  "plies": [
    {{
      "angle": 0,
      "thickness": 0.000125
    }}
  ],
  "loads": {{
    "Nx": 0,
    "Ny": 0,
    "Nxy": 0,
    "Mx": 0,
    "My": 0,
    "Mxy": 0
  }}
}}

No explanation is necessary.
"""

    text = ask_llm(prompt)

    # LLM text string -> Python dict
    data = json.loads(text)

    # validate with Pydantic
    validated = CLTInput.model_validate(data)

    return validated


def explain_result(problem, result):

    prompt = f"""
Please briefly explain the CLT calculation results below.

Input:
{problem.model_dump_json()}

CLT result:
{result}

Please do not speculate about information that has not been calculated.
"""

    return ask_llm(prompt)