from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response

from app.parsers.gfa import parse_gfa
from app.services.session_store import SessionStore, GraphSession
from app.services.scene_service import scene_bytes_for_session
from app.models.schemas import ComponentsDTO, ComponentDTO

router = APIRouter(prefix="/graphs", tags=["graphs"])

STORE = SessionStore()

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _session_or_404(graph_id: str) -> GraphSession:
    try:
        sid = UUID(graph_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid graph_id")
    if not STORE.has(sid):
        raise HTTPException(status_code=404, detail="Unknown graph_id")
    return STORE.get(sid)


@router.post("/load")
def load_graph(name: str = "example") -> dict:
    """Parse data/<name>.gfa into a new session and return its id + summary."""
    if not _NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="invalid name")
    path = DATA_DIR / f"{name}.gfa"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name}.gfa not found")

    g = parse_gfa(path)
    sid = STORE.create(g, source=name)
    return {
        "graph_id": str(sid),
        "source": name,
        "contigCount": len(g.nodes),
        "linkCount": len(g.edges),
        "componentCount": len(g.get_components().summaries),
    }


@router.post("/load-example")
def load_example() -> dict:
    """Back-compat alias for load(name='example')."""
    return load_graph("example")


@router.get("/{graph_id}/scene")
def get_scene(graph_id: str, recompute: bool = False) -> Response:
    """Binary GSC1 scene for the session (layout cached; recompute=true forces)."""
    sess = _session_or_404(graph_id)
    blob = scene_bytes_for_session(sess, recompute=recompute)
    return Response(
        content=blob,
        media_type="application/octet-stream",
        headers={"X-Scene-Source": sess.source},
    )


@router.get("/{graph_id}/components", response_model=ComponentsDTO)
def list_components(graph_id: str) -> ComponentsDTO:
    sess = _session_or_404(graph_id)
    comps = sess.graph.get_components()
    return ComponentsDTO(
        components=[
            ComponentDTO(cid=s.cid, num_nodes=s.num_nodes, num_edges=s.num_edges)
            for s in comps.summaries
        ]
    )
