# backend/app/services/session_store.py
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.domain.graph import CoreGraph


@dataclass
class GraphSession:
    id: UUID
    graph: CoreGraph


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[UUID, GraphSession] = {}

    def create(self, graph: CoreGraph) -> UUID:
        sid = uuid4()
        self._sessions[sid] = GraphSession(id=sid, graph=graph)
        return sid

    def get(self, sid: UUID) -> CoreGraph:
        return self._sessions[sid].graph

    def has(self, sid: UUID) -> bool:
        return sid in self._sessions
