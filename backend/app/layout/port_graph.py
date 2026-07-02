# backend/app/layout/port_graph.py
"""Port graph: the small layout representation that replaces the pseudo-vertex
RenderGraph.

Each core contig becomes exactly two layout nodes -- its IN port and its OUT
port -- joined by one INTERNAL edge whose target length encodes sequence length.
Core links become EXTERNAL edges between ports. Laying out *this* graph (2 nodes
per contig, not ~50) is what makes the SGD layout both fast and unfoldable, and
it hands each contig an oriented IN->OUT segment to draw a ribbon along.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math

from app.domain.graph import CoreGraph


def port_node_id(core_id: str, port: str) -> str:
    """Stable id for a port layout node, e.g. ("s1", "IN") -> "s1:IN"."""
    return f"{core_id}:{port}"


@dataclass(slots=True, frozen=True)
class PortEdge:
    u: str          # port node id
    v: str          # port node id
    kind: str       # "INTERNAL" | "EXTERNAL"
    target: float   # desired geometric length in layout units


@dataclass(slots=True)
class PortGraph:
    nodes: list[str]                         # all port node ids
    edges: list[PortEdge]
    contigs: dict[str, tuple[str, str]]      # core_id -> (in_node, out_node)
    meta: dict[str, dict] = field(default_factory=dict)  # core_id -> {length_bp, coverage}


@dataclass(slots=True, frozen=True)
class PortGraphParams:
    # Contig visual length L(bp) = min_len + length_scale * sqrt(bp).
    # sqrt keeps the huge bp dynamic range legible (Bandage-style).
    length_scale: float = 0.6
    min_len: float = 1.0
    default_len: float = 1.0     # used when length_bp is unknown
    # Junction gap between linked contig ends.
    external_target: float = 1.0


def contig_visual_length(length_bp: int | None, p: PortGraphParams) -> float:
    if length_bp is None or length_bp <= 0:
        return p.default_len
    return p.min_len + p.length_scale * math.sqrt(length_bp)


def build_port_graph(core: CoreGraph, params: PortGraphParams | None = None) -> PortGraph:
    p = params or PortGraphParams()

    nodes: list[str] = []
    contigs: dict[str, tuple[str, str]] = {}
    meta: dict[str, dict] = {}
    edges: list[PortEdge] = []

    for cid, node in core.nodes.items():
        in_id = port_node_id(cid, "IN")
        out_id = port_node_id(cid, "OUT")
        nodes.append(in_id)
        nodes.append(out_id)
        contigs[cid] = (in_id, out_id)
        meta[cid] = {"length_bp": node.length_bp, "coverage": node.coverage}
        edges.append(
            PortEdge(in_id, out_id, "INTERNAL", contig_visual_length(node.length_bp, p))
        )

    for e in core.edges.values():
        u_core, u_port = e.start
        v_core, v_port = e.end
        edges.append(
            PortEdge(
                port_node_id(u_core, u_port),
                port_node_id(v_core, v_port),
                "EXTERNAL",
                p.external_target,
            )
        )

    return PortGraph(nodes=nodes, edges=edges, contigs=contigs, meta=meta)
