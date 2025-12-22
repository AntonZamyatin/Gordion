from __future__ import annotations
import math
from typing import Iterable

from app.domain.graph import CoreGraph
from app.models.schemas import GraphDTO, NodeDTO, EdgeDTO


def coregraph_to_sigma_dto(
    g: CoreGraph,
    *,
    positions: dict[str, tuple[float, float]],
    node_ids: Iterable[str] | None = None,
) -> GraphDTO:
    """
    Convert CoreGraph to Sigma GraphDTO using provided positions.

    Note: CoreGraph edges are port-based endpoints; Sigma v0 draws edges
    between node centers, so we map edge to (start_node -> end_node).
    """
    if node_ids is None:
        node_list = sorted(g.nodes.keys())
        node_set = set(node_list)
    else:
        node_list = list(node_ids)
        node_set = set(node_list)

    nodes_out: list[NodeDTO] = []
    for nid in node_list:
        x, y = positions.get(nid, (0.0, 0.0))
        node = g.nodes[nid]

        # Size heuristic; keep deterministic and bounded
        size = 6.0
        if node.length_bp is not None and node.length_bp > 0:
            size = max(4.0, min(20.0, 2.0 + math.log10(node.length_bp)))

        nodes_out.append(NodeDTO(id=nid, x=x, y=y, label=nid, size=size))

    edges_out: list[EdgeDTO] = []
    for eid, e in g.edges.items():
        u = e.start[0]
        v = e.end[0]
        if u in node_set and v in node_set:
            edges_out.append(EdgeDTO(id=eid, source=u, target=v))

    return GraphDTO(nodes=nodes_out, edges=edges_out)
