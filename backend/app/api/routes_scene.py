# backend/app/api/routes_scene.py
"""Temporary Phase 3 endpoint: serve a binary scene for an example GFA.

This wires the binary scene contract end-to-end (parse -> port graph -> SGD ->
ribbon geometry -> GSC1 bytes) so the deck.gl spike can render a real graph from
the encoder. The session-based /graphs/{id}/scene is Phase 4/5; for now this
computes a fresh layout per request (no caching).
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response

from app.parsers.gfa import parse_gfa
from app.layout.port_graph import build_port_graph, PortGraphParams
from app.layout.engine_sgd import layout_port_graph, SgdParams
from app.services.ribbon import build_scene
from app.services.scene_codec import encode_scene

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


@router.get("/scene/{name}")
def get_scene(name: str, iterations: int = 30, pivots: int = 50) -> Response:
    if not _NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="invalid name")
    path = DATA_DIR / f"{name}.gfa"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name}.gfa not found")

    core = parse_gfa(path)
    pg = build_port_graph(core, PortGraphParams())
    positions = layout_port_graph(pg, SgdParams(iterations=iterations, n_pivots=pivots))
    scene = build_scene(core, pg, positions, source=name)
    blob = encode_scene(scene)

    return Response(
        content=blob,
        media_type="application/octet-stream",
        headers={"X-Scene-Source": name},
    )
