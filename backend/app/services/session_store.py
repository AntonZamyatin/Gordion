from __future__ import annotations
from dataclasses import dataclass, field
from uuid import UUID, uuid4
from app.domain.graph import CoreGraph


@dataclass
class PositionStore:
    # Most recently computed full-view positions (packed global coords)
    computed: dict[str, tuple[float, float]] = field(default_factory=dict)
    # User overrides (dragged positions)
    overrides: dict[str, tuple[float, float]] = field(default_factory=dict)

    def merged(self) -> dict[str, tuple[float, float]]:
        out = dict(self.computed)
        out.update(self.overrides)
        return out

    def set_override(self, node_id: str, x: float, y: float) -> None:
        self.overrides[node_id] = (x, y)

    def clear_override(self, node_id: str) -> None:
        self.overrides.pop(node_id, None)

    def clear_all_overrides(self) -> None:
        self.overrides.clear()


@dataclass
class GraphSession:
    id: UUID
    graph: CoreGraph
    pos: PositionStore = field(default_factory=PositionStore)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[UUID, GraphSession] = {}

    def create(self, graph: CoreGraph) -> UUID:
        sid = uuid4()
        self._sessions[sid] = GraphSession(id=sid, graph=graph)
        return sid

    def get_session(self, sid: UUID) -> GraphSession:
        return self._sessions[sid]

    def get_graph(self, sid: UUID) -> CoreGraph:
        return self._sessions[sid].graph

    def has(self, sid: UUID) -> bool:
        return sid in self._sessions
