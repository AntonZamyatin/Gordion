# backend/app/api/routes_scene.py
"""Stateless convenience endpoint: binary scene for a named example GFA.

Handy for dev/spikes (single URL, no session). The session-based
/graphs/{id}/scene is the real path. Recomputes the layout on every call.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response

from app.parsers.gfa import parse_gfa
from app.services.scene_service import scene_for_core
from app.services.scene_codec import encode_scene

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


@router.get("/scene/{name}")
def get_scene(name: str) -> Response:
    if not _NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="invalid name")
    path = DATA_DIR / f"{name}.gfa"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name}.gfa not found")

    core = parse_gfa(path)
    blob = encode_scene(scene_for_core(core, source=name))
    return Response(
        content=blob,
        media_type="application/octet-stream",
        headers={"X-Scene-Source": name},
    )
