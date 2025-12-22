from __future__ import annotations
import math
from dataclasses import dataclass

from app.layout.pack_base import PackingEngine, PackParams, BBox


@dataclass
class RowPackingEngine(PackingEngine):
    """
    Simple deterministic rectangle packing:
    - sort components by bbox area descending
    - place left-to-right into rows with padding
    - new row when width exceeds target

    Guarantees non-overlap (with padding) and keeps components relatively near.
    """
    name: str = "rows"

    def pack(self, *, component_boxes: dict[int, BBox],
                      params: PackParams) -> dict[int, tuple[float, float]]:
        items = list(component_boxes.items())
        # stable sort: area desc, cid asc
        items.sort(key=lambda kv: (-kv[1].area, kv[0]))

        total_area = sum(bb.area for _, bb in items)
        target = params.target_row_width
        if target is None:
            # heuristic target width
            target = math.sqrt(max(total_area, 1.0)) * 1.3

        pad = params.padding

        offsets: dict[int, tuple[float, float]] = {}

        cursor_x = 0.0
        cursor_y = 0.0
        row_h = 0.0

        for cid, bb in items:
            w = bb.w + pad
            h = bb.h + pad

            if cursor_x > 0.0 and (cursor_x + w) > target:
                # new row
                cursor_x = 0.0
                cursor_y += row_h
                row_h = 0.0

            # place bbox so that local (min_x, min_y) maps to (cursor_x + pad/2, cursor_y + pad/2)
            dx = cursor_x + (pad * 0.5) - bb.min_x
            dy = cursor_y + (pad * 0.5) - bb.min_y
            offsets[cid] = (dx, dy)

            cursor_x += w
            row_h = max(row_h, h)

        return offsets
