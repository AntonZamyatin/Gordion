"""Round-trip tests for the GSC1 binary scene codec and scene assembly."""
from __future__ import annotations

import numpy as np

from app.layout.port_graph import build_port_graph
from app.layout.engine_sgd import layout_port_graph, SgdParams
from app.services.ribbon import build_scene
from app.services.scene_codec import Scene, encode_scene, decode_scene


def _make_scene() -> Scene:
    return Scene(
        source="unit",
        contig_positions=np.array([0, 0, 10, 5, 3, 3, 3, 9], dtype=np.float32),
        contig_width=np.array([2.0, 7.5], dtype=np.float32),
        contig_color=np.array([1, 2, 3, 255, 250, 240, 230, 255], dtype=np.uint8),
        link_positions=np.array([10, 5, 3, 3], dtype=np.float32),
        id_table=["c0", "c1"],
        bbox=(0.0, 0.0, 10.0, 9.0),
    )


def test_encode_decode_round_trip():
    s = _make_scene()
    d = decode_scene(encode_scene(s))
    assert d.source == "unit"
    assert d.id_table == ["c0", "c1"]
    assert d.bbox == (0.0, 0.0, 10.0, 9.0)
    np.testing.assert_array_equal(d.contig_positions, s.contig_positions)
    np.testing.assert_array_equal(d.contig_width, s.contig_width)
    np.testing.assert_array_equal(d.contig_color, s.contig_color)
    np.testing.assert_array_equal(d.link_positions, s.link_positions)
    assert d.contig_count == 2
    assert d.link_count == 1


def test_magic_is_checked():
    import pytest

    with pytest.raises(ValueError):
        decode_scene(b"XXXX" + b"\x00" * 8)


def test_full_pipeline_round_trips(tiny_graph):
    pg = build_port_graph(tiny_graph)
    pos = layout_port_graph(pg, SgdParams(iterations=10, n_pivots=8))
    scene = build_scene(tiny_graph, pg, pos, source="tiny")
    d = decode_scene(encode_scene(scene))
    # one ribbon per contig; idTable lists the core node ids
    assert d.contig_count == len(tiny_graph.nodes)
    assert set(d.id_table) == set(tiny_graph.nodes)
    # 4 links in the fixture
    assert d.link_count == len(tiny_graph.edges)
    # each link carries (contig, side) refs for both endpoints, sides are 0/1,
    # and the referenced ports match the baked link coordinates
    assert d.link_endpoints.shape == (d.link_count * 4,)
    ep = d.link_endpoints.reshape(-1, 4)
    assert set(ep[:, 1]) | set(ep[:, 3]) <= {0, 1}
    for k, (ia, sa, ib, sb) in enumerate(ep):
        np.testing.assert_allclose(
            d.contig_positions[ia * 4 + sa * 2 : ia * 4 + sa * 2 + 2],
            d.link_positions[k * 4 : k * 4 + 2],
        )
        np.testing.assert_allclose(
            d.contig_positions[ib * 4 + sb * 2 : ib * 4 + sb * 2 + 2],
            d.link_positions[k * 4 + 2 : k * 4 + 4],
        )
