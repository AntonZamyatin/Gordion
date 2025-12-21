# backend/app/services/export_sigma.py
from __future__ import annotations

import math
from typing import Iterable

from app.domain.graph import CoreGraph
from app.models.schemas import GraphDTO, NodeDTO, EdgeDTO


def coregraph_to_sigma_dto(
    g: CoreGraph,
    *,
    node_ids: Iterable[str] | None = None,
) -> GraphDTO:
    """
    Convert CoreGraph to a Sigma-ready DTO.

    Important:
    - CoreGraph edges are port-based: (node_id, port).
    - Sigma (for now) renders edges between node centers.
      So we map each Edge to (start_node_id -> end_node_id) ignoring ports.
    """
    if node_ids is None:
        node_list = sorted(g.nodes.keys())
        node_set = set(node_list)
    else:
        node_list = list(node_ids)
        node_set = set(node_list)

    n = len(node_list)
    if n == 0:
        return GraphDTO(nodes=[], edges=[])

    # Simple circle layout
    R = 100.0
    nodes_out: list[NodeDTO] = []
    for i, nid in enumerate(node_list):
        angle = 2.0 * math.pi * (i / n)
        x = R * math.cos(angle)
        y = R * math.sin(angle)

        node = g.nodes[nid]
        # Optional: size derived from length (log scale), else fixed
        size = 6.0
        if node.length_bp is not None and node.length_bp > 0:
            size = max(4.0, min(20.0, 2.0 + math.log10(node.length_bp)))

        nodes_out.append(NodeDTO(id=nid, x=x, y=y, label=nid, size=size))

    # Edges: include only if both endpoints are in the selected node_set
    edges_out: list[EdgeDTO] = []
    for eid, e in g.edges.items():
        u = e.start[0]
        v = e.end[0]
        if u in node_set and v in node_set:
            edges_out.append(EdgeDTO(id=eid, source=u, target=v))

    return GraphDTO(nodes=nodes_out, edges=edges_out)
