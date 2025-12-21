from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Tuple

Port = Literal["IN", "OUT"]
Endpoint = Tuple[str, Port]   # (node_id, port)


@dataclass(slots=True)
class Node:
    id: str
    length_bp: int | None = None
    coverage: float | None = None
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class Edge:
    id: str
    start: Endpoint        # (node_id, port)
    end: Endpoint          # (node_id, port)
    overlap: str | None = None
    tags: dict[str, str] = field(default_factory=dict)
