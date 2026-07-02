"""Tests for the SGD port-graph layout engine.

Kept intentionally geometry-agnostic (no assertions about "linearity", which is
inherently fuzzy and eyeballed via the spike). These pin the contract: every
node placed, finite coordinates, and determinism under a fixed seed.
"""
from __future__ import annotations

import math

from app.layout.port_graph import build_port_graph
from app.layout.engine_sgd import layout_port_graph, SgdParams


def test_positions_cover_all_nodes(tiny_graph):
    pg = build_port_graph(tiny_graph)
    pos = layout_port_graph(pg, SgdParams(iterations=10, n_pivots=8))
    assert set(pos) == set(pg.nodes)


def test_positions_are_finite(tiny_graph):
    pg = build_port_graph(tiny_graph)
    pos = layout_port_graph(pg, SgdParams(iterations=10, n_pivots=8))
    for (x, y) in pos.values():
        assert math.isfinite(x) and math.isfinite(y)


def test_layout_is_deterministic_under_fixed_seed(tiny_graph):
    pg = build_port_graph(tiny_graph)
    a = layout_port_graph(pg, SgdParams(iterations=15, n_pivots=8, seed=7))
    b = layout_port_graph(pg, SgdParams(iterations=15, n_pivots=8, seed=7))
    assert a == b
