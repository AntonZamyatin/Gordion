# backend/app/services/export_sigma_render.py
from __future__ import annotations

from app.models.schemas import GraphDTO, NodeDTO, EdgeDTO
from app.render.render_graph import RenderGraph


def rendergraph_to_sigma_dto(rg: RenderGraph, *, positions: dict[str, tuple[float, float]]) -> GraphDTO:
    nodes_out: list[NodeDTO] = []
    for rid, rn in rg.nodes.items():
        x, y = positions.get(rid, (0.0, 0.0))
        size = 1.5 if rn.kind == "SPACER" else 4.0
        label = rn.core_node_id if rn.kind in ("IN", "OUT") else None
        nodes_out.append(NodeDTO(id=rid, x=x, y=y, label=label, size=size))

    edges_out: list[EdgeDTO] = []
    for eid, e in rg.edges.items():
        # key: internal edges thick, external thin
        edge_size = 8.0 if e.kind == "INTERNAL" else 1.5
        edges_out.append(EdgeDTO(id=eid, source=e.start, target=e.end, size=edge_size))

    return GraphDTO(nodes=nodes_out, edges=edges_out)
