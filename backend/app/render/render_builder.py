# backend/app/render/render_builder.py
from __future__ import annotations

import math

from app.domain.graph import CoreGraph
from app.render.render_graph import RenderGraph, RenderNode, RenderEdge, RenderChain
from app.render.render_policy import RenderPolicy


def _spacer_count(length_bp: int | None, policy: RenderPolicy) -> int:
    if length_bp is None or length_bp <= 0:
        k = policy.k_min
    else:
        k = int(round(length_bp / policy.bp_per_spacer))
    k = max(policy.k_min, min(policy.k_max, k))
    return k


def build_render_graph(core: CoreGraph, policy: RenderPolicy) -> RenderGraph:
    """
    Expand each CoreGraph node into a chain:
        IN -> (k spacers) -> OUT
    and translate each CoreGraph edge into an EXTERNAL RenderEdge connecting correct endpoints.
    """
    rg = RenderGraph()

    # 1) Create chains for all core nodes
    for core_id, node in core.nodes.items():
        k = _spacer_count(node.length_bp, policy)

        in_id = f"{core_id}::IN"
        out_id = f"{core_id}::OUT"
        spacer_ids = [f"{core_id}::S{i}" for i in range(1, k + 1)]

        # Add render nodes
        rg.add_node(RenderNode(id=in_id, core_node_id=core_id, kind="IN", chain_index=0))
        for i, sid in enumerate(spacer_ids, start=1):
            rg.add_node(RenderNode(id=sid, core_node_id=core_id, kind="SPACER", chain_index=i))
        rg.add_node(RenderNode(id=out_id, core_node_id=core_id, kind="OUT", chain_index=k + 1))

        chain = RenderChain(core_node_id=core_id, in_id=in_id, out_id=out_id, spacer_ids=spacer_ids)
        rg.chain_by_core_node[core_id] = chain

        # Add internal backbone edges
        chain_ids = chain.all_ids
        for a, b in zip(chain_ids, chain_ids[1:]):
            eid = f"int:{a}->{b}"
            rg.add_edge(
                RenderEdge(
                    id=eid,
                    start=a,
                    end=b,
                    kind="INTERNAL",
                    core_edge_id=None,
                    tags={"w": f"f:{policy.internal_edge_weight}"},
                )
            )

    # 2) Translate core edges into external render edges
    for core_eid, e in core.edges.items():
        u_core, u_port = e.start
        v_core, v_port = e.end

        u_chain = rg.chain_by_core_node.get(u_core)
        v_chain = rg.chain_by_core_node.get(v_core)
        if u_chain is None or v_chain is None:
            # should not happen if core graph is consistent
            continue

        u_r = u_chain.endpoint_for_port(u_port)
        v_r = v_chain.endpoint_for_port(v_port)

        reid = f"ext:{core_eid}"
        rg.add_edge(
            RenderEdge(
                id=reid,
                start=u_r,
                end=v_r,
                kind="EXTERNAL",
                core_edge_id=core_eid,
                tags={"w": f"f:{policy.external_edge_weight}"},
            )
        )

    return rg
