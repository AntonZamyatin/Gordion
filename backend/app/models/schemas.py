# backend/app/models/schemas.py
from __future__ import annotations

from pydantic import BaseModel
from typing import List, Optional


# -------- Sigma view DTOs --------
class NodeDTO(BaseModel):
    id: str
    x: float
    y: float
    label: Optional[str] = None
    size: float = 5.0


class EdgeDTO(BaseModel):
    source: str
    target: str
    id: Optional[str] = None
    size: float = 1.0   # NEW



class GraphDTO(BaseModel):
    nodes: List[NodeDTO]
    edges: List[EdgeDTO]


# -------- Components DTOs --------
class ComponentDTO(BaseModel):
    cid: int
    num_nodes: int
    num_edges: int


class ComponentsDTO(BaseModel):
    components: List[ComponentDTO]


# -------- Position update DTOs --------
class PositionUpdateDTO(BaseModel):
    id: str
    x: float
    y: float


class PositionUpdatesDTO(BaseModel):
    updates: List[PositionUpdateDTO]


class PositionResetDTO(BaseModel):
    # if None => reset all overrides
    id: Optional[str] = None
