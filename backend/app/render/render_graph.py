# backend/app/render/render_graph.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

RenderNodeKind = Literal["IN", "OUT", "SPACER"]
RenderEdgeKind = Literal["INTERNAL", "EXTERNAL"]


@dataclass(frozen=True, slots=True)
class RenderNode:
    """
    Node used for visualization/layout only.
    Each RenderNode maps back to exactly one CoreGraph node (core_node_id).
    """
    id: str
    core_node_id: str
    kind: RenderNodeKind
    # index along the chain: 0=IN, 1..k=spacers, k+1=OUT
    chain_index: int


@dataclass(frozen=True, slots=True)
class RenderEdge:
    """
    Edge used for visualization/layout only.

    INTERNAL edges form the backbone (IN -> ... -> OUT) of a CoreGraph node.
    EXTERNAL edges correspond to CoreGraph edges connecting ports.
    """
    id: str
    start: str  # render node id
    end: str    # render node id
    kind: RenderEdgeKind
    core_edge_id: Optional[str] = None  # only for EXTERNAL edges
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class RenderChain:
    """
    Convenience structure describing the pseudovertex chain for one core node.
    """
    core_node_id: str
    in_id: str
    out_id: str
    spacer_ids: list[str]

    def endpoint_for_port(self, port: str) -> str:
        # CoreGraph ports are "IN"/"OUT"
        return self.in_id if port == "IN" else self.out_id

    @property
    def all_ids(self) -> list[str]:
        return [self.in_id] + self.spacer_ids + [self.out_id]


@dataclass(slots=True)
class RenderGraph:
    """
    Graph used for layout + visualization.
    """
    nodes: dict[str, RenderNode] = field(default_factory=dict)   # render_node_id -> RenderNode
    edges: dict[str, RenderEdge] = field(default_factory=dict)   # render_edge_id -> RenderEdge

    # Mappings for interaction & back-references
    chain_by_core_node: dict[str, RenderChain] = field(default_factory=dict)  # core_node_id -> chain
    core_node_by_render_node: dict[str, str] = field(default_factory=dict)   # render_node_id -> core_node_id

    def add_node(self, n: RenderNode) -> None:
        if n.id in self.nodes:
            raise ValueError(f"Duplicate render node id: {n.id}")
        self.nodes[n.id] = n
        self.core_node_by_render_node[n.id] = n.core_node_id

    def add_edge(self, e: RenderEdge) -> None:
        if e.id in self.edges:
            raise ValueError(f"Duplicate render edge id: {e.id}")
        # endpoints must exist
        if e.start not in self.nodes or e.end not in self.nodes:
            raise ValueError(f"Render edge endpoints must exist: {e.start} -> {e.end}")
        self.edges[e.id] = e

    def has_node(self, render_node_id: str) -> bool:
        return render_node_id in self.nodes
