# backend/app/models/schemas.py
from __future__ import annotations

from pydantic import BaseModel
from typing import List


# -------- Components DTOs --------
class ComponentDTO(BaseModel):
    cid: int
    num_nodes: int
    num_edges: int


class ComponentsDTO(BaseModel):
    components: List[ComponentDTO]
