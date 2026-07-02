"""Regression tests for CoreGraph error handling.

Before the deck.gl migration, graph.py referenced NodeNotFound/NodeExists/
EdgeExists/EdgeNotFound/InvalidEdgeEndpoint without importing them, so every
error path raised NameError instead of the intended GraphError subclass. These
tests pin the corrected behavior.
"""
from __future__ import annotations

import pytest

from app.domain.graph import CoreGraph, Node, Edge
from app.domain.errors import (
    NodeExists,
    NodeNotFound,
    EdgeExists,
    EdgeNotFound,
    InvalidEdgeEndpoint,
)


def test_get_missing_node_raises_node_not_found():
    g = CoreGraph()
    with pytest.raises(NodeNotFound):
        g.get_node("nope")


def test_get_missing_edge_raises_edge_not_found():
    g = CoreGraph()
    with pytest.raises(EdgeNotFound):
        g.get_edge("nope")


def test_adding_duplicate_node_raises_node_exists():
    g = CoreGraph()
    g.add_node(Node(id="a"))
    with pytest.raises(NodeExists):
        g.add_node(Node(id="a"))


def test_adding_duplicate_edge_raises_edge_exists():
    g = CoreGraph()
    g.add_node(Node(id="a"))
    g.add_node(Node(id="b"))
    g.add_edge(Edge(id="e", start=("a", "OUT"), end=("b", "IN")))
    with pytest.raises(EdgeExists):
        g.add_edge(Edge(id="e", start=("a", "OUT"), end=("b", "IN")))


def test_edge_with_unknown_endpoint_raises_invalid_endpoint():
    g = CoreGraph()
    g.add_node(Node(id="a"))
    with pytest.raises(InvalidEdgeEndpoint):
        g.add_edge(Edge(id="e", start=("a", "OUT"), end=("ghost", "IN")))