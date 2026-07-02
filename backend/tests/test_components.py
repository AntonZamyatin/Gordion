"""Characterization tests for undirected connected-component detection.

Locks the current behavior of CoreGraph.get_components() for the migration.
The port graph that replaces RenderGraph will be layered on top of this same
component logic, so pinning it now protects the two-level layout pipeline.
"""
from __future__ import annotations


def test_component_membership(tiny_graph):
    ci = tiny_graph.get_components()
    assert ci.node_to_cid == {
        "s1": 0, "s2": 0, "s3": 0,  # linear+branch component
        "s4": 1, "s5": 1,           # separate pair
        "s6": 2,                    # isolated node
    }


def test_component_summaries(tiny_graph):
    ci = tiny_graph.get_components()
    summaries = [(s.cid, s.num_nodes, s.num_edges) for s in ci.summaries]
    assert summaries == [(0, 3, 3), (1, 2, 1), (2, 1, 0)]


def test_isolated_node_is_its_own_component(tiny_graph):
    ci = tiny_graph.get_components()
    assert ci.node_to_cid["s6"] == 2
    assert tiny_graph.nodes_in_component(2) == ["s6"]


def test_components_cached_until_topology_change(tiny_graph):
    # Current behavior: the index is cached and the same object is returned
    # until a topology mutation marks it dirty.
    first = tiny_graph.get_components()
    assert tiny_graph.get_components() is first