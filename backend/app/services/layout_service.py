from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

from app.domain.graph import CoreGraph
from app.layout.engine_base import LayoutEngine, LayoutParams
from app.layout.engine_circle import CircleLayoutEngine
from app.layout.pack_base import PackingEngine, PackParams, BBox
from app.layout.pack_rows import RowPackingEngine


def _bbox_of_positions(pos: dict[str, tuple[float, float]]) -> BBox:
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    if not xs:
        return BBox(0.0, 0.0, 0.0, 0.0)
    return BBox(min(xs), min(ys), max(xs), max(ys))


@dataclass
class LayoutService:
    """
    Orchestrates two-level layout:
      - per-component layout via LayoutEngine
      - packing via PackingEngine

    Modular via registry dicts.
    """

    layout_engines: dict[str, LayoutEngine]
    pack_engines: dict[str, PackingEngine]

    @staticmethod
    def default() -> "LayoutService":
        return LayoutService(
            layout_engines={
                "circle": CircleLayoutEngine(),
                # later: "sfdp": GraphvizSfdpEngine(...)
            },
            pack_engines={
                "rows": RowPackingEngine(),
                # later: "maxrects": ...
            },
        )

    def compute_full_view_positions(
        self,
        *,
        graph: CoreGraph,
        layout: str = "circle",
        pack: str = "rows",
        layout_params: LayoutParams | None = None,
        pack_params: PackParams | None = None,
    ) -> dict[str, tuple[float, float]]:
        """
        Returns GLOBAL positions for all nodes, packed so components don't overlap.
        """
        layout_engine = self.layout_engines[layout]
        pack_engine = self.pack_engines[pack]
        if layout_params is None:
            layout_params = LayoutParams(name=layout, seed=0)
        if pack_params is None:
            pack_params = PackParams(name=pack, padding=80.0)

        comps = graph.get_components()

        # Build node lists per component
        nodes_by_cid: dict[int, list[str]] = {}
        for nid, cid in comps.node_to_cid.items():
            nodes_by_cid.setdefault(cid, []).append(nid)

        # Step 1: local layout per component + bbox
        local_pos_by_cid: dict[int, dict[str, tuple[float, float]]] = {}
        bbox_by_cid: dict[int, BBox] = {}

        for cid, nids in nodes_by_cid.items():
            local = layout_engine.layout_component(graph=graph, node_ids=nids, params=layout_params)
            local_pos_by_cid[cid] = local
            bbox_by_cid[cid] = _bbox_of_positions(local)

        # Step 2: pack components (get offsets per component)
        offsets = pack_engine.pack(component_boxes=bbox_by_cid, params=pack_params)

        # Step 3: produce global positions
        global_pos: dict[str, tuple[float, float]] = {}
        for cid, local in local_pos_by_cid.items():
            dx, dy = offsets.get(cid, (0.0, 0.0))
            for nid, (x, y) in local.items():
                global_pos[nid] = (x + dx, y + dy)

        return global_pos

    def compute_component_positions(
        self,
        *,
        graph: CoreGraph,
        cid: int,
        layout: str = "circle",
        layout_params: LayoutParams | None = None,
        center: bool = True,
    ) -> dict[str, tuple[float, float]]:
        """
        Returns LOCAL positions for nodes in one component.
        Optionally recenters component around (0,0).
        """
        layout_engine = self.layout_engines[layout]
        if layout_params is None:
            layout_params = LayoutParams(name=layout, seed=0)

        node_ids = graph.nodes_in_component(cid)
        local = layout_engine.layout_component(graph=graph, node_ids=node_ids, params=layout_params)

        if center and local:
            bb = _bbox_of_positions(local)
            cx = 0.5 * (bb.min_x + bb.max_x)
            cy = 0.5 * (bb.min_y + bb.max_y)
            local = {nid: (x - cx, y - cy) for nid, (x, y) in local.items()}

        return local
