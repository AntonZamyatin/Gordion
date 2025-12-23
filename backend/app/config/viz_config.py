from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RenderPolicyConfig:
    # Pseudovertex expansion
    bp_per_spacer: int = 100_000
    k_min: int = 0
    k_max: int = 15


@dataclass(frozen=True, slots=True)
class VisualStyleConfig:
    # Sigma rendering attributes (backend emits these into DTOs)
    endpoint_node_size: float = 0.75     # IN/OUT nodes
    spacer_node_size: float = 4.0       # spacer nodes
    internal_edge_size: float = 8.0     # thick backbone “tube”
    external_edge_size: float = 1.5     # thin links


@dataclass(frozen=True, slots=True)
class LayoutConfig:
    # Layout engine selection & params
    default_engine: str = "igraph_fr"
    default_pack: str = "rows"

    # FR parameters
    fr_niter_small: int = 300
    fr_niter_large: int = 600
    fr_large_threshold: int = 2000
    fr_grid: str = "auto"

    # Weights for layout (not rendering stroke width)
    # Higher => stronger attraction for that edge in weighted layouts.
    internal_edge_weight: float = 1.0
    external_edge_weight: float = 3.0


@dataclass(frozen=True, slots=True)
class PackingConfig:
    padding: float = 50.0
    # If None => auto heuristic
    target_row_width: float | None = None


@dataclass(frozen=True, slots=True)
class NormalizationConfig:
    # Per-component normalization extent ~ target_extent_per_sqrt_n * sqrt(n)
    target_extent_per_sqrt_n: float = 60.0


@dataclass(frozen=True, slots=True)
class VizConfig:
    render: RenderPolicyConfig = RenderPolicyConfig()
    style: VisualStyleConfig = VisualStyleConfig()
    layout: LayoutConfig = LayoutConfig()
    pack: PackingConfig = PackingConfig()
    norm: NormalizationConfig = NormalizationConfig()


CFG = VizConfig()
