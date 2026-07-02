"""Tests for the session-based scene pipeline (layout caching + overrides)."""
from __future__ import annotations

from app.services.session_store import SessionStore
from app.services.scene_service import scene_for_core, scene_for_session


def test_scene_for_core(tiny_graph):
    scene = scene_for_core(tiny_graph, source="tiny")
    assert scene.contig_count == len(tiny_graph.nodes)
    assert set(scene.id_table) == set(tiny_graph.nodes)
    assert scene.link_count == len(tiny_graph.edges)


def test_session_caches_layout(tiny_graph):
    store = SessionStore()
    sess = store.get(store.create(tiny_graph, source="tiny"))
    assert sess.port_graph is None and not sess.computed

    scene_for_session(sess)
    pg, pos = sess.port_graph, sess.computed
    assert pg is not None and pos

    scene_for_session(sess)  # second call reuses the cache
    assert sess.port_graph is pg
    assert sess.computed is pos


def test_recompute_rebuilds_layout(tiny_graph):
    store = SessionStore()
    sess = store.get(store.create(tiny_graph, source="tiny"))
    scene_for_session(sess)
    pos1 = sess.computed
    scene_for_session(sess, recompute=True)
    assert sess.computed is not pos1


def test_override_flows_into_scene(tiny_graph):
    store = SessionStore()
    sess = store.get(store.create(tiny_graph, source="tiny"))
    scene_for_session(sess)  # populate port_graph + computed
    port = sess.port_graph.nodes[0]
    sess.set_override(port, 999.0, -999.0)
    scene = scene_for_session(sess)  # reuses layout, applies override
    assert scene.bbox[2] >= 999.0   # max_x picks up the override
    assert scene.bbox[1] <= -999.0  # min_y picks up the override
