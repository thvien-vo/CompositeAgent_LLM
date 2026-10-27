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
    material: str
    plies: List[Ply]
    loads: Loads
