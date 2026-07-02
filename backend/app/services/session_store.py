from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from app.domain.graph import CoreGraph
from app.layout.port_graph import PortGraph


@dataclass
class GraphSession:
    """An in-memory graph session: the topology plus its cached layout.

    Positions are keyed by *port node id* (e.g. "s1:IN"). `computed` holds the
    most recent SGD layout; `overrides` holds any user-set positions layered on
    top (dragging, later phases).
    """

    id: UUID
    graph: CoreGraph
    source: str = "graph"
    port_graph: PortGraph | None = None
    computed: dict[str, tuple[float, float]] = field(default_factory=dict)
    overrides: dict[str, tuple[float, float]] = field(default_factory=dict)

    def merged_positions(self) -> dict[str, tuple[float, float]]:
        out = dict(self.computed)
        out.update(self.overrides)
        return out

    def set_override(self, node_id: str, x: float, y: float) -> None:
        self.overrides[node_id] = (x, y)

    def clear_override(self, node_id: str) -> None:
        self.overrides.pop(node_id, None)

    def clear_all_overrides(self) -> None:
        self.overrides.clear()


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[UUID, GraphSession] = {}

    def create(self, graph: CoreGraph, source: str = "graph") -> UUID:
        sid = uuid4()
        self._sessions[sid] = GraphSession(id=sid, graph=graph, source=source)
        return sid

    def get(self, sid: UUID) -> GraphSession:
        return self._sessions[sid]

    def has(self, sid: UUID) -> bool:
        return sid in self._sessions
