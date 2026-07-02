"""Tests for the port graph builder (the layout representation that replaces
the pseudo-vertex RenderGraph)."""
from __future__ import annotations

from app.layout.port_graph import build_port_graph, PortGraphParams


def test_two_port_nodes_per_contig(tiny_graph):
    pg = build_port_graph(tiny_graph)
    assert len(pg.nodes) == 2 * len(tiny_graph.nodes)  # 6 contigs -> 12 ports
    for cid in tiny_graph.nodes:
        in_id, out_id = pg.contigs[cid]
        assert in_id == f"{cid}:IN"
        assert out_id == f"{cid}:OUT"
        assert in_id in pg.nodes and out_id in pg.nodes


def test_one_internal_edge_per_contig_plus_external_per_link(tiny_graph):
    pg = build_port_graph(tiny_graph)
    internal = [e for e in pg.edges if e.kind == "INTERNAL"]
    external = [e for e in pg.edges if e.kind == "EXTERNAL"]
    assert len(internal) == len(tiny_graph.nodes)   # 6
    assert len(external) == len(tiny_graph.edges)    # 4


def test_internal_target_grows_with_length(tiny_graph):
    pg = build_port_graph(tiny_graph)
    tgt = {}
    for e in pg.edges:
        if e.kind == "INTERNAL":
            core = e.u.rsplit(":", 1)[0]
            tgt[core] = e.target
    # s3 (250 bp) should be drawn longer than s6 (10 bp)
    assert tgt["s3"] > tgt["s6"]


def test_external_edges_map_core_endpoints_to_port_nodes(tiny_graph):
    pg = build_port_graph(tiny_graph)
    ext = {(e.u, e.v) for e in pg.edges if e.kind == "EXTERNAL"}
    # from parser golden: e0 (s1,OUT)->(s2,IN), e1 (s2,OUT)->(s3,OUT)
    assert ("s1:OUT", "s2:IN") in ext
    assert ("s2:OUT", "s3:OUT") in ext


def test_unknown_length_uses_default(tiny_graph):
    # every internal target is finite and positive even when length_bp missing
    p = PortGraphParams()
    pg = build_port_graph(tiny_graph, p)
    for e in pg.edges:
        if e.kind == "INTERNAL":
            assert e.target >= p.min_len or e.target == p.default_len
