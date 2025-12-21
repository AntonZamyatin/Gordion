# backend/app/api/routes_graph.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pathlib import Path
from uuid import UUID

from app.parsers.gfa import parse_gfa
from app.services.session_store import SessionStore
from app.services.export_sigma import coregraph_to_sigma_dto
from app.models.schemas import GraphDTO


router = APIRouter(prefix="/graphs", tags=["graphs"])

# In-memory store for MVP
STORE = SessionStore()

# Adjust this path to where you keep example.gfa
EXAMPLE_GFA_PATH = Path(__file__).resolve().parents[2] / "data" / "example.gfa"


@router.post("/load-example", response_model=str)
def load_example() -> str:
    if not EXAMPLE_GFA_PATH.exists():
        raise HTTPException(status_code=404, detail=f"example.gfa not found at {EXAMPLE_GFA_PATH}")

    g = parse_gfa(EXAMPLE_GFA_PATH)
    sid = STORE.create(g)
    return str(sid)


@router.get("/{graph_id}/view", response_model=GraphDTO)
def get_graph_view(graph_id: str) -> GraphDTO:
    try:
        sid = UUID(graph_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid graph_id")

    if not STORE.has(sid):
        raise HTTPException(status_code=404, detail="Unknown graph_id")

    g = STORE.get(sid)
    return coregraph_to_sigma_dto(g)
