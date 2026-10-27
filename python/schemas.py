from pydantic import BaseModel
from typing import List


class Ply(BaseModel):
    angle: float
    thickness: float


class Loads(BaseModel):
    Nx: float
    Ny: float
    Nxy: float
    Mx: float = 0
    My: float = 0
    Mxy: float = 0


class CLTInput(BaseModel):
    material: str                # group: CFRP / GFRP / KEVLAR (ML prediction)
    plies: List[Ply]
    loads: Loads
    material_name: str = ""      # CSV material whose measured properties are used ("" = ML group prediction)
    material_note: str = ""      # why a named material was or was not used
