from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RenderPolicy:
    """
    Controls pseudovertex expansion.

    bp_per_spacer:
      how many base pairs correspond to one spacer node.
      Smaller => more spacers => smoother/longer segments but more nodes.

    k_max:
      absolute cap on spacer count to avoid explosions.

    k_min:
      minimum spacer count (usually 0).

    internal_edge_weight:
      optionally used by some layout engines later (igraph weights).
    """
    bp_per_spacer: int = 10_000
    k_max: int = 50
    k_min: int = 0

    internal_edge_weight: float = 3.0
    external_edge_weight: float = 1.0
