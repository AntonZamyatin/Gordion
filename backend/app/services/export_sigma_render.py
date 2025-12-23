# backend/app/services/export_sigma_render.py
from __future__ import annotations

from app.models.schemas import GraphDTO, NodeDTO, EdgeDTO
from app.render.render_graph import RenderGraph
from app.config.viz_config import CFG


def rendergraph_to_sigma_dto(rg: RenderGraph, *, positions: dict[str, tuple[float, float]]) -> GraphDTO:
    nodes_out: list[NodeDTO] = []
    for rid, rn in rg.nodes.items():
        x, y = positions.get(rid, (0.0, 0.0))
        node_size = CFG.style.spacer_node_size if rn.kind == "SPACER" else CFG.style.endpoint_node_size
        label = rn.core_node_id if rn.kind in ("IN", "OUT") else None
        nodes_out.append(NodeDTO(
                           id=rid, 
                           x=x, y=y, 
                           label=label, 
                           size=node_size,
                           core_node_id=rn.core_node_id,)
                        )

    edges_out: list[EdgeDTO] = []
    for eid, e in rg.edges.items():
        # key: internal edges thick, external thin
        edge_size = CFG.style.internal_edge_size if e.kind == "INTERNAL" else CFG.style.external_edge_size
        # For INTERNAL edges, both endpoints belong to the same core node.
        core_node_id = None
        if e.kind == "INTERNAL":
            core_node_id = rg.nodes[e.start].core_node_id
        
        edges_out.append(
            EdgeDTO(
                id=eid,
                source=e.start,
                target=e.end,
                size=edge_size,
                kind=e.kind,
                core_node_id=core_node_id,
                core_edge_id=e.core_edge_id,
            )
        )

    return GraphDTO(nodes=nodes_out, edges=edges_out)
