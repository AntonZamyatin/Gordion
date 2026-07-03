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


# -------- Dataset DTOs --------
class DatasetDTO(BaseModel):
    name: str  # pass this as ?name= to POST /graphs/load
    sizeBytes: int


class DatasetsDTO(BaseModel):
    datasets: List[DatasetDTO]
