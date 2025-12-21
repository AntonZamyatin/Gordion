# backend/app/models/schemas.py
from __future__ import annotations

from pydantic import BaseModel
from typing import Optional, List


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


class GraphDTO(BaseModel):
    nodes: List[NodeDTO]
    edges: List[EdgeDTO]
