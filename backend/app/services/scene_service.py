# backend/app/services/scene_service.py
"""Pipeline glue: CoreGraph -> port graph -> SGD layout -> ribbon Scene.

Used by the session endpoints (with layout caching) and by the stateless
convenience endpoint.
"""
from __future__ import annotations

from app.domain.graph import CoreGraph
from app.layout.port_graph import build_port_graph, PortGraphParams
from app.layout.engine_sgd import layout_port_graph, SgdParams
from app.services.ribbon import build_scene
from app.services.scene_codec import Scene, encode_scene
from app.services.session_store import GraphSession


def scene_for_core(
    core: CoreGraph,
    *,
    source: str,
    layout_params: SgdParams | None = None,
    graph_params: PortGraphParams | None = None,
) -> Scene:
    pg = build_port_graph(core, graph_params or PortGraphParams())
    pos = layout_port_graph(pg, layout_params or SgdParams())
    return build_scene(core, pg, pos, source=source)


def compute_layout(
    session: GraphSession,
    *,
    layout_params: SgdParams | None = None,
    graph_params: PortGraphParams | None = None,
) -> None:
    """Build the port graph + SGD positions and cache them on the session."""
    pg = build_port_graph(session.graph, graph_params or PortGraphParams())
    session.port_graph = pg
    session.computed = layout_port_graph(pg, layout_params or SgdParams())


def scene_for_session(
    session: GraphSession,
    *,
    recompute: bool = False,
    layout_params: SgdParams | None = None,
) -> Scene:
    if recompute or session.port_graph is None or not session.computed:
        compute_layout(session, layout_params=layout_params)
    assert session.port_graph is not None
    return build_scene(
        session.graph,
        session.port_graph,
        session.merged_positions(),
        source=session.source,
    )


def scene_bytes_for_session(session: GraphSession, **kwargs) -> bytes:
    return encode_scene(scene_for_session(session, **kwargs))
