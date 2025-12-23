from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pathlib import Path
from uuid import UUID

from app.parsers.gfa import parse_gfa
from app.services.session_store import SessionStore
from app.services.layout_service import LayoutService
from app.services.export_sigma import coregraph_to_sigma_dto
from app.models.schemas import GraphDTO, ComponentsDTO, ComponentDTO, PositionUpdatesDTO, PositionResetDTO
from app.render.render_builder import build_render_graph
from app.config.viz_config import CFG
from app.render.render_policy import RenderPolicy
from app.services.export_sigma_render import rendergraph_to_sigma_dto

router = APIRouter(prefix="/graphs", tags=["graphs"])

STORE = SessionStore()
LAYOUT = LayoutService.default()

EXAMPLE_GFA_PATH = Path(__file__).resolve().parents[2] / "data" / "example2.gfa"

def _uuid_or_400(graph_id: str) -> UUID:
    try:
        return UUID(graph_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid graph_id")


@router.post("/load-example", response_model=str)
def load_example() -> str:
    if not EXAMPLE_GFA_PATH.exists():
        raise HTTPException(status_code=404, detail=f"example.gfa not found at {EXAMPLE_GFA_PATH}")

    g = parse_gfa(EXAMPLE_GFA_PATH)
    sid = STORE.create(g)
    return str(sid)


@router.get("/{graph_id}/components", response_model=ComponentsDTO)
def list_components(graph_id: str) -> ComponentsDTO:
    sid = _uuid_or_400(graph_id)
    if not STORE.has(sid):
        raise HTTPException(status_code=404, detail="Unknown graph_id")

    g = STORE.get_graph(sid)
    comps = g.get_components()

    out = [
        ComponentDTO(cid=s.cid, num_nodes=s.num_nodes, num_edges=s.num_edges)
        for s in comps.summaries
    ]
    return ComponentsDTO(components=out)


@router.get("/{graph_id}/view", response_model=GraphDTO)
def get_full_view(
    graph_id: str,
    layout: str = "igraph_fr",
    pack: str = "rows",
) -> GraphDTO:
    """
    Full graph view:
      - per-component layout
      - pack components to avoid overlap
      - apply user overrides (dragged nodes)
    """
    sid = _uuid_or_400(graph_id)
    if not STORE.has(sid):
        raise HTTPException(status_code=404, detail="Unknown graph_id")

    sess = STORE.get_session(sid)
    
    # 1) core -> render
    policy = RenderPolicy(
    bp_per_spacer=CFG.render.bp_per_spacer,
    k_min=CFG.render.k_min,
    k_max=CFG.render.k_max,
    internal_edge_weight=CFG.layout.internal_edge_weight,
    external_edge_weight=CFG.layout.external_edge_weight,)
    
    rg = build_render_graph(sess.graph, policy)

    # 2) layout render graph (two-level, components in render graph!)
    computed = LAYOUT.compute_full_view_positions(graph=rg, layout=layout, pack=pack)
    sess.pos.computed = computed
    final_pos = sess.pos.merged()

    # 3) export render graph to sigma
    return rendergraph_to_sigma_dto(rg, positions=final_pos)


@router.get("/{graph_id}/component/{cid}/view", response_model=GraphDTO)
def get_component_view(
    graph_id: str,
    cid: int,
    layout: str = "circle",
) -> GraphDTO:
    """
    Single component view (not packed with others), centered near origin.
    Overrides are still applied if present.
    """
    sid = _uuid_or_400(graph_id)
    if not STORE.has(sid):
        raise HTTPException(status_code=404, detail="Unknown graph_id")

    sess = STORE.get_session(sid)
    g = sess.graph

    # local positions for component
    local = LAYOUT.compute_component_positions(graph=g, cid=cid, layout=layout, center=True)

    # merge overrides for nodes in this component only
    final = dict(local)
    for nid, (x, y) in sess.pos.overrides.items():
        if nid in final:
            final[nid] = (x, y)

    node_ids = g.nodes_in_component(cid)
    return coregraph_to_sigma_dto(g, positions=final, node_ids=node_ids)


@router.post("/{graph_id}/positions")
def update_positions(graph_id: str, payload: PositionUpdatesDTO) -> dict[str, str]:
    """
    Store user overrides (frontend dragging).
    """
    sid = _uuid_or_400(graph_id)
    if not STORE.has(sid):
        raise HTTPException(status_code=404, detail="Unknown graph_id")

    sess = STORE.get_session(sid)
    g = sess.graph

    for u in payload.updates:
        if not g.has_node(u.id):
            # ignore unknown IDs to be robust; you can also raise 400 if you prefer strictness
            continue
        sess.pos.set_override(u.id, u.x, u.y)

    return {"status": "ok"}


@router.post("/{graph_id}/positions/reset")
def reset_positions(graph_id: str, payload: PositionResetDTO) -> dict[str, str]:
    """
    Reset overrides:
      - payload.id is None: reset all
      - payload.id provided: reset one node override
    """
    sid = _uuid_or_400(graph_id)
    if not STORE.has(sid):
        raise HTTPException(status_code=404, detail="Unknown graph_id")

    sess = STORE.get_session(sid)

    if payload.id is None:
        sess.pos.clear_all_overrides()
    else:
        sess.pos.clear_override(payload.id)

    return {"status": "ok"}
