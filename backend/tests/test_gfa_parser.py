"""Characterization tests for the GFA v1 parser.

These lock in the *current* behavior of app.parsers.gfa.parse_gfa so the
deck.gl migration cannot silently regress parsing. They snapshot the observable
output for tests/fixtures/tiny.gfa.
"""
from __future__ import annotations


def test_parses_all_segments_and_links(tiny_graph):
    assert sorted(tiny_graph.nodes) == ["s1", "s2", "s3", "s4", "s5", "s6"]
    assert len(tiny_graph.edges) == 4


def test_node_attributes(tiny_graph):
    got = {
        nid: (n.length_bp, n.coverage, dict(n.tags))
        for nid, n in tiny_graph.nodes.items()
    }
    assert got == {
        "s1": (100, 5.0, {"LN": "i:100", "dp": "f:5.0"}),
        "s2": (10, 3.5, {"dp": "f:3.5"}),
        "s3": (250, None, {"LN": "i:250"}),
        "s4": (40, 80.0, {"LN": "i:40", "KC": "i:80"}),
        "s5": (60, None, {"LN": "i:60"}),
        "s6": (10, None, {"LN": "i:10"}),
    }


def test_length_inferred_from_sequence_when_no_LN(tiny_graph):
    # s2 has no LN tag; length is inferred from the sequence "ACGTACGTAC".
    assert tiny_graph.nodes["s2"].length_bp == 10


def test_coverage_tag_priority(tiny_graph):
    # dp:f is preferred; falls back to KC:i; None when no coverage tag present.
    assert tiny_graph.nodes["s1"].coverage == 5.0   # dp:f
    assert tiny_graph.nodes["s4"].coverage == 80.0  # KC:i fallback
    assert tiny_graph.nodes["s3"].coverage is None


def test_edge_port_mapping(tiny_graph):
    # Locks the GFA-orientation -> port endpoint mapping, including the
    # '-' orientation case (L s2 + s3 - => (s2,OUT) -> (s3,OUT)).
    edges = [(e.id, e.start, e.end, e.overlap) for e in tiny_graph.edges.values()]
    assert edges == [
        ("e0:s1:OUT->s2:IN", ("s1", "OUT"), ("s2", "IN"), "10M"),
        ("e1:s2:OUT->s3:OUT", ("s2", "OUT"), ("s3", "OUT"), "5M"),
        ("e2:s1:OUT->s3:IN", ("s1", "OUT"), ("s3", "IN"), "0M"),
        ("e3:s4:OUT->s5:IN", ("s4", "OUT"), ("s5", "IN"), "3M"),
    ]


def test_header_and_unknown_records_ignored(tiny_graph):
    # The H line (and any non-S/L record) must not create nodes or edges.
    assert "H" not in tiny_graph.nodes
    assert len(tiny_graph.nodes) == 6